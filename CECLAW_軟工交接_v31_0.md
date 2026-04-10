# CECLAW 軟工交接文件 v31.0
**更新日期：2026-04-11 凌晨**
**總工：Claude Sonnet 4.6（本對話）→ 軟工：下一個對話**
**本次完成：Hermes v0.8.0升級、P3 hook移植、Admin去中國化、Pixel Office、Sessions stub、Portal修復**
**⚠️ 未完成核心問題：Hermes Workspace models/sessions/chat stream（必修）**

---

## ⚠️ 你是軟工，總工是 Kent（用戶）
- 遇到困難找總工
- 每次動手前提 SOP-002，等 Kent 確認才動
- 不改 master 檔案，先備份
- 每完成一步：`git add -A && git commit -m "..."`
- 只做被要求的事

## SOP-002 格式
```
【要改什麼】【為什麼】【改完Kent會看到什麼】
```

---

## 系統現況（2026-04-11 凌晨）

### pop-os（192.168.1.210 / 172.25.0.12）
| 服務 | Port | 狀態 | 啟動方式 |
|------|------|------|---------|
| ceclaw-gateway (OpenClaw 4.7) | 18789 | pm2 online | pm2 restart ceclaw-gateway |
| CECLAW Router | 8000 | systemd | sudo systemctl restart ceclaw-router |
| ceclaw-admin | 3005 | pm2 online | pm2 restart ceclaw-admin |
| ceclaw-portal | 9000 | pm2 online | pm2 restart ceclaw-portal |
| ceclaw-office | 5180 | pm2 online | pm2 restart ceclaw-office |
| ceclaw-bot-review (pixel office) | 4567 | pm2 online | pm2 restart ceclaw-bot-review |
| Hermes gateway v0.8.0 | 8642 | 手動 | bash ~/start-hermes.sh |
| Hermes workspace | 3000 | 手動 | bash ~/start-hermes.sh |
| SearXNG adapter | 2337 | 手動 | bash ~/start-hermes.sh |
| ollama | 11434 | systemd | sudo systemctl restart ollama |
| SearXNG | 8888 | Docker | docker ps |

### GB10（192.168.1.91）
| 服務 | Port | 啟動 |
|------|------|------|
| llama-server (Gemma 4 26B MoE Q8) | 8001 | ssh zoe_gb@192.168.1.91 "sudo systemctl restart llama-server" |
| Qdrant | 6333 | ssh zoe_gb@192.168.1.91 "docker restart qdrant" |
| ollama (bge-m3) | 11434 | ssh zoe_gb@192.168.1.91 "sudo systemctl restart ollama" |
| law_advisor_api | 8010 | ssh zoe_gb@192.168.1.91 "sudo systemctl restart law-advisor" |

---

## 本次對話完成事項

| 項目 | commit | 位置 | 說明 |
|------|--------|------|------|
| Admin v0.2.7 upstream merge | d83d77a | ~/openclaw-admin | 保留CECLAW修改 |
| Pixel Office iframe | ac64bc2 | views/myworld/MyWorldPage.vue | port 4567 |
| 頻道管理去中國化 | 0d1f4be | views/channels/ChannelsPage.vue | 移除QQ/飛書/釘釘/企業微信 |
| 頻道管理→Control UI | 1be178d | views/channels/ | 按鈕連:18789/channels?token=... |
| Portal hermes-exec修復 | d3eccb1 | ~/ceclaw-portal/status.py | /v1/chat/completions |
| Hermes v0.8.0升級完成 | 8215d359 | ~/hermes-agent-fork/ main | gateway.run，config.yaml |
| P3 hook移植 | 6e43241d | api_server.py 626行 | api_calls>=1觸發 |
| Sessions stub（5個endpoint）| main | api_server.py 1063行起 | items/total/session格式 |
| Sessions messages stub | main | api_server.py 1083行 | items格式 |
| pip安裝到venv | main | ~/hermes-agent-fork/venv/ | bootstrap.pypa.io |
| config.yaml api_server | ~/.hermes/config.yaml | platforms: api_server: enabled: true |
| start-hermes.sh更新 | ~/start-hermes.sh | -m gateway.run |
| Auto Demo 404修復 | pm2 restart | ceclaw-portal | 打/v1/chat/completions |
| 多用戶Hermes SOP | c878a84 | ~/ceclaw/ | CECLAW_多用戶Hermes_SOP_v1_0.md |

---

## ⚠️ 優先任務（下個對話必修，全是核心功能）

### P0：Hermes Workspace 修復

**Task 1：No models available**
```
原因：workspace /api/models route 有 isAuthenticated 401
關鍵檔：~/hermes-workspace/src/routes/api/models.ts（107行）
       ~/hermes-workspace/src/server/auth-middleware.ts

Debug：
  cat ~/hermes-workspace/src/server/auth-middleware.ts
  curl -sv http://172.25.0.12:3000/api/models 2>&1 | head -20
  grep -n "bypass\|dev\|local\|DISABLE\|DEV" ~/hermes-workspace/src/server/auth-middleware.ts

修法：
  1. auth-middleware.ts 加 localhost bypass（推薦）
  2. models.ts 拿掉 isAuthenticated（暴力但 workspace 是 local only）
```

