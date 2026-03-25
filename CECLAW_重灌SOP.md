# CECLAW 重灌 SOP
## 從零開始到端到端通的完整步驟

**預估時間**: 1~2 小時（不含模型下載）
**適用**: pop-os 重灌或全新機器
**SOP 版本**: 2.1 | **日期**: 2026-03-25

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

## Step 3：GB10 設定 SSH 免密碼

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_gb10 -N ""
ssh-copy-id -i ~/.ssh/id_gb10.pub zoe_gb@192.168.1.91

cat >> ~/.ssh/config << 'EOF'
Host gb10
    HostName 192.168.1.91
    User zoe_gb
    IdentityFile ~/.ssh/id_gb10
    ServerAliveInterval 30
    ServerAliveCountMax 3
EOF

ssh gb10 'echo OK'
```

GB10 設定 sudo NOPASSWD：
```bash
ssh gb10
sudo visudo
# 最後加一行：zoe_gb ALL=(ALL) NOPASSWD: ALL
```

---

## Step 4：GB10 啟動 llama-server

```bash
ssh gb10 "nohup ~/start_llama.sh > ~/llama.log 2>&1 &"
sleep 30
curl -s http://192.168.1.91:8001/v1/models | python3 -m json.tool
```

⚠️ **確認 `--parallel 2` + `--ctx-size 65536`**：每 slot 獨享 32768 tokens，支援雙並發。
```bash
ssh gb10 'grep "parallel\|ctx-size" ~/start_llama.sh'
# 預期：--ctx-size 65536 --parallel 2
```

`start_llama.sh` 正確內容：
```bash
#!/bin/bash
/home/zoe_gb/llama.cpp/build/bin/llama-server \
  --model /home/zoe_gb/Qwen3.5-122B/Qwen_Qwen3.5-122B-A10B-Q4_K_M/Qwen_Qwen3.5-122B-A10B-Q4_K_M-00001-of-00002.gguf \
  --alias minimax --host 0.0.0.0 --port 8001 \
  --ctx-size 65536 --parallel 2 \
  --flash-attn on --n-gpu-layers 99 --threads 20 \
  --cache-type-k q4_0 --cache-type-v q4_0 \
  --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0.0 \
  --reasoning off --jinja
```

---

## Step 5：Clone CECLAW 專案

```bash
cd ~
git clone git@github.com:kentgeeng/ceclaw.git
cd ceclaw
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi httpx uvicorn pyyaml pydantic
```

---

## Step 6：建立 Router 設定檔

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
  strategy: smart-routing
  timeout_local_ms: 60000
  local:
    backends:
      - name: ollama-fast
        type: ollama
        base_url: http://127.0.0.1:11434/v1
        priority: 1
        model: ministral-3:14b
        use_for: [simple_query]

      - name: gb10-llama
        type: llama.cpp
        base_url: http://192.168.1.91:8001/v1
        priority: 2
        models:
          - id: minimax
            alias: default
            context_window: 32768

      - name: ollama-backup
        type: ollama
        base_url: http://127.0.0.1:11434/v1
        priority: 3
        model: qwen3:8b
        options:
          think: false
        use_for: [fallback]

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

## Step 7：部署 Router systemd service

```bash
sudo cp ~/ceclaw/ceclaw-router.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ceclaw-router
sudo systemctl start ceclaw-router

sudo systemctl status ceclaw-router
curl -s http://localhost:8000/ceclaw/status | python3 -m json.tool
```

---

## Step 8：設定 iptables 網路穿透

```bash
sudo apt install iptables-persistent -y

# Port 8000（Router）— 多個網段（172.19 是 openshell container 實際網段）
sudo iptables -I FORWARD -s 172.20.0.0/16 -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -I FORWARD -s 10.42.0.0/16  -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -I FORWARD -s 10.200.0.0/16 -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -I FORWARD -s 172.19.0.0/16 -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -I FORWARD -i br-bb3142766d63 -o docker0 -j ACCEPT
sudo iptables -I FORWARD -i docker0 -o br-bb3142766d63 -j ACCEPT

