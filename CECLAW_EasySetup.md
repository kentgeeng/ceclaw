# CECLAW Easy Setup 快速上手手冊

**版本**: 1.3 | **日期**: 2026-03-22  
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
ssh zoe_gb@192.168.1.91 'sudo systemctl status llama-server'

# 4. SearXNG（docker --restart=always 自動起）
docker ps | grep searxng

# 5. 連 sandbox（gateway 已 autostart）
openshell sandbox connect ceclaw-agent
tui
```

---

## 🟡 場景 B：Sandbox 重建後（⚠️ 必做 4 步）

```bash
openshell sandbox connect ceclaw-agent
```

進去後依序執行：

```bash
# Step 1: 安裝 CECLAW plugin
openclaw plugins install /opt/ceclaw

# Step 2: tui alias
grep -q "alias tui=" ~/.bashrc || echo "alias tui='openclaw tui --session fresh-\$(date +%s) --history-limit 20'" >> ~/.bashrc

# Step 3: openclaw.json patch
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

# Step 4: gateway auto-start
grep -q "openclaw gateway run" ~/.bashrc || cat >> ~/.bashrc << 'BEOF'
if ! pgrep -f "openclaw-gatewa" > /dev/null 2>&1; then
    openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 &
fi
BEOF

source ~/.bashrc
```

然後驗證：
```bash
tui
# 問：你是誰
# 預期：我是 CECLAW 企業 AI 助手
```

---

## 🔴 場景 C：全新機器（從零開始）

詳見重灌 SOP v1.6。

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
| Router log | `[local] gb10-llama → 200` |

---

## 🚨 快速 Debug

| 症狀 | 解法 |
|------|------|
| Router 無回應 | `sudo systemctl start ceclaw-router` |
| GB10 無回應 | `ssh zoe_gb@192.168.1.91 'sudo systemctl restart llama-server'` |
| sandbox curl 無回應 | `bash ~/nemoclaw-config/restore-coredns.sh` 然後重建 sandbox |
| TUI 顯示 not connected | 等 30s，gateway 自動啟動；或手動 `openclaw gateway run &` |
| 身份洩漏（通義千問）| 確認 proxy.py 有 inject_system_prompt，重啟 Router |
| tokens ?/131k | 重建 sandbox 後未做 Step 3（json patch） |
| 503 All backends unavailable | context 滿了，開新 session：`tui` alias 已自動 fresh session |
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
| qwen3-nothink | ~200ms | fast：簡單對話 | CECLAW（Modelfile）|
| qwen3:8b | ~1.3s | backup：GB10 掛時 | CECLAW（Router inject）|
| GB10 Qwen3.5-122B | 15-36s | main：主力 | CECLAW（Router inject）|

---

*CECLAW — Secure local AI agents, your inference, your rules.*  
*版本: 1.3 | 日期: 2026-03-22*
