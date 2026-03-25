# CECLAW 規格規劃說明書
## ColdElectric Claw — 本地優先 AI Agent 推論路由系統

**版本**: 0.4.3
**作者**: Kent (總工)
**日期**: 2026-03-25
**狀態**: Alpha — P0~P1 大部分完成，TUI 身份驗證 ✅，web search 待修（D方案）

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
| K3s 跨網段 | 網路隔離 | iptables FORWARD + MASQUERADE（172.19 網段）|
| UFW routed | deny by default | `ufw default allow routed` |
| sandbox DNS | 只解析 internal | 外部查詢必須走 Router proxy（D方案）|

### 1.3 POC vs 量產定位

| 項目 | POC（當前）| 量產（未來）|
|------|-----------|-----------|
| 推論框架 | llama.cpp | vLLM（等 Blackwell 支援成熟）|
| 模型精度 | Q4_K_M GGUF | FP8/NVFP4 滿級 |
| 並發 | 2 slots（parallel 2，ctx-size 65536，每 slot 32768）| 數十~數百 |
| web search | SearXNG via Router proxy（D方案）| 企業內搜尋 + 外網 |
| 目標 | 驗證架構 + 展示 | 企業生產 |

---

## 2. 與其他方案的比較

### 2.1 vs NemoClaw

| 項目 | NemoClaw | CECLAW |
|------|---------|--------|
| 推論目標 | NVIDIA Cloud | 本地 GB10 + 雲端備援 |
| 資料流向 | 出內網 | 留在內網 |
| 推論成本 | 按 token | 本地 GPU 免費 |
| Router 層 | 無 | CECLAW Router ✅ |
| 降級策略 | 掛了就掛 | GB10 → ollama-backup → Cloud |
| 身份白標化 | 無 | inject_system_prompt ✅ |
| 本地搜尋 | 無 | SearXNG + Router proxy ✅ |
| 審計記錄 | 無 | Chain Audit Log（P5）✅ |
| 外部資訊 | 不適用 | D方案：Router fetch proxy（待實作）|

---

## 3. 系統架構

### 3.1 元件總覽

```
┌─────────────────────────────────────────────────────────────┐
│                    CECLAW 系統元件                           │
├─────────────────────────────────────────────────────────────┤
│  OpenShell Sandbox (ceclaw-agent)                           │
│  ├── openclaw gateway (ws://127.0.0.1:18789)                │
│  ├── TUI / Skills                                           │
│  └── SearXNG plugin (searxng_search tool)                   │
│       ↓ http://host.openshell.internal:8000                 │
│  CECLAW Router (pop-os:8000)                                │
│  ├── /v1/chat/completions → smart routing                   │
│  ├── /search → SearXNG proxy (port 8888)                    │
│  └── /v1/fetch → 外部 URL proxy（D方案，待實作）             │
│       ↓ smart routing                                       │
│  ├── ollama-fast (ministral-3:14b, ~636ms)                  │
│  ├── gb10-llama (Qwen3.5-122B, ~2624ms)                     │
│  └── ollama-backup (qwen3:8b, fallback)                     │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 網路拓樸（已確認）

```
sandbox (10.200.0.2 / 172.19.0.2)
    ↓ host.openshell.internal = 172.17.0.1
pop-os docker bridge (172.17.0.1)
    ↓ Router port 8000
CECLAW Router (0.0.0.0:8000)
    ↓
GB10 (192.168.1.91:8001)
```

### 3.3 關鍵設計決策

**為什麼不讓 sandbox 直接連外網：**
OpenShell sandbox 設計就是要隔離外部網路（安全賣點）。CECLAW 不破壞這個隔離，而是讓 Router 作為唯一出口，代理所有外部請求。

**D 方案（Router fetch proxy）：**
```
模型呼叫 web_search / web_fetch
→ 走 host.openshell.internal:8000
→ Router 代為查詢 SearXNG 或抓取外部 URL
→ 回傳結果給模型
```

---

## 4. 燒機結果

### 6000 輪（v3 腳本）
| 項目 | 結果 |
|------|------|
| 總成功率 | 6000/6000 ✅ 100% |
| Fast path avg | 621ms |
| Main path avg | 2594ms |
| SearXNG 60/60 | 100% |
| 全簡體異常 | 1/3000（0.03%）|

### 3000 輪（追加）
| 項目 | 結果 |
|------|------|
| 總成功率 | 3000/3000 ✅ 100% |
| Fast path avg | 636ms |
| Main path avg | 2624ms |
| 簡體字率 | 0.87%（26/3000）|
| 日期幻覺率 | 85%（`what day is today`）|
| 正確率（嚴格）| 97.1% |
| 正確率（排除日期）| 99.3% |

---

## 5. 已知問題與技術債

### P0（阻擋 POC）
- **web_fetch 全 EAI_AGAIN**：sandbox DNS 隔離，外部查詢全幻覺
  - 解法：D 方案（Router /v1/fetch proxy）
  - 影響：所有 Skills 需要外網的功能不可用

### 技術債
- **日期幻覺 85%**：system prompt 加「嚴禁編造日期」可修
- **簡體字率 0.87%**：集中在 `what is python`，已知 ministral-3:14b 限制
- **sandbox openclaw 2026.3.11**：base image ARM64 無法直接升級，需重建 image
- **台灣本土模型淘汰未入文件**（#66b）

---

## 6. 進度表

| Phase | 狀態 |
|-------|------|
| P0（身份白標化、Role rewrite）| ✅ 完成 |
| P1（Smart routing、SearXNG、燒機）| ✅ 大部分完成 |
| P1 web search D方案 | ⚠️ 進行中 |
| P2（HTTPS）| ✅ 完成 |
| P3（CoreDNS 持久化）| ✅ 完成 |
| P4（Multi-backend）| ✅ 完成 |
| P5（Chain Audit Log）| ✅ 完成 |
| P6（NemoClaw drop-in）| ⬜ 待做 |
| P7（Skill 相容性）| ⬜ 待做 |
| P8（UX 升級）| ⬜ 待做 |

---

*CECLAW — Secure local AI agents, your inference, your rules.*
*版本: 0.4.3 | 日期: 2026-03-25*