sudo iptables -t nat -A POSTROUTING -s 172.20.0.0/16 -d 172.17.0.1 -j MASQUERADE
sudo iptables -t nat -A POSTROUTING -s 10.42.0.0/16  -d 172.17.0.1 -j MASQUERADE
sudo iptables -t nat -A POSTROUTING -s 172.19.0.0/16 -d 172.17.0.1 -j MASQUERADE
sudo iptables -t nat -A POSTROUTING -s 10.200.0.0/16 -d 172.17.0.1 -j MASQUERADE

# INPUT（允許 sandbox 連 Router）
sudo iptables -I INPUT -s 172.19.0.0/16 -p tcp --dport 8000 -j ACCEPT
sudo iptables -I INPUT -s 10.200.0.0/16 -p tcp --dport 8000 -j ACCEPT

# UFW（重要：必須允許 routed）
sudo ufw allow from 172.20.0.0/16 to any port 8000
sudo ufw allow from 172.19.0.0/16 to any port 8000
sudo ufw default allow routed
sudo ufw reload

# Port 8888（SearXNG）
sudo iptables -I FORWARD -s 172.20.0.0/16 -d 172.17.0.1 -p tcp --dport 8888 -j ACCEPT
sudo iptables -I FORWARD -s 10.42.0.0/16  -d 172.17.0.1 -p tcp --dport 8888 -j ACCEPT
sudo iptables -I FORWARD -s 10.200.0.0/16 -d 172.17.0.1 -p tcp --dport 8888 -j ACCEPT
sudo iptables -I FORWARD -s 172.19.0.0/16 -d 172.17.0.1 -p tcp --dport 8888 -j ACCEPT

sudo netfilter-persistent save
```

---

## Step 8b：建立 CoreDNS restore 腳本

```bash
mkdir -p ~/nemoclaw-config
cat > ~/nemoclaw-config/restore-coredns.sh << 'EOF'
#!/bin/bash
CONTAINER=$(docker ps --format "{{.ID}}" | head -1)
docker exec $CONTAINER /usr/bin/kubectl patch configmap coredns -n kube-system --type merge \
  -p '{"data":{"NodeHosts":"172.17.0.1 inference.local\n172.17.0.1 host.openshell.internal\n"}}' 2>/dev/null || \
docker exec $CONTAINER kubectl patch configmap coredns -n kube-system --type merge \
  -p '{"data":{"NodeHosts":"172.17.0.1 inference.local\n172.17.0.1 host.openshell.internal\n"}}' 2>/dev/null || \
echo "CoreDNS patch failed (may be OK if /etc/hosts handles it)"
echo "CoreDNS patched"
EOF
chmod +x ~/nemoclaw-config/restore-coredns.sh
bash ~/nemoclaw-config/restore-coredns.sh
```

---

## Step 8c：監控 + logrotate

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

## Step 8d：安裝 ceclaw CLI + 工具腳本

```bash
chmod +x ~/ceclaw/ceclaw.py
sudo ln -sf /home/zoe_ai/ceclaw/ceclaw.py /usr/local/bin/ceclaw

# 工具腳本（新增）
chmod +x ~/ceclaw/sandbox-restore.sh
chmod +x ~/ceclaw/ceclaw-health-check.sh

ceclaw status
```

---

## Step 8e：安裝 Ollama + ministral-3:14b

```bash
ollama --version
ollama pull ministral-3:14b            # fast path，9.1GB
ollama pull qwen3:8b                    # backup 路徑，5.2GB

# 驗證（身份由 Router inject，應回 CECLAW）
ollama run ministral-3:14b "你是誰"
```

---

## Step 8f：安裝 openclaw 2026.3.13（pop-os 側）

```bash
npm install -g openclaw@2026.3.13
openclaw --version   # 預期: OpenClaw 2026.3.13
```

---

## Step 8g：啟動 SearXNG

```bash
mkdir -p ~/searxng-config

sudo tee ~/searxng-config/settings.yml << 'EOF'
use_default_settings: true
server:
  secret_key: "ceclaw-searxng-key-2026"
  limiter: false
  image_proxy: false
search:
  formats:
    - html
    - json
