# CECLAW 規格規劃說明書
## ColdElectric Claw — 本地優先 AI Agent 推論路由系統

**版本**: 0.3.2  
**作者**: Kent (總工)  
**日期**: 2026-03-21  
**狀態**: Alpha — P1~P3 完成，P4 multi-backend 開發中

---

## 1. 專案背景

### 1.1 起源

NVIDIA 在 GTC 2026 發布 NemoClaw + OpenShell，定位為企業 AI Agent 安全執行框架。其核心設計假設是：**推論走 NVIDIA Cloud**。

ColdElectric 擁有自建 GPU 推論基礎設施（GB10 機器，MiniMax-M2.5），需求：
- 資料不出內網
- 推論成本歸零
- 不依賴 NVIDIA Cloud

CECLAW（ColdElectric Claw）：**在 OpenShell 安全框架內，把推論流量重定向到本地 GPU**。

### 1.2 為什麼難

NV 的設計有三道關卡逆著我們走：

| 關卡 | NV 設計意圖 | CECLAW 解法 |
|------|------------|------------|
| `inference.local` DNS | 鎖死指向 NV Cloud | 改用 `host.openshell.internal` |
| OpenShell Proxy | deny-all | network_policies + allowed_ips + binaries |
| K3s 跨網段 | 網路隔離 | iptables FORWARD + MASQUERADE |

---

## 2. 與其他方案的比較

### 2.1 vs NemoClaw

| 項目 | NemoClaw | CECLAW |
|------|---------|--------|
| 執行環境 | OpenShell sandbox | OpenShell sandbox |
| 推論目標 | NVIDIA Cloud | 本地 GB10 + 雲端備援 |
| 資料流向 | 出內網 | 留在內網 |
| 推論成本 | 按 token | 本地 GPU 免費 |
| Router 層 | 無 | CECLAW Router ✅ |
| 降級策略 | 掛了就掛 | GB10 → Groq → Anthropic → OpenAI → NV |
| 模型選擇 | NV 指定 | 任意 GGUF |
| CLI 入口 | `nemoclaw` | `ceclaw`（對齊設計）|
| **審計記錄** | 無 | **Chain Audit Log（P5）** |
| **多後端** | 無 | **P4：Ollama + vLLM + SGLang** |

**核心差異：**
> NemoClaw = Secure Execution（安全執行）  
> CECLAW = Secure + Sovereign Inference（安全 + 主權推論）

### 2.2 vs Ollama

| 項目 | Ollama | CECLAW |
|------|--------|--------|
| 沙盒隔離 | 無 | OpenShell ✅ |
| 網路控制 | 無 | YAML policy + iptables |
| 雲端備援 | 無 | 4 個雲端 provider |
| 適用場景 | 單機測試 | 企業生產環境 |

### 2.3 vs 原生 OpenAI SDK

| 項目 | 原生 SDK | CECLAW |
|------|---------|--------|
| 沙盒隔離 | 無 | OpenShell ✅ |
| 資料出內網 | 是 | 否 |
| 本地推論 | 否 | 是 |
| 多 provider | 否 | 是 |

---

## 3. 系統架構

### 3.1 元件總覽

