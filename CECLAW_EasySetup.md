# CECLAW EasySetup v1.9
**更新日期：2026-03-26**

---

## 前置需求

- pop-os 主機（192.168.1.x）
- openshell 已安裝
- ceclaw-agent / ceclaw-agent-v2 sandbox 已建立
- Router 服務運行中

---

## 一鍵 Restore 流程

### Step 1：連接 sandbox

```bash
# Terminal 1
openshell sandbox connect ceclaw-agent
```

### Step 2：執行 restore（Terminal 2）

```bash
bash ~/ceclaw/sandbox-restore.sh
```

### Step 3：sandbox 內啟動

```bash
bash ~/ceclaw-start.sh
```

### Step 4：驗證

TUI 問：`你是誰` → 應回答：`我是 CECLAW 企業 AI 助手`

---

## Restore v3.4 執行流程

```
[1/9] 確認 sandbox
[2/9] 取得 sandbox-id + token
[3/9] 套用 network policy（外網 TLD 全開）
[5/9] sandbox_init.py（安裝 ceclaw plugin + openclaw.json + proxy）
[6/9] 重啟 gateway
[7/9] 同步 workspace（SOUL/TOOLS/AGENTS/USER.md）
[8/9] 部署 ceclaw-start.sh
[9/9] 七層健康檢查（sandbox 內跑）
```

---

## 七層健康檢查說明

| 層 | 檢測項目 | 正常狀態 |
|---|---------|---------|
| L1 | proxy 環境變數 | ✅ http_proxy=10.200.0.1:3128 |
| L2 | openclaw.json 欄位 | ✅ api=openai-completions |
| L3 | gateway PID | ✅ 有 PID |
| L4 | Router 連線 | ⚠️ 可能 403（已知假陰性）|
| L5 | 身份注入 | ⚠️ 可能 403（已知假陰性）|
| L6 | 外網 HTTPS | ⚠️ 新 domain 需 approve |
| L7 | extensions 乾淨 | ✅ 無 searxng-search |

> L4/L5 的 403 是從 sandbox python3 走 proxy 連 Router 被擋，是已知限制。
> 實際 TUI 推論正常（走 gateway WebSocket 不走 urllib）。

---

## ceclaw-start.sh 說明

```bash
bash ~/ceclaw-start.sh
# 1. pkill -9 -f openclaw（清除所有殘留）
# 2. source ~/.bashrc（載入 proxy 設定）
# 3. openclaw gateway run（啟動 gateway）
# 4. openclaw tui --session fresh-$(date +%s)（進入 TUI）
```

---

## 常見問題

### TUI 顯示 "LLM request timed out"

```bash
# 1. 確認 gateway 環境
cat /proc/$(pgrep openclaw-gateway)/environ | tr '\0' '\n' | grep proxy
# 應有：http_proxy=http://10.200.0.1:3128

# 2. 如果沒有，重啟 gateway
bash ~/ceclaw-start.sh
```

### gateway 已在跑但 TUI 連不到

```bash
pkill -9 -f 'openclaw' 2>/dev/null
sleep 3
bash ~/ceclaw-start.sh
```

### known_hosts 衝突

```bash
ssh-keygen -f "/home/zoe_ai/.ssh/known_hosts" -R "ceclaw-agent"
ssh-keygen -f "/home/zoe_ai/.ssh/known_hosts" -R "ceclaw-agent-v2"
```

---

## Restore v2 sandbox 指令

```bash
SANDBOX_ID=35c0ad04-bb06-434c-a07d-a9a2413ee90c \
TOKEN=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep "35c0ad04" | grep -o "token [a-z0-9-]*" | head -1 | awk '{print $2}') \
bash ~/ceclaw/sandbox-restore.sh
```
