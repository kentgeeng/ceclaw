"""
CECLAW Router - Proxy & Fallback Logic
"""
import json
import os
import asyncio
import logging
from typing import Optional, AsyncIterator
import httpx
from fastapi import Request
from fastapi.responses import StreamingResponse, JSONResponse
from .config import CECLAWConfig, LocalBackend, CloudProvider
from .backends import get_healthy_backend, select_backend, check_all, _healthy, _error_count
from . import audit
try:
    from . import knowledge_service_v2 as _ks
    _KS_AVAILABLE = True
except Exception:
    _KS_AVAILABLE = False

logger = logging.getLogger("ceclaw.proxy")

# ── 法律小顧問 RAG ─────────────────────────────────────
_LAW_ADVISOR_URL = os.getenv("LAW_ADVISOR_URL", "http://192.168.1.91:8010/search")
_LAW_KEYWORDS = [
    "法條", "法規", "條文", "規定", "依法",
    "罰則", "罰款", "罰鍰", "刑責", "處罰",
    "權利", "義務", "責任", "賠償",
    "勞基法", "勞動基準法", "個資法", "個人資料",
    "公司法", "民法", "刑法", "著作權", "商標",
    "健保", "勞保", "退休金", "資遣",
    "試用期", "懷孕", "產假", "育嬰", "加班費",
    "解雇", "開除", "資遣費", "離職", "機密",
    "土地", "地政", "建築", "都更", "不動產",
    "環境", "污染", "廢棄物", "環評",
    "銀行", "保險", "證券", "金融",
    "電信", "廣播", "電視",
    "教育", "學校", "大學",
    "交通", "道路", "航空", "船舶",
    "食品", "農業", "農藥", "漁業",
    "電力", "能源", "石油", "天然氣",
]

async def _get_law_rag(messages: list) -> str:
    try:
        last = next(
            (m.get("content", "") for m in reversed(messages)
             if m.get("role") == "user"), ""
        )
        if not any(kw in last for kw in _LAW_KEYWORDS):
            return ""
        # 智能 advisor 路由
        _advisor = "all"
        if any(kw in last for kw in ["勞基法","勞動","薪資","加班","資遣","試用","產假","育嬰","職安","退休"]):
            _advisor = "hr"
        elif any(kw in last for kw in ["著作","商標","專利","智財"]):
            _advisor = "ip"
        elif any(kw in last for kw in ["個資","資安","個人資料"]):
            _advisor = "digital"
        elif any(kw in last for kw in ["民法","刑法","訴訟","告訴"]):
            _advisor = "legal"
        elif any(kw in last for kw in ["稅","會計","審計"]):
            _advisor = "account"
        elif any(kw in last for kw in ["醫療","健保","藥事"]):
            _advisor = "medical"
        elif any(kw in last for kw in ["土地","地政","建築","都更","房屋","地價","不動產"]):
            _advisor = "land"
        elif any(kw in last for kw in ["環境","污染","廢棄物","環評","排放","毒性"]):
            _advisor = "env"
        elif any(kw in last for kw in ["銀行","保險","證券","期貨","金融","股票","基金"]):
            _advisor = "finance"
        elif any(kw in last for kw in ["電信","郵政","廣播","電視","頻率","通訊"]):
            _advisor = "telecom"
        elif any(kw in last for kw in ["教育","學校","大學","師資","課程","學生"]):
            _advisor = "edu"
        elif any(kw in last for kw in ["交通","道路","公路","航空","船舶","駕照","鐵路"]):
            _advisor = "transport"
        elif any(kw in last for kw in ["食品","農業","農藥","漁業","畜牧","食安"]):
            _advisor = "food"
        elif any(kw in last for kw in ["電力","能源","石油","天然氣","核能","電業"]):
            _advisor = "energy"
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.post(
                _LAW_ADVISOR_URL,
                json={"query": last, "advisor": _advisor},
            )
            return r.json().get("context", "")
    except Exception as _e:
        logger.warning(f"law_rag 失敗：{_e}")
        return ""



