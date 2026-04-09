"""
CECLAW Knowledge Service v2
三層知識庫：personal / dept / company
統一使用 Qdrant + bge-m3 1024 dim，threshold 0.7

架構說明：
- L3 collection 命名：ceclaw_{layer}_{scope}
  例：ceclaw_personal_kent, ceclaw_dept_engineering, ceclaw_company_poc
  前綴確保 B70 多租戶環境下不同公司的 collection 不撞名

查詢順序（proxy.py 呼叫）：
  ① L3（本檔）+ L2 tw_knowledge → 並行（B70 後升級 asyncio）
  ② L1 law_advisor_api          → 條件執行，_LAW_KEYWORDS 觸發

L2 更新機制：全量覆蓋（Full Re-index）
  每月從 GB10 建立 Qdrant snapshot，搬到 B70 後 restore。
  不做增量，避免殘留舊向量污染查詢結果。

Hermes 同步時機：對話結束後異步
  sync_hermes_memory() 由 proxy.py 在 response 送出後背景呼叫，
  不阻塞主查詢路徑。

去重邏輯：
  同一段落出現在多個 collection 時，取最高 similarity score，
  不重複注入 LLM context，避免幻覺。
"""
import os
import json
import hashlib
import logging
import httpx
from datetime import datetime
from pathlib import Path
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue,
    SearchRequest, SparseVectorParams, SparseIndexParams,
    TextIndexParams, TokenizerType,
)

logger = logging.getLogger(__name__)

QDRANT_URL      = os.environ.get("QDRANT_URL", "http://192.168.1.91:6333")
OLLAMA_URL      = os.environ.get("OLLAMA_URL", "http://192.168.1.91:11434")
BRIDGE_PATH     = os.path.expanduser("~/.ceclaw/knowledge/bridge")
SIMILARITY_THRESHOLD = 0.7   # bge-m3 中文語意，統一三層
VECTOR_DIM      = 1024       # bge-m3 輸出維度
TOP_K           = 3

_client: Optional[QdrantClient] = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=QDRANT_URL, timeout=10)
    return _client


def _collection_name(layer: str, scope: str = "") -> str:
    """
    統一命名規範：ceclaw_{layer}_{scope}
    layer: personal | dept | company
    scope: user_id / dept_name / company_id
    """
    if layer == "personal":
        return f"ceclaw_personal_{scope}" if scope else "ceclaw_personal_default"
    elif layer == "dept":
        return f"ceclaw_dept_{scope}" if scope else "ceclaw_dept_general"
    else:
        return f"ceclaw_company_{scope}" if scope else "ceclaw_company_poc"


def _ensure_collection(name: str) -> None:
    """建立 collection（若不存在）"""
    client = _get_client()
    existing = [c.name for c in client.get_collections().collections]
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        logger.info(f"knowledge_service_v2: created collection {name}")


def _embed(text: str) -> list[float]:
    """呼叫 bge-m3 取得 embedding"""
    resp = httpx.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": "bge-m3", "prompt": text[:500]},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]


def add_document(content: str, layer: str, scope: str = "",
                 metadata: dict = None) -> str:
    """新增或更新一筆知識"""
    name = _collection_name(layer, scope)
    _ensure_collection(name)
    client = _get_client()

    doc_id = hashlib.md5(content.encode()).hexdigest()[:12]
    vector = _embed(content)
    meta = metadata or {}
    meta.update({
        "layer": layer,
        "scope": scope,
        "created_at": datetime.now().isoformat(),
    })

    client.upsert(
        collection_name=name,
        points=[PointStruct(id=doc_id, vector=vector, payload=meta | {"content": content})],
    )
    logger.info(f"knowledge_service_v2: upserted {doc_id} → {name}")
    return doc_id


