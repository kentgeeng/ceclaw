# CECLAW EasySetup v5.5
**更新日期：2026-04-08 深夜**

---

## ⚠️ 架構現況（2026-04-08 深夜最新）

**OpenClaw 4.7 ✅**
**tw_knowledge 51,969筆（完成，12類分類）✅ 本次更新**
**tw_knowledge RAG接入 proxy.py ✅**
**加班費倍率精確化（1.67/2.67）✅ 本次完成**
**RAG大體檢5/5通過 ✅ 本次完成**
**LLM Wiki POC四關全通 ✅ 本次新增**
**OpenShell sandbox二次reboot存活 ✅ 本次新增**
**ollama 0.20.3 + systemd 0.0.0.0 ✅ 本次修復**
**法律小顧問 RAG（221,599條，18類）✅**
**14類 advisor mapping ✅**
**shared_bridge雙向 ✅**
**RAG Chroma三層 ✅**
**Portal v2.1 / Admin :3005 ✅**
**GB10 Gemma 4 26B MoE Q8，ctx=262144 ✅**

---

## 服務清單

### CECLAW 主系統（pm2，pop-os）

| id | name | port | 說明 |
|----|------|------|------|
| 1 | heartbeat-watch | - | HEARTBEAT |
| 2 | heartbeat-researcher | - | HEARTBEAT |
| 3 | heartbeat-analyst | - | HEARTBEAT |
| 4 | ceclaw-gateway | 18789 | OpenClaw 4.7 Gateway |
| 13 | tugcan-dashboard | 7001 | 系統監控 |
| 14 | ceclaw-admin | 3005 | 管理後台 |
| 17 | ceclaw-portal | 9000 | 入口首頁 + proxy |

### 新增服務（pop-os）

| 服務 | Port | 說明 |
|------|------|------|
| ollama | 11434 | systemd，OLLAMA_HOST=0.0.0.0 |
| OpenShell gateway ceclaw-test | 18234 | Docker K3s |
| OpenShell sandbox ceclaw-local | — | Ubuntu+python3+iproute2 |

### Hermes 系統（手動啟動，pop-os）

| 服務 | Port | 啟動 |
|------|------|------|
| hermes-agent-fork webapi | 8642 | `bash ~/start-hermes.sh` |
| hermes-workspace | 3000 | `bash ~/start-hermes.sh` |

### 法律顧問系統（GB10，192.168.1.91）

| 服務 | Port | 啟動方式 |
|------|------|---------|
| llama-server（Gemma 4）| 8001 | systemd ✅ |
| Qdrant（tw_laws + tw_knowledge）| 6333 | Docker ✅ |
| ollama（bge-m3）| 11434 | systemd ✅ |
| law_advisor_api | 8010 | systemd ✅ |

---

## 開機後正常流程

```bash
# 1. 體檢
pm2 list
curl -s http://localhost:9000/api/status | python3 -m json.tool
curl -s http://192.168.1.91:8001/health
curl -s http://192.168.1.91:8010/health

# 2. tw_knowledge確認
curl -s http://192.168.1.91:6333/collections/tw_knowledge | python3 -c "import json,sys; d=json.load(sys.stdin); print('tw_knowledge:', d['result']['points_count'])"
# 應為 51,969

# 3. 啟動 Hermes
bash ~/start-hermes.sh
curl -s http://localhost:8642/health

# 4. ollama確認
curl -s http://172.25.0.12:11434/api/tags | python3 -c "import json,sys; [print(m['name']) for m in json.load(sys.stdin)['models']]"

# 5. OpenClaw issue狀態（每次必查）
curl -s https://api.github.com/repos/openclaw/openclaw/issues/59598 | python3 -c "import json,sys; d=json.load(sys.stdin); print('#59598:', d['state'], d['updated_at'][:10])"
curl -s https://api.github.com/repos/openclaw/openclaw/issues/46049 | python3 -c "import json,sys; d=json.load(sys.stdin); print('#46049:', d['state'], d['updated_at'][:10])"
```

---

## 健康檢查清單

