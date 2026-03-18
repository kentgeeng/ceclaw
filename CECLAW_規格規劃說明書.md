# CECLAW 規格規劃說明書
## ColdElectric Claw — 本地優先 AI Agent 推論路由系統

**版本**: 0.1.0  
**作者**: Kent (總工)  
**日期**: 2026-03-19  
**狀態**: Alpha — 端到端驗證通過，Plugin 整合進行中

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
║                                                              ║
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
║                  │ HTTPS                                     ║
║                  ▼                                           ║
║         ┌────────────────┐                                   ║
║         │  NVIDIA Cloud  │                                   ║
║         │  (nemotron 等) │                                   ║
║         └────────────────┘                                   ║
╚══════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════╗
║  CECLAW 架構                                                 ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
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
║  │                                     │                    ║
║  │  Strategy: local-first              │                    ║
║  │  ┌─────────────┐ ┌───────────────┐  │                    ║
║  │  │ 健康檢查    │ │ 熱重載 SIGHUP │  │                    ║
║  │  └─────────────┘ └───────────────┘  │                    ║
║  └──────────┬──────────────────────────┘                    ║
║             │                                               ║
║     ┌───────┴────────────────────┐                         ║
║     │ local-first                │ fallback                 ║
║     ▼                            ▼                         ║
║  ┌──────────────┐    ┌─────────────────────────────┐       ║
║  │  GB10 :8001  │    │  Cloud Fallback              │       ║
║  │  MiniMax     │    │  Groq → Anthropic            │       ║
║  │  M2.5 GGUF   │    │  → OpenAI → NVIDIA          │       ║
║  │  llama.cpp   │    └─────────────────────────────┘       ║
║  └──────────────┘                                           ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 3. 系統架構

### 3.1 元件總覽

```
┌─────────────────────────────────────────────────────────────┐
│                    CECLAW 系統元件                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ① CECLAW Inference Router (ceclaw/router/)                │
│     - FastAPI + uvicorn                                     │
│     - 監聽 0.0.0.0:8000                                    │
│     - 本地優先 + 雲端降級                                   │
│     - 後端健康檢查 (30s interval)                           │
│     - SIGHUP 熱重載                                         │
│     - systemd 管理，開機自啟                                │
│                                                             │
│  ② CECLAW Plugin (ceclaw/plugin/)                          │
│     - TypeScript, openclaw plugin v1                        │
│     - Banner: CECLAW registered                             │
│     - 設定 local provider → Router                          │
│     - 內建於 sandbox image                                  │
│                                                             │
│  ③ Sandbox Image (ghcr.io/kentgeeng/ceclaw-sandbox)        │
│     - 基於 NV openclaw sandbox                              │
│     - 包含 CECLAW plugin                                    │
│     - ceclaw-start.sh 啟動腳本                              │
│                                                             │
│  ④ OpenShell Policy (ceclaw/config/ceclaw-policy.yaml)     │
│     - network_policies + allowed_ips + binaries             │
│     - 放行 host.openshell.internal:8000                     │
│                                                             │
│  ⑤ GB10 推論機                                             │
│     - llama.cpp llama-server                                │
│     - MiniMax-M2.5-UD-Q3_K_XL                              │
│     - 192.168.1.91:8001                                     │
│                                                             │
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
     ▼                           失敗/超時
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

### 3.4 網路拓撲

```
IP 位址分配：
┌────────────────────────────────────────────┐
│ pop-os (主機)                               │
│   eth0:    192.168.1.210 (LAN)             │
│   docker0: 172.17.0.1   (Docker bridge)   │
│   br-xxx:  172.18.0.1   (OpenShell bridge)│
│   br-xxx:  172.20.0.1   (K3s bridge)      │
├────────────────────────────────────────────┤
│ K3s container (OpenShell)                  │
│   IP: 172.20.0.2                           │
│   內含 K3s cluster:                        │
│     node IP:  10.42.0.1                   │
│     pod CIDR: 10.42.0.0/24               │
├────────────────────────────────────────────┤
│ ceclaw-agent pod                           │
│   IP: 10.42.0.x                           │
│   gateway: 10.200.0.1 (OpenShell proxy)   │
├────────────────────────────────────────────┤
│ GB10 推論機                                │
│   IP: 192.168.1.91                        │
│   llama-server: :8001                     │
└────────────────────────────────────────────┘