def query(text: str, layer: str, scope: str = "",
          n_results: int = TOP_K) -> list[dict]:
    """查詢單一 collection"""
    try:
        name = _collection_name(layer, scope)
        client = _get_client()
        existing = [c.name for c in client.get_collections().collections]
        if name not in existing:
            return []

        vector = _embed(text)
        hits = client.search(
            collection_name=name,
            query_vector=vector,
            limit=n_results,
            score_threshold=SIMILARITY_THRESHOLD,
            with_payload=True,
        )
        return [
            {
                "content": h.payload.get("content", ""),
                "similarity": round(h.score, 3),
                "meta": {k: v for k, v in h.payload.items() if k != "content"},
            }
            for h in hits
        ]
    except Exception as e:
        logger.warning(f"knowledge_service_v2 query error: {e}")
        return []


def query_all_layers(text: str, user_id: str = "",
                     dept: str = "", company_id: str = "poc") -> list[dict]:
    """
    查詢三層並合併去重。
    查詢順序：personal → dept → company
    去重：同一 content 取最高 similarity，不重複注入 LLM。
    """
    results = []

    if user_id:
        results += query(text, "personal", user_id)

    if dept:
        results += query(text, "dept", dept)
    else:
        client = _get_client()
        for col in client.get_collections().collections:
            if col.name.startswith("ceclaw_dept_"):
                scope = col.name[len("ceclaw_dept_"):]
                results += query(text, "dept", scope)

    results += query(text, "company", company_id)

    # 去重：content 為 key，取最高 score
    seen: set[str] = set()
    unique = []
    for r in sorted(results, key=lambda x: x["similarity"], reverse=True):
        if r["content"] not in seen:
            seen.add(r["content"])
            unique.append(r)

    return unique[:5]


def submit_to_bridge(content: str, source: str = "hermes",
                     user_id: str = "", dept: str = "") -> str:
    """提交知識到 shared_bridge pending 待審"""
    pending_dir = Path(BRIDGE_PATH) / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{ts}_{user_id or 'anon'}.json"
    payload = {
        "content": content,
        "source": source,
        "user_id": user_id,
        "dept": dept,
        "submitted_at": datetime.now().isoformat(),
        "status": "pending",
    }
    (pending_dir / filename).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(f"knowledge_service_v2: submitted {filename} to pending")
    return filename


def approve_pending(filename: str, layer: str = "company",
                    scope: str = "poc") -> bool:
    """審核通過 → 寫入 Qdrant"""
    pending_path = Path(BRIDGE_PATH) / "pending" / filename
    approved_dir = Path(BRIDGE_PATH) / "approved"
    approved_dir.mkdir(parents=True, exist_ok=True)
    if not pending_path.exists():
        return False
    payload = json.loads(pending_path.read_text(encoding="utf-8"))
    payload["status"] = "approved"
    payload["approved_at"] = datetime.now().isoformat()
    (approved_dir / filename).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    add_document(
        payload["content"], layer, scope,
        metadata={"source": payload["source"], "user_id": payload["user_id"]},
    )
    pending_path.unlink()
    logger.info(f"knowledge_service_v2: approved {filename} → {layer}/{scope}")
    return True


def list_pending() -> list[dict]:
    pending_dir = Path(BRIDGE_PATH) / "pending"
    items = []
    for f in sorted(Path(pending_dir).glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["filename"] = f.name
            items.append(data)
        except Exception:
            pass
    return items


def sync_hermes_memory(user_id: str = "default") -> int:
    """
    將 Hermes MEMORY.md 同步至 L3 personal collection。
    觸發時機：對話結束後異步呼叫，不阻塞主查詢路徑。
    """
    memory_path = Path.home() / ".hermes" / "memories" / "MEMORY.md"
    if not memory_path.exists():
        return 0
    content = memory_path.read_text(encoding="utf-8")
    chunks = [c.strip() for c in content.split("§") if c.strip()]
    count = 0
    for chunk in chunks:
        if len(chunk) > 20:
            add_document(chunk, "personal", user_id,
                         metadata={"source": "hermes_memory"})
            count += 1
    logger.info(f"knowledge_service_v2: synced {count} chunks from hermes memory")
    return count
