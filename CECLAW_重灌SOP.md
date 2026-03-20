# CECLAW 重灌 SOP
## 從零開始到端到端通的完整步驟

**預估時間**: 1~2 小時（不含模型下載）  
**適用**: pop-os 重灌或全新機器  
**SOP 版本**: 1.5 | **日期**: 2026-03-21

---

## 前置確認

| 項目 | 確認指令 | 備註 |
|------|---------|------|
| Docker 已裝 | `docker --version` | 需 20.x 以上 |
| Node.js v22 | `node --version` | |
| Python 3.10 | `python3 --version` | |
| Git | `git --version` | |
| GB10 機器開機 | `ping 192.168.1.91` | |
| GitHub SSH key | `ssh -T git@github.com` | |

---

## Step 1：安裝 OpenShell

```bash
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh
openshell --version   # 預期: 0.0.10
```

---

## Step 2：啟動 OpenShell Gateway

```bash
openshell gateway start
openshell gateway list   # 預期: openshell   local   Healthy
```

---

## Step 3：GB10 啟動 llama-server

```bash
ssh zoe_gb@192.168.1.91 "nohup ~/start_llama.sh > ~/llama.log 2>&1 &"
sleep 30
curl -s http://192.168.1.91:8001/v1/models | python3 -m json.tool
```

`~/start_llama.sh` 若遺失，從 pop-os 備份還原：
```bash
scp ~/ceclaw/backup/start_llama.sh.bak zoe_gb@192.168.1.91:~/start_llama.sh
ssh zoe_gb@192.168.1.91 "chmod +x ~/start_llama.sh"
```

---

## Step 4：Clone CECLAW 專案

```bash
cd ~
git clone git@github.com:kentgeeng/ceclaw.git
cd ceclaw
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi httpx uvicorn pyyaml pydantic
```

---

## Step 5：建立 Router 設定檔

```bash
mkdir -p ~/.ceclaw
cat > ~/.ceclaw/ceclaw.yaml << 'EOF'
version: 1
router:
  listen_host: "0.0.0.0"
  listen_port: 8000
  tls: false
  reload_on_sighup: true
inference:
  strategy: local-first
  timeout_local_ms: 60000
  local:
    backends:
      - name: gb10-llama
        type: llama.cpp
        base_url: http://192.168.1.91:8001/v1
        models:
          - id: minimax
            alias: default
            context_window: 32768
  cloud_fallback:
    enabled: true
    priority:
      - provider: groq
        env_key: GROQ_API_KEY
        models: [llama-3.3-70b-versatile]
      - provider: anthropic
        env_key: ANTHROPIC_API_KEY
        models: [claude-sonnet-4-6]
      - provider: openai
        env_key: OPENAI_API_KEY
        models: [gpt-4.1]
      - provider: nvidia
        env_key: NVIDIA_API_KEY
        models: [nvidia/nemotron-3-super-120b-a12b]
EOF
```

---

## Step 6：部署 Router systemd service

```bash
sudo cp ~/ceclaw/ceclaw-router.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ceclaw-router
sudo systemctl start ceclaw-router

sudo systemctl status ceclaw-router
curl -s http://localhost:8000/ceclaw/status | python3 -m json.tool
```

---

## Step 7：設定 iptables 網路穿透

```bash
sudo apt install iptables-persistent -y
sudo iptables -I FORWARD -s 172.20.0.0/16 -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -I FORWARD -s 10.42.0.0/16  -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -I FORWARD -s 10.200.0.0/16 -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -t nat -A POSTROUTING -s 172.20.0.0/16 -d 172.17.0.1 -j MASQUERADE
sudo iptables -t nat -A POSTROUTING -s 10.42.0.0/16  -d 172.17.0.1 -j MASQUERADE
sudo ufw allow from 172.20.0.0/16 to any port 8000
sudo netfilter-persistent save
```

---

## Step 8：建立 CoreDNS restore 腳本

⚠️ P3 已完成 CoreDNS 持久化（ceclaw-coredns.service），此腳本供手動修復使用。

```bash
mkdir -p ~/nemoclaw-config
cat > ~/nemoclaw-config/restore-coredns.sh << 'EOF'
#!/bin/bash
CONTAINER=$(docker ps --format "{{.ID}}" | head -1)
docker exec $CONTAINER kubectl patch configmap coredns -n kube-system --type merge \
  -p '{"data":{"NodeHosts":"172.17.0.1 inference.local\n172.17.0.1 host.openshell.internal\n"}}'
docker exec $CONTAINER kubectl rollout restart deployment/coredns -n kube-system
echo "CoreDNS patched"
EOF
chmod +x ~/nemoclaw-config/restore-coredns.sh
bash ~/nemoclaw-config/restore-coredns.sh
```

---

## Step 8b：監控 + logrotate

