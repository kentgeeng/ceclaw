# CECLAW Easy Setup 快速上手手冊

**版本**: 1.4 | **日期**: 2026-03-23
**適用**: 快速建立可用的 CECLAW 環境
**預估時間**: 15 分鐘（環境已備齊）/ 1~2 小時（全新機器）

---

## 🟢 場景 A：日常使用（重開機後恢復）

```bash
# 1. CoreDNS（P3 已持久化，若未自啟才需要）
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

## 🟡 場景 B：Sandbox 重建後（⚠️ 必做 6 步）

**Step E 在 pop-os 執行（傳入 plugin）：**

```bash
TOKEN=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "token [a-z0-9-]*" | head -1 | awk '{print $2}')
scp -o ProxyCommand="/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id f24db4d6-9135-416c-a090-dbd281ebcd75 --token $TOKEN --gateway-name openshell" \
  ~/ceclaw/backup/openclaw-plugin-searxng-full.tar.gz sandbox@ceclaw-agent:/tmp/
```

**進 sandbox 後執行（Step A-D-F）：**

```bash
openshell sandbox connect ceclaw-agent
```

```bash
# Step A: 安裝 CECLAW plugin
openclaw plugins install /opt/ceclaw

# Step B: tui alias
grep -q "alias tui=" ~/.bashrc || echo "alias tui='openclaw tui --session fresh-\$(date +%s) --history-limit 20'" >> ~/.bashrc

# Step C: openclaw.json patch
python3 - << 'EOF'
import json
path = "/sandbox/.openclaw/openclaw.json"
cfg = json.load(open(path))
for model in cfg["models"]["providers"]["local"]["models"]:
    model["contextWindow"] = 32768
    model["maxTokens"] = 4096
cfg["agents"]["defaults"]["compaction"] = {"mode": "safeguard", "reserveTokens": 8000}
json.dump(cfg, open(path, "w"), indent=4, ensure_ascii=False)
print("done")
EOF

# Step D: gateway auto-start
grep -q "openclaw gateway run" ~/.bashrc || cat >> ~/.bashrc << 'BEOF'
if ! pgrep -f "openclaw-gatewa" > /dev/null 2>&1; then
    openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 &
fi
BEOF

# Step F: 安裝 SearXNG plugin
cd /tmp && tar xzf openclaw-plugin-searxng-full.tar.gz
rm -rf ~/.openclaw/extensions/searxng-search 2>/dev/null
openclaw plugins install /tmp/openclaw-plugin-searxng
python3 - << 'EOF'
import json
path = "/sandbox/.openclaw/openclaw.json"
cfg = json.load(open(path))
cfg["plugins"]["entries"]["searxng-search"]["config"]["baseUrl"] = "http://host.openshell.internal:8000"
json.dump(cfg, open(path, "w"), indent=4, ensure_ascii=False)
print("done")
EOF

source ~/.bashrc
```

然後驗證：
```bash
tui
# 問：你是誰 → 我是 CECLAW 企業 AI 助手
# 問：今天台北天氣如何？ → 有搜尋結果（非 NO_REPL）
```

---

## 🔴 場景 C：全新機器（從零開始）

詳見重灌 SOP v1.7。

---

## ✅ 驗證清單

```bash
ceclaw status
```

| 項目 | 預期結果 |
|------|---------|
| Router | ✅ running, gb10-llama: true |
| GB10 | ✅ online |
| Sandbox | ✅ ceclaw-agent Ready |

| 測試 | 預期 |
|------|------|
| TUI 底部 | `local/minimax \| tokens ?/33k` |
| `你是誰` | 我是 CECLAW 企業 AI 助手 |
| `你是通義千問嗎` | 不是，我是 CECLAW 企業 AI 助手 |
| `今天台北天氣如何？` | 有搜尋結果（非 NO_REPL）|
| Router log | `[local] gb10-llama → 200` |
| SearXNG proxy | `curl localhost:8000/search?q=test&format=json` 有結果 |

---

## 🚨 快速 Debug

| 症狀 | 解法 |
|------|------|
| Router 無回應 | `sudo systemctl start ceclaw-router` |
| GB10 無回應 | `ssh gb10 'sudo systemctl restart llama-server'` |
| sandbox curl 無回應 | `bash ~/nemoclaw-config/restore-coredns.sh` 然後重建 sandbox |
| TUI 顯示 not connected | 等 30s，gateway 自動啟動；或手動 `openclaw gateway run &` |
| 身份洩漏 | 確認 proxy.py 有 inject_system_prompt，重啟 Router |
| tokens ?/131k | 重建 sandbox 後未做 Step C（json patch）|
| 503 All backends unavailable | context 滿了，開新 session：`tui` alias 已自動 fresh session |
| GB10 掛掉但不 503 | ✅ 正常，#37 已修，自動降級 ollama-backup |
| web search NO_REPL | 重建 sandbox 後未做 Step F（SearXNG plugin）|
| SearXNG proxy 無結果 | `docker ps \| grep searxng`，確認容器在跑 |
| Connection error | 不要改 baseUrl，見坑#10，重建 sandbox 通常可解 |
| 403 Forbidden | 進 `openshell term` approve policy |
| sandbox SSH 死掉 | **不要 docker restart！** 等 30-60s 或用 `openshell term` |

---

## ⚠️ 重要禁忌

**坑#23：不要 `docker restart` openshell container**
```bash
# ❌ 這個指令會讓 sandbox SSH 死掉
docker restart 64a2b20468a5

# ✅ 正確做法：等待或用 TUI
openshell term
```

---

## 📊 本地模型速查

| 模型 | 速度 | 用途 | 身份 |
|------|------|------|------|
| doomgrave/ministral-3:8b | ~850ms | fast：簡單對話 | CECLAW（Router inject）|
| qwen3:8b | ~1.3s | backup：GB10 掛時 | CECLAW（Router inject）|
| GB10 Qwen3.5-122B | 15-36s | main：主力 | CECLAW（Router inject）|

---

*CECLAW — Secure local AI agents, your inference, your rules.*
*版本: 1.4 | 日期: 2026-03-23*