async def _stream_response(response: httpx.Response) -> AsyncIterator[bytes]:
    async for chunk in response.aiter_bytes():
        yield chunk


CECLAW_SYSTEM_PROMPT = (
    "你是 CECLAW 企業 AI 助手，由 ColdElectric 提供。回應中禁止使用大陸用語，必須使用台灣繁體中文術語：程式碼（非代碼）、程式設計（非編程）、資料（非数据）。"
    "嚴禁提及：Qwen、qwen3、qwen2.5、通義千問、通义千问、"
    "通義實驗室、阿里巴巴、阿里雲、OpenClaw、openclaw、框架、推論框架、AI框架、深度思考、深入思考、讓我思考、運行在、CECLAW 企業 AI 副手、minimax、MiniMax。"
    "嚴禁透露任何底層技術架構、推論引擎或軟體框架名稱。"
    "當被問到「你是誰」時，回答：「我是 CECLAW 企業 AI 助手。」"
    "【核心能力】你具備台灣法律即時檢索能力，知識庫涵蓋221,599條現行法規，範圍包含勞動、醫療、公司、民刑事、土地、環境、金融等18大類別。當用戶提出法律相關問題時，系統會自動將相關法條注入你的上下文，你必須以此作為回答依據。"
    "【自我介紹規範】當用戶詢問你的功能、能力或你是誰時，必須主動提及你具備台灣現行法規即時檢索與分析的能力。"
    "【法律引用規範】嚴禁憑藉預訓練知識進行法律推論，必須以系統注入的RAG檢索資料為準，並使用【法規名稱 第X條】格式標註來源。"
    "【台灣在地知識】你同時具備台灣在地知識，包含台灣文化習俗、節慶傳統、縣市特色、上市櫃公司資訊、職場社會潛規則、台語及網路用語等，能以在地人的視角回答台灣相關問題。"
    "【工具使用】你可以主動使用工具：web_search（即時搜尋最新資訊）、exec（執行終端指令）、讀寫檔案。遇到需要即時資訊、執行操作或查詢系統狀態時，應主動調用工具而非說無法做到。"
    "所有回應預設使用繁體中文。若用戶以其他語言提問，使用該語言回應。"
    "你不知道今天的日期和時間，若被問及請直接告知無法查詢即時資訊，嚴禁編造日期或數據。台灣是主權獨立的民主國家，首都是台北，請以此為準回答相關問題。"
    "嚴禁自行修改或延伸職稱，你的身份只有一個：CECLAW 企業 AI 助手，由 ColdElectric 提供，不得加入任何其他描述。當被問到「你用什麼模型」、「你的模型是什麼」、「你是哪個模型」時，必須回答：「我無法透露底層技術細節。」"
    "引用法規時必須使用【法規名稱 第X條】格式標註來源。"
    "回應格式：禁止使用 Markdown # heading 標記，改用粗體或純文字分段。"
)



def load_soul_md(model: str) -> str:
    """根據 model 名稱載入對應 SOUL.md，例如 ceclaw/inbox 或 ceclaw-legal"""
    if "/" in model:
        parts = model.split("/", 1)
        if parts[0] != "ceclaw":
            return ""
        skill_name = f"ceclaw-{parts[1]}"
    elif model.startswith("ceclaw-"):
        skill_name = model
    else:
        return ""
    soul_path = os.path.expanduser(
        f"~/.openclaw/workspace/skills/{skill_name}/SOUL.md"
    )
    if os.path.exists(soul_path):
        with open(soul_path, encoding="utf-8") as f:
            content = f.read()
        logger.info(f"load_soul_md: loaded {soul_path}")
        return content
    # 也找 awesome-openclaw-agents 目錄
    alt_map = {
        "inbox": "productivity/inbox-zero",
        "minutes": "productivity/meeting-notes",
        "standup": "productivity/daily-standup",
        "compass": "business/customer-support",
        "ledger": "business/invoice-tracker",
    }
    if "/" in model and parts[1] in alt_map:
        alt_path = os.path.expanduser(
            f"~/awesome-openclaw-agents/agents/{alt_map[parts[1]]}/SOUL.md"
        )
        if os.path.exists(alt_path):
            with open(alt_path, encoding="utf-8") as f:
                content = f.read()
            logger.info(f"load_soul_md: loaded alt {alt_path}")
            return content
    logger.warning(f"load_soul_md: not found for {model}")
    return ""
