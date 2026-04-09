# CECLAW Hermes v0.8.0 升級計劃
**建立日期：2026-04-10**
**執行時機：B70 到位當天，搬家前執行**

---

## 升級前準備

```bash
# 1. 確認 upstream remote（已存在就跳過 add）
cd ~/hermes-agent-fork
git remote -v
# 若無 upstream：git remote add upstream https://github.com/NousResearch/hermes-agent.git
# 若已存在：直接執行下一行
git fetch upstream v2026.4.8

# 2. 記錄 P3 hook 現況（備份用）
grep -n "shared_bridge\|api_calls" ~/hermes-agent-fork/webapi/routes/chat.py > ~/ceclaw/p3_hook_backup.txt
sed -n '330,365p' ~/hermes-agent-fork/webapi/routes/chat.py >> ~/ceclaw/p3_hook_backup.txt
git -C ~/ceclaw add -A && git commit -m "docs: P3 hook 備份，升級前快照"

# 3. 記錄 shared_bridge 升級前時間戳（升級後比對用）
ls -la ~/.ceclaw/knowledge/bridge/shared/ > ~/ceclaw/bridge_before_upgrade.txt

# 4. 確認現在 shared_bridge 正常
curl -s http://localhost:8642/health
```

---

## 升級步驟

```bash
# Step 1：建升級分支
git checkout -b v0.8.0-upgrade
git merge upstream/v2026.4.8

# Step 2：安裝新版依賴
source .venv/bin/activate
pip install -e . --break-system-packages

# Step 3：確認目錄結構
ls gateway/platforms/api_server.py   # 應該存在
ls webapi/ 2>/dev/null && echo "webapi 還在" || echo "webapi 已廢棄（正常）"

# Step 4：現場確認函數名
grep -n "def.*chat\|def.*completion" gateway/platforms/api_server.py
# 確認函數名後再動手，不要盲改
```

⚠️ **Step 4 確認函數名後，提 SOP-002，Kent 確認再移植 P3 hook**

```
移植目標：
- 檔案：gateway/platforms/api_server.py
- 函數：_handle_chat_completions（現場確認實際名稱）
- 插入位置：result, usage = await _compute_completion() 之後
- 邏輯不變：api_calls > 1 觸發 shared_bridge
- 參考：~/ceclaw/p3_hook_backup.txt
```

```bash
# Step 5：驗證
bash ~/start-hermes.sh
curl -s http://localhost:8642/health

# 在 Hermes UI 跑一個需要 tool call 的任務
# 確認 shared_bridge 有新檔案產生
ls -la ~/.ceclaw/knowledge/bridge/shared/
diff <(cat ~/ceclaw/bridge_before_upgrade.txt) <(ls -la ~/.ceclaw/knowledge/bridge/shared/)

# Step 6：通過後合併
git checkout master
git merge v0.8.0-upgrade
git push
```

---

## 回滾機制

**觸發條件：** health check 失敗 / shared_bridge 不觸發 / Hermes 無回應

```bash
pkill -f hermes
kill $(lsof -ti:8642) 2>/dev/null
kill $(lsof -ti:3000) 2>/dev/null

rm -rf ~/hermes-agent-fork
cp -r ~/hermes-agent-fork.bak-[日期] ~/hermes-agent-fork

bash ~/start-hermes.sh
curl -s http://localhost:8642/health
```

回滾時間：**2 分鐘內可完成**（備份是完整 copy，不是 diff）

---

## 風險評估

| 項目 | 風險 | 說明 |
|------|------|------|
| P3 hook 移植失敗 | 🟡 中 | 邏輯簡單，備份清楚，30 分鐘可修 |
| 新版函數名變動 | 🟡 中 | Step 4 現場 grep 確認，不盲改 |
| config.yaml 不相容 | 🟢 低 | 外部檔案，升級不動 |
| vault 資料遺失 | 🟢 無 | symlink 指向外部，完全安全 |
| 回滾失敗 | 🟢 無 | 備份是完整 copy |

---

## 版本歷史

| 版本 | 日期 | 說明 |
|------|------|------|
| v1.0 | 2026-04-10 | 初版，Kent 審查通過 |
