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

REASONING_KEYWORDS = {
    # 中文
    "證明", "推導", "如何逃脫", "最優解",
    "為什麼", "分析", "比較", "策略",
    # English
    "prove", "derive", "escape", "optimal",
    "why", "analyze", "compare", "strategy",
    "reasoning", "explain", "how to", "solve",
    # 日文
    "証明", "導出", "最適", "なぜ", "分析", "比較", "戦略",
}

def needs_reasoning(query: str) -> bool:
    q = query.lower()
    return any(kw in q for kw in REASONING_KEYWORDS)

def select_backend(config: CECLAWConfig, query: str = "", tokens: int = 0) -> Optional[LocalBackend]:
    """
    Smart routing：
    - tokens > 80 → gb10-llama（長問題不賭關鍵字）
    - tokens <= 80 且無推理關鍵字 → ollama-fast
    - 否則 → gb10-llama
    - gb10-llama 掛 → ollama-backup
    - 全掛 → None（走雲端）
    """
    backends_by_name = {b.name: b for b in config.inference.local.backends}

    if tokens <= 80 and not needs_reasoning(query):
        fast = backends_by_name.get("ollama-fast")
        if fast and _healthy.get("ollama-fast", False):
            return fast

    main = backends_by_name.get("gb10-llama")
    if main and _healthy.get("gb10-llama", False):
        return main

    backup = backends_by_name.get("ollama-backup")
    if backup and _healthy.get("ollama-backup", False):
        return backup

    return None

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
    """回傳 priority 最高的健康後端（數字小 = 優先）"""
    healthy = [
        b for b in config.inference.local.backends
        if _healthy.get(b.name, False)
    ]
    if not healthy:
        return None
    return sorted(healthy, key=lambda b: b.priority)[0]

def is_healthy(backend_name: str) -> bool:
    return _healthy.get(backend_name, False)

def all_status() -> dict[str, bool]:
    return dict(_healthy)
