"""
CECLAW Router - Backend Health Check & Selection
"""
import asyncio
import logging
from typing import Optional
import httpx
from .config import LocalBackend, CECLAWConfig

logger = logging.getLogger("ceclaw.backends")

# 健康狀態快取
_healthy: dict[str, bool] = {}


async def check_backend(backend: LocalBackend, timeout: float = 5.0) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(f"{backend.base_url.rstrip('/')}/models")
            ok = r.status_code == 200
            _healthy[backend.name] = ok
            return ok
    except Exception as e:
        logger.warning(f"Backend {backend.name} unhealthy: {e}")
        _healthy[backend.name] = False
        return False


async def check_all(config: CECLAWConfig) -> None:
    tasks = [check_backend(b) for b in config.inference.local.backends]
    await asyncio.gather(*tasks)
    for name, ok in _healthy.items():
        logger.info(f"  {name}: {'✓' if ok else '✗'}")


def get_healthy_backend(config: CECLAWConfig) -> Optional[LocalBackend]:
    """回傳第一個健康的本地後端"""
    for backend in config.inference.local.backends:
        if _healthy.get(backend.name, False):
            return backend
    return None


def is_healthy(backend_name: str) -> bool:
    return _healthy.get(backend_name, False)


def all_status() -> dict[str, bool]:
    return dict(_healthy)
