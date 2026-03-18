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
