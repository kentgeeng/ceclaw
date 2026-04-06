# CECLAW Hermes Workspace 安裝 SOP
**版本：v1.6**
**更新日期：2026-04-06**

---

## 架構說明

```
hermes-workspace :3000（React UI）
    ↓ HERMES_API_URL=http://127.0.0.1:8642
hermes-agent-fork webapi :8642（Python）
    ├─ /api/sessions/{id}/chat/stream  ← 實際 chat 走這裡
    │       ↓
    │   Hermes agent loop
    │       ↓ resolve_runtime_provider() 讀 config.yaml + HERMES_BASE_URL env
    │       ↓
    │   CECLAW Router :8000 → GB10 :8001
    │
    ├─ /v1/chat/completions  ← 只有 onboarding 用（completions.py proxy）
    └─ /health, /api/sessions, /v1/models 等
```

> ⚠️ session chat 到 GB10 的關鍵：`HERMES_BASE_URL=http://localhost:8000/v1` env var
> 讓 agent loop 的 `resolve_runtime_provider()` 找到 CECLAW Router。
> completions.py 只是讓 onboarding 能通過，實際推理走 session-based path。

---

## 目錄結構

```
~/hermes-agent-fork/    ← webapi 後端（outsourc-e fork，有 webapi module）
~/hermes-workspace/     ← 前端 UI（React + Vite）
~/.hermes/
    config.yaml         ← provider 設定（必須在 model: 底下）
    memories/
        MEMORY.md       ← 個人記憶（rotate 上限 300 行）
    .env                ← ⚠️ 可能有殘留 OPENAI key，需清除
```

---

## 環境需求

| 工具 | 版本 | 用途 |
|------|------|------|
| Node.js | v22.22.1 | hermes-workspace |
| Python | 3.10.12 | hermes-agent-fork webapi |
| pnpm | 10.33.0 | workspace 套件管理 |

---

## Step 1：取得源碼

```bash
# webapi（outsourc-e fork，公開）
# ⚠️ 不是原版 NousResearch/hermes-agent，原版沒有 webapi module
git clone https://github.com/outsourc-e/hermes-agent ~/hermes-agent-fork

# workspace（公開，MIT）
git clone https://github.com/outsourc-e/hermes-workspace ~/hermes-workspace
```

---

## Step 2：webapi Python 環境

```bash
cd ~/hermes-agent-fork
python3 -m venv venv

# 必須用 pyproject.toml（requirements.txt 不完整，缺 fastapi/uvicorn）
venv/bin/pip install -e ".[all]"
```

---

## Step 3：patch runtime_provider.py（必做）

**問題：** fork 的 custom provider 判斷條件不包含 `llamacpp` alias，routing 失敗，打 openrouter。

```bash
# 確認是否需要 patch
grep -n "llamacpp" ~/hermes-agent-fork/hermes_cli/runtime_provider.py | head -3
```

若沒有 `llamacpp`，執行 patch：

```bash
sed -i 's/elif requested_norm == "custom" and cfg_provider == "custom":/elif requested_norm in {"custom", "llamacpp", "ollama", "vllm", "lmstudio"} and cfg_provider in {"custom", "llamacpp", "ollama", "vllm", "lmstudio"}:/' \
  ~/hermes-agent-fork/hermes_cli/runtime_provider.py

grep -n "llamacpp" ~/hermes-agent-fork/hermes_cli/runtime_provider.py
```

> ⚠️ `hermes update` 會覆蓋此 patch，更新後需重新套用。

---

## Step 4：新增 completions.py（onboarding 必要）

⚠️ 不管是否已存在，直接覆蓋寫入（確保版本正確）：

**Step 4.1：新增/更新 completions.py**

```bash
cat > ~/hermes-agent-fork/webapi/routes/completions.py << 'EOF'
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import httpx

router = APIRouter()
UPSTREAM = "http://localhost:8000/v1/chat/completions"
API_KEY = "97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759"

@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(
                UPSTREAM,
                json=body,
                headers={"Authorization": f"Bearer {API_KEY}"}
            )
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except httpx.ReadTimeout:
        return JSONResponse(
            content={"error": "upstream timeout"},
            status_code=503
        )
    except Exception as e:
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )
EOF
```

**Step 4.2：在 app.py 加 router（冪等保護）**

```bash
if ! grep -q "completions_router" ~/hermes-agent-fork/webapi/app.py; then
  sed -i 's/from webapi.routes.config import router as config_router/from webapi.routes.config import router as config_router\nfrom webapi.routes.completions import router as completions_router/' \
    ~/hermes-agent-fork/webapi/app.py
  sed -i 's/app.include_router(config_router)/app.include_router(config_router)\n    app.include_router(completions_router)/' \
    ~/hermes-agent-fork/webapi/app.py
fi

grep -n "completions" ~/hermes-agent-fork/webapi/app.py
```

---

## Step 5：workspace 前端環境

