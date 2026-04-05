"""
CECLAW Knowledge Service
三層知識庫：personal / dept / company
使用 Chroma 本地向量資料庫
"""
import os
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)

CHROMA_PATH = os.path.expanduser("~/.ceclaw/knowledge/chroma_db")
BRIDGE_PATH = os.path.expanduser("~/.ceclaw/knowledge/bridge")
SIMILARITY_THRESHOLD = 0.25  # 英文 embedding model 對中文語意分數偏低，正式版換中文 embedding 後再調回 0.7

_client = None
_ef = None

def _get_client():
    global _client, _ef
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
        _ef = embedding_functions.DefaultEmbeddingFunction()
    return _client, _ef

def _collection_name(layer: str, scope: str = "") -> str:
    if layer == "personal":
        return f"personal_{scope}" if scope else "personal_default"
    elif layer == "dept":
        return f"dept_{scope}" if scope else "dept_general"
    else:
        return "company"

def _get_or_create_collection(layer: str, scope: str = ""):
    client, ef = _get_client()
    name = _collection_name(layer, scope)
    return client.get_or_create_collection(name=name, embedding_function=ef, metadata={"hnsw:space": "cosine"})

def add_document(content: str, layer: str, scope: str = "",
                 metadata: dict = None) -> str:
    col = _get_or_create_collection(layer, scope)
    doc_id = hashlib.md5(content.encode()).hexdigest()[:12]
    meta = metadata or {}
    meta.update({"layer": layer, "scope": scope,
                 "created_at": datetime.now().isoformat()})
    col.upsert(documents=[content], ids=[doc_id], metadatas=[meta])
    logger.info(f"knowledge_service: added {doc_id} to {layer}/{scope}")
    return doc_id

def query(text: str, layer: str, scope: str = "",
          n_results: int = 3) -> list[dict]:
    try:
        col = _get_or_create_collection(layer, scope)
        results = col.query(query_texts=[text], n_results=n_results)
        if not results["documents"][0]:
            return []
        output = []
        for doc, dist, meta in zip(
            results["documents"][0],
            results["distances"][0],
            results["metadatas"][0]
        ):
            similarity = 1 - dist
            if similarity >= SIMILARITY_THRESHOLD:
                output.append({
                    "content": doc,
                    "similarity": round(similarity, 3),
                    "meta": meta
                })
        return output
    except Exception as e:
        logger.warning(f"knowledge_service query error: {e}")
        return []

def query_all_layers(text: str, user_id: str = "",
                     dept: str = "") -> list[dict]:
    results = []
    if user_id:
        results += query(text, "personal", user_id)
    if dept:
        results += query(text, "dept", dept)
    else:
        # 無指定 dept 時掃所有 dept collections
        client, _ = _get_client()
        for col in client.list_collections():
            if col.name.startswith("dept_"):
                scope = col.name[5:]
                results += query(text, "dept", scope)
    results += query(text, "company")
    seen = set()
    unique = []
    for r in sorted(results, key=lambda x: x["similarity"], reverse=True):
        if r["content"] not in seen:
            seen.add(r["content"])
            unique.append(r)
    return unique[:5]

def submit_to_bridge(content: str, source: str = "hermes",
                     user_id: str = "", dept: str = "") -> str:
    pending_dir = Path(BRIDGE_PATH) / "pending"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{ts}_{user_id or 'anon'}.json"
    payload = {
        "content": content,
        "source": source,
        "user_id": user_id,
        "dept": dept,
        "submitted_at": datetime.now().isoformat(),
        "status": "pending"
    }
    (pending_dir / filename).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"knowledge_service: submitted {filename} to pending")
    return filename

def approve_pending(filename: str, layer: str = "company",
                    scope: str = "") -> bool:
    pending_path = Path(BRIDGE_PATH) / "pending" / filename
    approved_dir = Path(BRIDGE_PATH) / "approved"
    if not pending_path.exists():
        return False
    payload = json.loads(pending_path.read_text(encoding="utf-8"))
    payload["status"] = "approved"
    payload["approved_at"] = datetime.now().isoformat()
    (approved_dir / filename).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    add_document(payload["content"], layer, scope,
                 metadata={"source": payload["source"],
                           "user_id": payload["user_id"]})
    pending_path.unlink()
    logger.info(f"knowledge_service: approved {filename} → {layer}/{scope}")
    return True

def list_pending() -> list[dict]:
    pending_dir = Path(BRIDGE_PATH) / "pending"
    items = []
    for f in sorted(pending_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["filename"] = f.name
            items.append(data)
        except Exception:
            pass
    return items

def sync_hermes_memory(user_id: str = "default") -> int:
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
    logger.info(f"knowledge_service: synced {count} chunks from hermes memory")
    return count
