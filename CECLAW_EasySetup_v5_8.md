# CECLAW EasySetup v5.8
**更新日期：2026-04-11 凌晨**

---

## ⚠️ 架構現況（2026-04-11 最新）

**OpenClaw 4.7 ✅（鎖定，issues #59598/#46049 仍 open）**
**Hermes v0.8.0 ✅（本次完成升級）**
**Hermes gateway.run ✅（取代舊版 webapi）**
**P3 hook 移植 v0.8.0 ✅（api_calls>=1觸發）**
**Sessions stub ✅（5個endpoint，格式正確）**
**shared_bridge 驗證 ✅（bridge新檔案生成）**
**Portal hermes-exec 修復 ✅（/v1/chat/completions）**
**Auto Demo 修復 ✅（無404）**
**Admin v0.2.7 去中國化 ✅**
**Pixel Office iframe ✅（port 4567）**
**⚠️ Hermes Workspace models/sessions/chat stream — 未完成，核心問題**
**L3 Chroma → Qdrant 遷移完成 ✅**
**knowledge_service_v2（async bge-m3）✅**
**三層 RAG 全通驗證 ✅**
**SearXNG adapter（:2337）✅**
**vault 記憶層 ✅**
**tw_knowledge 51,970筆（12類）✅**
**法律小顧問 RAG（221,599條，18類）✅**
**GB10 Gemma 4 26B MoE Q8，ctx=262144 ✅**

---

## 服務清單

### CECLAW 主系統（pm2，pop-os）
| id | name | port | 說明 |
|----|------|------|------|
| 0-2 | heartbeat-* | - | HEARTBEAT |
| 3 | ceclaw-gateway | 18789 | OpenClaw 4.7 |
| 4 | tugcan-dashboard | 7001 | 系統監控 |
| 5 | ceclaw-admin | 3005 | v0.2.7，繁中，去中國化 |
| 6 | ceclaw-portal | 9000 | 入口 + hermes-exec proxy |
| 8 | ceclaw-office | 5180 | WW-AI-Lab openclaw-office |
| 10 | ceclaw-bot-review | 4567 | xmanrui pixel office |

### Hermes 系統（手動啟動，pop-os）
| 服務 | Port | 啟動 |
|------|------|------|
| SearXNG adapter | 2337 | bash ~/start-hermes.sh |
| Hermes gateway v0.8.0 | 8642 | bash ~/start-hermes.sh |
| Hermes workspace | 3000 | bash ~/start-hermes.sh |

### GB10（192.168.1.91）
| 服務 | Port | 啟動 |
|------|------|------|
| llama-server（Gemma 4 26B MoE Q8）| 8001 | systemd ✅ |
| Qdrant | 6333 | Docker ✅ |
| ollama（bge-m3）| 11434 | systemd ✅ |
| law_advisor_api | 8010 | systemd ✅ |

---

## Qdrant Collections（GB10 :6333）
| Collection | 筆數 | 說明 |
|-----------|------|------|
| tw_laws | 221,599 | 法律骨架，18類 |
| tw_knowledge | 51,970 | 在地百科，12類 |
| ceclaw_company_poc | 395 | L3 公司知識 |
| ceclaw_dept_engineering | 1 | L3 研發部門 |
| ceclaw_dept_legal | 1 | L3 法務部門 |
| ceclaw_personal_kent | 3 | L3 個人記憶 |

---

## 開機後正常流程

```bash
# 1. 體檢
pm2 list
curl -s http://192.168.1.91:8001/health
curl -s http://192.168.1.91:8010/health

# 2. 啟動 Hermes
bash ~/start-hermes.sh
sleep 5
curl -s http://localhost:8642/health   # {"status":"ok","platform":"hermes-agent"}
curl -s http://localhost:8642/api/sessions  # {"items":[],"total":0}

# 3. vault 確認
cat ~/.ceclaw/vault/working-context.md

# 4. OpenClaw issues 每次必查
curl -s https://api.github.com/repos/openclaw/openclaw/issues/59598 | python3 -c "import json,sys; d=json.load(sys.stdin); print('#59598:', d['state'])"
curl -s https://api.github.com/repos/openclaw/openclaw/issues/46049 | python3 -c "import json,sys; d=json.load(sys.stdin); print('#46049:', d['state'])"
```