```
┌─────────────────────────────────────────────────────────────┐
│                    CECLAW 系統元件                           │
├─────────────────────────────────────────────────────────────┤
│  ① CECLAW Inference Router (ceclaw/router/)                │
│     - FastAPI + uvicorn，監聽 0.0.0.0:8000                 │
│     - Smart routing（P4）：fast → main → backup → cloud    │
│     - systemd 管理，開機自啟                                │
│                                                             │
│  ② CECLAW Plugin (ceclaw/plugin/)                          │
│     - TypeScript, openclaw plugin v1                        │
│     - registerCommand 暫時 disabled（P5 待修）              │
│                                                             │
│  ③ Sandbox Image (ghcr.io/kentgeeng/ceclaw-sandbox)        │
│     - B方案 5 個 bug 已全部修正                             │
│     - ceclaw-start.sh 自動設定                              │
│                                                             │
│  ④ OpenShell Policy                                        │
│     - network_policies + allowed_ips + binaries             │
│                                                             │
│  ⑤ GB10 推論機（主力）                                     │
│     - llama.cpp，MiniMax-M2.5-UD-Q3_K_XL，192.168.1.91:8001│
│                                                             │
│  ⑥ Ollama（P4，本地快速後端）                              │
│     - qwen2.5:7b（fast，0.19s）                             │
│     - qwen3:8b（backup，1.3s，think:false）                 │
│     - localhost:11434                                        │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Router API 端點

```
CECLAW Inference Router
├── GET  /ceclaw/status          健康狀態 + 後端清單
├── POST /ceclaw/reload          熱重載設定檔
├── GET  /v1/models              列出可用模型
├── POST /v1/chat/completions    推論
└── POST /v1/completions         推論
```

### 3.3 推論流程（P4 後）

```
Request 進來
     │
     ▼
Smart Routing 判斷
     │
     ├── 簡單問題（< 80 tokens，無推理關鍵字）
     │   → Ollama qwen2.5:7b（fast，0.19s）
     │
     ├── 複雜問題 / 預設
     │   → GB10 MiniMax（main，1.8s）
     │
     ├── GB10 掛掉
     │   → Ollama qwen3:8b（backup，1.3s）
     │
     └── 全部掛掉
         → 雲端 fallback（Groq → Anthropic → OpenAI → NV）
```

---

## 4. 已完成功能

### 4.1 功能清單

| 功能 | 狀態 | Commit |
|------|------|--------|
| Inference Router | ✅ | - |
| 本地優先路由 | ✅ | - |
| 雲端降級 | ✅ | - |
| 後端健康檢查 | ✅ | - |
| SIGHUP 熱重載 | ✅ | - |
| 零硬編碼 | ✅ | - |
| OpenShell Policy | ✅ | - |
| iptables 穿透 | ✅ | - |
| Sandbox Image | ✅ | 2dfab79 |
| timeout_local_ms 60000 | ✅ | 2dfab79 |
| CoreDNS 持久化 | ✅ | 1bffd63 |
| 監控腳本 + logrotate | ✅ | 70175b6 |
| GB10 備份 | ✅ | 70175b6 |
| ceclaw CLI v0.1.0 | ✅ | c412038 |
| 燒機 3500 輪 100% | ✅ | 70175b6 |
| 燒機 99999 輪 | 🔄 進行中 | - |
| Ollama multi-backend | ⬜ | P4 |
| Smart routing | ⬜ | P4 |
| Chain Audit Log | ⬜ | P5 |

### 4.2 驗證記錄

```
2026-03-20 燒機（P1）：200 輪 200/200 ✅
2026-03-20 Plugin 整合：openclaw TUI local/minimax ✅ commit: 6ebea02
2026-03-20 B方案驗證：自動設定，不需要手動 Step 12 ✅ commit: 2dfab79
2026-03-20 全鏈路燒機：3500/3500 100%，avg 1842ms ✅ commit: 70175b6
2026-03-21 Ollama 測試：
  - qwen2.5:7b：熱啟動 0.19s，能力基本，快速問答 ✅
  - qwen3:8b think:false：1.3s，能力強，LRU Cache/數學/邏輯全過 ✅
  - qwen3:8b 關鍵發現：能正確識別數學題型，qwen2.5:7b 不行
2026-03-21 燒機 99999 輪：進行中（截至 3400+ 輪 100%）
```

---

## 5. 設定檔規格

### 5.1 ceclaw.yaml 現有規格

```yaml
version: 1
router:
  listen_host: "0.0.0.0"
  listen_port: 8000
  tls: false
  reload_on_sighup: true
inference:
  strategy: local-first
  timeout_local_ms: 60000
  local:
    backends:
      - name: gb10-llama
        type: llama.cpp
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

### 5.2 ceclaw.yaml P4 擴充規格（待實作）

