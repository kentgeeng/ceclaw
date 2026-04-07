# 法律小顧問 RAG 對接 CECLAW SOP v2
> 執行者：Claude 軟工
> 目標：把法律小顧問 RAG 接進 CECLAW proxy.py
> 前置條件：Qdrant 索引建完（tw_laws collection，~217000 條）

---

## 一、架構

```
使用者請求
    ↓
proxy.py（pop-os 192.168.1.210:8000）
    ↓ 偵測到法規關鍵字（第 340 行附近）
    ↓ 呼叫 GB10 law_advisor_api（192.168.1.91:8010）
    ↓
law_advisor_api.py（GB10）
    ↓ ollama bge-m3 embedding → Qdrant 搜尋
    ↓
Top-5 相關條文
    ↓ 回傳 context 字串
    ↓
proxy.py 第 348 行 inject_system_prompt(rag_context=context)
    ↓
L1 Qwen3 回答
```

---

## 二、已確認事項

| 項目 | 確認結果 |
|------|----------|
| GB10 ollama bge-m3 | ✅ 已安裝（1.2GB，48分鐘前用過）|
| embedding 一致性 | ✅ 索引用 ollama bge-m3，查詢也用 ollama bge-m3 |
| proxy.py 路徑 | `~/ceclaw/router/proxy.py`（pop-os）|
| 注入函式 | `inject_system_prompt(body, soul_md, rag_context)` 第 89 行 |
| 注入位置 | 第 348 行，rag_context 參數傳入 |
| 現有 RAG | 第 345 行已有 RAG 注入，法律 RAG 接在後面，不衝突 |

---

## 三、新增檔案：law_advisor.py（GB10）

位置：`/home/zoe_gb/law_advisor.py`

```python
"""
法律小顧問 RAG 查詢
被 law_advisor_api.py 呼叫
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
    "hr":      ["01_HR"],
    "legal":   ["04_civil", "05_criminal"],
    "medical": ["02_medical"],
    "account": ["07_admin", "09_tax"],
    "ip":      ["06_ip"],
    "digital": ["08_digital"],
    "corp":    ["03_corporate"],
    "all":     None,
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
    """查詢相關法條，失敗時回傳空列表不拋例外"""
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

        results = client.search(
            collection_name=COLLECTION,
            query_vector=vec,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )

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
    """格式化成 rag_context 注入用"""
    if not results:
        return ""
    lines = ["以下是相關法規條文，請依據這些條文回答：\n"]
    for r in results:
        lines.append(r["text"] + "\n")
    return "\n".join(lines)
```

---

## 四、新增檔案：law_advisor_api.py（GB10）

位置：`/home/zoe_gb/law_advisor_api.py`

```python
from fastapi import FastAPI
from pydantic import BaseModel
import law_advisor

app = FastAPI()

class SearchRequest(BaseModel):
    query: str
    advisor: str = "all"
    top_k: int = 5

@app.post("/search")
def search(req: SearchRequest):
    results = law_advisor.search(req.query, req.advisor, req.top_k)
    context = law_advisor.format_context(results)
    return {"results": results, "context": context}

@app.get("/health")
def health():
    return {"status": "ok"}
```

啟動：

```bash
pip install fastapi uvicorn --break-system-packages
uvicorn law_advisor_api:app --host 0.0.0.0 --port 8010
```

---

## 五、修改 proxy.py（pop-os）

位置：`~/ceclaw/router/proxy.py`

### 5-1 加在頂部 import 區

```python
import requests as _req  # 避免與現有 requests 衝突

LAW_ADVISOR_URL = "http://192.168.1.91:8010/search"

LAW_KEYWORDS = [
    "法條", "法規", "條文", "規定", "依法", "幾天", "幾條",
    "罰則", "罰款", "刑責", "權利", "義務", "合法", "違法",
    "勞基法", "個資法", "公司法", "民法", "刑法", "勞動",
    "資遣", "解雇", "退休", "加班", "休假", "薪資", "契約",
    "醫療", "健保", "著作", "商標", "專利", "採購",
]
```

