# CECLAW 專案交接文件 v4.6
## 給下一個對話的軟工 + 總工角色說明

**總工（Kent）**：35年工程經驗，ZOE AI Digital Twin 作者，做決策、設計審核
**軟工（下個對話）**：負責實作、測試、debug，遇困難問總工
**原則**：SOP-002 — 每次動手前說意圖，等 Kent 確認；每步完成後 commit
**督察**：GLM-5 Turbo（OpenRouter）— 品質審查，$0.12/次

---

## ⚠️ 本次對話重要進展摘要（v4.5 → v4.6）

### 已完成 ✅

1. **TUI 身份驗證通過** ✅
   - 根因：`api: "openai-completions"` 缺失（坑#69）
   - 加入後 `你是誰` → `我是 CECLAW 企業 AI 助手`

2. **sandbox-restore.sh v1.2** ✅ commit `74a9ec4`
   - 動態取 sandbox-id + token
   - 全部 6 步自動化
   - Step C 補齊所有必要欄位

3. **ceclaw-health-check.sh** ✅ commit `f59c20c`
   - 五層體檢：Router/SearXNG/GB10/OpenShell/sandbox 內部
   - Layer 5 自動 SSH 進 sandbox 驗證所有關鍵欄位

4. **網路層全面排查** ✅
   - openshell 實際網段：`172.19.0.0/16`（非 `172.20.0.0/16`）
   - UFW `deny (routed)` 改為 `allow routed`
   - INPUT chain 加入 `172.19.0.0/16` 規則

5. **3000 輪燒機 100%** ✅
   - Fast: 1500/1500，avg 636ms
   - Main: 1500/1500，avg 2624ms
   - SearXNG 30/30 檢查點 100%

6. **web search 根因分析** ✅
   - 根本問題：sandbox 所有 `web_fetch` → `EAI_AGAIN`（DNS 隔離）
   - 模型幻覺：天氣/股價/新聞全是假數據
   - 解法確認：**D 方案** — Router 加 `/v1/fetch` proxy，SearXNG 作為唯一外部出口

7. **燒機品質分析** ✅
   - 簡體字率：0.87%（26/3000），`what is python` 是主要來源
   - 日期幻覺：`what day is today` 85% 給假日期 → 需加 system prompt

### ⚠️ 當前未完成（明天 P0）

**D 方案：Router 加 `/v1/fetch` proxy**
- sandbox 只能連 `host.openshell.internal:8000`
- 所有外部查詢必須走 Router → SearXNG
- 不完成 = Skills 所有需要外網的功能全幻覺 = POC 信任度歸零

---

## 🚨 明天第一優先：D 方案實作

### 要加的（不動現有功能）

**router/main.py 加 `/v1/fetch` endpoint：**
```python
@app.get("/v1/fetch")
async def proxy_fetch(url: str):
    """代抓外部 URL，讓 sandbox 透過 Router 存取外部內容"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=15)
        return {"content": resp.text, "url": url, "status": resp.status_code}
```

**sandbox TOOLS.md 告訴模型：**
```markdown
## Web Search
- 使用 searxng_search 查詢即時資訊
- 需要讀取網頁內容時，使用 web_fetch 工具，URL 會透過 Router proxy 存取

## 重要
- 無法取得即時資訊時，必須告知用戶，嚴禁編造數據
```

**proxy.py CECLAW_SYSTEM_PROMPT 加一行（修日期幻覺）：**
```python
"你不知道今天的日期和時間，若被問及請直接告知無法查詢即時資訊，嚴禁編造日期或數據。"
```

### 估計時間：1 小時

---

## 當前 sandbox 狀態

### sandbox 基本資訊
- name: `ceclaw-agent`
- ID: `2e04e3db-259d-4820-ae39-af385c5d0ce1`（⚠️ 重建後會變）
- image: `ghcr.io/kentgeeng/ceclaw-sandbox:latest`
- openclaw: **2026.3.11**（pop-os 是 2026.3.13）
- 取得最新 ID：`ps aux | grep ssh-proxy | grep -o "sandbox-id [a-z0-9-]*" | head -1 | awk '{print $2}'`

