# CECLAW 重灌 SOP
## 從零開始到端到端通的完整步驟

**預估時間**: 1~2 小時（不含模型下載）
**適用**: pop-os 重灌或全新機器
**SOP 版本**: 1.9 | **日期**: 2026-03-23

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
EOF

# 驗證
ssh gb10 'echo OK'
```

GB10 設定 sudo NOPASSWD（需登入 GB10）：
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

`~/start_llama.sh` 若遺失，從 pop-os 備份還原：
```bash
scp ~/ceclaw/backup/start_llama.sh.bak zoe_gb@192.168.1.91:~/start_llama.sh
ssh gb10 "chmod +x ~/start_llama.sh"
```

⚠️ **確認 `--parallel 1`**：parallel 2 會讓每 slot 只有 16384 tokens，搜尋結果超出後 400。
```bash
ssh gb10 'grep "parallel" ~/start_llama.sh'
# 預期：--parallel 1
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
        model: doomgrave/ministral-3:8b
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

# Port 8000（Router）
sudo iptables -I FORWARD -s 172.20.0.0/16 -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -I FORWARD -s 10.42.0.0/16  -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -I FORWARD -s 10.200.0.0/16 -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -t nat -A POSTROUTING -s 172.20.0.0/16 -d 172.17.0.1 -j MASQUERADE
sudo iptables -t nat -A POSTROUTING -s 10.42.0.0/16  -d 172.17.0.1 -j MASQUERADE
sudo ufw allow from 172.20.0.0/16 to any port 8000

# Port 8888（SearXNG，透過 Router proxy 存取）
sudo iptables -I FORWARD -s 172.20.0.0/16 -d 172.17.0.1 -p tcp --dport 8888 -j ACCEPT
sudo iptables -I FORWARD -s 10.42.0.0/16  -d 172.17.0.1 -p tcp --dport 8888 -j ACCEPT
sudo iptables -I FORWARD -s 10.200.0.0/16 -d 172.17.0.1 -p tcp --dport 8888 -j ACCEPT

sudo netfilter-persistent save
```

---

## Step 8b：建立 CoreDNS restore 腳本

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

## Step 8d：安裝 ceclaw CLI

```bash
chmod +x ~/ceclaw/ceclaw.py
sudo ln -sf /home/zoe_ai/ceclaw/ceclaw.py /usr/local/bin/ceclaw
ceclaw status
```

---

## Step 8e：安裝 Ollama + doomgrave/ministral-3:8b

```bash
# 確認已裝
ollama --version

# 下載模型
ollama pull doomgrave/ministral-3:8b   # fast path，5.8GB
ollama pull qwen3:8b                    # backup 路徑，5.2GB

# 驗證 fast path
ollama run doomgrave/ministral-3:8b "你是誰"
# 預期：不會說出 Mistral（身份由 Router inject 控制）
```

---

## Step 8f：啟動 SearXNG（本地搜尋）

```bash
mkdir -p ~/searxng-config

# 取得預設設定
docker run --rm searxng/searxng:latest cat /etc/searxng/settings.yml > ~/searxng-config/settings.yml

# 寫入正式設定（加 json format + 可靠引擎）
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

# 啟動
docker run -d --name searxng \
  --restart=always \
  -p 8888:8080 \
  -v ~/searxng-config:/etc/searxng \
  searxng/searxng:latest

sleep 5
# 驗證 pop-os 直接存取
curl -s "http://localhost:8888/search?q=NVIDIA+stock&format=json" | python3 -c "import json,sys; d=json.load(sys.stdin); print('results:', len(d.get('results',[])))"
# 驗證 Router proxy
curl -s "http://localhost:8000/search?q=test&format=json" | python3 -c "import json,sys; d=json.load(sys.stdin); print('results:', len(d.get('results',[])))"
```

⚠️ `~/searxng-config/settings.yml` 擁有者是 uid 977（docker 內的 searxng），需用 `sudo tee` 修改。

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
4. 有 pending（黃色）→ `A` Approve All

---

## Step 12：Sandbox 初始化（⚠️ 重要，必做 6 步）

### Step E（pop-os）：Build plugin + 傳入 sandbox

⚠️ sandbox 無法安裝 esbuild（npmjs.org 被封），需在 pop-os 側 build：

```bash
# Step E-1: Build dist/index.js（若 tar.gz 內無 dist/）
cd /tmp && tar xzf ~/ceclaw/backup/openclaw-plugin-searxng-full.tar.gz
cd openclaw-plugin-searxng
npm install
npx esbuild index.ts --bundle --format=esm --outfile=dist/index.js --external:@sinclair/typebox
ls dist/index.js && echo "build OK"

# Step E-2: 取 token（需有活著的 SSH session）
TOKEN=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "token [a-z0-9-]*" | head -1 | awk '{print $2}')
[ -z "$TOKEN" ] && echo "ERROR: no active SSH session，請先確認 openshell gateway 在跑" && exit 1

# Step E-3: 傳 plugin tar.gz
scp -o ProxyCommand="/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id f24db4d6-9135-416c-a090-dbd281ebcd75 --token $TOKEN --gateway-name openshell" \
  ~/ceclaw/backup/openclaw-plugin-searxng-full.tar.gz sandbox@ceclaw-agent:/tmp/