```bash
cd ~/hermes-workspace

# .env 指向 webapi（不是直接打 Router）
cat > .env << 'EOF'
HERMES_API_URL=http://127.0.0.1:8642
EOF

pnpm install

# ⚠️ 必須執行，否則 esbuild/unrs-resolver 不完整
pnpm approve-builds
# → 按 a 全選 → Enter → y → Enter
```

---

## Step 6：初始化 .hermes 目錄（含清除殘留）

```bash
mkdir -p ~/.hermes/memories
touch ~/.hermes/memories/MEMORY.md

# ⚠️ 清除 ~/.hermes/.env 殘留的 OPENAI key
# setup 期間可能曾執行過 cat >> ~/.hermes/.env 加入 OPENAI_API_KEY/BASE_URL
# 這些 key 會干擾 env -u 的清除效果，必須清掉
cat ~/.hermes/.env 2>/dev/null
# 若有 OPENAI_API_KEY 或 OPENAI_BASE_URL，清除：
cat /dev/null > ~/.hermes/.env
echo "# CECLAW: 所有 provider 設定在 config.yaml，不在此處" > ~/.hermes/.env
```

---

## Step 7：建立 config.yaml（結構關鍵）

```bash
cat > ~/.hermes/config.yaml << 'EOF'
model:
  provider: custom
  default: ceclaw
  base_url: http://localhost:8000/v1
  api_key: 97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759
EOF
```

> ⚠️ **實際踩過的坑：** `provider` 放頂層 → `config.get("model")` 讀不到 → 打 openrouter。
>
> 錯誤格式（實際踩過）：
> ```yaml
> provider: llamacpp   ← 頂層，讀不到
> base_url: http://...
> model:
>   default: ceclaw
> ```
>
> 正確格式：`provider` / `base_url` / `api_key` 全在 `model:` 底下。

---

## Step 8：建立 start-hermes.sh

```bash
cat > ~/start-hermes.sh << 'SCRIPT'
#!/bin/bash
echo "=== 清除所有相關進程 ==="
python3 ~/ceclaw/scripts/rotate_hermes_memory.py
kill -9 $(lsof -ti:8642) 2>/dev/null
kill -9 $(lsof -ti:3000) 2>/dev/null
kill -9 $(lsof -ti:3001) 2>/dev/null
kill -9 $(lsof -ti:3002) 2>/dev/null
sleep 2

echo "=== 啟動 webapi ==="
# ⚠️ 必須從 fork 目錄啟動，否則 No module named webapi
cd ~/hermes-agent-fork
env -u OPENAI_API_KEY -u OPENAI_BASE_URL -u ANTHROPIC_API_KEY \
  HERMES_WEBAPI_PORT=8642 \
  HERMES_INFERENCE_PROVIDER=custom \
  HERMES_BASE_URL=http://localhost:8000/v1 \
  HERMES_API_KEY=97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759 \
  venv/bin/python -m webapi &
sleep 3

echo "=== 啟動 workspace ==="
cd ~/hermes-workspace
pnpm dev --host &
sleep 3

echo "=== 完成 ==="
ss -tlnp | grep -E "8642|3000"
SCRIPT
chmod +x ~/start-hermes.sh
```

**env 變數說明：**

| 變數 | 用途 |
|------|------|
| `env -u OPENAI_API_KEY/BASE_URL/ANTHROPIC_API_KEY` | 清除外部 key，防止打 openrouter |
| `HERMES_INFERENCE_PROVIDER=custom` | 強制走 custom branch |
| `HERMES_BASE_URL=http://localhost:8000/v1` | **session chat 打到 GB10 的關鍵**，讓 `resolve_runtime_provider()` 找到 CECLAW Router |
| `HERMES_API_KEY` | Router Bearer token |
| `HERMES_WEBAPI_PORT=8642` | webapi port（固定用 8642） |

---

## Step 9：CECLAW 專屬修改

### 9.1 P3 Hook（shared_bridge 自動提交）

檔案：`~/hermes-agent-fork/webapi/routes/chat.py`

搜尋 `_emit_post_run_events` 之後的 try block，加 Auto Demo 過濾：

```python
_AUTODEMO_KEYWORDS = ["系統負載", "磁碟使用狀況", "網路介面", "系統日誌", "python 進程"]
_is_autodemo = any(kw in user_content for kw in _AUTODEMO_KEYWORDS)

if (result.get("completed")
        and result.get("final_response")
        and result.get("api_calls", 0) > 1
        and not _is_autodemo):
    import importlib as _il  # importlib 避免 sys.path 快取問題
    if "/home/zoe_ai/ceclaw/router" not in __import__('sys').path:
        __import__('sys').path.insert(0, "/home/zoe_ai/ceclaw/router")
    _sb = _il.import_module("shared_bridge")
    _sb.write(
        content=result["final_response"],
        source="hermes", direction="h2o",
        user_id=session_id, priority="normal",
        metadata={"api_calls": result.get("api_calls")}
    )
```

**改完後重啟：** `bash ~/start-hermes.sh`

### 9.2 提交知識按鈕

