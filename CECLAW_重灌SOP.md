# CECLAW 重灌 SOP
## 從零開始到端到端通的完整步驟

**預估時間**: 1~2 小時（不含模型下載）  
**適用**: pop-os 重灌或全新機器

---

## 前置確認

| 項目 | 確認指令 | 備註 |
|------|---------|------|
| Docker 已裝 | `docker --version` | 需 20.x 以上 |
| Node.js v22 | `node --version` | |
| Python 3.10 | `python3 --version` | |
| Git | `git --version` | |
| GB10 機器開機 | `ping 192.168.1.91` | |
| GitHub SSH key | `ssh -T git@github.com` | 見下方說明 |

### GitHub SSH key 設定（若沒有）
```bash
ssh-keygen -t ed25519 -C "kent@ceclaw"
cat ~/.ssh/id_ed25519.pub
# 複製上面的 key 貼到 github.com → Settings → SSH keys
```

### Docker login ghcr.io（推 image 時需要）
```bash
# 用 GitHub Personal Access Token（需要 write:packages 權限）
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u kentgeeng --password-stdin
```

---

## Step 1：安裝 OpenShell

```bash
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh
# 或用 uv：
# uv tool install -U openshell

# 確認
openshell --version
# 預期: openshell 0.0.10
```

---

## Step 2：啟動 OpenShell Gateway

```bash
# 第一次啟動，建立本地 gateway
openshell gateway start

# 確認
openshell gateway list
# 預期: openshell   local   Healthy
```

---

## Step 3：GB10 啟動 llama-server

```bash
# SSH 到 GB10 啟動推論服務
ssh zoe_gb@192.168.1.91 "nohup ~/start_llama.sh > ~/llama.log 2>&1 &"

# 等 30 秒後確認
sleep 30
curl -s http://192.168.1.91:8001/v1/models | python3 -m json.tool
# 預期看到 minimax model
```

`~/start_llama.sh` 內容（GB10 上，若遺失需重建）：
```bash
#!/bin/bash
/home/zoe_gb/llama.cpp/build/bin/llama-server \
  --model /home/zoe_gb/MiniMax-M2.5-GGUF/UD-Q3_K_XL/MiniMax-M2.5-UD-Q3_K_XL-00001-of-00004.gguf \
  --alias minimax --host 0.0.0.0 --port 8001 \
  --ctx-size 32768 --parallel 2 \
  --flash-attn on \
  --n-gpu-layers 99 \
  --threads 20 \
  --temp 0.3 --top-p 0.95 --top-k 40 --min-p 0.01 --jinja
```

---

## Step 4：Clone CECLAW 專案

```bash
cd ~
git clone git@github.com:kentgeeng/ceclaw.git
cd ceclaw

# 建立 Python venv
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
  timeout_local_ms: 30000
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
# 複製 service 檔（從 repo 來的）
sudo cp ~/ceclaw/ceclaw-router.service /etc/systemd/system/

# 啟動並設開機自啟
sudo systemctl daemon-reload
sudo systemctl enable ceclaw-router
sudo systemctl start ceclaw-router

# 確認
sudo systemctl status ceclaw-router
curl -s http://localhost:8000/ceclaw/status | python3 -m json.tool
# 預期: backends.gb10-llama: true
```

---

## Step 7：設定 iptables 網路穿透

OpenShell sandbox 在 K3s (172.20.x) 需要能連到 host Router (172.17.0.1:8000)。

```bash
# 安裝持久化工具（安裝時選「是」儲存現有規則）
sudo apt install iptables-persistent -y

# 加入規則
sudo iptables -I FORWARD -s 172.20.0.0/16 -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -I FORWARD -s 10.42.0.0/16  -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -I FORWARD -s 10.200.0.0/16 -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -t nat -A POSTROUTING -s 172.20.0.0/16 -d 172.17.0.1 -j MASQUERADE
sudo iptables -t nat -A POSTROUTING -s 10.42.0.0/16  -d 172.17.0.1 -j MASQUERADE
sudo ufw allow from 172.20.0.0/16 to any port 8000

# 持久化（重開機後自動恢復）
sudo netfilter-persistent save
```

---

## Step 8：建立 CoreDNS restore 腳本

⚠️ CoreDNS 的修改不持久，重開機或重建 OpenShell 後需要重跑。

```bash
mkdir -p ~/nemoclaw-config

cat > ~/nemoclaw-config/restore-coredns.sh << 'EOF'
#!/bin/bash
# 動態取得 K3s container ID（每次重建都不同）
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

## Step 9：確認 Sandbox Policy

```bash
# policy 已在 repo 裡，確認內容正確
cat ~/ceclaw/config/ceclaw-policy.yaml
```

預期內容：
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

若不存在則建立：
```bash
mkdir -p ~/ceclaw/config
cat > ~/ceclaw/config/ceclaw-policy.yaml << 'EOF'
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
EOF
```

---

## Step 10：建立 Sandbox

```bash
openshell sandbox create \
  --name ceclaw-agent \
  --from ghcr.io/kentgeeng/ceclaw-sandbox:latest \
  --policy ~/ceclaw/config/ceclaw-policy.yaml \
  --keep

# 指令可能停在這裡，屬正常。另開 terminal 確認：
openshell sandbox list
# 預期: ceclaw-agent   Ready
```

---

## Step 11：Approve Policy（TUI）

另開一個 terminal：
```bash
openshell term
```

在 TUI 裡：
1. Tab 切到 **Sandboxes** 面板
2. `j/k` 選到 ceclaw-agent → `Enter`
3. 按 `r` 看 pending rules
4. 按 `A` **Approve All**

若沒有 pending rules 表示 policy 已自動生效，跳過此步。

---

## Step 12：端到端驗證

在 sandbox 內：
```bash
# 狀態確認
curl -s http://host.openshell.internal:8000/ceclaw/status | python3 -m json.tool
# 預期: backends.gb10-llama: true

# 推論測試
curl -s http://host.openshell.internal:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"minimax","messages":[{"role":"user","content":"hi"}],"max_tokens":20}'
# 預期: choices[0].message.content 有內容
```

✅ 看到 MiniMax 回應 = 全通

---

## 重開機後恢復（不需重灌時）

```bash
# 1. CoreDNS restore（每次重開機後執行）
bash ~/nemoclaw-config/restore-coredns.sh

# 2. Router 已 systemd 自啟，確認
sudo systemctl status ceclaw-router

# 3. GB10 llama-server（若未設自啟）
ssh zoe_gb@192.168.1.91 "nohup ~/start_llama.sh > ~/llama.log 2>&1 &"

# 4. 重建 sandbox
openshell sandbox create \
  --name ceclaw-agent \
  --from ghcr.io/kentgeeng/ceclaw-sandbox:latest \
  --policy ~/ceclaw/config/ceclaw-policy.yaml --keep
```

---

## 關鍵技術背景（為什麼這麼複雜）

- OpenShell proxy **寫死** `host.openshell.internal` → `172.17.0.1`，CoreDNS 改不了它
- Sandbox 在 K3s (172.20.x)，跨網段到 host (172.17.0.1) 需要 iptables FORWARD + MASQUERADE
- Policy 必須同時有 `allowed_ips: [172.17.0.1]` + `binaries` proxy 才放行
- 新 sandbox 的 pending rules 需要 TUI 手動 Approve 一次

---

*CECLAW — Secure local AI agents, your inference, your rules.*  
*SOP 版本: 1.1 | 日期: 2026-03-19*
