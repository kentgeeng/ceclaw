# CECLAW 規格規劃說明書
## ColdElectric Claw — 本地優先 AI Agent 推論路由系統

**版本**: 0.3.7  
**作者**: Kent (總工)  
**日期**: 2026-03-21  
**狀態**: Alpha — P1~P5 進行中，GB10 模型切換中

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
│  ⑥ Ollama（P4/P5，本地快速後端）                           │
│     - qwen3-nothink（fast，Modelfile自訂，支援tools）        │
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

### 3.4 商業部署架構（三層推論）

CECLAW 支援三層推論架構，依客戶需求彈性部署：

```
┌─────────────────────────────────────────────────────────┐
│                   客戶端 CECLAW                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Tier 1: 本地小伺服器                                    │
│  ├─ 部署：客戶端小型伺服器                               │
│  ├─ 模型：Ollama / 小型 GGUF                            │
│  ├─ 用途：快速反應 (< 0.5s)                              │
│  ├─ 範例：問候、計算、翻譯、摘要                         │
│  └─ 價值：零延遲、資料不離開設備                         │
│                                                         │
│           ↓ Smart Routing ↓                             │
│                                                         │
│  Tier 2: GPU 推論伺服器                                  │
│  ├─ 部署：客戶自建 GPU 伺服器 或 租用算力                │
│  │        （如 ColdElectric AI CDC）                    │
│  ├─ 模型：大型 GPU 叢集（llama.cpp / vLLM）             │
│  ├─ 用途：複雜推理、長文分析 (1-3s)                      │
│  ├─ 範例：為什麼、分析、系統設計、研究                   │
│  └─ 價值：深度運算、資料不出自家機房                     │
│                                                         │
│           ↓ Cloud Fallback ↓                            │
│                                                         │
│  Tier 3: 任意模型 API                                    │
│  ├─ 部署：雲端                                           │
│  ├─ 模型：OpenAI / Anthropic / Groq / NVIDIA            │
│  ├─ 用途：最強能力、最新模型 (2-10s)                     │
│  ├─ 範例：特殊任務、尖峰備援                             │
│  └─ 價值：能力無上限、按需付費                           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**部署彈性：**
- 可只部署 Tier 1（純本地）
- 可 Tier 1 + Tier 2（本地 + GPU 伺服器）
- 可三層全開（完整智慧路由）

**自動切換：**
CECLAW Smart Router 依查詢類型自動選擇最佳路徑，用戶無感知。

**商業價值對應：**

| 客戶類型 | 部署模式 | 價值主張 |
|----------|----------|----------|
| 企業用戶 | Tier 1 + 2 + 3 | 資料主權 + 複雜能力 + 無上限備援 |
| 學術單位 | Tier 1 + 2 | 資料不出內網 + 經費可控 |
| 高端個人 | Tier 1 + 3 | 快速本地 + 雲端最強能力 |

> 一個系統，三層推論，依需求彈性部署，自動選擇最佳路徑。

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
| 燒機 20800 輪 100% | ✅ | - |
| Ollama multi-backend | ✅ | 756a1a0 |
| Smart routing | ✅ | 986a7b5 |
| 關鍵字擴充（辦公室/coding/日文）| ✅ | 0c09325 |
| 多後端燒機 200 輪 100% | ✅ | 3bac2a5 |
| Smart Routing 20000 輪 | ✅ | - |
| ceclaw logs --follow | ✅ | 575d488 |
| ceclaw logs --lines | ✅ | f115bd2 |
| P5 關鍵字補充（15個推理詞，三語對齊）| ✅ | 515c59a |
| P5 Health Check 配置化（15s，/health優先）| ✅ | 65f5d89 |
| P5 qwen3-nothink E方案（tools schema）| ✅ | 9d213b3/52aa117 |
| Chain Audit Log | ✅ | 40ac82a |

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
2026-03-21 單後端燒機 20800 輪 100%，avg 1843ms ✅
2026-03-21 P4 Smart Routing 端到端驗證：
  - "hi" → ollama-fast → 200 ✅（avg 173ms）
  - "why is the sky blue" → gb10-llama → 200 ✅（avg 1255ms）
  - 16種問題 routing 100% 正確 ✅
2026-03-21 多後端燒機 200/200 100%，ollama-fast avg=173ms，gb10-llama avg=1255ms ✅
2026-03-21 Smart Routing 20000 輪：20000/20000 100% ✅
2026-03-21 P5 E方案驗證：
  - qwen3-nothink + tools：149/149 100%，avg 1227ms ✅
  - 不亂觸發 tool_calls ✅
  - TUI 測試：你是誰→ollama-fast，為什麼天空是藍色→gb10-llama ✅
2026-03-21 P5 Chain Audit Log：200輪後585條記錄，鏈完整 ✅
2026-03-21 GB10 問題發現：MiniMax 228B reasoning OOM，換模型中
```

---

## 5. 設定檔規格

### 5.1 ceclaw.yaml 現有規格（P4 後）