**Task 2：chat stream slice 錯誤**
```
原因：SSE data 格式不對，undefined.slice() 爆炸
關鍵檔：~/hermes-agent-fork/gateway/platforms/api_server.py 1088行
       ~/hermes-workspace/src/screens/chat/hooks/use-streaming-message.ts 396行

正確 SSE 格式：
  event: message\ndata: {"delta": "文字"}\n\n
  data: [DONE]\n\n

Debug：
  curl -N -X POST http://localhost:8642/api/sessions/test/chat/stream \
    -H "Content-Type: application/json" -d '{"message":"你好"}'
  看輸出格式是否正確
```

**Task 3：sessions 側欄**
```
原因：stub 永遠回空
Debug：find ~/.hermes -name "*.db"
修法：讀取 Hermes 真實 session DB
```

### P1：立即 commit
```bash
cd ~/hermes-agent-fork
git add gateway/platforms/api_server.py
git commit -m "feat: sessions stub + P3 hook v0.8.0 完整版"

cd ~/ceclaw
git add -A && git commit -m "docs: 交接文件 v18，Hermes v0.8.0 完成"
git push
```

### P2：B70 到位後
- vLLM XPU 搬家（參考 CECLAW_L1_B70_搬家SOP_v1_4.md）
- Hermes P3 hook 重構為 builtin_hooks/
- OpenShell sandbox template
- 多用戶 Hermes Profiles
- Hermes systemd
- BM25 / Reranker / Graph RAG
- OpenClaw 升級（等 #59598/#46049）

---

## 重要技術細節

### Hermes v0.8.0 啟動機制
```bash
# ~/.hermes/config.yaml 必須有
platforms:
  api_server:
    enabled: true

# 啟動指令（在 start-hermes.sh）
API_SERVER_PORT=8642 \
HERMES_INFERENCE_PROVIDER=custom \
HERMES_BASE_URL=http://localhost:8000/v1 \
HERMES_API_KEY=97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759 \
venv/bin/python -m gateway.run &
```

### P3 hook（api_server.py 626行）
```python
# P3: auto-submit to shared_bridge if task completed with tools
if (result.get("api_calls", 0) >= 1
    and result.get("completed")
    and result.get("final_response")):
    # 動態 import，寫入 ~/.ceclaw/knowledge/bridge/shared/
```

### proxy.py RAG 注入順序
```
query → CECLAW Router :8000
  ① L3 Qdrant（ceclaw_* collections）
  ② L2 tw_knowledge（51,970筆，12類）
  ③ L1 law_advisor_api（_LAW_KEYWORDS 條件）
  ④ inject SOUL.md → Gemma 4（GB10 :8001）
```

### 關鍵設定檔
```yaml
# ~/.hermes/config.yaml
model:
  provider: custom
  default: ceclaw
  base_url: http://localhost:8000/v1
  api_key: 97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759
web:
  backend: firecrawl
platform_toolsets:
  webchat:
    - web
    - terminal
    - file
    - memory
    - session_search
platforms:
  api_server:
    enabled: true
```

---

## Debug 指引

### Hermes 無法啟動
```bash
kill $(lsof -ti:8642) 2>/dev/null
kill $(lsof -ti:3000) 2>/dev/null
sleep 2
bash ~/start-hermes.sh
curl -s http://localhost:8642/health
```

### P3 hook 驗證
```bash
curl -s http://localhost:8642/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"hermes-agent","messages":[{"role":"user","content":"用ls指令列出目錄"}]}'
ls -la ~/.ceclaw/knowledge/bridge/shared/ | tail -3
# 應該有新檔案
```

### shared_bridge 不觸發
```bash
grep -n "shared_bridge\|api_calls" ~/hermes-agent-fork/gateway/platforms/api_server.py | head -5
```

### proxy.py 改動沒生效
```bash
find ~/ceclaw -name "*.pyc" -delete
find ~/ceclaw -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
sudo systemctl restart ceclaw-router
```

### RAG log
```bash
grep -E "RAG query_text|RAG hits|RAG: injected|RAG query failed" ~/.ceclaw/router.log | tail -20
```

---

## 關鍵 Token & URL
```
Router Bearer：97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759
GitHub：kentgeeng/ceclaw（master）
GB10 SSH：ssh zoe_gb@192.168.1.91
pop-os：192.168.1.210 / 172.25.0.12
Hermes Workspace：http://172.25.0.12:3000
Pixel Office：http://172.25.0.12:4567
Admin：http://172.25.0.12:3005
Portal：http://172.25.0.12:9000
```

---

## repo 檔案清單（~/ceclaw/）
| 檔案 | 說明 |
|------|------|
| router/proxy.py | CECLAW Router，RAG注入 |
| router/knowledge_service_v2.py | L3 Qdrant async |
| router/searxng_adapter.py | Firecrawl→SearXNG |
| config/SOUL.md | Hermes SOUL，vault規則 |
| vault/ | 工作記憶（symlink→~/.ceclaw/vault/）|
| CECLAW_L1_B70_搬家SOP_v1_4.md | B70搬家SOP |
| CECLAW_多用戶Hermes_SOP_v1_0.md | 多用戶SOP |

---

## 版本歷史
| 版本 | 日期 | 主要變更 |
|------|------|---------|
| v31.0 | 2026-04-11 凌晨 | Hermes v0.8.0、P3 hook、Admin去中國化、Sessions stub |
| v30.0 | 2026-04-10 凌晨 | vault、架構圖、銷售文件、upstream策略、CDC OTA |
| v29.0 | 2026-04-09 下午 | L3遷移、async RAG、SearXNG、五題驗證 |
