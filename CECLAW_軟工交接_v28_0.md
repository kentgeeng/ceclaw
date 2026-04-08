# CECLAW 軟工交接文件 v28.0
**更新日期：2026-04-08 深夜**
**總工：Claude Sonnet 4.6（本對話）→ 軟工：下一個對話**
**本次對話完成：Wiki完成51,969筆+12類分類、RAG大體檢5/5、加班費修正、LLM Wiki POC四關全通、OpenShell sandbox二次reboot、RotorQuant調查、ollama 0.20.3修復**

---

## ⚠️ 你是軟工，總工是Kent（用戶）
- 遇到困難找總工
- 每次動手前必須提 SOP-002
- 不改 master 檔案，先備份
- 每完成一步：`git add -A && git commit -m "..."`

---

## SOP-002 格式
```
【要改什麼】
【為什麼】
【改完Kent會看到什麼】
```

---

## 系統現況（2026-04-08 深夜）

### pop-os（192.168.1.210 / 172.25.0.12）
- OpenClaw 4.7（pm2，7進程）
- CECLAW Router :8000（proxy.py，bak8最新備份）
- Hermes webapi :8642 + workspace :3000（手動啟動）
- Portal :9000 / Admin :3005
- **ollama 0.20.3（systemd，OLLAMA_HOST=0.0.0.0:11434）**
- **OpenShell gateway ceclaw-test（port 18234）**
- **LLM Wiki POC（~/llm-wiki-poc/）**

### GB10（192.168.1.91）
- Gemma 4 26B MoE Q8，ctx=262144，llama-server :8001
- Qdrant :6333
  - tw_laws：221,599條（18類）
  - tw_knowledge：**51,969筆（完成，12類分類）**
- ollama bge-m3 :11434（systemd）
- law_advisor_api :8010（systemd）

---

## 本次對話完成事項

| 項目 | 說明 |
|------|------|
| Gateway port衝突修復 | kill 舊進程，pm2 restart |
| Wiki ingestion確認 | 51,969筆完成 |
| RAG大體檢5/5 | 搶孤/聯發科/太魯閣/歹勢/鬼月 |
| git push | 已推，master=origin |
| 加班費倍率修正 | tw_knowledge寫入，1.67/2.67正確 |
| P3 TPEX全被擋 | 長期待辦 |
| tw_knowledge 12類分類 | 12,943筆重分類 |
| LLM Wiki POC四關 | ~/llm-wiki-poc/，⚠️待驗證正常 |
| OpenShell sandbox | ceclaw-local，二次reboot存活 |
| RotorQuant/TurboQuant | B70不可用（CUDA only） |
| ollama升級+修復 | 0.20.3，systemd override |

---

## ⚠️ 優先任務（下個對話）

### P0：ollama signin
```bash
ollama --version  # 確認 0.20.3
ollama signin     # 會開瀏覽器
# 登入後測試
ollama run gemma4:31b-cloud
```

### P1：每次必查
```bash
curl -s https://api.github.com/repos/openclaw/openclaw/issues/59598 | python3 -c "import json,sys; d=json.load(sys.stdin); print('#59598:', d['state'], d['updated_at'][:10])"
curl -s https://api.github.com/repos/openclaw/openclaw/issues/46049 | python3 -c "import json,sys; d=json.load(sys.stdin); print('#46049:', d['state'], d['updated_at'][:10])"
```

### P2：git commit 文件更新
```bash
cd ~/ceclaw
# 把新的交接文件複製進去
git add -A && git commit -m "docs: 更新交接文件 v15/v5.5/v3.5/v28"
git push
```

### P3：B70到位後（週五/下週一）
```
1. Intel compute-runtime v26.09 安裝
2. vLLM XPU Docker（從source build，支援Gemma 4）
3. git clone kentgeeng/ceclaw
4. Qdrant snapshot搬家：
   ssh zoe_gb@192.168.1.91
   curl -X POST http://localhost:6333/collections/tw_laws/snapshots
   curl -X POST http://localhost:6333/collections/tw_knowledge/snapshots
5. OpenShell sandbox template建立
6. 全系統體檢
參考：https://github.com/Hal9000AIML/arc-pro-b70-inference-setup
```

---

## 重要技術細節

### proxy.py RAG注入順序
```
1. Chroma RAG（公司/部門/個人）
2. 法律RAG（tw_laws，law_advisor_api）
3. tw_knowledge RAG（GB10 Qdrant）
4. inject_system_prompt（含SOUL.md）
```

### tw_knowledge RAG
```python
# endpoint: http://192.168.1.91:6333/collections/tw_knowledge/points/search
# embedding: http://192.168.1.91:11434/api/embeddings（bge-m3）
# score_threshold: 0.5（若不觸發降至0.45）
# limit: 3
```

### LLM Wiki POC
```bash
cd ~/llm-wiki-poc
python3 ingest.py raw/文件.md    # Gemma4 http://192.168.1.91:8001
python3 query.py "問題"
python3 lint.py                   # 含⚠️待驗證規則
```

