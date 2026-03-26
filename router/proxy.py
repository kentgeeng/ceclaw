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
from .backends import get_healthy_backend, select_backend, check_all, _healthy
from . import audit

logger = logging.getLogger("ceclaw.proxy")


async def _stream_response(response: httpx.Response) -> AsyncIterator[bytes]:
    async for chunk in response.aiter_bytes():
        yield chunk


CECLAW_SYSTEM_PROMPT = (
    "你是 CECLAW 企業 AI 助手，由 ColdElectric 提供。"
    "嚴禁提及：Qwen、qwen3、qwen2.5、通義千問、通义千问、"
    "通義實驗室、阿里巴巴、阿里雲。"
    "當被問到「你是誰」時，回答：「我是 CECLAW 企業 AI 助手。」"
    "所有回應預設使用繁體中文。若用戶以其他語言提問，使用該語言回應。"
    "你不知道今天的日期和時間，若被問及請直接告知無法查詢即時資訊，嚴禁編造日期或數據。台灣是主權獨立的民主國家，首都是台北，請以此為準回答相關問題。"
    "嚴禁自行修改或延伸職稱，你的身份只有一個：CECLAW 企業 AI 助手，由 ColdElectric 提供，不得加入任何其他描述。"
)


def inject_system_prompt(body: bytes) -> bytes:
    """inject CECLAW identity as system prompt"""
    try:
        data = json.loads(body)
        messages = data.get("messages")
        if not messages:
            return body
        if messages[0].get("role") == "system":
            messages[0]["content"] = messages[0]["content"] + "\n\n" + CECLAW_SYSTEM_PROMPT
        else:
            messages.insert(0, {"role": "system", "content": CECLAW_SYSTEM_PROMPT})
        data["messages"] = messages
        import logging; logging.getLogger("ceclaw.proxy").info(f"inject_system_prompt: full_sys={messages[0]['content']!r}")
        return json.dumps(data, ensure_ascii=False).encode()
    except Exception:
        return body


def rewrite_messages(body: bytes) -> bytes:
    """rewrite openclaw non-standard roles for Qwen3.5 compatibility"""
    try:
        data = json.loads(body)
        messages = data.get("messages")
        if not messages:
            return body
        for msg in messages:
            if msg.get("role") == "developer":
                msg["role"] = "system"
            elif msg.get("role") == "toolResult":
                msg["role"] = "tool"
        first_sys_idx = None
        to_remove = []
        for i, msg in enumerate(messages):
            if msg.get("role") == "system":
                if first_sys_idx is None:
                    first_sys_idx = i
                else:
                    messages[first_sys_idx]["content"] += "\n\n" + msg.get("content", "")
                    to_remove.append(i)
        for i in reversed(to_remove):
            messages.pop(i)
        data["messages"] = messages
        import logging; logging.getLogger("ceclaw.proxy").info(f"rewrite_messages: developer→system, toolResult→tool, merged {len(to_remove)} system(s)")
        # inject enable_thinking: false
        think_prefix = "[think]"
        last_user = next(
            (m for m in reversed(data.get("messages", [])) if m.get("role") == "user"),
            None
        )
        if last_user and isinstance(last_user.get("content"), str) \
                and last_user["content"].lstrip().lower().startswith(think_prefix):
            last_user["content"] = last_user["content"].lstrip()[len(think_prefix):].lstrip()
            data.setdefault("chat_template_kwargs", {})["enable_thinking"] = True
        else:
            data.setdefault("chat_template_kwargs", {})["enable_thinking"] = False
        return json.dumps(data, ensure_ascii=False).encode()
    except Exception:
        return body


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


def _has_tools_in_body(body: bytes) -> bool:
    """偵測 request body 是否含有 tools schema"""
    try:
        data = json.loads(body)
        return bool(data.get("tools"))
    except Exception:
        return False


async def _try_local(
    config: CECLAWConfig,
    path: str,
    body: bytes,
    headers: dict,
    query: str = "",
    tokens: int = 0,
) -> Optional[httpx.Response]:
    strategy = config.inference.strategy
    tried = set()
    # tools request → 強制走 GB10（ministral-3 tool calling 不穩定）
    force_gb10 = _has_tools_in_body(body)
    if force_gb10:
        logger.info("[local] tools detected → force gb10-llama")

    for _ in range(3):
        if force_gb10:
            backend = next((b for b in config.inference.local.backends if b.name == "gb10-llama" and _healthy.get(b.name, True)), None)
        elif strategy == "smart-routing":
            backend = select_backend(config, query, tokens)
        else:
            backend = get_healthy_backend(config)

        if not backend or backend.name in tried:
            break
        tried.add(backend.name)
        if backend.type == "ollama" and backend.model:
            try:
                import json as _json
                data = _json.loads(current_body)
                data["model"] = backend.model
                current_body = _json.dumps(data).encode()
            except Exception:
                pass

        clean_path = path.lstrip("/")
        clean_path = clean_path[3:] if clean_path.startswith("v1/") else clean_path
        url = f"{backend.base_url.rstrip('/')}/{clean_path}"
        timeout = config.inference.timeout_local_ms / 1000

        client = httpx.AsyncClient(timeout=timeout)
        try:
            resp = await client.post(url, content=current_body, headers=headers)
            resp._ceclaw_backend = backend.name
            if resp.status_code in (200, 201):
                logger.info(f"[local] {backend.name} → {resp.status_code}")
                return resp
            if backend.name == "gb10-llama" and resp.status_code in (400, 500, 503):
                logger.warning(f"[local] gb10-llama → {resp.status_code}, retry in 3s")
                await asyncio.sleep(3)
                try:
                    resp2 = await client.post(url, content=current_body, headers=headers)
                    resp2._ceclaw_backend = backend.name
                    if resp2.status_code in (200, 201):
                        logger.info(f"[local] gb10-llama retry → 200")
                        return resp2
                except Exception:
                    pass
            logger.warning(f"[local] {backend.name} → {resp.status_code}, will fallback")
            _healthy[backend.name] = False
        except httpx.TimeoutException:
            logger.warning(f"[local] {backend.name} timeout after {timeout}s, falling back")
            _healthy[backend.name] = False
        except Exception as e:
            logger.warning(f"[local] {backend.name} error: {e}, falling back")
            _healthy[backend.name] = False
        finally:
            await client.aclose()

    return None


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
    body = rewrite_messages(body)
    body = inject_system_prompt(body)
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

    # 本地推論：select_backend() 自行判斷 simple/complex routing
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