關鍵路由：
  sandbox (10.42.0.x)
    → proxy (10.200.0.1:3128)
    → [policy 放行]
    → iptables FORWARD
    → host (172.17.0.1:8000)  ← Router 在這裡
    → GB10 (192.168.1.91:8001)
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
| CECLAW Plugin | 🔄 | 已編譯，整合測試進行中 |
| openclaw TUI 對話 | ⬜ | 待測試 |
| ceclaw CLI | ⬜ | 待開發 |
| 串流回應 | ⬜ | 待完整測試 |

### 4.2 驗證記錄

```
2026-03-19 驗證結果：

sandbox → Router → GB10 推論測試：
  Request:  POST /v1/chat/completions
            {"model":"minimax","messages":[{"role":"user","content":"hi"}],"max_tokens":20}
  
  Response: HTTP 200
            {"choices":[{"finish_reason":"length","index":0,
              "message":{"role":"assistant",
              "content":"","reasoning_content":"The user has simply said hi..."}}],
             "model":"minimax","usage":{"completion_tokens":20,"prompt_tokens":39}}
  
  延遲: ~800ms (首 token)
  狀態: ✅ PASS
```

---

## 5. 設定檔規格

### 5.1 ceclaw.yaml 完整規格

```yaml
version: 1                        # 必填，目前只有 1

router:
  listen_host: "0.0.0.0"         # Router 監聽位址
  listen_port: 8000               # Router 監聽 port
  tls: false                      # TLS（目前不支援）
  reload_on_sighup: true          # SIGHUP 熱重載

inference:
  strategy: local-first           # local-first | cloud-only | local-only
  timeout_local_ms: 30000         # 本地後端超時（毫秒）

  local:
    backends:
      - name: gb10-llama          # 後端名稱（任意）
        type: llama.cpp           # 後端類型：llama.cpp | ollama | vllm
        base_url: http://192.168.1.91:8001/v1
        models:
          - id: minimax           # model id（對外暴露的名稱）
            alias: default        # 別名
            context_window: 32768 # context 長度

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
  ceclaw_router:                  # 規則名稱（任意）
    endpoints:
      - host: host.openshell.internal   # NV proxy 寫死解析到 172.17.0.1
        port: 8000
        access: full             # full | read | write
        allowed_ips:
          - 172.17.0.1           # 必填！對應 DNS 解析結果
    binaries:                    # 必填！指定哪些 binary 可以用此規則
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

### Phase 2 — Plugin 整合（🔄 進行中）
- Plugin 整合測試
- openclaw TUI 對話測試
- Banner 確認

### Phase 3 — 易用性
- `ceclaw` CLI
  - `ceclaw onboard` — 一鍵設定新機器
  - `ceclaw status` — 顯示所有元件狀態
  - `ceclaw connect` — 建立 sandbox
- CoreDNS 持久化（systemd）
- 自動 Approve policy（不需要 TUI）

### Phase 4 — 多後端
- Ollama 後端支援
- vLLM 後端支援
- SGLang 後端支援
- 多 GB10 負載均衡

### Phase 5 — 企業功能
- 串流回應完整支援
- 雲端降級完整測試
- 使用量統計
- 成本計算（本地 vs 雲端）
- 多租戶支援

---

## 7. 已知限制

| 限制 | 說明 | 計劃解法 |
|------|------|---------|
| CoreDNS 不持久 | 重開機後消失 | Phase 3 加到 systemd |
| TUI 手動 Approve | 新 sandbox 需人工操作 | Phase 3 自動化 |
| GB10 手動啟動 | llama-server 未設自啟 | 加 systemd service 到 GB10 |
| single sandbox | 目前只測一個 agent | Phase 4 多 sandbox |
| 無 auth | Router 無認證機制 | Phase 5 加 API key |

---

## 8. 技術債

1. **CoreDNS 持久化** — 重開機後需手動 `bash ~/nemoclaw-config/restore-coredns.sh`
2. **TUI Approve** — 每次新建 sandbox 需要手動 Approve pending rules
3. **GB10 自啟** — llama-server 需手動 SSH 啟動
4. **Plugin 未整合測試** — openclaw TUI 對話流程未驗證

---

## 9. 競爭定位

```
                    本地推論 ◄─────────────────► 雲端推論
                        │                           │
  資料不出內網 ──────────┤                           ├── 資料送外部
                        │                           │
  ┌─────────────────────┼───────────────────────────┼──────────┐
  │                     │                           │          │
  │  CECLAW ●───────────┘           NemoClaw ───────┘          │
  │  (本地優先 + 雲端備援)           (雲端優先)                  │
  │                                                            │
  └────────────────────────────────────────────────────────────┘
        高安全性                                    低安全性
        低成本                                      高成本
        高延遲控制                                  依賴外部
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
*總工: Kent | 文件版本: 0.1.0 | 日期: 2026-03-19*