```bash
chmod +x ~/ceclaw/ceclaw_monitor.sh
(crontab -l 2>/dev/null; echo "*/5 * * * * bash ~/ceclaw/ceclaw_monitor.sh") | crontab -

sudo tee /etc/logrotate.d/ceclaw-router << 'EOF'
/home/zoe_ai/.ceclaw/router.log
/home/zoe_ai/.ceclaw/monitor.log
{
    daily
    rotate 7
    compress
    missingok
    notifempty
}
EOF
```

---

## Step 8c：安裝 ceclaw CLI

```bash
chmod +x ~/ceclaw/ceclaw.py
sudo ln -sf /home/zoe_ai/ceclaw/ceclaw.py /usr/local/bin/ceclaw
ceclaw status
```

---

## Step 8d：安裝 Ollama（P4，若需要）

```bash
# 確認已裝
ollama --version

# 下載模型
ollama pull qwen2.5:7b   # fast 路徑，4.7GB
ollama pull qwen3:8b     # backup 路徑，5.2GB

# 確認 VRAM 夠用
nvidia-smi --query-gpu=memory.total,memory.used,memory.free --format=csv
```

---

## Step 9：確認 Sandbox Policy

```bash
cat ~/ceclaw/config/ceclaw-policy.yaml
```

預期：
```yaml
version: 1
network_policies:
  ceclaw_router:
    endpoints:
      - host: host.openshell.internal
        port: 8000
        access: full
        allowed_ips:
          - 172.17.0.1
    binaries:
      - path: /usr/bin/curl
      - path: /usr/bin/node
      - path: /usr/local/bin/openclaw
```

---

## Step 10：建立 Sandbox

```bash
openshell sandbox create \
  --name ceclaw-agent \
  --from ghcr.io/kentgeeng/ceclaw-sandbox:latest \
  --policy ~/ceclaw/config/ceclaw-policy.yaml \
  --keep
# --keep 保留 policy approved 記錄

openshell sandbox list   # 預期: ceclaw-agent   Ready
```

---

## Step 11：Approve Policy（TUI）

```bash
openshell term
```

在 TUI 裡：
1. Tab → **Sandboxes** 面板
2. `j/k` 選 ceclaw-agent → `Enter`
3. `r` 看 Network Rules
4. 有 pending（黃色）→ `A` Approve All

⚠️ **新建 sandbox 後需先進 sandbox 跑 `ceclaw-start`，sandbox 內程序連線後才會產生 pending rules，再回 TUI 按 A。不是「沒有 pending = 自動生效」。**

---

## Step 12：端到端驗證

**Terminal 1：**
```bash
openshell sandbox connect ceclaw-agent
# 看到: [gateway] agent model: local/minimax = 成功
```

若出現 403 → 回 openshell term Approve policy

**Terminal 2：**
```bash
openshell sandbox connect ceclaw-agent
openclaw tui
# 底部: local/minimax | tokens ?/131k
# 發訊息確認回應
```

**pop-os：**
```bash
tail -f ~/.ceclaw/router.log
# 看到: [local] gb10-llama → 200
```

或用 ceclaw CLI：
```bash
ceclaw status   # 三項全綠
```

✅ 全通

---

## Step 13：備份關鍵檔案

```bash
mkdir -p ~/ceclaw/backup
scp zoe_gb@192.168.1.91:~/start_llama.sh ~/ceclaw/backup/start_llama.sh.bak
cp ~/.ceclaw/ceclaw.yaml ~/ceclaw/backup/ceclaw.yaml.bak
cp ~/nemoclaw-config/restore-coredns.sh ~/ceclaw/backup/
echo "備份完成"
```

---

## 重開機後恢復

```bash
# 1. CoreDNS（若未自啟）
bash ~/nemoclaw-config/restore-coredns.sh

# 2. Router（systemd 自啟，確認）
sudo systemctl status ceclaw-router

# 3. GB10（若未設自啟）
ssh zoe_gb@192.168.1.91 "nohup ~/start_llama.sh > ~/llama.log 2>&1 &"

# 4. 重建 sandbox
openshell sandbox create --name ceclaw-agent \
  --from ghcr.io/kentgeeng/ceclaw-sandbox:latest \
  --policy ~/ceclaw/config/ceclaw-policy.yaml --keep

# 5. 進 sandbox，自動執行 ceclaw-start
# 或用 ceclaw CLI：ceclaw status
```

---

## 關鍵技術背景

- OpenShell proxy 寫死 `host.openshell.internal` → `172.17.0.1`
- Sandbox 在 K3s (172.20.x)，需 iptables FORWARD + MASQUERADE
- Policy 必須同時有 `allowed_ips` + `binaries`
- 新 sandbox pending rules 需 TUI 手動 Approve
- openclaw gateway 必須前景執行
- timeout_local_ms 60000 避免冷啟動失敗
- ⚠️ Connection error → 不要改 baseUrl，見坑#10

---

*CECLAW — Secure local AI agents, your inference, your rules.*  
*SOP 版本: 1.5 | 日期: 2026-03-21*
