# CECLAW Easy Setup 快速上手手冊

**版本**: 1.2 | **日期**: 2026-03-21  
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

# 3. 確認 GB10（若未設自啟）
ssh zoe_gb@192.168.1.91 "nohup ~/start_llama.sh > ~/llama.log 2>&1 &"

# 4. 重建 sandbox
openshell sandbox create \
  --name ceclaw-agent \
  --from ghcr.io/kentgeeng/ceclaw-sandbox:latest \
  --policy ~/ceclaw/config/ceclaw-policy.yaml --keep
```

然後跳到 **→ 啟動 openclaw**。

---

## 🟡 場景 B：全新機器（從零開始）

詳見重灌 SOP v1.5，完整步驟在那份文件。

快速摘要：
1. 安裝 OpenShell
2. Clone ceclaw repo
3. 建立 `~/.ceclaw/ceclaw.yaml`
4. 部署 ceclaw-router systemd
5. 設定 iptables
6. 建立 CoreDNS restore 腳本
7. 設定監控 + logrotate
8. 安裝 ceclaw CLI
9. 建立 sandbox
10. Approve policy（TUI）

---

## 🔧 啟動 openclaw

**B方案已完成，重建 sandbox 後自動設定，不需要手動設定 openclaw.json。**

**Terminal 1：**
```bash
openshell sandbox connect ceclaw-agent
# 自動執行 ceclaw-start
# 看到: [gateway] agent model: local/minimax = 成功
```

**Terminal 2：**
```bash
openshell sandbox connect ceclaw-agent
openclaw tui
# 底部看到 local/minimax = 成功
```

---

## ✅ 驗證清單

```bash
ceclaw status
```

| 項目 | 預期結果 |
|------|---------|
| Router | ✅ running, gb10-llama: true |
| GB10 | ✅ online, models: minimax |
| Sandbox | ✅ ceclaw-agent Ready |

或手動驗證：

| 項目 | 指令 | 預期 |
|------|------|------|
| Router | `curl -s http://localhost:8000/ceclaw/status \| python3 -m json.tool` | `"gb10-llama": true` |
| GB10 | `curl -s http://192.168.1.91:8001/v1/models \| python3 -m json.tool` | 看到 minimax |
| sandbox 網路 | sandbox 內 `curl -s http://host.openshell.internal:8000/ceclaw/status` | 同上 |
| openclaw agent | TUI 底部 | `local/minimax` |
| 推論正常 | TUI 發訊息 | MiniMax 有回應 |
| Router 有流量 | `tail -f ~/.ceclaw/router.log` | `gb10-llama → 200` |

---

## 🚨 快速 Debug

| 症狀 | 解法 |
|------|------|
| Router 無回應 | `sudo systemctl start ceclaw-router` |
| GB10 無回應 | `ssh zoe_gb@192.168.1.91 "nohup ~/start_llama.sh > ~/llama.log 2>&1 &"` |
| sandbox curl 無回應 | `bash ~/nemoclaw-config/restore-coredns.sh` 然後重建 sandbox |
| TUI 顯示 not connected | gateway 沒跑，重新連入 sandbox |
| 第一個 request 超時 | timeout 已調 60s，若仍超時代表 GB10 負載高，稍候再試 |
| Connection error（一堆）| 清 session 歷史（坑#13）：`> ~/.openclaw/agents/main/sessions/<id>.jsonl` |
| Connection error（網路）| 不要改 baseUrl，見坑#10，重建 sandbox 通常可解 |
| 403 Forbidden | 進 `openshell term` approve policy |

---

## 📊 本地模型速查（P4 後）

| 模型 | 速度 | 用途 |
|------|------|------|
| qwen2.5:7b | 0.19s | fast：簡單對話 |
| qwen3:8b | 1.3s | backup：GB10 掛時 |
| GB10 MiniMax | 1.8s | main：主力 |

⚠️ 開工前確認 VRAM：
```bash
nvidia-smi --query-gpu=memory.used,memory.free --format=csv
```

---

*CECLAW — Secure local AI agents, your inference, your rules.*  
*版本: 1.2 | 日期: 2026-03-21*
