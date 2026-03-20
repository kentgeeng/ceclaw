# CECLAW Easy Setup 快速上手手冊

**版本**: 1.0 | **日期**: 2026-03-20  
**適用**: 快速建立可用的 CECLAW 環境  
**預估時間**: 15 分鐘（環境已備齊）/ 1~2 小時（全新機器）

---

## 🟢 場景 A：日常使用（重開機後恢復）

每次重開機後跑這 4 個指令：

```bash
# 1. 修 CoreDNS（每次重開機必跑）
bash ~/nemoclaw-config/restore-coredns.sh

# 2. 確認 Router 活著
curl -s http://localhost:8000/ceclaw/status | python3 -m json.tool
# 看到 "gb10-llama": true = OK，若 Router 掛了：sudo systemctl start ceclaw-router

# 3. 確認 GB10 活著
curl -s http://192.168.1.91:8001/v1/models | python3 -m json.tool
# 看到 minimax = OK，若掛了：ssh zoe_gb@192.168.1.91 "nohup ~/start_llama.sh > ~/llama.log 2>&1 &"

# 4. 重建 sandbox
openshell sandbox create \
  --name ceclaw-agent \
  --from ghcr.io/kentgeeng/ceclaw-sandbox:latest \
  --policy ~/ceclaw/config/ceclaw-policy.yaml --keep
```

然後跳到 **→ 啟動 openclaw**。

---

## 🟡 場景 B：全新機器（從零開始）

### B-1 安裝依賴

```bash
# OpenShell
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh
openshell --version   # 預期: 0.0.10

# OpenShell Gateway
openshell gateway start
openshell gateway list   # 預期: openshell   local   Healthy
```

### B-2 Clone 專案 + 建 venv

```bash
cd ~
git clone git@github.com:kentgeeng/ceclaw.git
cd ceclaw
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi httpx uvicorn pyyaml pydantic
```

### B-3 建立 Router 設定檔

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

### B-4 啟動 Router（systemd）

```bash
sudo cp ~/ceclaw/ceclaw-router.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ceclaw-router
sudo systemctl start ceclaw-router

# 驗證
curl -s http://localhost:8000/ceclaw/status | python3 -m json.tool
# 預期: "gb10-llama": true
```

### B-5 設定 iptables

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

### B-6 CoreDNS restore 腳本

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

### B-7 建立 Sandbox

```bash
openshell sandbox create \
  --name ceclaw-agent \
  --from ghcr.io/kentgeeng/ceclaw-sandbox:latest \
  --policy ~/ceclaw/config/ceclaw-policy.yaml --keep

# 另開 terminal 確認
openshell sandbox list
# 預期: ceclaw-agent   Ready
```

### B-8 Approve Policy

```bash
openshell term
```
TUI 裡：Tab → Sandboxes → 選 ceclaw-agent → `r` → `A`（Approve All）  
若沒有 pending rules 跳過。

---

## 🔧 啟動 openclaw（場景 A/B 共用）

**⚠️ B 方案 rebuild image 完成前，每次重建 sandbox 都要跑這段。**

進 sandbox：
```bash
openshell sandbox connect ceclaw-agent
```

設定 openclaw：
```bash
openclaw config set gateway.mode local

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
    'models': [{'id': 'minimax', 'name': 'CECLAW Local', 'contextWindow': 131072,
                'maxTokens': 8192, 'cost': {'input': 0, 'output': 0, 'cacheRead': 0,
                'cacheWrite': 0}, 'reasoning': False, 'input': ['text']}]
}
c.setdefault('agents', {}).setdefault('defaults', {})['model'] = {'primary': 'local/minimax'}
with open(path, 'w') as f:
    json.dump(c, f, indent=2)
print('Done')
"
```

**Terminal 1（gateway）：**
```bash
openclaw gateway
# 確認看到: [gateway] agent model: local/minimax
```

**Terminal 2（對話）：**
```bash
openshell sandbox connect ceclaw-agent
openclaw tui
# 底部看到 local/minimax = 成功
```

---

## ✅ 驗證清單

| 項目 | 指令 | 預期結果 |
|------|------|---------|
| Router 活著 | `curl -s http://localhost:8000/ceclaw/status \| python3 -m json.tool` | `"gb10-llama": true` |
| GB10 活著 | `curl -s http://192.168.1.91:8001/v1/models \| python3 -m json.tool` | 看到 minimax |
| sandbox 網路通 | sandbox 內 `curl -s http://host.openshell.internal:8000/ceclaw/status` | 同上 |
| openclaw agent | TUI 底部 | `local/minimax` |
| 推論正常 | TUI 發訊息 | MiniMax 有回應 |
| Router 有流量 | `tail -f ~/.ceclaw/router.log` | `gb10-llama → 200` |

六項全過 = 環境正常。

---

## 🚨 快速 Debug

| 症狀 | 解法 |
|------|------|
| Router 無回應 | `sudo systemctl start ceclaw-router` |
| GB10 無回應 | `ssh zoe_gb@192.168.1.91 "nohup ~/start_llama.sh > ~/llama.log 2>&1 &"` |
| sandbox curl 無回應 | `bash ~/nemoclaw-config/restore-coredns.sh` 然後重建 sandbox |
| TUI 顯示 anthropic | openclaw.json 沒設定，重跑「啟動 openclaw」段落 |
| TUI 顯示 not connected | gateway 沒跑，開 Terminal 1 執行 `openclaw gateway` |
| 第一個 request 超時 | 正常，MiniMax 冷啟動慢，再試一次 |

---

*CECLAW — Secure local AI agents, your inference, your rules.*  
*版本: 1.0 | 日期: 2026-03-20*