```yaml
inference:
  strategy: smart-routing        # 新策略
  timeout_local_ms: 60000
  local:
    backends:
      - name: ollama-fast
        type: ollama
        base_url: http://127.0.0.1:11434/v1
        priority: 1
        model: qwen2.5:7b
        use_for: [simple_query]
      - name: gb10-llama
        type: llama.cpp
        base_url: http://192.168.1.91:8001/v1
        priority: 2
        models:
          - id: minimax
            alias: default
      - name: ollama-backup
        type: ollama
        base_url: http://127.0.0.1:11434/v1
        priority: 3
        model: qwen3:8b
        options:
          think: false
        use_for: [fallback]
```

---

## 6. 路線圖

### Phase 1~3（✅ 完成）
- Inference Router, Policy, iptables, CoreDNS
- Plugin 整合, B方案 rebuild image
- ceclaw CLI v0.1.0
- 監控, logrotate, 備份
- 燒機 3500 輪 100%

### Phase 4 — 多後端（開發中）
- [ ] ceclaw.yaml schema 擴充（前置）
- [ ] Ollama adapter（backends.py）
- [ ] Backend health check 更新
- [ ] Smart routing 實作
- [ ] 多後端燒機驗證

### Phase 5 — 企業功能
- [ ] Chain Audit Log（hash chain，不跑節點，鏈式審計）
- [ ] Streaming 完整支援
- [ ] 雲端降級完整測試
- [ ] registerCommand bug 修正
- [ ] session 持久化（坑#13）

### Phase 6 — 相容性驗證
- [ ] NemoClaw drop-in 替代驗證報告

---

## 7. 已知限制

| 限制 | 說明 | 計劃解法 |
|------|------|---------|
| 單後端 | 目前只有 GB10 | Phase 4 多後端 |
| TUI 底部顯示 | openclaw 寫死 `local/minimax` | 無解，坑#11 |
| Auto-approve | OpenShell 安全設計 | 無解，坑#12 |
| Session replay | 歷史累積造成 Connection error | Phase 5，坑#13 |
| GB10 手動啟動 | llama-server 未設自啟 | 加 systemd to GB10 |
| VRAM 限制 | 16GB，兩個 Ollama 模型 9.9GB | 按需載入策略 |

---

## 8. 技術債

1. **Session replay**（坑#13）— main session 歷史累積造成 Connection error
2. **GB10 自啟** — llama-server 需手動 SSH 啟動
3. **registerCommand TypeError**
4. **undici EnvHttpProxyAgent** — experimental，長期關注 openclaw 更新

---

## 9. 本地模型能力評估（P4 參考）

| 模型 | 速度 | 題型識別 | 數學/邏輯 | 程式碼 | 用途 |
|------|------|---------|---------|--------|------|
| qwen2.5:7b | ⭐⭐⭐⭐⭐ 0.19s | ⭐⭐ 弱 | ⭐⭐⭐ | ⭐⭐⭐ | fast |
| qwen3:8b | ⭐⭐⭐ 1.3s | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | backup |
| GB10 MiniMax | ⭐⭐⭐⭐ 1.8s | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | main |

---

## 10. 競爭定位

```
NemoClaw = Secure Execution
CECLAW   = Secure + Sovereign Inference

                    本地推論 ◄─────────────────► 雲端推論
  CECLAW ●──────────────┘           NemoClaw ───────┘
  Ollama ●── 本地單機，無沙盒
  原生SDK ─────────────────────────────────────── 雲端
```

---

## 11. 參考資料

- OpenShell docs: https://docs.nvidia.com/openshell/latest/
- NemoClaw GitHub: https://github.com/NVIDIA/NemoClaw
- CECLAW sandbox image: ghcr.io/kentgeeng/ceclaw-sandbox:latest
- CECLAW repo: github.com/kentgeeng/ceclaw

---

*CECLAW — Secure local AI agents, your inference, your rules.*  
*總工: Kent | 版本: 0.3.2 | 日期: 2026-03-21*