### 5-2 加 law_rag 函式

```python
def get_law_rag(messages: list) -> str:
    """偵測法規關鍵字，呼叫 GB10 law_advisor_api"""
    try:
        last = next(
            (m.get("content", "") for m in reversed(messages)
             if m.get("role") == "user"), ""
        )
        if not any(kw in last for kw in LAW_KEYWORDS):
            return ""
        r = _req.post(
            LAW_ADVISOR_URL,
            json={"query": last, "advisor": "all"},
            timeout=5,
        )
        return r.json().get("context", "")
    except Exception as e:
        import logging
        logging.getLogger("ceclaw.proxy").warning(f"law_rag 失敗：{e}")
        return ""
```

### 5-3 修改注入位置（第 345~348 行）

找到這段：
```python
# 現有 RAG
if _rag_context:
    logger.info(f"RAG: injected {len(_rag_hits)} chunks")

body = inject_system_prompt(body, soul_md=_soul_md, rag_context=_rag_context)
```

改成：
```python
# 現有 RAG
if _rag_context:
    logger.info(f"RAG: injected {len(_rag_hits)} chunks")

# 法律 RAG（接在現有 RAG 後面）
_law_context = get_law_rag(data.get("messages", []))
if _law_context:
    logger.info("law_rag: injected law context")
    _rag_context = (_rag_context + "\n\n" + _law_context).strip()

body = inject_system_prompt(body, soul_md=_soul_md, rag_context=_rag_context)
```

---

## 六、測試

```bash
# 步驟1：確認 Qdrant 索引筆數
ssh zoe_gb@192.168.1.91 "python3 -c \"
from qdrant_client import QdrantClient
c = QdrantClient('localhost', 6333)
print(c.get_collection('tw_laws').points_count)
\""
# 期望：~217000

# 步驟2：啟動 law_advisor_api（GB10）
ssh zoe_gb@192.168.1.91 "cd ~ && uvicorn law_advisor_api:app --host 0.0.0.0 --port 8010 &"

# 步驟3：測試 law_advisor_api
curl -s http://192.168.1.91:8010/health
curl -s http://192.168.1.91:8010/search \
  -H "Content-Type: application/json" \
  -d '{"query":"試用期可以低於基本工資嗎","advisor":"hr"}' | python3 -m json.tool

# 步驟4：修改 proxy.py，重啟 gateway
pm2 restart ceclaw-gateway

# 步驟5：端對端測試
curl -s http://192.168.1.210:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"ceclaw","messages":[{"role":"user","content":"試用期可以低於基本工資嗎？"}]}' | \
  python3 -m json.tool
```

---

## 七、pm2 設定（GB10）

```bash
pm2 start "uvicorn law_advisor_api:app --host 0.0.0.0 --port 8010" \
  --name "law-advisor" \
  --cwd /home/zoe_gb

pm2 save
```

---

## 八、執行順序

```
1. 確認 Qdrant 索引 ~217000 條
2. GB10：建立 law_advisor.py + law_advisor_api.py
3. GB10：pm2 啟動 law-advisor（port 8010）
4. 測試 /health 和 /search 正常
5. pop-os proxy.py 加 LAW_KEYWORDS + get_law_rag()
6. pop-os proxy.py 修改第 345~348 行注入邏輯
7. pm2 restart ceclaw-gateway
8. 端對端測試
```

---

## 九、注意事項

- embedding 全程用 ollama bge-m3，索引與查詢一致
- `get_law_rag()` timeout=5 秒，失敗不影響正常回答
- `law_advisor.search()` 全包 try/except，Qdrant 離線不會讓 proxy 爆掉
- 法律 RAG context 接在現有 _rag_context 後面，不覆蓋
- score 門檻 0.5，低於此不注入
