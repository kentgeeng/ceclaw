# CECLAW 重灌 SOP
## 從零開始到端到端通的完整步驟

**預估時間**: 1~2 小時（不含模型下載）  
**適用**: pop-os 重灌或全新機器  
**SOP 版本**: 1.2 | **日期**: 2026-03-20

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
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u kentgeeng --password-stdin
```

---

## Step 1：安裝 OpenShell

```bash
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh

# 確認
openshell --version
# 預期: openshell 0.0.10
```

---

## Step 2：啟動 OpenShell Gateway

```bash
openshell gateway start

# 確認
openshell gateway list
# 預期: openshell   local   Healthy
```

---

## Step 3：GB10 啟動 llama-server

```bash
ssh zoe_gb@192.168.1.91 "nohup ~/start_llama.sh > ~/llama.log 2>&1 &"

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
sudo cp ~/ceclaw/ceclaw-router.service /etc/systemd/system/
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

⚠️ CoreDNS 的修改不持久，重開機或重建 OpenShell 後需要重跑。

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

## Step 9：確認 Sandbox Policy

```bash
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

---

## Step 10：建立 Sandbox

```bash
openshell sandbox create \
  --name ceclaw-agent \
  --from ghcr.io/kentgeeng/ceclaw-sandbox:latest \
  --policy ~/ceclaw/config/ceclaw-policy.yaml \
  --keep

# 另開 terminal 確認
openshell sandbox list
# 預期: ceclaw-agent   Ready
```

---

## Step 11：Approve Policy（TUI）

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

## Step 12：Plugin 設定（B方案完成前的手動步驟）

⚠️ **B 方案 rebuild image 完成後，此步驟自動化，可跳過。**  
B 方案狀態請查交接文件第 4 節。

進 sandbox：
```bash
openshell sandbox connect ceclaw-agent
```

設定 gateway mode：
```bash
openclaw config set gateway.mode local
```

設定 local provider 和 agent model：
```bash
python3 -c "
import json, os
path = os.path.expanduser('~/.openclaw/openclaw.json')
try:
    with open(path) as f:
        c = json.load(f)
except:
    c = {}
c.setdefault('models', {}).setdefault('providers', {})['local'] = {
    'baseUrl': 'http://host.openshell.internal:8000/v1',
    'apiKey': 'ceclaw-local',
    'api': 'openai-completions',
    'models': [{'id': 'minimax', 'name': 'CECLAW Local', 'contextWindow': 131072, 'maxTokens': 8192, 'cost': {'input': 0, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0}, 'reasoning': False, 'input': ['text']}]
}
c.setdefault('agents', {}).setdefault('defaults', {})['model'] = {'primary': 'local/minimax'}
with open(path, 'w') as f:
    json.dump(c, f, indent=2)
print('Done')
"
```

確認：
```bash
cat /sandbox/.openclaw/openclaw.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('agents',{}).get('defaults',{}))"
# 預期: {'workspace': '...', 'model': {'primary': 'local/minimax'}}
```

---

## Step 13：端到端驗證

在 sandbox 內（另開 terminal 一個跑 gateway，一個跑 TUI）：

**Terminal 1：**
```bash
openclaw gateway
# 確認看到: [gateway] agent model: local/minimax
```

**Terminal 2：**
```bash
openclaw tui
# 底部應顯示: local/minimax | tokens ?/131k
# 發訊息，確認 MiniMax 有回應
```

**pop-os 確認 Router 有流量：**
```bash
tail -f ~/.ceclaw/router.log
# 應看到: [local] gb10-llama → 200
```

✅ 三項全中 = 全通

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

# 5. ⚠️ B方案未完成前，進 sandbox 執行 Step 12 手動設定
```

---

## 關鍵技術背景（為什麼這麼複雜）

- OpenShell proxy **寫死** `host.openshell.internal` → `172.17.0.1`，CoreDNS 改不了它
- Sandbox 在 K3s (172.20.x)，跨網段到 host (172.17.0.1) 需要 iptables FORWARD + MASQUERADE
- Policy 必須同時有 `allowed_ips: [172.17.0.1]` + `binaries` proxy 才放行
- 新 sandbox 的 pending rules 需要 TUI 手動 Approve 一次
- openclaw gateway 在 container 內不能用 systemd，必須前景執行
- MiniMax 冷啟動慢，第一個 request 可能超時，屬正常

---

*CECLAW — Secure local AI agents, your inference, your rules.*  
*SOP 版本: 1.2 | 日期: 2026-03-20*
