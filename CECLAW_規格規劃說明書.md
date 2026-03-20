# CECLAW 規格規劃說明書
## ColdElectric Claw — 本地優先 AI Agent 推論路由系統

**版本**: 0.3.0  
**作者**: Kent (總工)  
**日期**: 2026-03-20  
**狀態**: Alpha — P1 + P2 + B方案 + P3 CoreDNS 完成

---

## 1. 專案背景

### 1.1 起源

NVIDIA 在 GTC 2026 發布 NemoClaw + OpenShell，定位為企業 AI Agent 安全執行框架。其核心設計假設是：**推論走 NVIDIA Cloud**（integrate.api.nvidia.com）。

ColdElectric 擁有自建 GPU 推論基礎設施（GB10 機器，MiniMax-M2.5），有以下需求：
- 資料不出內網
- 推論成本歸零（自有 GPU）
- 不依賴 NVIDIA Cloud 服務可用性

CECLAW（ColdElectric Claw）因此誕生：**在 OpenShell 安全框架內，把推論流量從 NVIDIA Cloud 重定向到本地 GPU**。

### 1.2 為什麼難

```
NemoClaw 設計方向：
  Agent → OpenShell Proxy → NVIDIA Cloud

CECLAW 要做的：
  Agent → OpenShell Proxy → CECLAW Router → 本地 GB10
                              ↓ fallback
                           雲端（Groq/Anthropic/OpenAI）
```

NV 的設計有三道關卡逆著我們走：

| 關卡 | NV 設計意圖 | CECLAW 解法 |
|------|------------|------------|
| `inference.local` DNS | 鎖死指向 NVIDIA Cloud | 改用 `host.openshell.internal` |
| OpenShell Proxy | deny-all，只放行 NV 端點 | network_policies + allowed_ips + binaries |
| K3s 跨網段 | sandbox 與 host 網路隔離 | iptables FORWARD + MASQUERADE |

---

## 2. 與 NemoClaw 的比較

### 2.1 相同之處

| 項目 | NemoClaw | CECLAW |
|------|---------|--------|
| 執行環境 | OpenShell sandbox | OpenShell sandbox |
| 隔離機制 | K3s + Linux namespace | K3s + Linux namespace |
| Policy 格式 | YAML network_policies | YAML network_policies（相同 schema）|
| Agent 框架 | openclaw | openclaw |
| Plugin 格式 | TypeScript v1 | TypeScript v1（相同介面）|
| API 格式 | OpenAI compatible | OpenAI compatible |
| 安全模型 | deny-by-default | deny-by-default |

### 2.2 差異之處

| 項目 | NemoClaw | CECLAW |
|------|---------|--------|
| **推論目標** | NVIDIA Cloud | 本地 GB10（優先）+ 雲端（備援）|
| **資料流向** | 出內網 | 留在內網 |
| **推論成本** | 按 token 計費 | 本地 GPU 免費 |
| **隱私等級** | 資料送 NV 伺服器 | 資料不出內網 |
| **Router 層** | 無（直連 NV API）| CECLAW Router（本地 FastAPI）|
| **降級策略** | NV Cloud 掛了就掛 | GB10 掛 → Groq → Anthropic → OpenAI → NV |
| **模型選擇** | NV 提供的模型 | 任意 GGUF 模型 |
| **inference.local** | 鎖定 NV Cloud | 不使用，改用 host.openshell.internal |
| **部署複雜度** | 低（NV 全包）| 高（需自建 Router + iptables）|

### 2.3 架構對比圖

