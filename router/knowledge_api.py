"""
CECLAW Knowledge API
雙向知識橋接 endpoints
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from . import knowledge_service as ks

logger = logging.getLogger("ceclaw.knowledge_api")
router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

BRIDGE_PATH = Path.home() / ".ceclaw" / "knowledge" / "bridge"
HERMES_MEMORY = Path.home() / ".hermes" / "memories" / "MEMORY.md"

# ── Request models ──────────────────────────────────────────

class SubmitRequest(BaseModel):
    content: str
    user_id: Optional[str] = ""
    dept: Optional[str] = ""
    source: Optional[str] = "hermes"

class ApproveRequest(BaseModel):
    filename: str
    layer: Optional[str] = "company"
    scope: Optional[str] = ""

class PolicyRequest(BaseModel):
    content: str
    title: Optional[str] = ""

# ── Endpoints ────────────────────────────────────────────────

@router.post("/submit")
async def submit(req: SubmitRequest):
    """Hermes 提交經驗到 pending，等待主管審核"""
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="content is empty")
    filename = ks.submit_to_bridge(
        content=req.content,
        source=req.source,
        user_id=req.user_id,
        dept=req.dept,
    )
    logger.info(f"knowledge_api: submit {filename}")
    return {"status": "ok", "filename": filename, "message": "已提交，等待主管審核"}

@router.get("/pending")
async def list_pending():
    """主管查看待審清單"""
    items = ks.list_pending()
    return {"status": "ok", "count": len(items), "items": items}

@router.post("/approve")
async def approve(req: ApproveRequest):
    """主管批准，自動入庫並推送 policy 通知到 Hermes"""
    ok = ks.approve_pending(req.filename, layer=req.layer, scope=req.scope)
    if not ok:
        raise HTTPException(status_code=404, detail=f"pending file not found: {req.filename}")
    # 同步通知：把採納事件寫入 policies/，Hermes 下次 sync 時會讀到
    policy_note = (
        f"[企業知識庫更新 {datetime.now().strftime('%Y-%m-%d %H:%M')}] "
        f"新知識已採納入庫（{req.layer}/{req.scope or 'general'}），"
        f"來源檔案：{req.filename}"
    )
    _write_policy(policy_note)
    logger.info(f"knowledge_api: approved {req.filename}")
    return {"status": "ok", "message": f"已採納入庫：{req.layer}/{req.scope or 'general'}"}

@router.post("/add")
async def add_direct(req: SubmitRequest):
    """IT 直接入庫（跳過審核，給管理員用）"""
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="content is empty")
    layer = req.dept or "company"
    doc_id = ks.add_document(req.content, layer=layer, scope=req.user_id or "")
    return {"status": "ok", "doc_id": doc_id}

@router.post("/sync-policies")
async def sync_policies(req: PolicyRequest):
    """OpenClaw 推送規則/政策到 Hermes MEMORY.md（OpenClaw → Hermes 方向）"""
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="content is empty")
    _write_policy(req.content)
    _append_to_hermes_memory(req.content, title=req.title)
    logger.info(f"knowledge_api: policy synced to hermes memory")
    return {"status": "ok", "message": "政策已推送到 Hermes 記憶"}

@router.post("/sync-hermes")
async def sync_hermes(user_id: str = "default"):
    """將 Hermes MEMORY.md 同步到個人知識庫 collection"""
    count = ks.sync_hermes_memory(user_id=user_id)
    return {"status": "ok", "synced_chunks": count}

@router.get("/query")
async def query(q: str, user_id: str = "", dept: str = ""):
    """查詢知識庫（debug 用）"""
    hits = ks.query_all_layers(q, user_id=user_id, dept=dept)
    return {"status": "ok", "count": len(hits), "hits": hits}

# ── Helpers ──────────────────────────────────────────────────

def _write_policy(content: str):
    policy_dir = BRIDGE_PATH / "policies"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    (policy_dir / f"{ts}.txt").write_text(content, encoding="utf-8")

def _append_to_hermes_memory(content: str, title: str = ""):
    if not HERMES_MEMORY.exists():
        return
    existing = HERMES_MEMORY.read_text(encoding="utf-8")
    label = f"[企業規則] {title}" if title else "[企業規則]"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n§\n[{ts}] {label}\n{content}"
    HERMES_MEMORY.write_text(existing + entry, encoding="utf-8")
    logger.info(f"knowledge_api: appended to hermes MEMORY.md")
