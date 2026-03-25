# CECLAW 重灌 SOP v2.2
**更新日期：2026-03-26**

---

## 重灌觸發條件

- Sandbox 完全損壞無法修復
- openclaw.json 設定錯誤導致 gateway 無法啟動
- 需要全新部署

---

## 重灌前備份

```bash
# 備份 workspace
TOKEN=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep "2e04e3db" | grep -o "token [a-z0-9-]*" | head -1 | awk '{print $2}')
for f in SOUL.md TOOLS.md AGENTS.md USER.md HEARTBEAT.md; do
  scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    -o "ProxyCommand=/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id 2e04e3db-259d-4820-ae39-af385c5d0ce1 --token $TOKEN --gateway-name openshell" \
    sandbox@ceclaw-agent:/sandbox/.openclaw/workspace/$f ~/ceclaw/config/$f && echo "✅ $f"
done
cd ~/ceclaw && git add -A && git commit -m "backup: workspace before rebuild"
```

---

## 重灌流程

### Step 1：刪除舊 sandbox

```bash
openshell sandbox delete ceclaw-agent
```

### Step 2：建立新 sandbox

```bash
openshell sandbox create ceclaw-agent \
  --image ghcr.io/kentgeeng/ceclaw-sandbox:latest
```

### Step 3：連接並執行 restore

```bash
# Terminal 1
openshell sandbox connect ceclaw-agent

# Terminal 2
bash ~/ceclaw/sandbox-restore.sh
```

### Step 4：驗證

```bash
bash ~/ceclaw-start.sh
# TUI 問：你是誰 → 我是 CECLAW 企業 AI 助手
```

---

## Router 重灌

### Router 服務設定

```bash
# 服務位置
cat /etc/systemd/system/ceclaw-router.service

# 重啟
sudo systemctl restart ceclaw-router

# 確認
curl -s http://localhost:8000/ceclaw/status
```

### main.py 重灌注意

```bash
# 不要啟用 tcp_mux（已回滾）
# tcp_mux 的 30s pipe timeout 會截斷大型 system prompt

# 正確的 main.py 是回滾版本
ls ~/ceclaw/router/main.py.bak  # 備份在此
```

---

## 設定還原清單

重灌後必須確認：

- [ ] openclaw.json: `api: openai-completions`（坑#69）
- [ ] .bashrc: `http_proxy=http://10.200.0.1:3128`
- [ ] .bashrc: `no_proxy` 不含 `host.openshell.internal`（坑#78）
- [ ] gateway 在 source .bashrc 後才啟動（坑#79）
- [ ] searxng-search 目錄不存在（坑#77）
- [ ] ceclaw-start.sh 已部署

---

## 網路 Policy 設定

```bash
# ceclaw-policy.yaml 位置
cat ~/ceclaw/config/ceclaw-policy.yaml

# 套用 policy
openshell policy set ceclaw-agent \
  --policy ~/ceclaw/config/ceclaw-policy.yaml --wait

# 新 domain 需要在 openshell term approve
# 常用 domain 已在 policy：wttr.in, finance.yahoo.com 等
```

---

## 已知問題記錄

| 坑# | 問題 | 解法 |
|-----|------|------|
| #69 | 缺 api 欄位 → timeout | 加 `api: openai-completions` |
| #77 | searxng extensions path bug | 移除目錄 |
| #78 | no_proxy 含 host.openshell.internal | 移除此 host |
| #79 | gateway 繼承空 proxy | source .bashrc 後再啟動 |
| #80 | known_hosts 衝突 | UserKnownHostsFile=/dev/null |
