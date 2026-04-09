# CECLAW 軟工交接文件 v30.0
**更新日期：2026-04-10 凌晨**
**總工：Claude Sonnet 4.6（本對話）→ 軟工：下一個對話**
**本次對話完成：vault 記憶層、架構圖系列、銷售文件 v1.2、upstream 策略、Hermes v0.8.0 升級分析、CDC OTA 流程**

---

## ⚠️ 你是軟工，總工是 Kent（用戶）
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

## 系統現況（2026-04-10 凌晨）

### pop-os（192.168.1.210）
- OpenClaw 4.7（pm2，7 進程）— 鎖定，不升級
- CECLAW Router :8000（proxy.py，bak9 最新備份）
- Hermes webapi :8642 + workspace :3000（手動啟動）
- SearXNG adapter :2337（start-hermes.sh 啟動）
- Portal :9000 / Admin :3005
- vault：~/ceclaw/vault/（symlink → ~/.ceclaw/vault/）
- ollama 0.20.3（systemd）
- OpenShell gateway ceclaw-test（port 18234）

### GB10（192.168.1.91）
- Gemma 4 26B MoE Q8，ctx=262144，F16 KV cache，--parallel 2
- Qdrant :6333（六個 collections）
- ollama bge-m3 :11434
- law_advisor_api :8010

---

## 本次對話完成事項

| 項目 | commit | 說明 |
|------|--------|------|
| 四份交接文件 | 3326bd2 | v16/v5.6/v3.6/v29 |
| 架構圖 v6.1 | e31ad5e | SearXNG 獨立 |
| SOUL.md vault 規則 | 76f2ae0 | 讀寫時機 |
| vault 初始化 | 8eaf52e | 三關驗證通過 |
| 總架構圖 v1 | d752dc7 | 六層 SVG |
| 使用架構圖 v1 | a5a7e3d | 員工視角 |
| 功能對照圖 | bc8b0ef | OpenClaw vs Hermes |
| 銷售文件 v1.1 | e235795 | 五維度論據 |
| 銷售文件 v1.2 | 03350b0 | 異常處理鏈、常見誤解 |
| upstream 策略 | 1099c76 | 三元件策略 |
| upstream CDC OTA | e652737 | 72小時驗證流程 |

---

## 重要技術細節

### vault 架構
```
~/ceclaw/vault/（git tracked）
  ├── working-context.md
  ├── project-state.md
  ├── decisions-log.md
  └── daily/
      └── 2026-04-09.md

~/.ceclaw/vault → symlink → ~/ceclaw/vault/
（Hermes 用 ~/.ceclaw/vault/ 路徑，git 用 ~/ceclaw/vault/）
```

### Hermes P3 hook（重要）
```python
# 現在位置：~/hermes-agent-fork/webapi/routes/chat.py 第338-357行
# 觸發條件：result.get("api_calls", 0) > 1
# 功能：任務完成後自動提交到 shared_bridge

# B70後升級v0.8.0，新位置：
# gateway/platforms/api_server.py
# _handle_chat_completions 函數
# result, usage = await _compute_completion() 之後
# 工作量約30分鐘
```

### proxy.py RAG 注入順序
```python
# 1. L3 knowledge_service_v2（async，await）
# 2. L1 law_advisor_api（_LAW_KEYWORDS 條件執行）
# 3. L2 tw_knowledge（async with AsyncClient）
# 4. inject_system_prompt（含 SOUL.md）
# threshold 全部 0.7
```

### knowledge_service_v2.py 關鍵參數
```python
QDRANT_URL = "http://192.168.1.91:6333"
OLLAMA_URL = "http://192.168.1.91:11434"  # GB10 bge-m3
SIMILARITY_THRESHOLD = 0.7
VECTOR_DIM = 1024  # bge-m3
# B70後改：OLLAMA_URL = "http://localhost:11434"
```

---

## ⚠️ 優先任務（下個對話）

### P0：每次必查
```bash
curl -s https://api.github.com/repos/openclaw/openclaw/issues/59598 | python3 -c "import json,sys; d=json.load(sys.stdin); print('#59598:', d['state'], d['updated_at'][:10])"
curl -s https://api.github.com/repos/openclaw/openclaw/issues/46049 | python3 -c "import json,sys; d=json.load(sys.stdin); print('#46049:', d['state'], d['updated_at'][:10])"
```