檔案：`~/hermes-workspace/src/screens/chat/components/message-actions-bar.tsx`

搜尋 `MessageActionsBar` function，參考 Copy 按鈕的 TooltipProvider + HugeiconsIcon 風格加 Upload 按鈕：

```typescript
import { Upload01Icon } from '@hugeicons/core-free-icons'

const [submitted, setSubmitted] = useState(false)
const [submitting, setSubmitting] = useState(false)

const handleSubmitKnowledge = async () => {
  setSubmitting(true)
  await fetch('http://172.25.0.12:9000/api/knowledge-submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: text, source: 'hermes', user_id: 'kent', dept: 'engineering' })
  })
  setSubmitted(true)
  setSubmitting(false)
}

// align === 'start' 才顯示（assistant 訊息）
// 風格對齊：TooltipProvider > TooltipRoot > TooltipTrigger + HugeiconsIcon
```

**改完後：** Vite hot reload 自動生效，不需重啟。

---

## Step 10：驗收

```bash
bash ~/start-hermes.sh

# webapi 健康
curl -s http://localhost:8642/health
# → {"status":"ok","platform":"hermes-agent","service":"webapi"}

# completions proxy（onboarding 用）
curl -s -X POST http://localhost:8642/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"ceclaw","messages":[{"role":"user","content":"你是誰"}],"stream":false}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['choices'][0]['message']['content'][:50])"
# → 我是 CECLAW 企業 AI 助手

# 瀏覽器 http://172.25.0.12:3000
# → onboarding "Backend is reachable" → Continue → 主畫面
# → Chat 輸入「你是誰？」→ GPU 應有活動 → 回 CECLAW 身份
```

> ⚠️ Dashboard 顯示 `Model: Offline` 是**正常現象**，webapi 的 `/models` endpoint
> 沒有 CECLAW model 對應。Chat 仍可正常使用。

---

## 常見問題

| 問題 | 原因 | 解法 |
|------|------|------|
| `Connection refused` :8642 | webapi 沒起來 | `bash ~/start-hermes.sh` |
| `No module named webapi` | 不在 fork 目錄 | `cd ~/hermes-agent-fork` 再啟動 |
| 還是打 openrouter | runtime_provider.py 沒 patch | 重做 Step 3 |
| 還是打 openrouter | config.yaml 結構錯 | provider 放到 model: 底下 |
| 還是打 openrouter | ~/.hermes/.env 有殘留 OPENAI key | 清除 Step 6 |
| onboarding Continue 按不了 | completions.py 沒加 | 重做 Step 4 |
| `pnpm install` 後 esbuild 失敗 | 沒跑 approve-builds | `pnpm approve-builds` |
| GPU 沒動 | HERMES_BASE_URL 沒設 | 確認 start-hermes.sh 有 HERMES_BASE_URL |
| 兩個 webapi 進程（8642/8643 同時存在）| 舊進程沒清 | `kill -9 $(lsof -ti:8642)` 再重啟 |
| Model 顯示 Offline | /models 無 CECLAW 對應 | 正常，chat 仍可用 |
| context 超出 | session 歷史太長 | `bash ~/start-hermes.sh` 重啟 |
| MEMORY.md 太大 | rotate 未觸發 | `python3 ~/ceclaw/scripts/rotate_hermes_memory.py` |
| hermes update 後壞了 | patch 被覆蓋 | 重做 Step 3 |
| P3 hook 不觸發 | sys.path 快取問題 | 確認用 importlib，不用 from...import |
| chatCompletions missing | completions.py ReadTimeout 讓 route 壞掉 | `bash ~/start-hermes.sh` 重啟 |
| Auto Demo 卡住不動 | completions.py route 壞掉後 session 卡住 | `bash ~/start-hermes.sh` 重啟 |

---

## SearXNG 整合（待做，config key 待驗證）

```yaml
search:
  provider: searxng
  base_url: http://localhost:8888
```

> ⚠️ 此結構未驗證，需確認 Hermes 是否支援此 key。

---

## 版本歷史

| 版本 | 日期 | 變更 |
|------|------|------|
| v1.6 | 2026-04-06 | Step 4.1 completions.py 加 try/except ReadTimeout，timeout=180，防止 route 壞掉；移除「已存在跳過」邏輯，改為直接覆蓋 |
| v1.5 | 2026-04-06 | 補 ~/.hermes/.env 殘留清除（Step 6）、env 變數表格說明、P3 hook 加 sys.path 確認、常見問題補 .env 殘留 |
| v1.4 | 2026-04-06 | 補 session chat 到 GB10 路徑、兩個 webapi 進程陷阱、Model Offline 說明、Step 4 冪等保護 |
| v1.3 | 2026-04-06 | 補 completions.py、pnpm approve-builds、webapi 目錄要求 |
| v1.2 | 2026-04-06 | 補 runtime_provider.py patch、架構圖、.env 說明 |
| v1.1 | 2026-04-06 | 修正 repo 說明、pyproject.toml 安裝 |
| v1.0 | 2026-04-06 | 初版 |