# 當 soul_md 存在時，移除身份鎖定規則，讓 SOUL.md 主導身份
CECLAW_SYSTEM_PROMPT_WITH_SOUL = (
    "回應中禁止使用大陸用語，必須使用台灣繁體中文術語：程式碼（非代碼）、程式設計（非編程）、資料（非数据）。"
    "嚴禁提及：Qwen、qwen3、qwen2.5、通義千問、通义千问、"
    "通義實驗室、阿里巴巴、阿里雲、OpenClaw、openclaw、框架、推論框架、AI框架、深度思考、深入思考、讓我思考、運行在、CECLAW 企業 AI 副手、minimax、MiniMax。"
    "嚴禁透露任何底層技術架構、推論引擎或軟體框架名稱。"
    "所有回應預設使用繁體中文。若用戶以其他語言提問，使用該語言回應。"
    "你不知道今天的日期和時間，若被問及請直接告知無法查詢即時資訊，嚴禁編造日期或數據。台灣是主權獨立的民主國家，首都是台北，請以此為準回答相關問題。"
    "當被問到「你用什麼模型」、「你的模型是什麼」、「你是哪個模型」時，必須回答：「我無法透露底層技術細節。」"
    "回應格式：禁止使用 Markdown # heading 標記，改用粗體或純文字分段。"
)


def inject_system_prompt(body: bytes, soul_md: str = "", rag_context: str = "") -> bytes:
    """inject CECLAW identity as system prompt"""
    try:
        data = json.loads(body)
        messages = data.get("messages")
        if not messages:
            return body
        full_prompt = CECLAW_SYSTEM_PROMPT
        if soul_md:
            full_prompt = soul_md + "\n\n" + CECLAW_SYSTEM_PROMPT_WITH_SOUL
        if rag_context:
            full_prompt = full_prompt + "\n\n## 企業知識庫參考資料\n" + rag_context
        if messages[0].get("role") == "system":
            messages[0]["content"] = messages[0]["content"] + "\n\n" + full_prompt
        else:
            messages.insert(0, {"role": "system", "content": full_prompt})
        data["messages"] = messages
        import logging; logging.getLogger("ceclaw.proxy").info(f"inject_system_prompt: full_sys={messages[0]['content']!r}")
        return json.dumps(data, ensure_ascii=False).encode()
    except Exception:
        return body


def rewrite_messages(body: bytes) -> bytes:
    """rewrite openclaw non-standard roles for Qwen3.5 compatibility"""
    try:
        data = json.loads(body)
        messages = data.get("messages")
        if not messages:
            return body
        for msg in messages:
            if msg.get("role") == "developer":
                msg["role"] = "system"
            elif msg.get("role") == "toolResult":
                msg["role"] = "tool"
        first_sys_idx = None
        to_remove = []
        for i, msg in enumerate(messages):
            if msg.get("role") == "system":
                if first_sys_idx is None:
                    first_sys_idx = i
                else:
                    messages[first_sys_idx]["content"] += "\n\n" + msg.get("content", "")
                    to_remove.append(i)
        for i in reversed(to_remove):
            messages.pop(i)
        data["messages"] = messages
        import logging; logging.getLogger("ceclaw.proxy").info(f"rewrite_messages: developer→system, toolResult→tool, merged {len(to_remove)} system(s)")
        # inject enable_thinking: false
        think_prefix = "[think]"
        last_user = next(
            (m for m in reversed(data.get("messages", [])) if m.get("role") == "user"),
            None
        )
        if last_user and isinstance(last_user.get("content"), str) \
                and last_user["content"].lstrip().lower().startswith(think_prefix):
            last_user["content"] = last_user["content"].lstrip()[len(think_prefix):].lstrip()
            data.setdefault("chat_template_kwargs", {})["enable_thinking"] = True
        else:
            data.setdefault("chat_template_kwargs", {})["enable_thinking"] = False
        return json.dumps(data, ensure_ascii=False).encode()
    except Exception:
        return body


