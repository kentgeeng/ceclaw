"""
CECLAW Shared Bridge
雙向知識橋接層 — OpenClaw 與 Hermes 共用
核心函式：write / scan / classify
JSON 格式：id / timestamp / source / direction / content / status / state / version / priority / ttl
"""
import json
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("ceclaw.shared_bridge")

SHARED_DIR = Path.home() / ".ceclaw" / "knowledge" / "bridge" / "shared"
SHARED_DIR.mkdir(parents=True, exist_ok=True)

TTL_SECONDS = 86400 * 7  # 7天自動清理


def _make_id(source: str, content: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    h = hashlib.md5(content.encode()).hexdigest()[:8]
    return f"{ts}_{source}_{h}"


def write(
    content: str,
    source: str,              # "openclaw" | "hermes"
    direction: str,           # "o2h" | "h2o"
    user_id: str = "",
    dept: str = "",
    priority: str = "normal", # "high" | "normal" | "low"
    parent_id: str = "",
    metadata: dict = None,
) -> str:
    """寫入一筆到共同區，回傳 id"""
    if not content.strip():
        raise ValueError("content is empty")

    # version：同內容累加版號
    version = 1
    h = hashlib.md5(content.encode()).hexdigest()[:8]
    existing = list(SHARED_DIR.glob(f"*_{source}_{h}.json"))
    if existing:
        try:
            last = json.loads(existing[-1].read_text(encoding="utf-8"))
            version = last.get("version", 1) + 1
        except Exception:
            pass

    doc_id = _make_id(source, content)
    payload = {
        "id": doc_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "direction": direction,
        "user_id": user_id,
        "dept": dept,
        "content": content,
        "status": "pending",
        "state": "new",        # new / processing / applied / failed
        "version": version,
        "parent_id": parent_id,
        "priority": priority,  # high / normal / low
        "ttl": TTL_SECONDS,
        "metadata": metadata or {},
    }
    path = SHARED_DIR / f"{doc_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"shared_bridge.write: {doc_id} source={source} direction={direction} priority={priority} v{version}")
    return doc_id


def scan(
    direction: str = None,    # None=全部, "o2h", "h2o"
    status: str = "pending",  # None=全部
    source: str = None,       # None=全部
    priority: str = None,     # None=全部
) -> list[dict]:
    """掃描共同區，回傳符合條件的項目清單（依 priority 排序：high > normal > low）"""
    _cleanup_expired()
    items = []
    priority_order = {"high": 0, "normal": 1, "low": 2}
    for f in sorted(SHARED_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["_path"] = str(f)
            if direction and data.get("direction") != direction:
                continue
            if status and data.get("status") != status:
                continue
            if source and data.get("source") != source:
                continue
            if priority and data.get("priority") != priority:
                continue
            items.append(data)
        except Exception as e:
            logger.warning(f"shared_bridge.scan: skip {f.name}: {e}")
    items.sort(key=lambda x: priority_order.get(x.get("priority", "normal"), 1))
    return items


def classify(
    doc_id: str,
    new_status: str,           # "approved" | "rejected" | "processed"
    new_state: str = "applied", # "processing" | "applied" | "failed"
    classified_by: str = "",   # "openclaw" | "hermes"
) -> bool:
    """更新一筆的 status 與 state，代表各自分類完成"""
    path = SHARED_DIR / f"{doc_id}.json"
    if not path.exists():
        logger.warning(f"shared_bridge.classify: not found {doc_id}")
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    data["status"] = new_status
    data["state"] = new_state
    data["classified_by"] = classified_by
    data["classified_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"shared_bridge.classify: {doc_id} → {new_status}/{new_state} by {classified_by}")
    return True


def _cleanup_expired():
    """清除超過 TTL 的項目"""
    now = datetime.now(timezone.utc).timestamp()
    for f in SHARED_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            ts = datetime.fromisoformat(data["timestamp"]).timestamp()
            ttl = data.get("ttl", TTL_SECONDS)
            if now - ts > ttl:
                f.unlink()
                logger.info(f"shared_bridge.cleanup: expired {f.name}")
        except Exception:
            pass
