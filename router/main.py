"""
CECLAW Inference Router
監聽 host.openshell.internal:8000，取代 Caddy，直通本地後端或降級至雲端
"""
import asyncio
import logging
import os
import signal
import sys
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import load_config, CECLAWConfig
from .backends import check_all, all_status
from .proxy import handle_inference

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("ceclaw.main")

# 全域設定（支援熱重載）
_config: Optional[CECLAWConfig] = None
_config_path: Optional[str] = None


def get_config() -> CECLAWConfig:
    return _config


def reload_config():
    global _config
    logger.info("Reloading config...")
    _config = load_config(_config_path)
    logger.info(f"Config reloaded: strategy={_config.inference.strategy}, "
                f"backends={[b.name for b in _config.inference.local.backends]}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 啟動時健康檢查所有後端
    logger.info("CECLAW Router starting...")
    logger.info(f"Strategy: {_config.inference.strategy}")
    logger.info(f"Local backends: {[b.name for b in _config.inference.local.backends]}")
    await check_all(_config)

    # SIGHUP 熱重載
    if _config.router.reload_on_sighup:
        def _sighup_handler(sig, frame):
            reload_config()
            asyncio.create_task(check_all(_config))
        signal.signal(signal.SIGHUP, _sighup_handler)

    # 定期健康檢查（每 30 秒）
    async def _periodic_check():
        while True:
            await asyncio.sleep(30)
            await check_all(_config)

    task = asyncio.create_task(_periodic_check())
    yield
    task.cancel()


app = FastAPI(title="CECLAW Inference Router", lifespan=lifespan)

from .knowledge_api import router as knowledge_router
app.include_router(knowledge_router)


# ── OpenAI-compatible endpoints ───────────────────────────

@app.get("/v1/models")
async def list_models():
    cfg = get_config()
    models = []
    for backend in cfg.inference.local.backends:
        for m in backend.models:
            models.append({
                "id": m.id,
                "object": "model",
                "owned_by": f"ceclaw/{backend.name}",
                "type": "model",
            })
    return {"object": "list", "data": models}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    return await handle_inference(get_config(), "v1/chat/completions", request)


@app.post("/v1/completions")
async def completions(request: Request):
    return await handle_inference(get_config(), "v1/completions", request)


# ── CECLAW status endpoint ────────────────────────────────

@app.get("/search")
@app.post("/search")
async def proxy_search(request: Request):
    """Proxy SearXNG search requests from sandbox"""
    params = dict(request.query_params)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "http://localhost:8888/search",
                params=params,
                headers={"Accept": "application/json"}
            )
            return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.get("/v1/fetch")
async def proxy_fetch(url: str, request: Request):
    """D方案：代抓外部 URL，讓 sandbox 透過 Router 存取外部內容"""
    # allowed_domains 白名單佔位（空 = 全放行，量產前需設定）
    ALLOWED_DOMAINS: list[str] = []
    if ALLOWED_DOMAINS:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        if not any(domain.endswith(d) for d in ALLOWED_DOMAINS):
            return JSONResponse({"error": f"domain not allowed: {domain}"}, status_code=403)
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, verify=False) as client:
            resp = await client.get(url, headers={"User-Agent": "CECLAW-Proxy/1.0"})
            return JSONResponse({
                "content": resp.text,
                "url": str(resp.url),
                "status": resp.status_code
            })
    except Exception as e:
        return JSONResponse({"error": str(e), "url": url}, status_code=502)

@app.get("/v1/dns")
async def proxy_dns(name: str):
    """DNS over HTTPS proxy - sandbox 內 DNS resolver 用"""
    try:
        async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
            resp = await client.get(
                f"https://1.1.1.1/dns-query?name={name}&type=A",
                headers={"accept": "application/dns-json"}
            )
            data = resp.json()
            answers = [r["data"] for r in data.get("Answer", []) if r.get("type") == 1]
            if not answers:
                return JSONResponse({"error": "no A record", "name": name}, status_code=404)
            return JSONResponse({"name": name, "addresses": answers})
    except Exception as e:
        return JSONResponse({"error": str(e), "name": name}, status_code=502)

@app.get("/ceclaw/status")
async def status():
    cfg = get_config()
    return {
        "version": "0.1.0",
        "strategy": cfg.inference.strategy,
        "backends": all_status(),
        "cloud_fallback": cfg.inference.cloud_fallback.enabled,
        "cloud_providers": [
            {
                "provider": p.provider,
                "has_key": bool(p.api_key()),
            }
            for p in cfg.inference.cloud_fallback.priority
        ],
    }


@app.post("/ceclaw/reload")
async def reload():
    reload_config()
    await check_all(get_config())
    return {"status": "reloaded"}


# ── Entry point ───────────────────────────────────────────

def main(config_path: Optional[str] = None):
    global _config, _config_path
    _config_path = config_path or os.environ.get("CECLAW_CONFIG")
    _config = load_config(_config_path)

    logger.info("=" * 50)
    logger.info("  CECLAW Inference Router")
    logger.info(f"  Listen: {_config.router.listen_host}:{_config.router.listen_port}")
    logger.info(f"  Strategy: {_config.inference.strategy}")
    logger.info("=" * 50)

    uvicorn.run(
        app,
        host=_config.router.listen_host,
        port=_config.router.listen_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