# Step E-4: 建立 dist/ 並傳入編譯好的 index.js
ssh -o ProxyCommand="/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id f24db4d6-9135-416c-a090-dbd281ebcd75 --token $TOKEN --gateway-name openshell" \
  sandbox@ceclaw-agent "mkdir -p /sandbox/.openclaw/extensions/searxng-search/dist"
scp -o ProxyCommand="/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id f24db4d6-9135-416c-a090-dbd281ebcd75 --token $TOKEN --gateway-name openshell" \
  /tmp/openclaw-plugin-searxng/dist/index.js sandbox@ceclaw-agent:/sandbox/.openclaw/extensions/searxng-search/dist/index.js
```

### 進 sandbox 執行：

```bash
openshell sandbox connect ceclaw-agent
```

```bash
# Step A: 安裝 CECLAW plugin
openclaw plugins install /opt/ceclaw

# Step B: tui alias
grep -q "alias tui=" ~/.bashrc || echo "alias tui='openclaw tui --session fresh-\$(date +%s) --history-limit 20'" >> ~/.bashrc

# Step C: openclaw.json patch（contextWindow + compaction + tools）
python3 - << 'EOF'
import json
path = "/sandbox/.openclaw/openclaw.json"
cfg = json.load(open(path))
for model in cfg["models"]["providers"]["local"]["models"]:
    model["contextWindow"] = 32768
    model["maxTokens"] = 4096
cfg["agents"]["defaults"]["compaction"] = {"mode": "safeguard", "reserveTokens": 8000}
cfg["tools"] = {}  # 移除 coding profile，讓 searxng_search 可用
json.dump(cfg, open(path, "w"), indent=4, ensure_ascii=False)
print("done")
EOF

# Step D: gateway auto-start
grep -q "openclaw gateway run" ~/.bashrc || cat >> ~/.bashrc << 'BEOF'
if ! pgrep -f "openclaw-gatewa" > /dev/null 2>&1; then
    openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 &
fi
BEOF

# Step F: 安裝 SearXNG plugin + 修正 package.json
cd /tmp && tar xzf openclaw-plugin-searxng-full.tar.gz
rm -rf ~/.openclaw/extensions/searxng-search 2>/dev/null
openclaw plugins install /tmp/openclaw-plugin-searxng

# 修正 package.json（name + extensions 指向 dist/index.js）
python3 - << 'EOF'
import json
path = "/sandbox/.openclaw/extensions/searxng-search/package.json"
pkg = json.load(open(path))
pkg["name"] = "searxng-search"
pkg["openclaw"]["extensions"] = ["./dist/index.js"]
json.dump(pkg, open(path, "w"), indent=2, ensure_ascii=False)
print("package.json done")
EOF

# 修正 openclaw.json plugin config
python3 - << 'EOF'
import json
path = "/sandbox/.openclaw/openclaw.json"
cfg = json.load(open(path))
cfg["plugins"]["entries"]["searxng-search"]["config"]["baseUrl"] = "http://host.openshell.internal:8000"
json.dump(cfg, open(path, "w"), indent=4, ensure_ascii=False)
print("openclaw.json done")
EOF

source ~/.bashrc
```

---

## Step 13：端到端驗證

```bash
# sandbox 內
tui
# 問：你是誰 → 我是 CECLAW 企業 AI 助手
# 問：今天台北天氣如何？ → 有搜尋結果
```

```bash
# pop-os
tail -f ~/.ceclaw/router.log
# 看到: [local] gb10-llama → 200
ceclaw status   # 三項全綠
```

---

## Step 14：備份關鍵檔案

```bash
mkdir -p ~/ceclaw/backup
scp gb10:~/start_llama.sh ~/ceclaw/backup/start_llama.sh.bak
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

# 3. GB10（systemd 自啟，確認）
ssh gb10 'sudo systemctl status llama-server'

# 4. SearXNG（docker --restart=always，自動起）
docker ps | grep searxng

# 5. 連 sandbox（gateway 自動啟動）
openshell sandbox connect ceclaw-agent
tui
```

---

## ⚠️ 關鍵注意事項

**坑#10（關鍵）**: 不要改 `baseUrl` 為 IP，保持 `host.openshell.internal:8000/v1`

**坑#23（關鍵）**: **不要 `docker restart` openshell container**
- 會讓 K3s 網路混亂，sandbox SSH 死掉
- 正確做法：等 pod 自己恢復，或用 `openshell term`

**坑#24**: sandbox SearXNG plugin 每次重建後消失，必須執行 Step E+F

**坑#25（關鍵）**: `openclaw.json tools.profile: "coding"` 會擋住 searxng_search。Step C 必須加 `cfg["tools"] = {}`

**坑#26**: SearXNG plugin 缺少 `dist/index.js`（需在 pop-os 側 esbuild 編譯後 scp 進 sandbox）

**坑#27（關鍵）**: `--parallel 2` 讓每 slot 只有 16384 tokens → 搜尋結果塞滿後 400。必須用 `--parallel 1`

**sandbox 重建後**：必須執行 Step 12 的全部 6 步（A + B + C + D + E + F）

---

*CECLAW — Secure local AI agents, your inference, your rules.*
*SOP 版本: 1.9 | 日期: 2026-03-23*