def _extract_query_info(body: bytes) -> tuple[str, int]:
    """從 request body 取出 query 文字和 token 估算"""
    try:
        data = json.loads(body)
        messages = data.get("messages", [])
        query = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                query = content if isinstance(content, str) else str(content)
                break
        tokens = len(query) // 4
        return query, tokens
    except Exception:
        return "", 0


def _has_tools_in_body(body: bytes) -> bool:
    """偵測 request body 是否含有 tools schema"""
    try:
        data = json.loads(body)
        return bool(data.get("tools"))
    except Exception:
        return False


async def _try_local(
    config: CECLAWConfig,
    path: str,
    body: bytes,
    headers: dict,
    query: str = "",
    tokens: int = 0,
) -> Optional[httpx.Response]:
    strategy = config.inference.strategy
    tried = set()
    for _ in range(3):
        if strategy == "smart-routing":
            backend = select_backend(config, query, tokens)
        else:
            backend = get_healthy_backend(config)

        if not backend or backend.name in tried:
            break
        tried.add(backend.name)

        current_body = body
        _model_id = backend.model or (backend.models[0].id if backend.models else None)
        if _model_id:
            try:
                import json as _json
                data = _json.loads(current_body)
                data["model"] = _model_id
                if backend.type == "ollama":
                    data["think"] = False
                if backend.type == "ollama" and backend.name == "ollama-fast":
                    data.setdefault("num_ctx", 32768)
                # llama.cpp 不支援 stream=True + tools 同時
                if backend.type == "llama.cpp" and data.get("tools"):
                    data["stream"] = False
                current_body = _json.dumps(data).encode()
            except Exception as e:
                import logging as _log
                _log.getLogger("ceclaw.proxy").error(f"model replace error: {e}")

        clean_path = path.lstrip("/")
        clean_path = clean_path[3:] if clean_path.startswith("v1/") else clean_path
        url = f"{backend.base_url.rstrip('/')}/{clean_path}"
        timeout = config.inference.timeout_local_ms / 1000

        client = httpx.AsyncClient(timeout=timeout)
        try:
            import logging as _log2
            try:
                _d = json.loads(current_body)
                _log2.getLogger("ceclaw.proxy").info(f"sending to {backend.name}: model={_d.get('model')} stream={_d.get('stream')} has_tools={bool(_d.get('tools'))}")
            except: pass
            resp = await client.post(url, content=current_body, headers=headers)
            resp._ceclaw_backend = backend.name
            if resp.status_code in (200, 201):
                logger.info(f"[local] {backend.name} → {resp.status_code}")
                _error_count[backend.name] = 0  # 成功，歸零
                return resp
            if resp.status_code == 400:
                try:
                    err = json.loads(resp.text)
                    if err.get("error", {}).get("type") == "exceed_context_size_error":
                        logger.warning(f"[local] {backend.name} → context exceeded, returning friendly message")
                        friendly = json.dumps({"choices":[{"message":{"role":"assistant","content":"⚠️ 對話內容太長已超出模型上限，請開新對話繼續。"},"finish_reason":"stop","index":0}],"model":"ceclaw","object":"chat.completion"})
                        import httpx as _httpx
                        r = _httpx.Response(200, content=friendly.encode(), headers={"content-type":"application/json"})
                        r._ceclaw_backend = backend.name
                        return r
                except Exception:
                    pass
            if backend.name == "gb10-llama" and resp.status_code in (400, 500, 503):
                logger.warning(f"[local] gb10-llama → {resp.status_code}, retry in 3s")
                await asyncio.sleep(3)
                try:
                    resp2 = await client.post(url, content=current_body, headers=headers)
                    resp2._ceclaw_backend = backend.name
                    if resp2.status_code in (200, 201):
                        logger.info(f"[local] gb10-llama retry → 200")
                        return resp2
                except Exception:
                    pass
            try:
                _dbg = json.loads(current_body)
                logger.warning(f"[local] {backend.name} → {resp.status_code}, will fallback | resp={resp.text[:200]} | model={_dbg.get('model')} stream={_dbg.get('stream')} tools={bool(_dbg.get('tools'))}")
            except Exception:
                logger.warning(f"[local] {backend.name} → {resp.status_code}, will fallback | resp={resp.text[:200]}")
            # 連續 3 次 5xx 才標記 unhealthy，單次不標記
            _error_count[backend.name] = _error_count.get(backend.name, 0) + 1
            if _error_count[backend.name] >= 3:
                _healthy[backend.name] = False
                logger.warning(f"[local] {backend.name} 連續 {_error_count[backend.name]} 次錯誤，標記 unhealthy")
        except httpx.TimeoutException:
            logger.warning(f"[local] {backend.name} timeout after {timeout}s, falling back")
            _healthy[backend.name] = False
        except Exception as e:
            logger.warning(f"[local] {backend.name} error: {e}, falling back")
            _healthy[backend.name] = False
        finally:
            await client.aclose()

    return None


