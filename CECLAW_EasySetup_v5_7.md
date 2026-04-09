# CECLAW EasySetup v5.7
**更新日期：2026-04-10 凌晨**

---

## ⚠️ 架構現況（2026-04-10 最新）

**OpenClaw 4.7 ✅（鎖定，issues #59598/#46049 仍 open）**
**L3 Chroma → Qdrant 遷移完成 ✅**
**knowledge_service_v2（async bge-m3）✅**
**三層 RAG 全通驗證 ✅**
**SearXNG adapter（:2337）✅**
**Hermes web_search 接通 ✅**
**vault 記憶層 ✅ 本次完成**
**SOUL.md vault 讀寫規則 ✅ 本次完成**
**架構圖系列（總/使用/功能對照）✅ 本次完成**
**upstream 維護策略 ✅ 本次完成**
**CDC OTA 升級流程 ✅ 本次完成**
**tw_knowledge 51,970筆（12類分類）✅**
**法律小顧問 RAG（221,599條，18類）✅**
**shared_bridge 雙向 ✅**
**Portal v2.1 / Admin :3005 ✅**
**GB10 Gemma 4 26B MoE Q8，ctx=262144 ✅**

---

## 服務清單

### CECLAW 主系統（pm2，pop-os）

| id | name | port | 說明 |
|----|------|------|------|
| 0 | heartbeat-watch | - | HEARTBEAT |
| 1 | heartbeat-researcher | - | HEARTBEAT |
| 2 | heartbeat-analyst | - | HEARTBEAT |
| 3 | ceclaw-gateway | 18789 | OpenClaw 4.7 Gateway |
| 4 | tugcan-dashboard | 7001 | 系統監控 |
| 5 | ceclaw-admin | 3005 | 管理後台 |
| 6 | ceclaw-portal | 9000 | 入口首頁 + proxy |

### Hermes 系統（手動啟動，pop-os）

| 服務 | Port | 啟動 |
|------|------|------|
| SearXNG adapter | 2337 | bash ~/start-hermes.sh |
| hermes-agent-fork webapi | 8642 | bash ~/start-hermes.sh |
| hermes-workspace | 3000 | bash ~/start-hermes.sh |

### pop-os 額外服務

| 服務 | Port | 說明 |
|------|------|------|
| ollama | 11434 | systemd，OLLAMA_HOST=0.0.0.0 |
| OpenShell gateway ceclaw-test | 18234 | Docker K3s |
| SearXNG | 8888 | web 搜尋後端 |
| CECLAW Router | 8000 | proxy.py，systemd |

### GB10（192.168.1.91）

| 服務 | Port | 啟動方式 |
|------|------|---------|
| llama-server（Gemma 4）| 8001 | systemd ✅ |
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

## vault 記憶層（本次新增）

```
~/ceclaw/vault/（symlink → ~/.ceclaw/vault/）
  working-context.md   ← 現在做什麼/進度/下一步
  project-state.md     ← 所有專案狀態
  decisions-log.md     ← 重要決策
  daily/2026-04-10.md  ← 每日日誌
```

讀寫規則在 `~/ceclaw/config/SOUL.md`：
- 對話開始讀 working-context + project-state
- 每 3-5 次 tool call 寫 working-context
- 任務完成 flush daily log

---

## 開機後正常流程

```bash
# 1. 體檢
pm2 list
curl -s http://localhost:9000/api/status | python3 -m json.tool
curl -s http://192.168.1.91:8001/health
curl -s http://192.168.1.91:8010/health

# 2. L3 collections 確認
for col in ceclaw_company_poc ceclaw_dept_engineering ceclaw_dept_legal ceclaw_personal_kent; do
  curl -s http://192.168.1.91:6333/collections/$col | python3 -c "import json,sys; d=json.load(sys.stdin); print('$col:', d['result']['points_count'])"
done

# 3. 啟動 Hermes + SearXNG adapter
bash ~/start-hermes.sh
curl -s http://localhost:8642/health
curl -s http://localhost:2337/health

# 4. vault 確認
cat ~/.ceclaw/vault/working-context.md

# 5. OpenClaw issue 狀態（每次必查）
curl -s https://api.github.com/repos/openclaw/openclaw/issues/59598 | python3 -c "import json,sys; d=json.load(sys.stdin); print('#59598:', d['state'], d['updated_at'][:10])"
curl -s https://api.github.com/repos/openclaw/openclaw/issues/46049 | python3 -c "import json,sys; d=json.load(sys.stdin); print('#46049:', d['state'], d['updated_at'][:10])"
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
| L7 | OpenClaw-Admin | ✅ port 3005 |
| L8 | GB10 model | ✅ Gemma 4 26B MoE，ctx=262144 |
| L9 | GB10 vision | ✅ vision=true |
| L10 | lossless-claw | ✅ lcm Plugin loaded |
| L11 | Hermes Workspace | ✅ Terminal/File/Memory/Browser |
| L12 | RAG L3 Qdrant | ✅ ceclaw_* 四個 collection |
| L13 | shared_bridge | ✅ 雙向 h2o/o2h |
| L14 | 知識庫審核 UI | ✅ Admin :3005/knowledge |
| L15 | 遙控 Hermes | ✅ Admin :3005/hermes-control |
| L16 | law_advisor_api | ✅ GB10 :8010（systemd）|
| L17 | 法律 RAG 觸發 | ✅ 勞基法條文正確引用 |
| L18 | 14類 advisor 路由 | ✅ proxy.py 已補齊 |
| L19 | tw_knowledge RAG | ✅ 51,970筆，threshold 0.7 |
| L20 | CECLAW 工具意識 | ✅ web_search 正常觸發 |
| L21 | 加班費倍率 | ✅ 1.67/2.67 正確 |
| L22 | ollama systemd | ✅ 0.20.3，0.0.0.0:11434 |
| L23 | OpenShell sandbox | ✅ ceclaw-local Ready |
| L24 | L3 Qdrant ceclaw_* | ✅ 四個 collection |
| L25 | SearXNG adapter | ✅ :2337，/v1+/v2 search |
| L26 | Hermes web_search | ✅ 天氣/股價可查 |
| L27 | RAG 三層全通 | ✅ L1/L2/L3 五題驗證 |
| **L28** | **vault 記憶層** | **✅ 讀寫跨對話三關驗證，本次完成** |

---

## 已知問題

| 問題 | 狀態 | Workaround |
|------|------|-----------|
| OpenClaw #59598/#46049 | open | 鎖 4.7 |
| TPEX 上櫃公司資料不完整 | 低 | 長期待辦 |
| GB10 單 slot 長任務佔滿 | 中 | 等 B70 |
| Admin UI 中國服務殘留 | 低 | B70 後清理 |
| BM25 Hybrid Search 未開啟 | 中 | B70 後同批 |
| Hermes 手動啟動 | 低 | B70 後改 systemd |

---

## 版本歷史

| 版本 | 日期 | 主要變更 |
|------|------|---------|
| v5.7 | 2026-04-10 凌晨 | vault 記憶層、架構圖系列、upstream 策略、CDC OTA |
| v5.6 | 2026-04-09 下午 | L3 Qdrant、async RAG、SearXNG adapter、三層驗證 |
| v5.5 | 2026-04-08 深夜 | Wiki 51,969筆、分類、加班費、LLM Wiki POC、OpenShell |
