# CECLAW 規格規劃說明書 v3.8
**更新日期：2026-04-11 凌晨**

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
管理/知識/合規        員工日常對話/任務執行
    ↕ shared_bridge ↕
    ~/.ceclaw/knowledge/bridge/shared/
```

**UI 對應：**
- Admin :3005 / OpenClaw :18789 → IT/Admin 管理介面
- Hermes :3000（workspace）→ 員工日常使用

**銷售一句話：**
> 一個 AI 管不了兩件性質完全相反的事。OpenClaw 是公司的法務與人事部門，Hermes 是每個員工的私人秘書。

**銷售問答：**
- Q：為什麼要兩個AI？→ 公司知識全員共用，員工記憶只有本人，一個AI只能選一種
- Q：用ChatGPT Teams不就好了？→ 你的資料會出內網。CECLAW全部在你的伺服器

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

## 三層推理架構（定案）

```
L1：Gemma4 26B MoE Q8（自建，擋70%）→ GB10 :8001
L2：Qwen3.5-72B/Omni（自建，擋95%）→ B70後
L3：雲端旗艦API（Qwen3-Max/GPT-5/Claude，擋5%）→ 僅定制客戶
```

---

## B70 部署架構（定案）

```
OpenShell Gateway
├── sandbox-companyA
│   ├── OpenClaw + CECLAW proxy :8000
│   ├── Hermes v0.8.0 gateway :8642 + workspace :3000
│   ├── SearXNG adapter :2337
│   └── shared_bridge
└── sandbox-companyB（完全隔離）

共用推理層（sandbox 外）
└── vLLM XPU（Gemma 4，B70×2 TP=2）~140 tok/s
└── Qdrant :6333（tw_laws + tw_knowledge + ceclaw_*）
└── ollama bge-m3 :11434
└── law_advisor_api :8010
```

**B70 推理數據（實測）：**
- L1 B70×2：~140 tok/s（continuous batching，可服務多人並發）
- L2 B70×4：~540 tok/s
- llama.cpp multi-GPU bug #16767 → 必須用 vLLM，不用 llama-server

---

## Upstream 維護策略（定案）

| 元件 | 策略 | 說明 |
|------|------|------|
| OpenClaw | 永久 fork（選項 A）| 等重大安全漏洞才升級 |
| Hermes | 選項 B→C | P3 hook 目前直改源碼；B70 時改成 builtin_hooks/ plugin |
| proxy.py | 完全自主 | 不依賴任何 upstream |

**CDC OTA 流程：**
upstream 新版 → CDC 72小時燒機 → 驗證P3/RAG/bridge → 客戶 OTA

---

## Hermes v0.8.0 關鍵變化（2026-04-11 完成）

```
舊版（廢棄）：
  -m webapi
  P3 hook 在 webapi/routes/chat.py

新版（現在）：
  -m gateway.run
  P3 hook 在 gateway/platforms/api_server.py 626行
  Sessions API stub：1063行起（5個endpoint）
  config.yaml 需加：platforms: api_server: enabled: true
```

---

## 神經系統優化路線（B70 後）

| 優先 | 技術 | 說明 |
|------|------|------|
| P1 | Reranker（bge-reranker-v2-m3）| RAG 注入前重排序 top-3 |
| P1 | Reasoning on | Gemma 4 thinking mode |
| P2 | Graph RAG（Neo4j）| 法律交叉引用 |

---

## POC 完成進度

✅ OpenClaw 4.7 / Gemma4 ctx=262144
✅ Hermes v0.8.0（本次完成）
✅ P3 hook 移植（api_calls>=1）
✅ Sessions stub（5個endpoint）
✅ shared_bridge 雙向驗證
✅ Portal hermes-exec 修復
✅ Auto Demo 修復
✅ Admin v0.2.7 去中國化
✅ Pixel Office iframe :4567
✅ RAG 三層 / tw_laws 18類 / 14類 advisor / law_advisor systemd
✅ tw_knowledge 51,970筆 12類 / 加班費修正
✅ L3 Chroma→Qdrant 遷移（ceclaw_ 前綴）
✅ knowledge_service_v2（async bge-m3）
✅ SearXNG adapter（Hermes web_search 接通）
✅ vault 記憶層（三關驗證）
✅ 架構圖系列（總/使用/功能對照）
✅ upstream 維護策略 + CDC OTA

⚠️ **Hermes Workspace models/sessions/chat stream — 未完成**

📋 B70: vLLM XPU / OpenShell template / Qdrant搬家 / Hermes systemd / Reranker

---

## 版本歷史
| 版本 | 日期 | 主要變更 |
|------|------|---------|
| v3.8 | 2026-04-11 凌晨 | Hermes v0.8.0架構、P3 hook新位置、Sessions stub、三層推理架構 |
| v3.7 | 2026-04-10 凌晨 | 四層記憶架構、upstream策略、神經系統優化路線 |
| v3.6 | 2026-04-09 下午 | L3 Qdrant架構、SearXNG adapter、樣板驗證 |
