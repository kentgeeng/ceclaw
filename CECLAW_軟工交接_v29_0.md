# CECLAW 軟工交接文件 v29.0
**更新日期：2026-04-09 下午**
**總工：Claude Sonnet 4.6（本對話）→ 軟工：下一個對話**
**本次對話完成：L3 Chroma→Qdrant 遷移、knowledge_service_v2（async）、proxy.py AsyncClient 修復、SearXNG adapter、Hermes web_search 接通、五題 RAG 驗證全過**

---

## ⚠️ 你是軟工，總工是 Kent（用戶）
- 遇到困難找總工
- 每次動手前必須提 SOP-002
- 不改 master 檔案，先備份
- 每完成一步：`git add -A && git commit -m "..."`

---

## SOP-002 格式
```
【要改什麼】
【為什麼】
【改完Kent會看到什麼】
```

---

## 系統現況（2026-04-09 下午）

### pop-os（192.168.1.210 / 172.25.0.12）
- OpenClaw 4.7（pm2，7 進程）
- CECLAW Router :8000（proxy.py，bak9 最新備份）
- Hermes webapi :8642 + workspace :3000（手動啟動）
- **SearXNG adapter :2337（start-hermes.sh 啟動）** ← 本次新增
- Portal :9000 / Admin :3005
- ollama 0.20.3（systemd，OLLAMA_HOST=0.0.0.0:11434）
- OpenShell gateway ceclaw-test（port 18234）
- LLM Wiki POC（~/llm-wiki-poc/）

### GB10（192.168.1.91）
- Gemma 4 26B MoE Q8，ctx=262144，llama-server :8001（systemd）
- Qdrant :6333
  - tw_laws：221,599條（18類）
  - tw_knowledge：51,970筆（12類）
  - **ceclaw_company_poc：395筆** ← 本次新增
  - **ceclaw_dept_engineering：1筆** ← 本次新增
  - **ceclaw_dept_legal：1筆** ← 本次新增
  - **ceclaw_personal_kent：3筆** ← 本次新增
- ollama bge-m3 :11434（systemd）
- law_advisor_api :8010（systemd）

---

## 本次對話完成事項

| 項目 | commit | 說明 |
|------|--------|------|
| 交接文件入 repo | be35083 | v15/v5.5/v3.5/v28 |
| B70 搬家 SOP v1.3 | 04dc46d | Phase8 順序修正 + token 佔位符 |
| B70 架構圖 v2 | e285a49 | 修正箭頭路徑 |
| L3 Chroma→Qdrant | d9b9805 | knowledge_service_v2，threshold 0.7 |
| 清理 bak/pycache | 28e1f98 | gitignore 補齊 |
| search→query_points | e72cab8 | qdrant_client 1.17 API |
| async embed | 5c1b646 | L3 RAG 正常運作 |
| gitignore bak | c72762e | 清理 |
| SearXNG adapter | 4ff78b4 | Hermes web_search 接通 |
| AsyncClient leak | dece450 | proxy.py + adapter async 修正 |

---

## 重要技術細節

### knowledge_service_v2.py
```python
# 路徑：~/ceclaw/router/knowledge_service_v2.py
# 關鍵參數：
QDRANT_URL = "http://192.168.1.91:6333"
OLLAMA_URL = "http://192.168.1.91:11434"  # GB10 bge-m3
SIMILARITY_THRESHOLD = 0.7
VECTOR_DIM = 1024  # bge-m3

# collection 命名規範：
# ceclaw_personal_{user_id}
# ceclaw_dept_{dept_name}
# ceclaw_company_{company_id}

# 注意：query_all_layers 是 async，proxy.py 要 await
_rag_hits = await _ks.query_all_layers(_query_text, dept=_dept)
```

### proxy.py RAG 注入順序
```python
# 1. L3 knowledge_service_v2（async，await）
# 2. L1 law_advisor_api（_LAW_KEYWORDS 條件執行）
# 3. L2 tw_knowledge（async with AsyncClient）
# 4. inject_system_prompt（含 SOUL.md）
```

### SearXNG adapter
```python
# 路徑：~/ceclaw/router/searxng_adapter.py
# Port：2337
# Endpoints：POST /v1/search + POST /v2/search（Hermes 用 /v2）
# Backend：SearXNG :8888
# 啟動：start-hermes.sh 自動啟動

# 格式轉換：
# SearXNG: {results: [{url, title, content, ...}]}
# → Firecrawl: {success: true, data: {web: [{title, url, description, position}]}}
```

### Hermes 設定
```yaml
# ~/.hermes/config.yaml
model:
  provider: custom
  default: ceclaw
  base_url: http://localhost:8000/v1
  api_key: 97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759
web:
  backend: firecrawl
platform_toolsets:
  webchat:
    - web
    - terminal
    - file
    - memory
    - session_search
```

```bash
# ~/.hermes/.env
FIRECRAWL_API_URL=http://localhost:2337
```

### proxy.py threshold
```python
# L3（knowledge_service_v2）：SIMILARITY_THRESHOLD = 0.7
# L2（tw_knowledge）：score_threshold=0.7
# L1（law_advisor_api）：條件執行，內部有自己的 threshold
```

---

## ⚠️ 優先任務（下個對話）

### P0：每次必查
```bash
curl -s https://api.github.com/repos/openclaw/openclaw/issues/59598 | python3 -c "import json,sys; d=json.load(sys.stdin); print('#59598:', d['state'], d['updated_at'][:10])"
curl -s https://api.github.com/repos/openclaw/openclaw/issues/46049 | python3 -c "import json,sys; d=json.load(sys.stdin); print('#46049:', d['state'], d['updated_at'][:10])"
```