| 層 | 項目 | 正常 |
|---|------|------|
| L0 | CECLAW身份 | ✅ 我是 CECLAW 企業 AI 助手 |
| L1 | gateway pm2 | ✅ online（OpenClaw 4.7）|
| L2 | Router | ✅ gb10-llama healthy |
| L3 | GB10 health | ✅ {"status":"ok"} |
| L4 | Portal 四燈 | ✅ 全綠 |
| L5 | web_search | ✅ SearXNG :8888 |
| L6 | exec tool | ✅ workspace可寫 |
| L7 | OpenClaw-Admin | ✅ port 3005 |
| L8 | GB10 model | ✅ Gemma 4 26B MoE，ctx=262144 |
| L9 | GB10 vision | ✅ vision=true |
| L10 | lossless-claw | ✅ lcm Plugin loaded |
| L11 | Hermes Workspace | ✅ Terminal/File/Memory/Browser |
| L12 | RAG Chroma | ✅ 三層，query正常 |
| L13 | shared_bridge | ✅ 雙向h2o/o2h |
| L14 | 知識庫審核UI | ✅ Admin :3005/knowledge |
| L15 | 遙控Hermes | ✅ Admin :3005/hermes-control |
| L16 | law_advisor_api | ✅ GB10 :8010（systemd）|
| L17 | 法律RAG觸發 | ✅ 勞基法條文正確引用 |
| L18 | 14類advisor路由 | ✅ proxy.py已補齊 |
| L19 | tw_knowledge RAG | ✅ 51,969筆，12類分類 |
| L20 | CECLAW工具意識 | ✅ Gemma 4知道exec/search/git |
| **L21** | **加班費倍率** | **✅ 1.67/2.67正確 本次修復** |
| **L22** | **ollama systemd** | **✅ 0.20.3，0.0.0.0:11434 本次修復** |
| **L23** | **OpenShell sandbox** | **✅ ceclaw-local Ready，reboot存活 本次新增** |

---

## tw_knowledge 知識庫（最新）

| 分類 | 筆數 |
|------|------|
| 台灣文化地理（保底）| 34,706 |
| 台灣地理 | 5,320 |
| 台灣上市公司 | 3,280 |
| 台灣歷史 | 1,493 |
| 台灣教育學術 | 1,181 |
| 台灣政治 | 988 |
| 台灣宗教信仰 | 974 |
| 台灣交通建設 | 930 |
| 台灣體育 | 629 |
| 台灣藝術文化 | 493 |
| 台灣產業經濟 | 482 |
| 台灣人物 | 374 |
| 台灣上櫃公司 | 993 |
| 台灣飲食+手工整理 | ~126 |
| **總計** | **51,969** |

---

## LLM Wiki POC（~/llm-wiki-poc/）

Karpathy pattern 實作，三層架構：
- **Raw Sources**（raw/）→ 唯讀原始文件
- **The Wiki**（wiki/）→ LLM編譯markdown
- **Schema**（schema.md + schema.yaml）→ 規則

```bash
cd ~/llm-wiki-poc
python3 ingest.py raw/文件.md  # 編譯
python3 query.py "問題"         # 查詢
python3 lint.py                 # 健康檢查（含⚠️待驗證）
```

---

## 已知問題

| 問題 | 狀態 | Workaround |
|------|------|-----------|
| OpenClaw #59598/#46049 open | 中 | pin 4.7 |
| TPEX上櫃公司資料不完整 | 低 | 長期待辦 |
| gemma4:31b-cloud需登入 | 低 | ollama signin |
| GB10單slot長任務佔滿 | 中 | 等B70 |
| Admin UI中國服務殘留 | 低 | B70到後清理 |
| RotorQuant B70不可用 | 低 | 等vLLM社群 |

---

## 版本歷史

| 版本 | 日期 | 主要變更 |
|------|------|---------|
| v5.5 | 2026-04-08 深夜 | Wiki完成51,969筆、分類12類、加班費修正、LLM Wiki POC、OpenShell POC、ollama修復 |
| v5.4 | 2026-04-08 下午 | OpenClaw 4.7、tw_knowledge、RAG接入、SYSTEM_PROMPT完整版 |
| v5.3 | 2026-04-08 凌晨 | tw_laws全分類、18類advisor、systemd常駐確認 |