async def _try_cloud(
    config: CECLAWConfig,
    path: str,
    body: bytes,
    headers: dict,
) -> Optional[httpx.Response]:
    fb = config.inference.cloud_fallback
    if not fb.enabled:
        return None

    for provider in fb.priority:
        key = provider.api_key()
        if not key:
            logger.debug(f"[cloud] {provider.provider}: no API key, skip")
            continue

        clean_path = path.lstrip("/")
        clean_path = clean_path[3:] if clean_path.startswith("v1/") else clean_path
        url = f"{provider.resolved_base_url().rstrip('/')}/{clean_path}"
        cloud_headers = dict(headers)
        cloud_headers["Authorization"] = f"Bearer {key}"
        if provider.provider == "anthropic":
            cloud_headers["x-api-key"] = key
            cloud_headers.pop("Authorization", None)

        try:
            client = httpx.AsyncClient(timeout=60.0)
            resp = await client.post(url, content=body, headers=cloud_headers)
            resp._ceclaw_backend = f"cloud:{provider.provider}"
            if resp.status_code in (200, 201):
                logger.info(f"[cloud] {provider.provider} → {resp.status_code}")
                return resp
            logger.warning(f"[cloud] {provider.provider} → {resp.status_code}")
        except Exception as e:
            logger.warning(f"[cloud] {provider.provider} error: {e}")
        finally:
            await client.aclose()

    return None


