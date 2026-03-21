"""
CECLAW Router - Proxy & Fallback Logic
"""
import json
import asyncio
import logging
from typing import Optional, AsyncIterator
import httpx
from fastapi import Request
from fastapi.responses import StreamingResponse, JSONResponse
from .config import CECLAWConfig, LocalBackend, CloudProvider
from .backends import get_healthy_backend, select_backend, check_all
from . import audit

logger = logging.getLogger("ceclaw.proxy")


async def _stream_response(response: httpx.Response) -> AsyncIterator[bytes]:
    async for chunk in response.aiter_bytes():
        yield chunk


def _extract_query_info(body: bytes) -> tuple[str, int]:
    """從 request body 取出 query 文字和 token 估算"""
    try:
        data = json.loads(body)
        messages = data.get("messages", [])
        query = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                query = content if isinstance(content, str) else str(content)
                break
        tokens = len(query) // 4
        return query, tokens
    except Exception:
        return "", 0


async def _try_local(
    config: CECLAWConfig,
    path: str,
    body: bytes,
    headers: dict,
    query: str = "",
    tokens: int = 0,
) -> Optional[httpx.Response]:
    strategy = config.inference.strategy
    if strategy == "smart-routing":
        backend = select_backend(config, query, tokens)
    else:
        backend = get_healthy_backend(config)

    if not backend:
        return None

    if backend.type == "ollama" and backend.model:
        try:
            import json as _json
            data = _json.loads(body)
            data["model"] = backend.model
            body = _json.dumps(data).encode()
        except Exception:
            pass

    clean_path = path.lstrip("/")
    clean_path = clean_path[3:] if clean_path.startswith("v1/") else clean_path
    url = f"{backend.base_url.rstrip('/')}/{clean_path}"
    timeout = config.inference.timeout_local_ms / 1000

    try:
        client = httpx.AsyncClient(timeout=timeout)
        resp = await client.post(url, content=body, headers=headers)
        resp._ceclaw_backend = backend.name
        if resp.status_code in (200, 201):
            logger.info(f"[local] {backend.name} → {resp.status_code}")
            return resp
        logger.warning(f"[local] {backend.name} → {resp.status_code}, will fallback")
        return None
    except httpx.TimeoutException:
        logger.warning(f"[local] {backend.name} timeout after {timeout}s, falling back")
        return None
    except Exception as e:
        logger.warning(f"[local] {backend.name} error: {e}, falling back")
        return None
    finally:
        await client.aclose()


async def _try_cloud(
    config: CECLAWConfig,
    path: str,
    body: bytes,
    headers: dict,
) -> Optional[httpx.Response]:
    fb = config.inference.cloud_fallback
    if not fb.enabled:
        return None

    for provider in fb.priority:
        key = provider.api_key()
        if not key:
            logger.debug(f"[cloud] {provider.provider}: no API key, skip")
            continue

        clean_path = path.lstrip("/")
        clean_path = clean_path[3:] if clean_path.startswith("v1/") else clean_path
        url = f"{provider.resolved_base_url().rstrip('/')}/{clean_path}"
        cloud_headers = dict(headers)
        cloud_headers["Authorization"] = f"Bearer {key}"
        if provider.provider == "anthropic":
            cloud_headers["x-api-key"] = key
            cloud_headers.pop("Authorization", None)

        try:
            client = httpx.AsyncClient(timeout=60.0)
            resp = await client.post(url, content=body, headers=cloud_headers)
            resp._ceclaw_backend = f"cloud:{provider.provider}"
            if resp.status_code in (200, 201):
                logger.info(f"[cloud] {provider.provider} → {resp.status_code}")
                return resp
            logger.warning(f"[cloud] {provider.provider} → {resp.status_code}")
        except Exception as e:
            logger.warning(f"[cloud] {provider.provider} error: {e}")
        finally:
            await client.aclose()

    return None


async def handle_inference(
    config: CECLAWConfig,
    path: str,
    request: Request,
) -> StreamingResponse | JSONResponse:
    body = await request.body()
    headers = {
        "Content-Type": request.headers.get("Content-Type", "application/json"),
        "Accept": request.headers.get("Accept", "*/*"),
    }

    strategy = config.inference.strategy
    query, tokens = _extract_query_info(body)
    resp: Optional[httpx.Response] = None
    request_id = audit.new_request_id()
    backend_name = "unknown"
    audit_status = "ok"

    # 本地推論
    if strategy in ("local-first", "local-only", "smart-routing"):
        resp = await _try_local(config, path, body, headers, query, tokens)
        if resp is None:
            audit_status = "timeout"  # 本地失敗，先標記，後續若雲端成功會覆蓋

    if resp is None and strategy == "local-only":
        audit.append_entry(backend_name, query, "", "error", request_id)
        return JSONResponse(
            {"error": {"message": "No local backend available", "type": "ceclaw_error"}},
            status_code=503,
        )

    # 雲端 fallback
    if resp is None and strategy in ("local-first", "cloud-only", "smart-routing"):
        resp = await _try_cloud(config, path, body, headers)
        if resp is not None:
            audit_status = "ok"  # 雲端成功，覆蓋前面的 timeout 標記

    if resp is None:
        audit.append_entry(backend_name, query, "", "error", request_id)
        return JSONResponse(
            {"error": {"message": "All backends unavailable", "type": "ceclaw_error"}},
            status_code=503,
        )

    backend_name = getattr(resp, "_ceclaw_backend", "unknown")

    if "text/event-stream" in resp.headers.get("content-type", ""):
        async def stream_with_audit():
            buf = b""
            status = "ok"
            try:
                async for chunk in resp.aiter_bytes():
                    yield chunk
                    if len(buf) < audit.MAX_BUFFER:
                        buf += chunk
            except Exception:
                status = "error"
                raise
            finally:
                response_text = buf.decode(errors="replace")
                audit.append_entry(backend_name, query, response_text, status, request_id)

        return StreamingResponse(
            stream_with_audit(),
            status_code=resp.status_code,
            media_type="text/event-stream",
            headers={"X-CECLAW-Backend": backend_name},
        )

    # 非 streaming
    resp_json = resp.json()
    response_text = ""
    try:
        response_text = resp_json["choices"][0]["message"]["content"]
    except Exception:
        response_text = json.dumps(resp_json)[:100]

    audit.append_entry(backend_name, query, response_text, audit_status, request_id)
    return JSONResponse(resp_json, status_code=resp.status_code)