### 當前 openclaw.json 完整結構（已確認可工作）
```json
{
    "models": {
        "providers": {
            "local": {
                "baseUrl": "http://host.openshell.internal:8000/v1",
                "apiKey": "ceclaw-local-key",
                "api": "openai-completions",
                "models": [{"id": "minimax", "name": "minimax", "contextWindow": 32768, "maxTokens": 4096}]
            }
        }
    },
    "gateway": {"mode": "local"},
    "agents": {
        "defaults": {
            "compaction": {"mode": "safeguard", "reserveTokens": 8000},
            "model": {"primary": "local/minimax"}
        }
    },
    "tools": {
        "web": {
            "search": {"enabled": true},
            "fetch": {"enabled": true}
        }
    },
    "plugins": {
        "entries": {
            "searxng-search": {"enabled": true, "config": {"baseUrl": "http://host.openshell.internal:8000"}},
            "ceclaw": {}
        }
    }
}
```

### auth-profiles.json（必須存在）
```
/sandbox/.openclaw/agents/main/agent/auth-profiles.json
{"local": {"apiKey": "ceclaw-local-key"}}
```

---

## Sandbox 重建後必做（已自動化）

```bash
# Step 1: 先連進 sandbox（取得 token）
openshell sandbox connect ceclaw-agent

# Step 2: 在 pop-os 另一個 terminal 跑
bash ~/ceclaw/sandbox-restore.sh
```

### sandbox-restore.sh 會自動做：
- 動態取 sandbox-id + token
- Build SearXNG plugin + scp 進 sandbox
- Step A-F 全部自動執行
- 啟動 gateway

---

## 系統環境

### pop-os
- IP: `192.168.1.210`，User: `zoe_ai`
- openclaw: **2026.3.13** (pop-os 側 npm install -g)
- Router: `http://localhost:8000`，systemd 自啟

### GB10
- IP: `192.168.1.91`，SSH: `ssh gb10`
- 模型: Qwen3.5-122B-A10B Q4_K_M
- `--ctx-size 65536 --parallel 2`（#59）

### iptables（今日新增，已 save）
```bash
# 172.19.0.0/16 = openshell container 實際網段
sudo iptables -I FORWARD -s 172.19.0.0/16 -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -I INPUT -s 172.19.0.0/16 -p tcp --dport 8000 -j ACCEPT
sudo iptables -t nat -A POSTROUTING -s 172.19.0.0/16 -d 172.17.0.1 -j MASQUERADE
sudo ufw default allow routed
```

---

## 全局進度表

| # | 項目 | Phase | 狀態 | Commit |
|---|------|-------|------|--------|
| 1-35 | 歷史完成項 | P1~P5 | ✅ | — |
| 37 | 503 fallback | P1 | ✅ | c894fc6 |
| 38 | SearXNG 整合 | P1 | ✅ | 328d491 |
| 39 | Qwen2.5-72B 評估 | P1 | ⬜ | — |
| 40 | reasoning 殘留 | P1 | ✗ 暫擱 | — |
| 51 | fast path ministral-3:14b | P1 | ✅ | 2753e28 |
| 59 | ctx-size 65536 + parallel 2 | P1 | ✅ | 9a0fac1 |
| 60 | fallback warning | P1 | ⬜ | — |
| **61** | **台積電/NVIDIA股價漏答** | P1 | **⬜ D方案解決** | — |
| 62 | gb10 retry 機制 | P1 | ⬜ | — |
| 63 | fast 路徑繁體強化 | P1 | ✅ | 512177f |
| 64 | tools 覆寫根因修復 | P1 | ✅ | b4e7ad3 |
| 65 | burnin Layer 2A 重構 | P1 | ✅ | — |
| 66 | SearXNG 穩定性盤查 | P1 | ✅ | — |
| 66b | 台灣本土模型補文件 | P1 | ⬜ | — |
| openclaw | 升級 2026.3.13（pop-os）| — | ✅ | — |
| 68 | sandbox-restore.sh v1.2 | P8 | ✅ | 74a9ec4 |
| 69 | ceclaw-health-check.sh | P8 | ✅ | f59c20c |
| **70** | **D方案：Router fetch proxy** | P1 | **⬜ P0明天** | — |
| 71 | 3000輪燒機 | P1 | ✅ | — |
| 72 | A/B sandbox image 2026.3.13 | P1 | ⬜ | — |
| 41 | NemoClaw drop-in 驗證 | P6 | ⬜ | — |
| 42-43 | Skill 相容性測試 | P7 | ⬜ | — |
| 44-48 | UX 升級 | P8 | ⬜ | — |
| 67 | Plugin OTA + ceclaw update | P8 | ⬜ | — |