```
╔══════════════════════════════════════════════════════════════╗
║  NemoClaw 架構                                               ║
╠══════════════════════════════════════════════════════════════╣
║  ┌─────────────────────────────────────┐                    ║
║  │  OpenShell Sandbox (K3s pod)        │                    ║
║  │  ┌──────────┐                       │                    ║
║  │  │ openclaw │                       │                    ║
║  │  └────┬─────┘                       │                    ║
║  │       │ inference.local             │                    ║
║  │  ┌────▼──────────────────────┐      │                    ║
║  │  │  OpenShell Proxy (3128)   │      │                    ║
║  │  └────────────┬──────────────┘      │                    ║
║  └───────────────┼─────────────────────┘                    ║
║                  ▼                                           ║
║         ┌────────────────┐                                   ║
║         │  NVIDIA Cloud  │                                   ║
║         └────────────────┘                                   ║
╚══════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════╗
║  CECLAW 架構                                                 ║
╠══════════════════════════════════════════════════════════════╣
║  ┌─────────────────────────────────────┐                    ║
║  │  OpenShell Sandbox (K3s pod)        │                    ║
║  │  10.42.0.x                          │                    ║
║  │  ┌──────────────────────────┐       │                    ║
║  │  │ openclaw + CECLAW plugin │       │                    ║
║  │  └────────────┬─────────────┘       │                    ║
║  │               │ http://             │                    ║
║  │               │ host.openshell      │                    ║
║  │               │ .internal:8000      │                    ║
║  │  ┌────────────▼──────────────┐      │                    ║
║  │  │  OpenShell Proxy (3128)   │      │                    ║
║  │  │  [policy: ceclaw_router   │      │                    ║
║  │  │   allowed_ips: 172.17.0.1]│      │                    ║
║  │  └────────────┬──────────────┘      │                    ║
║  └───────────────┼─────────────────────┘                    ║
║                  │ iptables FORWARD                          ║
║                  │ 172.20.x → 172.17.0.1                    ║
║  ┌───────────────▼─────────────────────┐                    ║
║  │  CECLAW Inference Router :8000      │                    ║
║  │  (FastAPI, systemd, pop-os host)    │                    ║
║  └──────────┬──────────────────────────┘                    ║
║             │                                               ║
║     ┌───────┴────────────────────┐                         ║
║     │ local-first                │ fallback                 ║
║     ▼                            ▼                         ║
║  ┌──────────────┐    ┌─────────────────────────────┐       ║
║  │  GB10 :8001  │    │  Cloud Fallback              │       ║
║  │  MiniMax     │    │  Groq → Anthropic            │       ║
║  │  M2.5 GGUF   │    │  → OpenAI → NVIDIA          │       ║
║  └──────────────┘    └─────────────────────────────┘       ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 3. 系統架構

### 3.1 元件總覽

```
┌─────────────────────────────────────────────────────────────┐
│                    CECLAW 系統元件                           │
├─────────────────────────────────────────────────────────────┤
│  ① CECLAW Inference Router (ceclaw/router/)                │
│     - FastAPI + uvicorn，監聽 0.0.0.0:8000                 │
│     - 本地優先 + 雲端降級，30s 健康檢查，SIGHUP 熱重載     │
│     - systemd 管理，開機自啟                                │
│                                                             │
│  ② CECLAW Plugin (ceclaw/plugin/)                          │
│     - TypeScript, openclaw plugin v1                        │
│     - 設定 local provider → Router                          │
│     - ⚠️ registerCommand 暫時 disabled（待修）             │
│                                                             │
│  ③ Sandbox Image (ghcr.io/kentgeeng/ceclaw-sandbox)        │
│     - 基於 NV openclaw sandbox                              │
│     - B方案 5 個 bug 已全部修正                             │
│     - ceclaw-start.sh 自動設定 openclaw.json + 啟動 gateway │
│                                                             │
│  ④ OpenShell Policy (ceclaw/config/ceclaw-policy.yaml)     │
│     - network_policies + allowed_ips + binaries             │
│     - 放行 host.openshell.internal:8000                     │
│                                                             │
│  ⑤ GB10 推論機                                             │
│     - llama.cpp llama-server，MiniMax-M2.5-UD-Q3_K_XL      │
│     - 192.168.1.91:8001                                     │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Router API 端點

