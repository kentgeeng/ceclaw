# CECLAW 規格規劃說明書
## ColdElectric Claw — 本地優先 AI Agent 推論路由系統

**版本**: 0.3.8  
**作者**: Kent (總工)  
**日期**: 2026-03-22  
**狀態**: Alpha — P1~P5 完成，P0 修復中，GB10 模型切換完成

---

## 1. 專案背景

### 1.1 起源

NVIDIA 在 GTC 2026 發布 NemoClaw + OpenShell，定位為企業 AI Agent 安全執行框架。其核心設計假設是：**推論走 NVIDIA Cloud**。

ColdElectric 擁有自建 GPU 推論基礎設施（GB10 機器，DGX Spark），需求：
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

### 1.3 POC vs 量產定位

| 項目 | POC（當前）| 量產（未來）|
|------|-----------|-----------|
| 推論框架 | llama.cpp | vLLM（等 Blackwell 支援成熟）|
| 模型精度 | Q4_K_M GGUF | FP8/NVFP4 滿級 |
| 模型大小 | 47-70GB | 依需求選擇 |
| 並發 | 2 slots | 數十~數百 |
| 目標 | 驗證架構 + 穩定 | 企業生產 |

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
| **多後端** | 無 | **P4：Ollama + llama.cpp** |

**核心差異：**
> NemoClaw = Secure Execution（安全執行）  
> CECLAW = Secure + Sovereign Inference（安全 + 主權推論）

---

## 3. 系統架構

### 3.1 元件總覽

```
┌─────────────────────────────────────────────────────────────┐
│                    CECLAW 系統元件                           │
├─────────────────────────────────────────────────────────────┤
│  ① CECLAW Inference Router (ceclaw/router/)                │
│     - FastAPI + uvicorn，監聽 0.0.0.0:8000                 │
│     - Smart routing：fast → main → backup → cloud          │
│     - systemd 管理，開機自啟                                │
│                                                             │
│  ② CECLAW Plugin (ceclaw/plugin/)                          │
│     - TypeScript, openclaw plugin v1                        │
│     - registerCommand 無解（openclaw 不支援此 API）          │
│                                                             │
│  ③ Sandbox Image (ghcr.io/kentgeeng/ceclaw-sandbox)        │
│     - B方案 5 個 bug 已全部修正                             │
│                                                             │
│  ④ OpenShell Policy                                        │
│     - network_policies + allowed_ips + binaries             │
│                                                             │
│  ⑤ GB10 推論機（主力）✅ 已切換                             │
│     - llama.cpp，Qwen3.5-122B Q4_K_M，192.168.1.91:8001   │
│     - systemd 開機自啟，LLaMA Server (Qwen3.5-122B)        │
│     - 備選：Qwen2.5-72B Q4_K_M（已下載，待測試）           │
│                                                             │
│  ⑥ Ollama（本地快速後端）                                   │
│     - qwen3-nothink（fast，Modelfile自訂，支援tools）        │
│     - qwen3:8b（backup，think:false）                       │
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
     ├── 簡單問題（無推理關鍵字）
     │   → Ollama qwen3-nothink（fast，~1s）
     │
     ├── 複雜問題 / 預設
     │   → GB10 Qwen3.5-122B（main，15-36s）
     │
     ├── GB10 掛掉
     │   → Ollama qwen3:8b（backup，~1.3s）
     │
     └── 全部掛掉
         → 雲端 fallback（Groq → Anthropic → OpenAI → NV）
```

### 3.4 商業部署架構（三層推論）