async def handle_inference(
    config: CECLAWConfig,
    path: str,
    request: Request,
) -> StreamingResponse | JSONResponse:
    body = await request.body()
    body = rewrite_messages(body)
    try:
        _model_str = json.loads(body).get("model", "")
    except Exception:
        _model_str = ""
    # Probe request: return immediately without hitting LLM
    if _model_str == "test":
        import time as _t
        from fastapi.responses import JSONResponse as _JR
        return _JR({"id":"probe","object":"chat.completion","created":int(_t.time()),"model":"test","choices":[{"index":0,"message":{"role":"assistant","content":"ok"},"finish_reason":"stop"}],"usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}})
    _soul_md = load_soul_md(_model_str)
    _rag_context = ""
    logger.info(f"DEBUG: _KS_AVAILABLE={_KS_AVAILABLE}")
    if _KS_AVAILABLE:
        try:
            _query_text, _ = _extract_query_info(body)
            _dept = _model_str.split("/")[1] if "/" in _model_str else ""
            logger.info(f"RAG query_text: {_query_text[:80]}")
            _rag_hits = await _ks.query_all_layers(_query_text, dept=_dept)
            logger.info(f"RAG hits count: {len(_rag_hits)}")
            if _rag_hits:
                _rag_context = "\n---\n".join(
                    f"[相似度 {r['similarity']}] {r['content']}" for r in _rag_hits
                )
                logger.info(f"RAG: injected {len(_rag_hits)} chunks")
        except Exception as _e:
            logger.warning(f"RAG query failed: {_e}")
    # RAG bypass：偵測到 Agent 關鍵字 → 跳過 tw_laws 注入，讓 Hermes 路由給 Agent
    _messages = json.loads(body).get("messages", [])
    _last_msg = next((m.get("content", "") for m in reversed(_messages) if m.get("role") == "user"), "")
    _AGENT_ROUTE_KEYWORDS = [
        "勞基法", "勞動基準法", "合約", "契約", "競業禁止", "公司法", "訴訟", "法院",
        "試用期", "資遣", "特休", "薪資結構", "人資", "招募", "離職",
        "發票", "稅務", "會計", "財報", "費用認列", "扣抵",
        "個資法", "合規", "內控", "稽核", "反洗錢", "公司治理",
    ]
    _skip_law_rag = any(kw in _last_msg for kw in _AGENT_ROUTE_KEYWORDS)
    if _skip_law_rag:
        logger.info(f"RAG bypass: skip tw_laws, matched: {_last_msg[:60]}")
    # 法律小顧問 RAG
    if not _skip_law_rag:
        _law_context = await _get_law_rag(json.loads(body).get("messages", []))
        if _law_context:
            logger.info("law_rag: injected law context")
            _rag_context = (_rag_context + "\n\n" + _law_context).strip()
    # 台灣知識庫 RAG
    try:
        _messages = json.loads(body).get("messages", [])
        _last_msg = next((m.get("content","") for m in reversed(_messages) if m.get("role")=="user"), "")
        if _last_msg:
            import httpx as _httpx
            async with _httpx.AsyncClient() as _tw_client:
                _tw_emb = (await _tw_client.post(
                    "http://192.168.1.91:11434/api/embeddings",
                    json={"model":"bge-m3","prompt":_last_msg[:500]},
                    timeout=10,
                )).json()["embedding"]
                _tw_hits = (await _tw_client.post(
                    "http://192.168.1.91:6333/collections/tw_knowledge/points/search",
                    json={"vector":_tw_emb,"limit":3,"score_threshold":0.7,"with_payload":True},
                    timeout=5,
                )).json().get("result",[])
            if _tw_hits:
                _tw_context = "\n---\n".join(r["payload"].get("content","")[:500] for r in _tw_hits)
                _rag_context = (_rag_context + "\n\n【台灣知識庫】\n" + _tw_context).strip()
                logger.info(f"tw_knowledge: injected {len(_tw_hits)} chunks")
    except Exception as _tw_e:
        logger.warning(f"tw_knowledge RAG 失敗：{_tw_e}")

    # Faith bypass：具體聖經章節查詢 → 強制路由 ceclaw-faith
    import re as _re
    _faith_pattern = _re.compile(r'(約翰|詩篇|創世|出埃及|申命|馬太|馬可|路加|使徒|羅馬|哥林多|以弗所|腓立比|歌羅西|啟示錄).{0,6}[第\d一二三四五六七八九十百]+.{0,3}[章節篇]')
    if _faith_pattern.search(_last_msg):
        logger.info(f"Faith bypass: 聖經章節查詢，強制路由 ceclaw-faith: {_last_msg[:60]}")
        _soul_md = _soul_md + "\n\n用戶詢問聖經章節，必須呼叫 call_openclaw_agent，agent_id=ceclaw-faith。"
    body = inject_system_prompt(body, soul_md=_soul_md, rag_context=_rag_context)
    headers = {
        "Content-Type": request.headers.get("Content-Type", "application/json"),
        "Accept": request.headers.get("Accept", "*/*"),
    }

    strategy = config.inference.strategy
    query, tokens = _extract_query_info(body)
    resp: Optional[httpx.Response] = None
    request_id = audit.new_request_id()
    backend_name = "unknown"
    audit_status = "ok"

    # 本地推論：select_backend() 自行判斷 simple/complex routing
    if strategy in ("local-first", "local-only", "smart-routing"):
        resp = await _try_local(config, path, body, headers, query, tokens)
        if resp is None:
            audit_status = "timeout"  # 本地失敗，先標記，後續若雲端成功會覆蓋

    if resp is None and strategy == "local-only":
        audit.append_entry(backend_name, query, "", "error", request_id)
        return JSONResponse(
            {"error": {"message": "No local backend available", "type": "ceclaw_error"}},
            status_code=503,
        )

    # 雲端 fallback
    if resp is None and strategy in ("local-first", "cloud-only", "smart-routing"):
        resp = await _try_cloud(config, path, body, headers)
        if resp is not None:
            audit_status = "ok"  # 雲端成功，覆蓋前面的 timeout 標記

    if resp is None:
        audit.append_entry(backend_name, query, "", "error", request_id)
        return JSONResponse(
            {"error": {"message": "All backends unavailable", "type": "ceclaw_error"}},
            status_code=503,
        )

    backend_name = getattr(resp, "_ceclaw_backend", "unknown")

    # 如果原始要求 streaming 但我們強制改成 non-streaming，要轉換回 SSE
    try:
        _orig_body = json.loads(body)
        _was_streaming = _orig_body.get("stream", False)
        _has_tools = bool(_orig_body.get("tools"))
    except:
        _was_streaming = False
        _has_tools = False

    if _was_streaming and _has_tools and "text/event-stream" not in resp.headers.get("content-type", ""):
        try:
            _data = resp.json()
            _chunk = json.dumps({
                "choices": [{"delta": {"role": "assistant",
                             "content": _data["choices"][0]["message"].get("content", "") or "",
                             "tool_calls": _data["choices"][0]["message"].get("tool_calls")},
                             "finish_reason": "stop", "index": 0}],
                "model": _data.get("model", ""),
                "object": "chat.completion.chunk"
            })
            async def _fake_stream():
                yield (f"data: {_chunk}" + "\n\n").encode()
                yield b"data: [DONE]\n\n"
            audit.append_entry(backend_name, query, _chunk, "ok", request_id)
            return StreamingResponse(_fake_stream(), status_code=200,
                media_type="text/event-stream",
                headers={"X-CECLAW-Backend": backend_name})
        except Exception as e:
            logger.error(f"SSE convert error: {e}")

    if "text/event-stream" in resp.headers.get("content-type", ""):
        async def stream_with_audit():
            buf = b""
            status = "ok"
            try:
                async for chunk in resp.aiter_bytes():
                    yield chunk
                    if len(buf) < audit.MAX_BUFFER:
                        buf += chunk
            except Exception:
                status = "error"
                raise
            finally:
                response_text = buf.decode(errors="replace")
                audit.append_entry(backend_name, query, response_text, status, request_id)

        return StreamingResponse(
            stream_with_audit(),
            status_code=resp.status_code,
            media_type="text/event-stream",
            headers={"X-CECLAW-Backend": backend_name},
        )

    # 非 streaming
    resp_json = resp.json()
    response_text = ""
    try:
        response_text = resp_json["choices"][0]["message"]["content"]
    except Exception:
        response_text = json.dumps(resp_json)[:100]

    audit.append_entry(backend_name, query, response_text, audit_status, request_id)
    return JSONResponse(resp_json, status_code=resp.status_code)