```yaml
version: 1
router:
  listen_host: "0.0.0.0"
  listen_port: 8000
  tls: false
  reload_on_sighup: true
inference:
  strategy: smart-routing
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
            context_window: 32768

      - name: ollama-backup
        type: ollama
        base_url: http://127.0.0.1:11434/v1
        priority: 3
        model: qwen3:8b
        options:
          think: false
        use_for: [fallback]

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

### 5.2 ceclaw.yaml P4 已實作規格

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

### Phase 4 — 多後端（✅ 完成）
- [x] ceclaw.yaml schema 擴充 ✅（commit: 454d088）
- [x] Ollama adapter（backends.py）✅（commit: f40fa4f）
- [x] Backend health check 更新 ✅
- [x] Smart routing 實作 ✅（token threshold 移除 + 關鍵字擴充，commit: 0c09325）
- [x] 多後端燒機驗證 ✅（commit: 3bac2a5，200輪100%）
- [x] Smart Routing 20000 輪 ✅（20000/20000 100%）

### Phase 5 — 企業功能（進行中）
- [x] `ceclaw logs --follow` ✅（commit: 575d488）
- [x] `ceclaw logs --lines <n>` ✅（commit: f115bd2）
- [x] 關鍵字補充（15個推理詞，三語對齊）✅（commit: 515c59a）
- [x] Health Check 配置化（15s timeout，llama.cpp→/health，ollama→/models）✅（commit: 65f5d89）
- [x] qwen3-nothink E方案（tools schema 偵測，fast路徑換模型）✅（commit: 9d213b3/52aa117）
- [x] Chain Audit Log（hash chain，flock並發保護，10MB buffer）✅（commit: 40ac82a）
- [x] Streaming 完整測試 ✅（逐chunk轉發確認）
- [x] session `--history-limit 20` ✅（鎖定解法：`openclaw tui --history-limit 20`）
- [ ] 雲端降級完整測試（待 API key）
- [ ] registerCommand bug ✗（無解：openclaw 不支援此 API）
- [ ] session 持久化（P8 再議）
- [ ] 時間閾值方案B（rolling avg，燒機穩定後再做）

### Phase 6 — 相容性驗證
- [ ] NemoClaw drop-in 替代驗證報告
- [ ] 指令對照表（草稿完成，待正式驗證）

**已確認結論：**
- 核心 CLI 100% 對齊（onboard/connect/status/logs/start/stop）
- 整體相似度 67-72%，差距為設計決策非功能缺失
- P8 補 `ceclaw list` 可達 78%

### Phase 7 — OpenClaw Skill 相容性測試
> CECLAW Router（本地 MiniMax）作為推論後端，驗證 OpenClaw skill 能否正常執行

- [ ] A 級（無網路，10個）：Self-Improving Agent / Capability Evolver / Nano Pdf / Obsidian / Mcporter / Skill Creator / Openai Whisper / Model Usage / Apple Notes / Apple Reminders
- [ ] B 級（有網路，15個）
- [ ] C 級（功能補完，25個）

⚠️ 安全原則：測試用 API key、隔離 sandbox、安裝前確認 skill 來源（ClawHavoc 事件：820+ 惡意 skill 已被清除，仍需驗證）

### Phase 8 — UX 升級
> 前置條件：P4~P7 全部完成 + P6 drop-in 驗證通過

- [ ] `ceclaw onboard` 升級為 one-click installer（對齊 NemoClaw `nemoclaw.sh` 體驗）
- [ ] `ceclaw doctor` 診斷指令（自動檢查 Router / GB10 / sandbox / CoreDNS 狀態）
- [ ] `ceclaw list` 指令（對齊 NemoClaw `list`，整體相似度從 72% 提升至 78%）
- [ ] 自動引導 policy approve 流程（坑#12 UX 解法）
- [ ] session 自動管理（坑#13 UX 解法，自動開新 session 或清歷史）

---

## 7. 已知限制

| 限制 | 說明 | 計劃解法 |
|------|------|---------|
| MiniMax OOM | 228B reasoning 無限生成導致 KV cache 耗盡 | 換 Qwen3.5-122B（進行中）|
| TUI 底部顯示 | openclaw 寫死 `local/minimax` | 無解，坑#11 |
| Auto-approve | OpenShell 安全設計 | 無解，坑#12 |
| Session replay | 歷史累積造成 Connection error | Phase 5，坑#13 |
| GB10 手動啟動 | llama-server 未設自啟 | 加 systemd to GB10 |
| VRAM 限制 | 16GB，兩個 Ollama 模型 9.9GB | 按需載入策略 |

---

## 8. 技術債

1. **Session replay**（坑#13）— main session 歷史累積造成 Connection error，已鎖定解法
2. **GB10 自啟** — llama-server 需手動 SSH 啟動
3. **registerCommand**（坑#5）— openclaw 不支援此 API，無解
4. **undici EnvHttpProxyAgent** — experimental，長期關注 openclaw 更新
5. **MiniMax reasoning OOM**（坑#14）— 228B 模型 reasoning 無限生成，換 Qwen3.5-122B 解決
6. **qwen3-nothink reasoning 殘留** — Modelfile `/nothink` workaround 非完美，偶爾有 reasoning 輸出
7. **difference between 冗餘** — `difference` 已包含 `difference between`，可清理

---

## 9. 本地模型能力評估（P4 參考）

| 模型 | 速度 | 題型識別 | 數學/邏輯 | 程式碼 | 用途 |
|------|------|---------|---------|--------|------|
| qwen3-nothink | ⭐⭐⭐ 1.2s | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | fast（tools支援）|
| qwen3:8b | ⭐⭐⭐ 1.3s | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | backup |
| GB10 MiniMax 228B | ⭐⭐⭐⭐ 33s | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | main（reasoning OOM問題）|
| Qwen3.5-122B Q4 | ⭐⭐⭐⭐ 預期快 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 未來main（下載中）|

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
*總工: Kent | 版本: 0.3.7 | 日期: 2026-03-21*
