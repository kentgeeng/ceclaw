"""
CECLAW Router - Chain Audit Log
鏈式審計記錄，每條 entry 包含前一條的 hash，形成不可竄改鏈。
"""
import fcntl
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("ceclaw.audit")

AUDIT_PATH = Path.home() / ".ceclaw" / "audit.log"
MAX_BUFFER = 10 * 1024 * 1024  # 10MB
GENESIS_HASH = "0" * 64


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _compute_chain_hash(
    seq: int,
    request_id: str,
    timestamp: str,
    backend: str,
    query_hash: str,
    response_hash: str,
    status: str,
    prev_hash: str,
) -> str:
    raw = (
        str(seq)
        + request_id
        + timestamp
        + backend
        + query_hash
        + response_hash
        + status
        + prev_hash
    )
    return _sha256(raw)


def _get_last_entry() -> tuple[int, str]:
    """回傳 (last_seq, last_chain_hash)，空檔案回傳 (0, GENESIS_HASH)"""
    if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
        return 0, GENESIS_HASH
    try:
        with open(AUDIT_PATH, "rb") as f:
            # 從尾端找最後一行
            f.seek(0, 2)
            size = f.tell()
            buf = b""
            pos = size - 1
            while pos >= 0:
                f.seek(pos)
                ch = f.read(1)
                if ch == b"\n" and buf:
                    break
                buf = ch + buf
                pos -= 1
            line = buf.decode().strip()
            if not line:
                return 0, GENESIS_HASH
            entry = json.loads(line)
            return entry["seq"], entry["chain_hash"]
    except Exception as e:
        logger.warning(f"[audit] 讀取最後一條失敗: {e}")
        return 0, GENESIS_HASH


def append_entry(
    backend: str,
    query: str,
    response: str,
    status: str,
    request_id: str,
) -> None:
    """寫入一條 audit entry，使用 flock 保護並發。"""
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    query_preview = query[:50]
    query_hash = _sha256(query)
    response_preview = response[:50]
    response_hash = _sha256(response[:100])

    try:
        with open(AUDIT_PATH, "a") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                seq, prev_hash = _get_last_entry()
                seq += 1
                chain_hash = _compute_chain_hash(
                    seq, request_id, timestamp, backend,
                    query_hash, response_hash, status, prev_hash,
                )
                entry = {
                    "seq": seq,
                    "request_id": request_id,
                    "timestamp": timestamp,
                    "backend": backend,
                    "query_preview": query_preview,
                    "query_hash": query_hash,
                    "response_preview": response_preview,
                    "response_hash": response_hash,
                    "status": status,
                    "prev_hash": prev_hash,
                    "chain_hash": chain_hash,
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        logger.error(f"[audit] 寫入失敗: {e}")


def verify() -> tuple[bool, str]:
    """
    驗證 audit.log 鏈完整性。
    回傳 (ok, message)
    """
    if not AUDIT_PATH.exists():
        return True, "audit.log 不存在，尚無記錄。"

    prev_hash = GENESIS_HASH
    prev_seq = 0

    try:
        with open(AUDIT_PATH, "r") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    return False, f"第 {lineno} 行 JSON 解析失敗"

                # seq 遞增檢查
                if e["seq"] != prev_seq + 1:
                    return False, f"第 {lineno} 行 seq 不連續（預期 {prev_seq+1}，實際 {e['seq']}）"

                # prev_hash 檢查
                if e["prev_hash"] != prev_hash:
                    return False, f"第 {lineno} 行（seq={e['seq']}）prev_hash 不符，鏈斷裂"

                # chain_hash 重算
                expected = _compute_chain_hash(
                    e["seq"], e["request_id"], e["timestamp"], e["backend"],
                    e["query_hash"], e["response_hash"], e["status"], e["prev_hash"],
                )
                if e["chain_hash"] != expected:
                    return False, f"第 {lineno} 行（seq={e['seq']}）chain_hash 驗證失敗，記錄可能被竄改"

                prev_hash = e["chain_hash"]
                prev_seq = e["seq"]

    except Exception as ex:
        return False, f"驗證過程發生錯誤: {ex}"

    return True, f"✅ 驗證通過，共 {prev_seq} 條記錄，鏈完整。"


def new_request_id() -> str:
    return str(uuid.uuid4())