### P1：更新文件進 repo
```bash
cd ~/ceclaw
# 複製新版文件
cp ~/Downloads/HANDOFF-2026-04-09-v16.md .
cp ~/Downloads/CECLAW_EasySetup_v5_6.md .
cp ~/Downloads/"CECLAW_規格規劃說明書_v3_6.md" .
cp ~/Downloads/CECLAW_軟工交接_v29_0.md .
git add -A && git commit -m "docs: 更新交接文件 v16/v5.6/v3.6/v29"
git push
```

### P2：B70 到位後
```bash
# 參考 CECLAW_L1_B70_搬家SOP_v1_3.md（已在 repo）
# 1. Intel compute-runtime v26.09
# 2. vLLM XPU Docker from source
# 3. Qdrant snapshot 搬家（六個 collections）
# 4. 更新 IP：192.168.1.91 → localhost
# 5. OpenShell sandbox template
# 6. 全系統體檢
```

---

## Debug 指引

### L3 RAG 不觸發
```bash
# 確認 _KS_AVAILABLE
cd ~/ceclaw && .venv/bin/python3 -c "from router import proxy; print('_KS_AVAILABLE:', proxy._KS_AVAILABLE)"

# 直接測 async query
cd ~/ceclaw && .venv/bin/python3 - << 'EOF'
import asyncio
from router.knowledge_service_v2 import _embed, query_all_layers
async def test():
    vec = await _embed("測試")
    print(f"embed OK, dim={len(vec)}")
    hits = await query_all_layers("研發部門Git規範")
    print(f"hits: {len(hits)}")
    for h in hits: print(f"  {h['similarity']} {h['content'][:60]}")
asyncio.run(test())
EOF

# 常見問題：
# 1. 'QdrantClient' has no attribute 'search' → 改 query_points
# 2. sync httpx 在 async event loop → 確認 _embed 是 async
# 3. pycache 舊版 → find ~/ceclaw -name "*.pyc" -delete
```

### SearXNG adapter 不工作
```bash
curl -s http://localhost:2337/health
# 若無回應，重啟：
kill $(lsof -ti:2337) 2>/dev/null && sleep 1
cd ~/ceclaw/router && source ../.venv/bin/activate && python3 searxng_adapter.py &

# 確認 /v2/search（Hermes 用這個）
curl -s -X POST http://localhost:2337/v2/search \
  -H "Content-Type: application/json" \
  -d '{"query":"台北天氣","limit":2}'
```

### Hermes web_search 404
```bash
# Hermes 打 /v2/search，舊版 adapter 只有 /v1/search
# 確認 searxng_adapter.py 有兩個 decorator：
grep "app.post" ~/ceclaw/router/searxng_adapter.py
# 應看到：@app.post("/v1/search") + @app.post("/v2/search")
```

### proxy.py 改動沒生效
```bash
find ~/ceclaw -name "*.pyc" -delete
find ~/ceclaw -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
sudo systemctl restart ceclaw-router && sleep 3
grep "knowledge_service\|score_threshold" ~/ceclaw/router/proxy.py | grep -v bak
```

### RAG log 診斷
```bash
# 完整 RAG 追蹤
grep -E "DEBUG|RAG query_text|RAG hits count|RAG: injected|RAG query failed|law_rag|tw_knowledge" ~/.ceclaw/router.log | tail -20
```

---

## 關鍵 URL & Token

```
Router Bearer：97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759
Admin 登入：admin/admin
GitHub：kentgeeng/ceclaw（master）
GB10 SSH：ssh zoe_gb@192.168.1.91
pop-os：192.168.1.210 / 172.25.0.12
ollama（GB10）：http://192.168.1.91:11434
SearXNG：http://localhost:8888
SearXNG adapter：http://localhost:2337
OpenShell gateway：https://127.0.0.1:18234
```

---

## 重啟規則

```bash
sudo systemctl restart ceclaw-router    # proxy.py
bash ~/start-hermes.sh                  # Hermes + SearXNG adapter
pm2 restart ceclaw-gateway              # OpenClaw
sudo systemctl restart ollama           # ollama
openshell gateway start --name ceclaw-test --port 18234
ssh zoe_gb@192.168.1.91 "sudo systemctl restart law-advisor"
```

---

## 已知問題

| 問題 | 嚴重度 | Workaround |
|------|--------|-----------|
| OpenClaw 升級待評估 | 低 | 2026-04-15 後 |
| TPEX 上櫃資料不完整 | 低 | 長期待辦 |
| GB10 單 slot 長任務佔滿 | 中 | 等 B70 |
| Admin UI 中國服務殘留 | 低 | B70 後清理 |
| BM25 Hybrid Search 未開啟 | 中 | B70 後同批做 |
| L3+L2 仍為串行 | 低 | B70 後 asyncio 真並行 |

---

## 版本歷史

| 版本 | 日期 | 主要變更 |
|------|------|---------|
| v29.0 | 2026-04-09 下午 | L3 遷移、async RAG、SearXNG、五題驗證、樣板完成 |
| v28.0 | 2026-04-08 深夜 | Wiki、分類、RAG 體檢、加班費、LLM Wiki POC、OpenShell |
| v27.0 | 2026-04-08 下午 | OpenClaw 4.7、tw_knowledge、14類 advisor |