### OpenShell Sandbox
```bash
# 啟動gateway（若未啟動）
openshell gateway start --name ceclaw-test --port 18234

# 查看
openshell term --gateway ceclaw-test

# 連入
openshell sandbox connect ceclaw-local --gateway ceclaw-test

# 自訂image最低需求：
# - sandbox user/group
# - iproute2
# openshell-sandbox binary由gateway自動side-load
```

### ollama systemd override
```bash
cat /etc/systemd/system/ollama.service.d/override.conf
# [Service]
# Environment="OLLAMA_HOST=0.0.0.0:11434"
```

---

## Debug 指引

### tw_knowledge RAG不觸發
```bash
tail -20 ~/.ceclaw/router.log | grep "tw_knowledge"
# 應看到：tw_knowledge: injected X chunks
# 若沒有：
# 1. curl http://192.168.1.91:6333/collections/tw_knowledge
# 2. curl http://192.168.1.91:11434/api/tags（bge-m3在線？）
# 3. score_threshold=0.5過高，改0.45
```

### law_advisor_api掛掉
```bash
curl -s http://192.168.1.91:8010/health
ssh zoe_gb@192.168.1.91 "sudo systemctl restart law-advisor && sleep 2"
curl -s http://192.168.1.91:8010/health
```

### OpenShell sandbox crash
```bash
docker exec openshell-cluster-ceclaw-test kubectl logs ceclaw-local -n openshell -c agent 2>&1 | tail -10
# 常見原因：缺sandbox user、缺iproute2
```

### ollama掛掉
```bash
sudo systemctl status ollama
sudo journalctl -u ollama -n 20 --no-pager
# 若permission denied：
sudo mkdir -p /usr/share/ollama/.ollama
sudo chown -R ollama:ollama /usr/share/ollama
sudo systemctl restart ollama
```

### Gateway port衝突
```bash
ss -tlnp | grep 18789
# 若有兩個pid：
pkill -f "openclaw-gateway"
pm2 restart ceclaw-gateway
```

### Gemma4 timeout
```bash
tail -50 ~/.ceclaw/router.log | grep "timeout\|TimeoutError"
# proxy.py已有workaround，若還爆：
sudo systemctl restart ceclaw-router
```

---

## 完整體檢指令

```bash
# pop-os
pm2 list && \
curl -s http://localhost:9000/api/status | python3 -m json.tool && \
curl -s http://192.168.1.91:8001/health && \
curl -s http://192.168.1.91:8010/health && \
ss -tlnp | grep -E "3005|8000|18789|8642|3000|9000|11434"

# Qdrant
curl -s http://192.168.1.91:6333/collections/tw_laws | python3 -c "import json,sys; d=json.load(sys.stdin); print('tw_laws:', d['result']['points_count'])"
curl -s http://192.168.1.91:6333/collections/tw_knowledge | python3 -c "import json,sys; d=json.load(sys.stdin); print('tw_knowledge:', d['result']['points_count'])"

# ollama
curl -s http://172.25.0.12:11434/api/tags | python3 -c "import json,sys; [print(m['name']) for m in json.load(sys.stdin)['models']]"

# OpenShell
openshell sandbox list --gateway ceclaw-test

# OpenClaw issues
curl -s https://api.github.com/repos/openclaw/openclaw/issues/59598 | python3 -c "import json,sys; d=json.load(sys.stdin); print('#59598:', d['state'])"
curl -s https://api.github.com/repos/openclaw/openclaw/issues/46049 | python3 -c "import json,sys; d=json.load(sys.stdin); print('#46049:', d['state'])"
```

---

## 關鍵URL & Token

```
Router Bearer：97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759
Admin登入：admin/admin
GitHub：kentgeeng/ceclaw（master，已push）
GB10 SSH：ssh zoe_gb@192.168.1.91
pop-os：192.168.1.210 / 172.25.0.12
ollama：http://172.25.0.12:11434
OpenShell gateway：https://127.0.0.1:18234
```

---

## 重啟規則

```bash
sudo systemctl restart ceclaw-router    # proxy.py
bash ~/start-hermes.sh                  # Hermes
pm2 restart ceclaw-gateway              # OpenClaw
sudo systemctl restart ollama           # ollama
openshell gateway start --name ceclaw-test --port 18234  # OpenShell
ssh zoe_gb@192.168.1.91 "sudo systemctl restart law-advisor"  # GB10
```

---

## 已知問題

| 問題 | 嚴重度 | Workaround |
|------|--------|-----------|
| OpenClaw #59598/#46049 open | 中 | pin 4.7 |
| TPEX上櫃資料不完整 | 低 | 長期待辦 |
| gemma4:31b-cloud需登入 | 低 | ollama signin |
| GB10單slot長任務佔滿 | 中 | 等B70 |
| Admin UI中國服務殘留 | 低 | B70後清理 |
| RotorQuant B70不可用 | 低 | 等vLLM社群 |

---

## 版本歷史

| 版本 | 日期 | 主要變更 |
|------|------|---------|
| v28.0 | 2026-04-08 深夜 | Wiki完成、分類、RAG體檢、加班費、LLM Wiki POC、OpenShell、ollama修復 |
| v27.0 | 2026-04-08 下午 | OpenClaw 4.7、tw_knowledge、14類advisor、Gemma4三關 |
| v26.0 | 2026-04-08 凌晨 | tw_laws全分類、systemd |
