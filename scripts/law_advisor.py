"""
法律小顧問 RAG 查詢
embedding：ollama bge-m3（與 build_index.py 一致）
"""

import requests
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

OLLAMA_URL  = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3"
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION  = "tw_laws"
TOP_K       = 5
SCORE_MIN   = 0.5

ADVISOR_CATEGORIES = {
    "hr":        ["01_HR"],
    "legal":     ["04_civil", "05_criminal"],
    "medical":   ["02_medical"],
    "account":   ["07_admin", "09_tax"],
    "ip":        ["06_ip"],
    "digital":   ["08_digital"],
    "corp":      ["03_corporate"],
    "land":      ["11_land"],
    "env":       ["12_env"],
    "finance":   ["13_finance"],
    "telecom":   ["14_telecom"],
    "edu":       ["15_edu"],
    "transport": ["16_transport"],
    "food":      ["17_food"],
    "energy":    ["18_energy"],
    "all":       None,
}

try:
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
except Exception as e:
    client = None
    print(f"[law_advisor] Qdrant 連線失敗：{e}")


def embed(text: str) -> list:
    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": EMBED_MODEL, "prompt": text[:8000]},
            timeout=30,
        )
        return r.json().get("embedding", [])
    except Exception as e:
        print(f"[law_advisor] embed 失敗：{e}")
        return []


def search(query: str, advisor: str = "all", top_k: int = TOP_K) -> list:
    if not client:
        return []
    try:
        vec = embed(query)
        if not vec:
            return []

        cats = ADVISOR_CATEGORIES.get(advisor)
        query_filter = None
        if cats:
            query_filter = Filter(
                should=[
                    FieldCondition(key="category", match=MatchValue(value=c))
                    for c in cats
                ]
            )

        results = client.query_points(
            collection_name=COLLECTION,
            query=vec,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        ).points

        return [
            {
                "law":      r.payload.get("law", ""),
                "article":  r.payload.get("article", ""),
                "category": r.payload.get("category", ""),
                "text":     r.payload.get("text", ""),
                "score":    round(r.score, 3),
            }
            for r in results
            if r.score >= SCORE_MIN
        ]
    except Exception as e:
        print(f"[law_advisor] search 失敗：{e}")
        return []


def format_context(results: list) -> str:
    if not results:
        return ""
    lines = ["以下是相關法規條文，請依據這些條文回答：\n"]
    for r in results:
        lines.append(r["text"] + "\n")
    return "\n".join(lines)
