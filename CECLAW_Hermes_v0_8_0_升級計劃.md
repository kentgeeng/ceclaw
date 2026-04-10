# CECLAW Hermes v0.8.0 升級計劃（已完成）
**建立日期：2026-04-10**
**完成日期：2026-04-11 凌晨**
**狀態：✅ 升級完成，⚠️ Workspace 功能仍有問題**

---

## ✅ 升級完成清單

| 項目 | commit | 狀態 |
|------|--------|------|
| staging-v0.8.0 分支建立 | - | ✅ |
| upstream v2026.4.8 merge | - | ✅ |
| pip 安裝（bootstrap.pypa.io）| - | ✅ |
| config.yaml api_server enabled | ~/.hermes/config.yaml | ✅ |
| start-hermes.sh 更新（gateway.run）| ~/start-hermes.sh | ✅ |
| P3 hook 移植（626行）| 6e43241d | ✅ |
| api_calls 條件修正（>1→>=1）| main | ✅ |
| staging→main merge | 8215d359 | ✅ |
| Sessions stub（5個endpoint）| main | ✅ |
| Sessions格式修正 | main | ✅ |
| health check 驗證 | - | ✅ |
| bridge 生成驗證 | - | ✅ |

---

## 現在的啟動方式

```bash
# ~/.hermes/config.yaml（必須有）
platforms:
  api_server:
    enabled: true

# start-hermes.sh 關鍵行
API_SERVER_PORT=8642 \
HERMES_INFERENCE_PROVIDER=custom \
HERMES_BASE_URL=http://localhost:8000/v1 \
HERMES_API_KEY=97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759 \
venv/bin/python -m gateway.run &

# 快速啟動
bash ~/start-hermes.sh
sleep 5
curl -s http://localhost:8642/health
# 預期：{"status": "ok", "platform": "hermes-agent"}
```

---

## 現在的 Sessions API（api_server.py 1063行起）

```python
# GET /api/sessions → {"items": [], "total": 0}
# POST /api/sessions → {"session": {"id":uuid, "key":uuid, "friendlyId":..., "title":null, ...}}
# GET /api/sessions/{id} → {"session": {...}}
# GET /api/sessions/{id}/messages → {"items": [], "total": 0}
# POST /api/sessions/{id}/chat/stream → SSE（有問題，workspace slice錯誤）
# GET /api/history → {"sessionKey":..., "sessionId":..., "messages":[]}
```

---

## ⚠️ 未完成（下個對話繼續）

### Workspace 三個核心問題

**1. No models available**
```
原因：/api/models route 有 isAuthenticated 401
檔案：~/hermes-workspace/src/routes/api/models.ts（107行）
     ~/hermes-workspace/src/server/auth-middleware.ts
Debug：cat ~/hermes-workspace/src/server/auth-middleware.ts
修法：加 localhost bypass 或找 .env 開關
```

**2. chat stream slice 錯誤**
```
原因：SSE data 格式不對，undefined.slice() 爆炸
現在的 stub：api_server.py 1088行 _handle_session_chat_stream
正確格式：
  event: message\ndata: {"delta": "..."}\n\n
  data: [DONE]\n\n
Debug：
  curl -N -X POST http://localhost:8642/api/sessions/test/chat/stream \
    -H "Content-Type: application/json" -d '{"message":"你好"}'
```

**3. sessions 側欄空白**
```
原因：stub 永遠回空
修法：讀取 Hermes 真實 session DB
Debug：find ~/.hermes -name "*.db"
       grep -rn "class SessionDB" ~/hermes-agent-fork/gateway/ --include="*.py"
```

---

## P3 hook 詳細（626行）

```python
# P3: auto-submit to shared_bridge if task completed with tools
# 條件：api_calls >= 1（不是 > 1）AND completed AND final_response 非空
# 動態 import shared_bridge
# 寫入：~/.ceclaw/knowledge/bridge/shared/YYYYMMDD_HHMMSS_hermes_xxxx.json
# 驗證：ls -la ~/.ceclaw/knowledge/bridge/shared/ | tail -3

# 觸發測試
curl -s http://localhost:8642/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"hermes-agent","messages":[{"role":"user","content":"用ls指令列出目錄"}]}'
```

---

## B70 後繼續做

1. P3 hook 重構為 builtin_hooks/ plugin（目前直改源碼）
2. Hermes systemd 常駐（pnpm build + systemd，現在是手動啟動）
3. OpenShell sandbox template
4. 多用戶 Hermes Profiles（每員工獨立 vault + Hermes instance）

---

## 回滾方式（如果升級出問題）

```bash
pkill -f hermes
kill $(lsof -ti:8642) 2>/dev/null

# 備份還在
ls ~/hermes-agent-fork.bak-20260410
cp -r ~/hermes-agent-fork.bak-20260410 ~/hermes-agent-fork

bash ~/start-hermes.sh
curl -s http://localhost:8642/health
```

---

## 版本歷史
| 版本 | 日期 | 說明 |
|------|------|------|
| v1.1 | 2026-04-11 | 升級完成，記錄未完成workspace問題 |
| v1.0 | 2026-04-10 | 初版升級計劃 |