```
┌─────────────────────────────────────────────────────────┐
│  Tier 1: 本地小伺服器                                    │
│  ├─ 模型：Ollama / 小型 GGUF                            │
│  ├─ 用途：快速反應 (< 0.5s)                              │
│  └─ 資料不離開設備                                       │
│           ↓ Smart Routing ↓                             │
│  Tier 2: GPU 推論伺服器（GB10 / AI CDC）                 │
│  ├─ 模型：大型 GPU 叢集（llama.cpp / vLLM）             │
│  ├─ 用途：複雜推理、長文分析 (1-36s)                     │
│  └─ 資料不出自家機房                                     │
│           ↓ Cloud Fallback ↓                            │
│  Tier 3: 任意模型 API                                    │
│  ├─ 模型：OpenAI / Anthropic / Groq / NVIDIA            │
│  └─ 最強能力、按需付費                                   │
└─────────────────────────────────────────────────────────┘
```

---

## 4. 已完成功能

### 4.1 功能清單

| 功能 | 狀態 | Commit |
|------|------|--------|
| Inference Router | ✅ | - |
| 本地優先路由 | ✅ | - |
| 雲端降級 | ✅ | - |
| 後端健康檢查 | ✅ | 65f5d89 |
| SIGHUP 熱重載 | ✅ | - |
| OpenShell Policy | ✅ | - |
| Sandbox Image | ✅ | 2dfab79 |
| CoreDNS 持久化 | ✅ | 1bffd63 |
| 監控腳本 + logrotate | ✅ | 70175b6 |
| ceclaw CLI v0.1.0 | ✅ | c412038 |
| Ollama multi-backend | ✅ | 756a1a0 |
| Smart routing | ✅ | 986a7b5 |
| 多後端燒機 200 輪 | ✅ | 3bac2a5 |
| ceclaw logs --follow | ✅ | 575d488 |
| ceclaw logs --lines | ✅ | f115bd2 |
| P5 關鍵字補充（三語對齊）| ✅ | 515c59a |
| P5 Health Check 配置化 | ✅ | 65f5d89 |
| P5 qwen3-nothink E方案 | ✅ | 9d213b3 |
| Chain Audit Log | ✅ | 40ac82a |
| **燒機 2000 輪 100%** | ✅ | - |
| **GB10 Qwen3.5-122B** | ✅ | - |
| **GB10 systemd 開機自啟** | ✅ | - |
| **GLM-5 Turbo 評審通過** | ✅ | - |

### 4.2 驗證記錄

```
2026-03-21 P1~P5 全部完成驗證
2026-03-22 GB10 模型比較測試：
  - 10題標準測試：Qwen3.5 9/10，MiniMax 8/10
  - 8題高難度（GLM-5 Turbo 評審）：
    Qwen3.5 8/8 ✅，MiniMax 1/8（2❌/5⚠️）
  - MiniMax 致命問題：日文崩潰（4種語言混入）、Q4空白輸出
2026-03-22 燒機 2000 輪：2000/2000 100% ✅
2026-03-22 Audit verify：2900 條記錄，鏈完整 ✅
2026-03-22 GB10 systemd 開機自啟驗證 ✅
```

---

## 5. 設定檔規格

### 5.1 ceclaw.yaml 現有規格（最新）

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
        model: qwen3-nothink          # ✅ 已從 qwen2.5:7b 升級
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

---

## 6. 路線圖

### Phase 1~5（✅ 完成）
- Inference Router, Policy, iptables, CoreDNS
- Plugin 整合, B方案 rebuild image
- ceclaw CLI v0.1.0
- 監控, logrotate, 備份
- Chain Audit Log, Smart Routing, E方案
- 燒機 2000 輪 100%

### Phase 0 — P0 修復（進行中）🔴
- [ ] **坑#19 白標化**：system prompt 加入 CECLAW 身份，雙 Path
- [ ] **坑#20 Context 膨脹**：`memory.qmd.limits.maxInjectedChars: 8000`
- [ ] **坑#21 history-limit 預設化**：ceclaw.py TUI 呼叫加預設參數
- [ ] **坑#18 Role 相容性**：研究 openclaw.json 原生解法
- [ ] **坑#22 web_search**：SearXNG 自架或 Brave API key
- [ ] **Qwen2.5-72B 評估**：47GB，預期更穩定，需跑 8 題 + GLM 審查

