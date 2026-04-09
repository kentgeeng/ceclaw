# CECLAW 規格規劃說明書 v3.6
**更新日期：2026-04-09 下午**

---

## 產品定位

**CECLAW = 企業隱形顧問團，懂你的行業，懂台灣，住在你的伺服器裡**

核心賣點：
- **資料主權**（全部在客戶內網，永不出門）
- **按行業訂製顧問組合**（護城河）
- **台灣在地化專家**（文化/法規/產業/語言）
- **Hermes 智能代理**（員工層，stateful）
- **OpenShell sandbox 隔離**（每客戶獨立環境，B70 後）
- **工具執行能力**（exec/web_search/git）

---

## 雙層 AI 架構（定案）

```
OpenClaw（公司層）    Hermes（員工層）
Stateless            Stateful
管理/工具用途         員工日常對話
    ↕ shared_bridge ↕
```

**UI 對應：**
- OpenClaw :18789 → 管理介面（IT/Admin）
- Hermes :3000 → 員工日常使用介面

---

## B70 部署架構（定案）

```
OpenShell Gateway
├── sandbox-companyA
│   ├── OpenClaw + CECLAW proxy :8000
│   ├── Hermes webapi :8642 + workspace :3000
│   ├── SearXNG adapter :2337
│   └── shared_bridge
└── sandbox-companyB（完全隔離）

共用推理層（sandbox 外）
└── vLLM XPU（Gemma 4，B70×2，64GB）
└── Qdrant :6333（tw_laws + tw_knowledge + ceclaw_*）
└── ollama bge-m3 :11434
└── law_advisor_api :8010
```

**pop-os + GB10 = B70 樣板，現在打通 = 搬家後直接用**

---

## 三層知識架構（定案）

```
Layer 1: tw_laws → 221,599條，18類，Qdrant，threshold 0.7
Layer 2: tw_knowledge → 51,970筆，12類，Qdrant，threshold 0.7
Layer 3: ceclaw_* → Qdrant，ceclaw_ 前綴多租戶隔離
         - ceclaw_personal_{user_id}
         - ceclaw_dept_{dept_name}
         - ceclaw_company_{company_id}
```

**統一技術棧：** Qdrant + bge-m3 1024 dim + threshold 0.7

---

## 查詢順序（定案）

```
query → proxy.py
  ① L3 Qdrant（ceclaw_*）
  ② L2 tw_knowledge             ← 並行（現為串行，B70 後升 asyncio）
  ③ 合併去重（取最高 score）
  ④ L1 law_advisor_api           ← 條件執行，_LAW_KEYWORDS 觸發（省 200-400ms）
  ⑤ inject SOUL.md → LLM
```

---

## Hermes web_search 架構（定案）

```
Hermes web_search tool
  → Firecrawl API（/v1/search + /v2/search）
  → SearXNG adapter :2337（~/ceclaw/router/searxng_adapter.py）
  → SearXNG :8888（本機，免費，無 API key）
```

---

## Gemma 4 知識進化（三階段）

### Phase 1：RAG（目前）✅
- 51,970筆台灣知識 + 221,599條法規 + 公司 L3 知識
- bge-m3 統一 embedding，threshold 0.7

### Phase 2：LLM Wiki（B70 後）📋
- Karpathy pattern，POC 四關全通
- Raw → LLM 編譯 → Wiki markdown
- 知識複利，矛盾自動標記

### Phase 3：SFT（B70×4 後）📋
- Unsloth Intel GPU LoRA
- 高品質問答對微調

---

## KV Cache 壓縮評估

| 技術 | B70 | 狀態 |
|------|-----|------|
| RotorQuant | ❌ | CUDA only |
| TurboQuant | ❌ | CUDA/Metal only |
| vLLM TurboQuant | ❌ | issue #38171，無人做 |
| vLLM XPU 原生 | ✅ | B70 直接用 |

B70×2=64GB，Gemma4 28GB，KV cache 36GB，暫不需要壓縮。

---

## 顧問矩陣（15類全上線）

hr / legal / ip / digital / account / medical / corp / finance / land / env / food / energy / transport / telecom / edu

套件：基礎版 / 醫療版 / 科技版 / 製造版 / 金融版 / 建設版 / 全行業版

---

## 系統架構（當前）

```
Portal :9000 → Admin :3005 / Hermes :3000
OpenClaw :18789 → CECLAW Router :8000
    → knowledge_service_v2（L3 Qdrant）
    → 法律 RAG（law_advisor_api :8010）
    → tw_knowledge RAG（Qdrant :6333）
    → GB10 :8001（Gemma 4）

Hermes :3000/:8642 → SearXNG adapter :2337 → SearXNG :8888

GB10: tw_laws + tw_knowledge + ceclaw_* + bge-m3 + law_advisor_api
pop-os: ollama :11434 + OpenShell gateway :18234 + SearXNG :8888
```

---

## POC 完成進度

✅ OpenClaw 4.7 / Gemma4 ctx=262144 / Hermes / shared_bridge
✅ RAG 三層 / tw_laws 18類 / 14類 advisor / law_advisor systemd
✅ tw_knowledge 51,970筆 12類 / RAG 接入 / 加班費修正
✅ RAG 大體檢 5/5 / LLM Wiki POC 四關 / OpenShell 二次 reboot
✅ ollama 0.20.3 systemd / gemma4:31b-cloud 解鎖
✅ **L3 Chroma→Qdrant 遷移（ceclaw_ 前綴）**
✅ **knowledge_service_v2（async，bge-m3，query_points）**
✅ **三層 RAG 全通驗證（五題）**
✅ **SearXNG adapter（Hermes web_search 接通）**
✅ **pop-os + GB10 樣板驗證完成**

⏳ TPEX 補強（長期）/ Admin UI 清理（B70 後）/ BM25（B70 後）

📋 B70: vLLM XPU / OpenShell template / Qdrant 搬家 / LLM Wiki 正式 / SFT

---

## 版本歷史

| 版本 | 日期 | 主要變更 |
|------|------|---------|
| v3.6 | 2026-04-09 下午 | L3 Qdrant 架構、SearXNG adapter、樣板驗證完成 |
| v3.5 | 2026-04-08 深夜 | B70 架構、LLM Wiki 路線、OpenShell、KV 壓縮評估 |
| v3.4 | 2026-04-08 下午 | tw_knowledge、14類 advisor |
