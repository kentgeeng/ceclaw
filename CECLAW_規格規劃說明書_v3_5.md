# CECLAW 規格規劃說明書 v3.5
**更新日期：2026-04-08 深夜**

---

## 產品定位

**CECLAW = 企業隱形顧問團，懂你的行業，懂台灣，住在你的伺服器裡**

核心賣點：
- **資料主權**（全部在客戶內網，永不出門）
- **按行業訂製顧問組合**（護城河）
- **台灣在地化專家**（文化/法規/產業/語言）
- **Hermes 智能代理**
- **OpenShell sandbox隔離**（每客戶獨立環境，B70後）
- **工具執行能力**（exec/web_search/git）

---

## 雙層 AI 架構（定案）

```
OpenClaw（公司層）    Hermes（員工層）
Stateless            Stateful
    ↕ shared_bridge ↕
```

---

## B70 部署架構（定案）

```
OpenShell Gateway
├── sandbox-companyA
│   ├── OpenClaw + CECLAW proxy
│   ├── Chroma（公司知識庫）
│   ├── Hermes-員工A / B / C（各自parquet）
│   └── tw_laws + tw_knowledge（唯讀共用）
└── sandbox-companyB（完全隔離）

共用推理層（sandbox外）
└── vLLM XPU（Gemma 4，B70×2，64GB）
```

---

## 三層知識架構

```
Layer 1: tw_laws → 221,599條，18類
Layer 2: tw_knowledge → 51,969筆，12類
Layer 3: Chroma RAG → personal/dept/company
         B70後升級為 LLM Wiki
```

---

## Gemma 4 知識進化（三階段）

### Phase 1：RAG（目前）✅
- 51,969筆台灣知識 + 221,599條法規
- 加班費倍率已修正

### Phase 2：LLM Wiki（B70後）📋
Karpathy pattern，POC四關全通：
- Raw → LLM編譯 → Wiki markdown
- 知識複利，矛盾自動標記
- ⚠️無來源推論標記待驗證（已實作）

### Phase 3：SFT（B70×4後）📋
- Unsloth Intel GPU LoRA
- 高品質問答對微調

---

## KV Cache 壓縮評估

| 技術 | B70 | 狀態 |
|------|-----|------|
| RotorQuant | ❌ | CUDA only |
| TurboQuant | ❌ | CUDA/Metal only |
| vLLM TurboQuant | ❌ | issue #38171，無人做 |
| vLLM XPU原生 | ✅ | B70直接用 |

B70×2=64GB，Gemma4 28GB，KV cache 36GB，暫不需要壓縮。

---

## 顧問矩陣（15類全上線）

hr / legal / ip / digital / account / medical / corp / finance / land / env / food / energy / transport / telecom / edu

套件：基礎版 / 醫療版 / 科技版 / 製造版 / 金融版 / 建設版 / 全行業版

---

## 系統架構

```
Portal :9000 → Admin :3005 / Hermes :3000
OpenClaw :18789 → CECLAW Router :8000
    → Chroma RAG / 法律RAG / tw_knowledge RAG
    → GB10 :8001（Gemma 4）

GB10: tw_laws(221,599) + tw_knowledge(51,969) + bge-m3 + law_advisor_api
pop-os額外: ollama :11434(RTX5070Ti) + OpenShell gateway :18234
```

---

## POC 完成進度

✅ OpenClaw 4.7 / Gemma4 ctx=262144 / Hermes / shared_bridge
✅ RAG三層 / tw_laws 18類 / 14類advisor / law_advisor systemd
✅ tw_knowledge 51,969筆 12類 / RAG接入 / 加班費修正
✅ RAG大體檢5/5 / LLM Wiki POC四關 / OpenShell二次reboot
✅ ollama 0.20.3 systemd

⏳ ollama cloud signin / TPEX補強（長期）/ Admin UI清理（B70後）

📋 B70: vLLM XPU / OpenShell template / Qdrant搬家 / LLM Wiki正式 / SFT

---

## 版本歷史

| 版本 | 日期 | 主要變更 |
|------|------|---------|
| v3.5 | 2026-04-08 深夜 | B70架構、LLM Wiki路線、OpenShell、KV壓縮評估 |
| v3.4 | 2026-04-08 下午 | tw_knowledge、14類advisor |
| v3.3 | 2026-04-08 | tw_laws全分類 |