```
CECLAW Inference Router
├── GET  /ceclaw/status          健康狀態 + 後端清單
├── POST /ceclaw/reload          熱重載設定檔
├── GET  /v1/models              列出可用模型（OpenAI 格式）
├── POST /v1/chat/completions    推論（chat，proxy 到後端）
└── POST /v1/completions         推論（completion，proxy 到後端）
```

### 3.3 推論流程

```
Request 進來
     │
     ▼
是否有健康的本地後端？
     │
   Yes ──────────────────────► 送到 GB10 :8001
     │                              │
    No                         成功 ──► 回應 Client
     │                              │
     ▼                           失敗/超時（60s）
雲端降級序列：                       │
  1. Groq (GROQ_API_KEY)   ◄────────┘
  2. Anthropic (ANTHROPIC_API_KEY)
  3. OpenAI (OPENAI_API_KEY)
  4. NVIDIA (NVIDIA_API_KEY)
     │
  有 key → 送出
  沒 key → 跳下一個
     │
     ▼
全部失敗 → 503 Service Unavailable
```

---

## 4. 已完成功能

### 4.1 功能清單

| 功能 | 狀態 | 說明 |
|------|------|------|
| Inference Router | ✅ | FastAPI，systemd，開機自啟 |
| 本地優先路由 | ✅ | local-first strategy |
| 雲端降級 | ✅ | 4 個雲端 provider，按序嘗試 |
| 後端健康檢查 | ✅ | 啟動 + 每 30 秒 |
| SIGHUP 熱重載 | ✅ | 不重啟更新設定 |
| 零硬編碼 | ✅ | 全部讀 ceclaw.yaml + 環境變數 |
| OpenShell Policy | ✅ | 正確格式，TUI Approve |
| iptables 穿透 | ✅ | 持久化 |
| Sandbox Image | ✅ | 推上 ghcr.io public |
| 端到端驗證 | ✅ | sandbox → Router → GB10 → 回應 |
| Plugin 整合測試 | ✅ | openclaw TUI local/minimax 對話正常 |
| openclaw TUI 對話 | ✅ | MiniMax 回應正常 |
| B方案 rebuild image | ✅ | 5 個問題全部修正，commit: 2dfab79 |
| timeout_local_ms 60000 | ✅ | 解決冷啟動超時，commit: 2dfab79 |
| CoreDNS 持久化 | ✅ | ceclaw-coredns.service，commit: 1bffd63 |
| ceclaw CLI | ⬜ | P3 待開發 |
| 串流回應 | ⬜ | P5 待完整測試 |

### 4.2 驗證記錄

```
2026-03-19 端到端驗證：
  sandbox → Router → GB10 推論：HTTP 200，MiniMax 回應 ✅

2026-03-20 燒機：
  200 輪 sandbox curl，200/200 HTTP 200 ✅

2026-03-20 Plugin 整合測試：
  openclaw tui，agent model: local/minimax
  中文對話正常，Router log gb10-llama → 200 ✅
  commit: 6ebea02

2026-03-20 B方案驗證：
  重建 sandbox，自動完成設定，不需要手動 Step 12
  TUI 對話正常，Router log gb10-llama → 200 ✅
  commit: 2dfab79
```

---

## 5. 設定檔規格

### 5.1 ceclaw.yaml 完整規格