---

## 健康檢查清單

| 層 | 項目 | 正常 |
|---|------|------|
| L0 | CECLAW 身份 | ✅ 我是 CECLAW 企業 AI 助手 |
| L1 | gateway pm2 | ✅ online（OpenClaw 4.7）|
| L2 | Router | ✅ gb10-llama healthy |
| L3 | GB10 health | ✅ {"status":"ok"} |
| L4 | Portal 四燈 | ✅ 全綠 |
| L5 | web_search | ✅ SearXNG :8888 |
| L6 | exec tool | ✅ workspace 可寫 |
| L7 | OpenClaw-Admin | ✅ port 3005 v0.2.7 |
| L8 | GB10 model | ✅ Gemma 4 26B MoE，ctx=262144 |
| L9 | GB10 vision | ✅ vision=true |
| L10 | lossless-claw | ✅ lcm Plugin loaded |
| L11 | Hermes Workspace | ✅ 啟動，Terminal/File/Memory 可用 |
| L11a | Hermes Workspace models | ❌ auth問題，No models available |
| L11b | Hermes Workspace chat | ❌ stream slice錯誤 |
| L11c | Hermes Workspace sessions | ❌ 空白（stub） |
| L12 | RAG L3 Qdrant | ✅ ceclaw_* 四個 collection |
| L13 | shared_bridge | ✅ 雙向 h2o/o2h |
| L14 | 知識庫審核 UI | ✅ Admin :3005/knowledge |
| L15 | 遙控 Hermes | ✅ Admin :3005/hermes-control（Auto Demo已修）|
| L16 | law_advisor_api | ✅ GB10 :8010（systemd）|
| L17 | 法律 RAG 觸發 | ✅ 勞基法條文正確引用 |
| L18 | 14類 advisor 路由 | ✅ proxy.py 已補齊 |
| L19 | tw_knowledge RAG | ✅ 51,970筆，threshold 0.7 |
| L20 | CECLAW 工具意識 | ✅ web_search 正常觸發 |
| L21 | 加班費倍率 | ✅ 1.67/2.67 正確 |
| L22 | ollama systemd | ✅ 0.20.3，0.0.0.0:11434 |
| L23 | OpenShell sandbox | ✅ ceclaw-local Ready |
| L24 | L3 Qdrant ceclaw_* | ✅ 四個 collection |
| L25 | SearXNG adapter | ✅ :2337 |
| L26 | Hermes web_search | ✅ 天氣/股價可查 |
| L27 | RAG 三層全通 | ✅ 五題驗證 |
| L28 | vault 記憶層 | ✅ 跨對話三關驗證 |
| **L29** | **Hermes v0.8.0** | **✅ gateway.run，api_calls>=1** |
| **L30** | **Admin 去中國化** | **✅ 無QQ/飛書/釘釘** |
| **L31** | **Pixel Office** | **✅ :4567 iframe** |

---

## 已知問題

| 問題 | 嚴重度 | 狀態 | Workaround |
|------|--------|------|-----------|
| Hermes Workspace models | 🔴 高 | **未修** | 直接打:8642 |
| Hermes Workspace chat stream | 🔴 高 | **未修** | 用 Portal 遙控 |
| Hermes Workspace sessions | 🔴 高 | **未修** | 無 |
| OpenClaw #59598/#46049 | 🟡 中 | open | 鎖4.7 |
| Admin OpenClaw-Admin殘留 | 🟡 中 | 未修 | 視覺問題 |
| GB10 單 slot 長任務佔滿 | 🟡 中 | 等B70 | 避免長任務 |
| BM25 Hybrid Search 未開啟 | 🟡 中 | 等B70 | |
| Hermes 手動啟動 | 🟢 低 | 等B70 | bash ~/start-hermes.sh |

---

## 版本歷史
| 版本 | 日期 | 主要變更 |
|------|------|---------|
| v5.8 | 2026-04-11 凌晨 | Hermes v0.8.0、P3 hook、Admin去中國化、Pixel Office、L29-31 |
| v5.7 | 2026-04-10 凌晨 | vault記憶層、架構圖系列、upstream策略、CDC OTA |
| v5.6 | 2026-04-09 下午 | L3 Qdrant、async RAG、SearXNG adapter |
