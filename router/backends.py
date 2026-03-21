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
    # 中文 — 推理/分析
    "證明", "推導", "最優解", "為什麼", "分析", "比較", "策略",
    "原理", "推理", "邏輯", "解釋", "評估", "判斷", "建議",
    # 中文 — 數學/科學
    "數學", "計算", "解題", "公式", "定理", "方程", "微積分",
    "統計", "機率", "線性代數", "幾何", "物理", "化學",
    # 中文 — 辦公室/商業
    "報告", "提案", "企劃", "預算", "財務", "成本", "效益",
    "市場", "競爭", "風險", "合約", "法律", "規範", "流程",
    "會議", "簡報", "摘要", "結論", "決策", "規劃", "目標",
    # 中文 — 程式/技術
    "演算法", "複雜度", "架構", "設計", "優化", "重構",
    "除錯", "效能", "安全", "資料庫", "API", "部署", "測試",
    "程式", "程式碼", "函數", "類別", "繼承", "多型",
    # English — reasoning/analysis
    "prove", "derive", "optimal", "why", "analyze", "compare",
    "strategy", "reasoning", "explain", "how to", "solve",
    "evaluate", "assess", "recommend", "justify", "design",
    "tradeoff", "trade-off", "pros and cons", "difference between",
    # English — math/science
    "algorithm", "complexity", "equation", "formula", "theorem",
    "calculus", "statistics", "probability", "matrix", "proof",
    # English — office/business
    "report", "proposal", "budget", "forecast", "revenue",
    "contract", "compliance", "risk", "stakeholder", "roadmap",
    "summary", "conclusion", "decision", "planning", "objective",
    # English — coding/tech
    "architecture", "refactor", "optimize", "debug", "performance",
    "security", "database", "deploy", "testing", "implement",
    "best practice", "design pattern", "scalability", "bottleneck",
    "concurrency", "async", "memory leak", "race condition",
    # 日文
    "証明", "導出", "最適", "なぜ", "分析", "比較", "戦略",
    "アルゴリズム", "設計", "最適化",
}

def needs_reasoning(query: str) -> bool:
    q = query.lower()
    return any(kw in q for kw in REASONING_KEYWORDS)

def select_backend(config: CECLAWConfig, query: str = "", tokens: int = 0) -> Optional[LocalBackend]:
    """
    Smart routing：
    - 空字串（解析失敗）→ gb10-llama（保守）
    - 有推理關鍵字 → gb10-llama
    - 否則 → ollama-fast
    - gb10-llama 掛 → ollama-backup
    - 全掛 → None（走雲端）
    """
    backends_by_name = {b.name: b for b in config.inference.local.backends}

    if not query or needs_reasoning(query):
        main = backends_by_name.get("gb10-llama")
        if main and _healthy.get("gb10-llama", False):
            return main
    else:
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