```yaml
version: 1                        # 必填，目前只有 1

router:
  listen_host: "0.0.0.0"
  listen_port: 8000
  tls: false
  reload_on_sighup: true

inference:
  strategy: local-first           # local-first | cloud-only | local-only
  timeout_local_ms: 60000         # 本地後端超時（毫秒），60000 適合 MiniMax 冷啟動

  local:
    backends:
      - name: gb10-llama
        type: llama.cpp           # llama.cpp | ollama | vllm
        base_url: http://192.168.1.91:8001/v1
        models:
          - id: minimax
            alias: default
            context_window: 32768

  cloud_fallback:
    enabled: true
    priority:
      - provider: groq
        env_key: GROQ_API_KEY
        models: [llama-3.3-70b-versatile]
      - provider: anthropic
        env_key: ANTHROPIC_API_KEY
        models: [claude-sonnet-4-6]
      - provider: openai
        env_key: OPENAI_API_KEY
        models: [gpt-4.1]
      - provider: nvidia
        env_key: NVIDIA_API_KEY
        models: [nvidia/nemotron-3-super-120b-a12b]
```

### 5.2 ceclaw-policy.yaml 完整規格

```yaml
version: 1
network_policies:
  ceclaw_router:
    endpoints:
      - host: host.openshell.internal
        port: 8000
        access: full
        allowed_ips:
          - 172.17.0.1           # 必填，對應 DNS 解析結果
    binaries:                    # 必填，指定哪些 binary 可以用此規則
      - path: /usr/bin/curl
      - path: /usr/bin/node
      - path: /usr/local/bin/openclaw
```

---

## 6. 路線圖

### Phase 1 — 核心通路（✅ 完成）
- Inference Router
- OpenShell sandbox 網路穿透
- 端到端推論驗證
- 燒機 200 輪

### Phase 2 — Plugin 整合（✅ 完成）
- Plugin 整合測試 ✅
- openclaw TUI 對話測試 ✅
- B方案 rebuild image ✅（修 5 個已知問題，commit: 2dfab79）

### Phase 3 — 易用性（部分完成）
- CoreDNS 持久化 ✅（commit: 1bffd63）
- `ceclaw` CLI（`onboard`/`connect`/`status`）⬜
- 自動 Approve policy（不需要 TUI）⬜

### Phase 4 — 多後端
- Ollama 後端支援
- vLLM 後端支援
- SGLang 後端支援

### Phase 5 — 企業功能
- 串流回應完整支援
- 雲端降級完整測試
- 使用量統計 / 成本計算
- 多租戶支援
- `registerCommand` bug 修正

---

## 7. 已知限制

| 限制 | 說明 | 計劃解法 |
|------|------|---------|
| TUI 手動 Approve | 新 sandbox 需人工操作一次 | Phase 3 自動化 |
| GB10 手動啟動 | llama-server 未設自啟 | 加 systemd service 到 GB10 |
| registerCommand 不可用 | TypeError 待查 | Phase 5 修正 |
| undici proxy 行為 | experimental，no_proxy 不可靠 | 保持走 proxy 路徑，見坑#10 |

---

## 8. 技術債

1. **TUI Approve** — 每次新建 sandbox 需要手動 Approve pending rules
2. **GB10 自啟** — llama-server 需手動 SSH 啟動
3. **registerCommand TypeError** — `Cannot read properties of undefined (reading 'trim')`
4. **undici EnvHttpProxyAgent** — experimental，行為不穩定，長期應關注 openclaw 更新

---

## 9. 競爭定位

```
                    本地推論 ◄─────────────────► 雲端推論
  CECLAW ●──────────────┘           NemoClaw ───────┘
  (本地優先 + 雲端備援)              (雲端優先)
  高安全性 / 低成本                  低安全性 / 高成本
```

---

## 10. 參考資料

- OpenShell docs: https://docs.nvidia.com/openshell/latest/
- OpenShell GitHub: https://github.com/NVIDIA/OpenShell
- NemoClaw GitHub: https://github.com/NVIDIA/NemoClaw
- CECLAW sandbox image: ghcr.io/kentgeeng/ceclaw-sandbox:latest
- CECLAW repo: github.com/kentgeeng/ceclaw
- llama.cpp: https://github.com/ggerganov/llama.cpp

---

*CECLAW — Secure local AI agents, your inference, your rules.*  
*總工: Kent | 版本: 0.3.0 | 日期: 2026-03-20*