**完成：56 ✅ | 待做：14 ⬜ | 暫擱：1 ✗**

---

## 坑記錄（今日新增）

**坑#68（關鍵）**: `openshell gateway start` 在 gateway stopped 時 = 重建整個 K3s = sandbox 消失
- 正確做法：`docker start <container_id>`

**坑#69（關鍵）**: openclaw.json 必須有 `api: "openai-completions"`
- 缺少 → TUI auth 失敗，顯示 `local/minimax` 但推論不通

**坑#70**: sandbox 內 `ALL_PROXY` 環境變數
- unset http_proxy 不夠，`ALL_PROXY` 還在
- curl 測試必須用 `--noproxy "*"`

**坑#71**: openshell 實際網段 `172.19.0.0/16`，不是 SOP 說的 `172.20.0.0/16`

**坑#72**: UFW `deny (routed)` 封鎖所有路由轉發
- 解法：`sudo ufw default allow routed`

**坑#73**: web_fetch 在 sandbox 全部 EAI_AGAIN
- sandbox DNS 隔離，只有 `host.openshell.internal` 可用
- 模型用幻覺填充 → 不可信

**坑#74**: openclaw 2026.3.11 plugin tool name 衝突
- plugin 叫 `web_search` → 跟內建衝突被擋
- plugin 叫 `searxng_search` → 模型不會自動呼叫
- 解法：D 方案（Router proxy），讓內建 `web_search` 走 SearXNG

**坑#75**: sandbox policy dynamic rule 只記錄 curl，不記錄 node
- 需要重建 sandbox 讓 policy 重新生成含 node 的規則

---

## 台灣本土模型評估（未入文件，需記住）

| 模型 | 淘汰原因 |
|------|---------|
| taiwanllm-7b | 指令遵從差 |
| taiwanllm-13b | System prompt 洩漏 |
| TAIDE-8b (ryan4559) | 冷啟動 2s+，指令遵從差 |
| llama-3-taiwan-8b (cwchang) | 直接說「我是 Taiwan-LLM」|

待補進 #66b。

---

## Debug SOP

### TUI auth 失敗
```
症狀：No API key found for provider "local"
1. 確認 /sandbox/.openclaw/agents/main/agent/auth-profiles.json 存在
2. 確認 openclaw.json models.providers.local.api = "openai-completions"
3. 重啟 gateway
```

### web search 全幻覺
```
症狀：模型給了股價/天氣但 log 無 web_fetch 成功記錄
根因：sandbox 所有外部 DNS = EAI_AGAIN
解法：D 方案完成前暫時無法解決
臨時：system prompt 加「嚴禁編造數據」
```

### sandbox 連 Router 失敗
```
症狀：curl http://host.openshell.internal:8000 timeout
1. 確認 UFW routed = allow
2. 確認 iptables 有 172.19.0.0/16 規則
3. sandbox 用 --noproxy "*" 測試
```

---

## SOP-002

每次動手前：【要改什麼】/【為什麼】/【改完 Kent 會看到什麼】

每步完成後：
```
⚠️ 記得 commit：git add -A && git commit -m "..."
```

---

*CECLAW — Secure local AI agents, your inference, your rules.*
*總工: Kent | 軟工: 下個對話 Claude | 督察: GLM-5 Turbo*
*文件版本: v4.6 | 日期: 2026-03-25*
*最新狀態: TUI ✅ | web_fetch 全幻覺 ⚠️ | D方案 P0 明天 | 最新commit: 3f5a3bc*