### Phase 6 — 相容性驗證
- [ ] NemoClaw drop-in 驗證報告
- 已確認：核心 CLI 100% 對齊，整體 67-72% 相似度

### Phase 7 — OpenClaw Skill 相容性測試
- [ ] A 級（無網路，10個）優先
- 前置條件：P0 全修完

### Phase 8 — UX 升級
- [ ] `ceclaw onboard` 升級
- [ ] `ceclaw doctor` 診斷指令
- [ ] `ceclaw list` 指令
- 前置條件：P6 完成

---

## 7. 已知限制

| 限制 | 說明 | 計劃解法 |
|------|------|---------|
| 身份洩漏 | 100% 洩漏通義千問/阿里巴巴 | P0 白標化 |
| Context 膨脹 | session 發瘋 | P0 memory limit |
| web_search 觸發 | 所有 prompt 都搜 | SearXNG 或 Brave key |
| Qwen3.5-122B 極限操作 | ~86GB/128GB，不是穩定區間 | 考慮換 Qwen2.5-72B |
| TUI 底部顯示 | openclaw 寫死 `local/minimax` | 無解，坑#11 |
| Auto-approve | OpenShell 安全設計 | 無解，坑#12 |
| GB10 reasoning 殘留 | qwen3-nothink 約11% 洩漏 | P1 middleware 過濾 |
| vLLM on GB10 | Blackwell 支援尚未成熟 | 等 vLLM 更新 |

---

## 8. 技術債

1. **Session replay**（坑#13）— P0 處理中
2. **身份洩漏**（坑#19）— P0 處理中
3. **Context 膨脹**（坑#20）— P0 處理中
4. **registerCommand**（坑#5）— openclaw 不支援，無解
5. **undici EnvHttpProxyAgent** — experimental，長期關注
6. **qwen3-nothink reasoning 殘留** — 11% 洩漏率
7. **difference between 冗餘** — 關鍵字重複，可清理
8. **MiniMax Q3_K_XL 未清理** — 95GB，`~/MiniMax-M2.5-GGUF/UD-Q3_K_XL/`
9. **tokens ?/131k 顯示** — context window 顯示不正確

---

## 9. 本地模型能力評估（v4.0 最新）

| 模型 | 大小 | GB10記憶體 | 速度 | 品質 | 穩定性 | 狀態 |
|------|------|-----------|------|------|--------|------|
| Qwen3.5-122B Q4_K_M | 70GB | ~86GB | 22t/s | ⭐⭐⭐⭐⭐ | ⚠️ 極限 | **當前主力** |
| Qwen2.5-72B Q4_K_M | 47GB | ~60GB | 待測 | ⭐⭐⭐⭐ | ✅ 穩定 | 待測試 |
| MiniMax IQ2_M | 74GB | ~82GB | 29t/s | ⭐⭐ | ❌ 日文崩潰 | 淘汰 |
| MiniMax Q3_K_XL | 95GB | ~110GB+ | 27t/s | ⭐⭐⭐ | ❌ OOM | 淘汰 |
| qwen3-nothink | ~5GB | Ollama | ~200ms | ⭐⭐⭐ | ✅ | fast path |
| qwen3:8b | ~5GB | Ollama | ~1.3s | ⭐⭐⭐ | ✅ | backup |

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
- Qwen3.5-122B GGUF: https://huggingface.co/bartowski/Qwen_Qwen3.5-122B-A10B-GGUF
- Qwen2.5-72B GGUF: https://huggingface.co/bartowski/Qwen2.5-72B-Instruct-GGUF
- ZengboJames GB10 參考: https://github.com/ZengboJamesWang/Qwen3.5-35B-A3B-openclaw-dgx-spark
- GLM-5 Turbo 督察: OpenRouter → zhipuai/glm-5-turbo

---

*CECLAW — Secure local AI agents, your inference, your rules.*  
*總工: Kent | 版本: 0.3.8 | 日期: 2026-03-22*  
*P1✅ P2✅ B方案✅ P3✅ P4✅ P5✅ GB10✅ | 下一步: P0修復*
