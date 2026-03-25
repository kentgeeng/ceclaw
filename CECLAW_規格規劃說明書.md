# CECLAW 規格規劃說明書 v0.4.4
**更新日期：2026-03-26**

---

## 系統架構

```
┌─────────────────────────────────────────┐
│  Sandbox (K3s Container)                │
│  ceclaw-agent / ceclaw-agent-v2         │
│                                         │
│  OpenClaw Gateway (ws://127.0.0.1:18789)│
│  └─ ceclaw plugin (身份注入)             │
│  └─ web_fetch (外網抓取)                 │
│                                         │
│  Proxy: 10.200.0.1:3128 (K3s)          │
└──────────────────┬──────────────────────┘
                   │ http://host.openshell.internal:8000
                   ▼
┌─────────────────────────────────────────┐
│  CECLAW Router (pop-os:8000)            │
│  FastAPI + uvicorn                      │
│                                         │
│  proxy.py                               │
│  └─ inject CECLAW system prompt         │
│  └─ 日期幻覺禁令                         │
│                                         │
│  Backends:                              │
│  ├─ ollama-fast (minimax, 11434) ✅     │
│  ├─ gb10-llama (192.168.1.91:8001) ✅  │
│  └─ cloud fallback (無 API key)         │
└─────────────────────────────────────────┘
```

---

## 核心功能規格

### 1. 身份注入
- **位置**：`~/ceclaw/router/proxy.py`
- **方式**：攔截所有 `/v1/chat/completions` 請求，在 system prompt 末尾加入 CECLAW 身份
- **禁止詞**：Qwen、通義千問、阿里巴巴 等（模型品牌隱藏）
- **日期禁令**：不知道今天日期，禁止編造

### 2. web_fetch
- **啟用**：`openclaw.json` 的 `tools.web.fetch.enabled: true`
- **路由**：sandbox → K3s proxy → 外網
- **限制**：每個新 domain 需在 openshell term approve 一次
- **已知問題**：模型（ministral-3:14b）不主動呼叫，需要 TOOLS.md 強制指示

### 3. Workspace 同步
- **來源**：`~/ceclaw/config/`（git 管理）
- **目的地**：`/sandbox/.openclaw/workspace/`
- **觸發**：`sandbox-restore.sh` Step 7
- **包含**：SOUL.md, TOOLS.md, AGENTS.md, USER.md, HEARTBEAT.md

### 4. 多 Sandbox 支援
- **ceclaw-agent**：主要測試 sandbox
- **ceclaw-agent-v2**：第二個測試 sandbox
- **Restore**：透過 `SANDBOX_ID` 環境變數指定目標

---

## 技術規格

### Router
- Framework: FastAPI
- Runtime: uvicorn（非 tcp_mux）
- Port: 8000
- 模型路由: smart-routing（ollama-fast 優先）
- System prompt size: ~4KB（minimax）

### OpenClaw
- 版本: 2026.3.11 (29dc654)
- Gateway: WebSocket ws://127.0.0.1:18789
- 模型: local/minimax（ministral-3:14b via ollama）
- Context window: 33k tokens

### Sandbox Image
- `ghcr.io/kentgeeng/ceclaw-sandbox:latest`
- 包含：ceclaw plugin at `/opt/ceclaw`
- OS: Linux 6.12.10（x64）
- Node: v22.22.1

---

## 網路規格

| 連線 | 路徑 | 狀態 |
|------|------|------|
| Sandbox → Router | host.openshell.internal:8000 via K3s proxy | ✅ |
| Sandbox → 外網 HTTPS | K3s proxy 10.200.0.1:3128 | ✅（需 approve）|
| Sandbox → 外網 HTTP | K3s proxy | ✅（需 approve）|
| Router → ollama | localhost:11434 | ✅ |
| Router → GB10 | 192.168.1.91:8001 | ✅ |

---

## POC 進度

### 完成
- [x] 基礎架構部署
- [x] 身份注入
- [x] Restore 自動化腳本 v3.4
- [x] 七層健康檢查
- [x] Workspace 同步
- [x] 多 sandbox 支援
- [x] 日期幻覺修復
- [x] 外網 web_fetch（需 approve）

### 進行中
- [ ] web_fetch 模型主動呼叫（P0）
- [ ] TOOLS.md 優化

### 待做
- [ ] POC 多人測試（Step 2：2 人同時）
- [ ] searxng plugin（等 openclaw 修復坑#77）
- [ ] CECLaw policy 白名單 one-click 生成
- [ ] GB10 onclaw 升級目標

---

## 已知技術限制

1. **K3s proxy 限制**：sandbox 內只有 node binary 可以走 K3s proxy 連外網，python3 urllib 被 403
2. **ministral-3 tool use**：工具呼叫能力弱，需要 TOOLS.md 明確指示
3. **openclaw 2026.3.11 坑#77**：extensions path bug，searxng 無法使用
4. **tcp_mux 放棄**：30s timeout 截斷大型 system prompt

---

## 版本歷史

| 版本 | 日期 | 主要變更 |
|------|------|---------|
| v0.4.4 | 2026-03-26 | sandbox-restore v3.4，七層健康檢查，workspace 同步，多坑修復 |
| v0.4.3 | 2026-03-25 | D方案架構，網路拓撲，燒機結果 |
| v0.4.2 | 2026-03-24 | POC 架構確認 |