### P1：立即
```bash
cd ~/ceclaw
# 更新四份交接文件
cp ~/Downloads/HANDOFF-2026-04-10-v17.md .
cp ~/Downloads/CECLAW_EasySetup_v5_7.md .
cp ~/Downloads/CECLAW_規格規劃說明書_v3_7.md .
cp ~/Downloads/CECLAW_軟工交接_v30_0.md .
# Hermes 完整功能圖
cp ~/Downloads/hermes_capabilities_full.svg .
git add -A && git commit -m "docs: 更新交接文件 v17/v5.7/v3.7/v30 + Hermes功能圖"
git push
```

### P2：B70 到位後
```bash
# 參考 CECLAW_L1_B70_搬家SOP_v1_3.md（已在 repo）
# 1. Intel compute-runtime v26.09
# 2. vLLM XPU tensor parallel（B70×2 TP=2，B70×4 TP=4）
# 3. Qdrant snapshot 搬家（六個 collections）
# 4. 更新 IP：192.168.1.91 → localhost
# 5. OpenShell sandbox template
# 6. Hermes v0.8.0 升級 + P3 hook 移植到 gateway/builtin_hooks/
# 7. Reranker（bge-reranker-v2-m3）
# 8. 全系統體檢 + 72小時燒機
```

---

## Debug 指引

### vault 不工作
```bash
# 確認 symlink
ls -la ~/.ceclaw/vault
ls -la ~/ceclaw/vault/
# 確認 SOUL.md 有 vault 段落
grep "vault" ~/ceclaw/config/SOUL.md
# 手動測試 Hermes 讀 vault
# 在 Hermes UI 說：「請讀取 working-context.md」
```

### L3 RAG 不觸發
```bash
cd ~/ceclaw && .venv/bin/python3 -c "from router import proxy; print('_KS_AVAILABLE:', proxy._KS_AVAILABLE)"
find ~/ceclaw -name "*.pyc" -delete
sudo systemctl restart ceclaw-router
```

### SearXNG adapter 不工作
```bash
curl -s http://localhost:2337/health
kill $(lsof -ti:2337) 2>/dev/null && sleep 1
cd ~/ceclaw/router && source ../.venv/bin/activate && python3 searxng_adapter.py &
```

### shared_bridge 不觸發
```bash
# 確認 P3 hook 還在
grep -n "shared_bridge\|api_calls" ~/hermes-agent-fork/webapi/routes/chat.py
# 確認 Hermes 用 :8000 作為 base_url
cat ~/.hermes/config.yaml | grep base_url
```

### proxy.py 改動沒生效
```bash
find ~/ceclaw -name "*.pyc" -delete
find ~/ceclaw -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
sudo systemctl restart ceclaw-router && sleep 3
```

---

## 關鍵 URL & Token

```
Router Bearer：97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759
Admin 登入：admin/admin
GitHub：kentgeeng/ceclaw（master）
GB10 SSH：ssh zoe_gb@192.168.1.91
pop-os：192.168.1.210
SearXNG adapter：http://localhost:2337
OpenShell gateway：https://127.0.0.1:18234
```

---

## 重啟規則

```bash
sudo systemctl restart ceclaw-router    # proxy.py
bash ~/start-hermes.sh                  # Hermes + SearXNG adapter
pm2 restart ceclaw-gateway              # OpenClaw
sudo systemctl restart ollama           # pop-os ollama
ssh zoe_gb@192.168.1.91 "sudo systemctl restart law-advisor"
ssh zoe_gb@192.168.1.91 "sudo systemctl restart llama-server"
```

---

## 已知問題

| 問題 | 嚴重度 | Workaround |
|------|--------|-----------|
| OpenClaw #59598/#46049 未修 | 低 | 鎖 4.7 |
| TPEX 上櫃資料不完整 | 低 | 長期待辦 |
| GB10 單 slot 長任務佔滿 | 中 | 等 B70 |
| Admin UI 中國服務殘留 | 低 | B70 後清理 |
| BM25 Hybrid Search 未開啟 | 中 | B70 後同批 |
| L3+L2 仍為串行 | 低 | B70 後 asyncio |
| Hermes 手動啟動 | 低 | B70 後 systemd |

---

## 版本歷史

| 版本 | 日期 | 主要變更 |
|------|------|---------|
| v30.0 | 2026-04-10 凌晨 | vault、架構圖、銷售文件、upstream 策略、CDC OTA |
| v29.0 | 2026-04-09 下午 | L3 遷移、async RAG、SearXNG、五題驗證 |
| v28.0 | 2026-04-08 深夜 | Wiki、分類、RAG 體檢、LLM Wiki POC |
