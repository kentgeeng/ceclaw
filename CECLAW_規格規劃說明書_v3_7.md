# CECLAW 規格規劃說明書 v3.7
**更新日期：2026-04-10 凌晨**

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
- **CDC 驗證→客戶 OTA**（幫客戶擋 upstream 風險）

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

**銷售一句話：**
> 一個 AI 管不了兩件性質完全相反的事。OpenClaw 是公司的法務與人事部門，Hermes 是每個員工的私人秘書。

---

## 四層記憶架構（定案）

```
Layer 1：SOUL.md + CECLAW_SYSTEM_PROMPT（靜態，每次注入）
Layer 2：~/.ceclaw/vault/（結構化工作狀態，Hermes file tool 讀寫）
          working-context.md / project-state.md / decisions-log.md / daily/
Layer 3：Qdrant RAG（語意搜尋，按需）
          L1 tw_laws / L2 tw_knowledge / L3 ceclaw_*
Layer 4：Hermes session_search（跨對話回溯，最後手段）
```

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
└── vLLM XPU（Gemma 4，B70×2，64GB）tensor parallel
└── Qdrant :6333（tw_laws + tw_knowledge + ceclaw_*）
└── ollama bge-m3 :11434
└── law_advisor_api :8010
```

**B70 推理數據（實測）：**
- L1 B70×2：~140 tok/s（vLLM continuous batching，可服務多人並發）
- L2 B70×4：~540 tok/s
- llama.cpp multi-GPU bug #16767 → 必須用 vLLM，不用 llama-server

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

---

## 查詢順序（定案）

```
query → proxy.py
  ① L3 Qdrant（ceclaw_*）
  ② L2 tw_knowledge             ← 並行（現為串行，B70 後升 asyncio）
  ③ 合併去重（取最高 score）
  ④ L1 law_advisor_api           ← 條件執行，_LAW_KEYWORDS 觸發
  ⑤ inject SOUL.md → LLM
```

---

## Upstream 維護策略（定案）

| 元件 | 策略 | 說明 |
|------|------|------|
| OpenClaw | 永久 fork | 等重大安全漏洞才升級 |
| Hermes | 選項 B→C | B70 升級時 P3 hook 改成 builtin_hooks/ |
| proxy.py | 完全自主 | 不依賴任何 upstream |

**CDC OTA 流程：**
upstream 新版 → CDC 72小時燒機 → 客戶 OTA

---

## 神經系統優化路線（B70 後）

| 優先 | 技術 | 說明 |
|------|------|------|
| P1 | Reranker（bge-reranker-v2-m3）| RAG 注入前重排序 top-3 |
| P1 | Reasoning on | Gemma 4 thinking mode |
| P2 | Graph RAG（Neo4j）| 法律交叉引用 |

---

## Hermes 功能清單

**已啟用：**
- 跨對話記憶（vault 四個 md 檔）
- 工具執行（file/terminal/web/memory）
- 法規知識查詢（Router proxy 自動注入）
- 歷史對話搜尋（session_search，FTS5）
- 即時網路搜尋（SearXNG adapter :2337）
- 雙層協作（shared_bridge）

**程式內建待啟用（B70 後）：**
- Skill 自動創建
- Cron 排程
- 多平台 Gateway（Telegram/Slack）
- MCP 整合
- Honcho 用戶建模
- 子 Agent 並行

---

## 顧問矩陣（15類）

hr / legal / ip / digital / account / medical / corp / finance / land / env / food / energy / transport / telecom / edu

套件：基礎版 / 醫療版 / 科技版 / 製造版 / 金融版 / 建設版 / 全行業版

---

## POC 完成進度

✅ OpenClaw 4.7 / Gemma4 ctx=262144 / Hermes / shared_bridge
✅ RAG 三層 / tw_laws 18類 / 14類 advisor / law_advisor systemd
✅ tw_knowledge 51,970筆 12類 / RAG 接入 / 加班費修正
✅ RAG 大體檢 5/5 / LLM Wiki POC 四關 / OpenShell 二次 reboot
✅ ollama 0.20.3 systemd / gemma4:31b-cloud 解鎖
✅ L3 Chroma→Qdrant 遷移（ceclaw_ 前綴）
✅ knowledge_service_v2（async，bge-m3，query_points）
✅ 三層 RAG 全通驗證（五題）
✅ SearXNG adapter（Hermes web_search 接通）
✅ pop-os + GB10 樣板驗證完成
✅ **vault 記憶層（三關驗證：讀/寫/跨對話）**
✅ **架構圖系列（總/使用/功能對照 SVG）**
✅ **upstream 維護策略 + CDC OTA 流程**

⏳ TPEX 補強（長期）/ Admin UI 清理（B70 後）/ BM25（B70 後）

📋 B70: vLLM XPU / OpenShell template / Qdrant 搬家 / Hermes v0.8.0 / Reranker / Telegram gateway

---

## 版本歷史

| 版本 | 日期 | 主要變更 |
|------|------|---------|
| v3.7 | 2026-04-10 凌晨 | 四層記憶架構、upstream 策略、神經系統優化路線、Hermes 功能清單 |
| v3.6 | 2026-04-09 下午 | L3 Qdrant 架構、SearXNG adapter、樣板驗證完成 |
| v3.5 | 2026-04-08 深夜 | B70 架構、LLM Wiki 路線、OpenShell、KV 壓縮評估 |