general:
  debug: false
  instance_name: "CECLAW Search"
engines:
  - name: duckduckgo
    engine: duckduckgo
    categories: general, news
    disabled: false
  - name: brave
    engine: brave
    categories: general, news
    disabled: false
  - name: bing
    engine: bing
    categories: general, news
    disabled: false
EOF

docker run -d --name searxng \
  --restart=always \
  -p 8888:8080 \
  -v ~/searxng-config:/etc/searxng \
  searxng/searxng:latest

sleep 5
curl -s "http://localhost:8888/search?q=test&format=json" | python3 -c "import json,sys; d=json.load(sys.stdin); print('results:', len(d.get('results',[])))"
curl -s "http://localhost:8000/search?q=test&format=json" | python3 -c "import json,sys; d=json.load(sys.stdin); print('results:', len(d.get('results',[])))"
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
4. 確認 `172.17.0.1:8000` 有 node binary

---

## Step 12：Sandbox 初始化（一鍵）

```bash
# 先連進 sandbox
openshell sandbox connect ceclaw-agent

# 另一個 terminal
bash ~/ceclaw/sandbox-restore.sh
```

腳本自動完成 Step A-F + 啟動 gateway。

---

## Step 13：端到端驗證

```bash
bash ~/ceclaw/ceclaw-health-check.sh
# 五層全綠

# sandbox 內
tui
# 問：你是誰 → 我是 CECLAW 企業 AI 助手
```

```bash
# pop-os
tail -f ~/.ceclaw/router.log
# 看到: [local] gb10-llama → 200
ceclaw status   # 三項全綠
```

---

## Step 14：備份

```bash
mkdir -p ~/ceclaw/backup
scp gb10:~/start_llama.sh ~/ceclaw/backup/start_llama.sh.bak
cp ~/.ceclaw/ceclaw.yaml ~/ceclaw/backup/ceclaw.yaml.bak
cp ~/nemoclaw-config/restore-coredns.sh ~/ceclaw/backup/

# 備份 sandbox openclaw.json（每次設定完必做）
TOKEN=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "token [a-z0-9-]*" | head -1 | awk '{print $2}')
SANDBOX_ID=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "sandbox-id [a-z0-9-]*" | head -1 | awk '{print $2}')
scp -o "ProxyCommand=/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id $SANDBOX_ID --token $TOKEN --gateway-name openshell" \
  -o StrictHostKeyChecking=no \
  sandbox@ceclaw-agent:/sandbox/.openclaw/openclaw.json ~/ceclaw/backup/openclaw.json.bak-$(date +%Y%m%d)

echo "備份完成"
```

---

## 重開機後恢復

```bash
# 1. CoreDNS（若未自啟）
bash ~/nemoclaw-config/restore-coredns.sh

# 2. Router（systemd 自啟）
sudo systemctl status ceclaw-router

# 3. GB10（systemd 自啟）
ssh gb10 'sudo systemctl status llama-server'

# 4. SearXNG（docker --restart=always）
docker ps | grep searxng

# 5. 連 sandbox
openshell sandbox connect ceclaw-agent
tui
```

---

## ⚠️ 關鍵注意事項

**坑#10**: `baseUrl` 不能改成 IP，保持 `host.openshell.internal:8000/v1`

**坑#23**: 不要 `docker restart openshell container`

**坑#27（歷史）**: `--parallel 2 --ctx-size 32768` 讓每 slot 16384 tokens → 400。現已改 `--ctx-size 65536`（#59）

**坑#68（新，關鍵）**: 不要 `openshell gateway start`（gateway stopped 時）→ sandbox 消失
- 正確：`docker start <container_id>`

**坑#69（新，關鍵）**: openclaw.json 必須有 `api: "openai-completions"` 才能通

**坑#71（新）**: openshell 實際網段是 `172.19.0.0/16`，不是 `172.20.0.0/16`

**坑#72（新）**: UFW `deny (routed)` 會擋掉 sandbox → Router 的流量
- 解法：`sudo ufw default allow routed`

---

*CECLAW — Secure local AI agents, your inference, your rules.*
*SOP 版本: 2.1 | 日期: 2026-03-25*
