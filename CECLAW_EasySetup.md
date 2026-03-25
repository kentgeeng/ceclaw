# CECLAW Easy Setup 快速上手手冊

**版本**: 1.8 | **日期**: 2026-03-25
**適用**: 快速建立可用的 CECLAW 環境
**預估時間**: 15 分鐘（環境已備齊）/ 1~2 小時（全新機器）

---

## 🟢 場景 A：日常使用（重開機後恢復）

```bash
# 1. CoreDNS（若未自啟）
bash ~/nemoclaw-config/restore-coredns.sh

# 2. 確認 Router
ceclaw status
# 三項全綠 = OK

# 3. GB10（systemd 自啟，確認）
ssh gb10 'sudo systemctl status llama-server'

# 4. SearXNG（docker --restart=always 自動起）
docker ps | grep searxng

# 5. 連 sandbox（gateway 已 autostart）
openshell sandbox connect ceclaw-agent
tui
```

---

## 🟡 場景 B：Sandbox 重建後（一鍵恢復）

**Step 1：先連進 sandbox（取得 token）**
```bash
openshell sandbox connect ceclaw-agent
```

**Step 2：另一個 terminal 跑 restore 腳本**
```bash
bash ~/ceclaw/sandbox-restore.sh
```

腳本自動完成全部 6 步 + 啟動 gateway。

**Step 3：進 TUI approve policy**
```bash
openshell term
# Tab → Sandboxes → ceclaw-agent → r → 確認 172.17.0.1:8000 有 node binary
```

**Step 4：驗證**
```bash
tui
# 問：你是誰 → 我是 CECLAW 企業 AI 助手
```

---

## 🔴 場景 C：全新機器（從零開始）

詳見重灌 SOP v2.1。

---

## ✅ 驗證清單

```bash
bash ~/ceclaw/ceclaw-health-check.sh
# 五層全綠 = OK
```

| 測試 | 預期 |
|------|------|
| `你是誰` | 我是 CECLAW 企業 AI 助手 |
| `你是通義千問嗎` | 不是，我是 CECLAW 企業 AI 助手 |
| `1+1=?` | 2 |
| `今天台北天氣如何？` | 有天氣資訊（web_fetch 通後）|
| Router log | `[local] gb10-llama → 200` |
| SearXNG proxy | `curl localhost:8000/search?q=test&format=json` 有結果 |

---

## 🚨 快速 Debug

| 症狀 | 解法 |
|------|------|
| Router 無回應 | `sudo systemctl start ceclaw-router` |
| GB10 無回應 | `ssh gb10 'sudo systemctl restart llama-server'` |
| sandbox SSH 死掉 | **不要 docker restart！** 等 30-60s 或用 `openshell term` |
| TUI auth 失敗（No API key）| 確認 openclaw.json 有 `api: openai-completions`，確認 auth-profiles.json 存在 |
| TUI not connected | 等 30s；或手動 `openclaw gateway run &` |
| 身份洩漏 | 確認 proxy.py 有 inject_system_prompt，重啟 Router |
| web search 幻覺 | D 方案未完成，屬已知問題 |
| sandbox curl 無回應 | 確認 UFW `ufw status verbose \| grep routed` = allow |
| 403 Forbidden | 進 `openshell term` approve policy |
| gateway start 後 sandbox 消失 | 坑#68！用 `docker start <id>` 不要用 `openshell gateway start` |

---

## ⚠️ 重要禁忌

**坑#23**: 不要 `docker restart openshell container` → sandbox SSH 死掉

**坑#68（新）**: 不要 `openshell gateway start`（gateway stopped 時）→ K3s 重建 → sandbox 消失
```bash
# ❌ 這個會毀掉 sandbox
openshell gateway start   # 若 gateway 已 stopped

# ✅ 正確做法
docker start $(docker ps -a | grep openshell-cluster-openshell | awk '{print $1}')
sleep 10
openshell sandbox list
```

---

## 📊 本地模型速查

| 模型 | 速度 | 用途 | 身份 |
|------|------|------|------|
| ministral-3:14b | ~636ms | fast：簡單對話 | CECLAW（Router inject）|
| qwen3:8b | ~1.3s | backup：GB10 掛時 | CECLAW（Router inject）|
| GB10 Qwen3.5-122B | ~2624ms | main：主力 | CECLAW（Router inject）|

---

*CECLAW — Secure local AI agents, your inference, your rules.*
*版本: 1.8 | 日期: 2026-03-25*
