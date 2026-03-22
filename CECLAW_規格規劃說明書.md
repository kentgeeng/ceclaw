# CECLAW 規格規劃說明書
## ColdElectric Claw — 本地優先 AI Agent 推論路由系統

**版本**: 0.3.9  
**作者**: Kent (總工)  
**日期**: 2026-03-22  
**狀態**: Alpha — P0~P5 完成，POC 展示就緒

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
| 目標 | 驗證架構 + 展示 | 企業生產 |

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
| **身份白標化** | 無 | **P0：inject_system_prompt** |
| **Role 相容** | 無 | **P0：rewrite_messages** |
| **本地搜尋** | 無 | **P0：SearXNG 自架** |

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
│     - rewrite_messages()：role 相容性修復                   │
│     - inject_system_prompt()：CECLAW 身份注入               │
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
│  ⑤ GB10 推論機（主力）✅                                    │
│     - llama.cpp，Qwen3.5-122B Q4_K_M，192.168.1.91:8001   │
│     - systemd 開機自啟，LLaMA Server (Qwen3.5-122B)        │
│     - 備選：Qwen2.5-72B Q4_K_M（已下載，待測試）           │
│                                                             │
│  ⑥ Ollama（本地快速後端）                                   │
│     - qwen3-nothink（fast，Modelfile含CECLAW身份）          │
│     - qwen3:8b（backup，think:false）                       │
│     - localhost:11434                                        │
│                                                             │
│  ⑦ SearXNG（本地搜尋）✅ 新增                               │
│     - Docker，port 8888                                     │
│     - 172.17.0.1:8888（sandbox 可達）                      │
│     - P0-4b Router 攔截待做                                 │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Router API 端點

```
CECLAW Inference Router
├── GET  /ceclaw/status          健康狀態 + 後端清單
├── POST /ceclaw/reload          熱重載設定檔
├── GET  /v1/models              列出可用模型
├── POST /v1/chat/completions    推論（含 role rewrite + identity inject）
└── POST /v1/completions         推論
```

### 3.3 推論流程（P0 後）

```
Request 進來
     │
     ▼
rewrite_messages()
     │ developer→system, toolResult→tool, system merge
     ▼
inject_system_prompt()
     │ CECLAW 身份注入（最後位置，recency bias）
     ▼
Smart Routing 判斷
     │
     ├── 身份問題 / 複雜問題
     │   → GB10 Qwen3.5-122B（main，15-36s）
     │
     ├── 簡單問題
     │   → Ollama qwen3-nothink（fast，~1s）
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
| Chain Audit Log | ✅ | 40ac82a |
| 燒機 2000 輪 100% | ✅ | - |
| GB10 Qwen3.5-122B | ✅ | - |
| GB10 systemd 開機自啟 | ✅ | - |
| GLM-5 Turbo 評審通過 | ✅ | - |
| **P0-2 Role 相容性** | ✅ | ada85a7 |
| **P0-3 tui alias + history-limit** | ✅ | 903e8cc |
| **P0-1 身份白標化** | ✅ | 4c1e888 |
| **P0-4a SearXNG 自架** | ✅ | cf44a1f |
| **contextWindow 32768 修正** | ✅ | db24708 |
| **30題壓力測試通過** | ✅ | - |

### 4.2 驗證記錄

```
2026-03-21 P1~P5 全部完成驗證
2026-03-22 GB10 模型比較測試：
  - Qwen3.5 8/8 ✅（GLM-5 Turbo 評審），MiniMax IQ2_M 淘汰
2026-03-22 燒機 2000 輪：2000/2000 100% ✅
2026-03-22 P0 全部完成：
  - Role rewrite 驗證 ✅
  - 身份白標化：「你是誰」→「我是 CECLAW 企業 AI 助手」✅
  - 「你是通義千問嗎」→「不是，我是 CECLAW 企業 AI 助手」✅
  - contextWindow 32768：tokens ?/33k ✅
  - 30題壓力測試無 503 ✅
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
        model: qwen3-nothink
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

### 5.2 sandbox openclaw.json 關鍵設定（重建後需 patch）

```json
{
  "models": {
    "providers": {
      "local": {
        "baseUrl": "http://host.openshell.internal:8000/v1",
        "apiKey": "ceclaw-local",
        "api": "openai-completions",
        "models": [{
          "id": "minimax",
          "name": "CECLAW Local",
          "contextWindow": 32768,
          "maxTokens": 4096
        }]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {"primary": "local/minimax"},
      "compaction": {
        "mode": "safeguard",
        "reserveTokens": 8000
      }
    }
  }
}
```

---

## 6. 路線圖

### Phase 0~5（✅ 完成）
- P0：Role 相容、身份白標化、context 修正、SearXNG 自架
- P1~P5：Router, Policy, iptables, CoreDNS, CLI, 監控, Audit, Smart Routing

### Phase 1（P0 後，進行中）
- [ ] P0-4b：Router 攔截 web_search → 轉發 SearXNG
- [ ] Qwen2.5-72B 評估（47GB，穩定區間）
- [ ] 身份關鍵字補充（「訓練的」、「什麼模型」）
- [ ] qwen3-nothink reasoning 殘留過濾

### Phase 6 — 相容性驗證
- [ ] NemoClaw drop-in 驗證報告
- 前置條件：P0 全修完 ✅

### Phase 7 — OpenClaw Skill 相容性測試
- [ ] A 級（無網路，10個）優先

### Phase 8 — UX 升級
- [ ] `ceclaw onboard` 補完（plugin install + gateway autostart 自動化）
- [ ] `ceclaw doctor` 診斷指令
- [ ] `ceclaw list` 指令

---

## 7. 已知限制

| 限制 | 說明 | 計劃解法 |
|------|------|---------|
| web_search 出內網 | openclaw 走 Brave API | P1-1 Router 攔截→SearXNG |
| Qwen3.5-122B 極限 | ~86GB/128GB，不是穩定區間 | 考慮換 Qwen2.5-72B |
| TUI 底部顯示 | openclaw 寫死 `local/minimax` | 無解，坑#11 |
| Auto-approve | OpenShell 安全設計 | 無解，坑#12 |
| qwen3-nothink reasoning 殘留 | 約11% | P1 middleware 過濾 |
| vLLM on GB10 | Blackwell 支援尚未成熟 | 等 vLLM 更新 |
| sandbox 重建後需手動 4 步 | 見交接文件 | P8 自動化 |
| docker restart → sandbox 死 | 坑#23 | 不要 restart container |

---

## 8. 技術債

1. **P0-4b web_search Router 攔截** — P1 待做
2. **qwen3-nothink reasoning 殘留** — 11% 洩漏率
3. **registerCommand**（坑#5）— openclaw 不支援，無解
4. **undici EnvHttpProxyAgent** — experimental，長期關注
5. **MiniMax Q3_K_XL 未清理** — 95GB，`~/MiniMax-M2.5-GGUF/UD-Q3_K_XL/`
6. **ceclaw onboard 不完整** — 缺 plugin install + gateway autostart

---

## 9. 本地模型能力評估（v4.1 最新）

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
*總工: Kent | 版本: 0.3.9 | 日期: 2026-03-22*  
*P0✅ P1✅ P2✅ B方案✅ P3✅ P4✅ P5✅ GB10✅ | 下一步: P1→P6*
