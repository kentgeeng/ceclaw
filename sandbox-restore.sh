#!/bin/bash
# CECLAW Sandbox Restore Script v3.2
# 用法：bash ~/ceclaw/sandbox-restore.sh
# 前置：需要先在另一個終端 openshell sandbox connect <sandbox-name>
# v3.2 修正：
#   - http_proxy 也要設（gateway 連 Router 需要）
#   - no_proxy 不包含 host.openshell.internal（讓 http_proxy 幫轉發）
#   - 加 Step G: 環境自我檢查
# v3.1 修正：UserKnownHostsFile=/dev/null
# v3.0 修正：searxng 移除，policy 自動套用

SANDBOX_NAME="ceclaw-agent"
BACKUP_DIR=~/ceclaw/backup
echo "=== CECLAW Sandbox Restore v3.2 ==="

# Step 1: 確認 sandbox
echo "[1/7] 確認 sandbox..."
openshell sandbox list | grep -q "$SANDBOX_NAME" || { echo "ERROR: $SANDBOX_NAME 不存在"; exit 1; }

# Step 2: 動態取 sandbox-id + token
echo "[2/7] 取得 sandbox-id + token..."
SANDBOX_ID=${SANDBOX_ID:-$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "sandbox-id [a-z0-9-]*" | head -1 | awk '{print $2}')}
TOKEN=${TOKEN:-$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "token [a-z0-9-]*" | head -1 | awk '{print $2}')}

if [ -z "$TOKEN" ] || [ -z "$SANDBOX_ID" ]; then
    echo "ERROR: 需要先建立 SSH session"
    echo "  openshell sandbox connect $SANDBOX_NAME"
    exit 1
fi
echo "  sandbox-id: $SANDBOX_ID"
echo "  token: OK"

PROXY="ProxyCommand=/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id $SANDBOX_ID --token $TOKEN --gateway-name openshell"
SSH_OPTS="StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"

# Step 3: 套用 openshell policy
echo "[3/7] 套用 network policy..."
openshell policy set "$SANDBOX_NAME" --policy ~/ceclaw/config/ceclaw-policy.yaml --wait 2>/dev/null && \
    echo "  policy OK" || echo "  policy set 失敗，繼續..."

# Step 4: 寫 sandbox_init.py
cat > /tmp/sandbox_init.py << 'PYEOF'
import json, subprocess, os, shutil

print("=== sandbox_init.py v3.2 開始 ===")

CFG_PATH = "/sandbox/.openclaw/openclaw.json"
bashrc_path = os.path.expanduser("~/.bashrc")

# Step A: install ceclaw plugin
r = subprocess.run(["openclaw", "plugins", "install", "/opt/ceclaw"], capture_output=True, text=True)
print("Step A:", "OK" if r.returncode == 0 else r.stderr.strip())

# Step B: tui alias
bashrc = open(bashrc_path).read()
if "alias tui=" not in bashrc:
    with open(bashrc_path, "a") as f:
        f.write('\nalias tui=\'openclaw tui --session fresh-$(date +%s) --history-limit 20\'\n')
    print("Step B: alias added")
else:
    print("Step B: alias already exists")

# Step C: openclaw.json 完整 patch
cfg = json.load(open(CFG_PATH))

if "models" not in cfg:
    cfg["models"] = {}
if "providers" not in cfg["models"]:
    cfg["models"]["providers"] = {}
if "local" not in cfg["models"]["providers"]:
    cfg["models"]["providers"]["local"] = {}

local = cfg["models"]["providers"]["local"]
local["baseUrl"] = "http://host.openshell.internal:8000/v1"
local["apiKey"] = "ceclaw-local-key"
local["api"] = "openai-completions"
if "models" not in local:
    local["models"] = []
minimax = next((m for m in local["models"] if m.get("id") == "minimax"), None)
if minimax is None:
    local["models"].append({"id": "minimax", "name": "minimax", "contextWindow": 32768, "maxTokens": 4096})
else:
    minimax["contextWindow"] = 32768
    minimax["maxTokens"] = 4096

if "gateway" not in cfg:
    cfg["gateway"] = {}
cfg["gateway"]["mode"] = "local"

if "agents" not in cfg:
    cfg["agents"] = {}
if "defaults" not in cfg["agents"]:
    cfg["agents"]["defaults"] = {}
cfg["agents"]["defaults"]["compaction"] = {"mode": "safeguard", "reserveTokens": 8000}
cfg["agents"]["defaults"]["model"] = {"primary": "local/minimax"}

cfg["tools"] = {
    "web": {
        "search": {"enabled": False},
        "fetch": {"enabled": True}
    }
}

if "plugins" not in cfg:
    cfg["plugins"] = {}
if "entries" not in cfg["plugins"]:
    cfg["plugins"]["entries"] = {}
cfg["plugins"].pop("allow", None)
cfg["plugins"]["entries"].pop("searxng-search", None)

json.dump(cfg, open(CFG_PATH, "w"), indent=4, ensure_ascii=False)
print("Step C: openclaw.json patched")

# Step D: gateway autostart
bashrc = open(bashrc_path).read()
if "openclaw gateway run" not in bashrc:
    with open(bashrc_path, "a") as f:
        f.write('\nif ! pgrep -f "openclaw-gatewa" > /dev/null 2>&1; then\n    openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 &\nfi\n')
    print("Step D: gateway autostart added")
else:
    print("Step D: already exists")

# Step E: proxy 持久化
# 關鍵：http_proxy 也要設，gateway 透過 K3s proxy 連 Router
# no_proxy 不加 host.openshell.internal（讓 proxy 幫做 DNS 解析）
lines = open(bashrc_path).read().splitlines()
clean_lines = []
skip = False
for line in lines:
    if '# CECLAW proxy' in line or '# override openshell' in line:
        skip = True
        continue
    if skip and (line.startswith('export') or line.startswith('unset')) and \
       any(k in line for k in ['PROXY', 'proxy']):
        continue
    if skip and line.strip() == '':
        skip = False
        continue
    clean_lines.append(line)

clean_lines += [
    '',
    '# CECLAW proxy（v3.2：http+https 都走 K3s proxy）',
    'unset ALL_PROXY HTTPS_PROXY HTTP_PROXY http_proxy https_proxy grpc_proxy no_proxy NO_PROXY',
    'export http_proxy=http://10.200.0.1:3128',
    'export https_proxy=http://10.200.0.1:3128',
    'export HTTP_PROXY=http://10.200.0.1:3128',
    'export HTTPS_PROXY=http://10.200.0.1:3128',
    '# no_proxy 不含 host.openshell.internal（讓 proxy 幫做 DNS）',
    'export no_proxy="127.0.0.1,localhost"',
    'export NO_PROXY="127.0.0.1,localhost"',
]
with open(bashrc_path, 'w') as f:
    f.write('\n'.join(clean_lines) + '\n')
print("Step E: proxy 設定寫入完成（http+https，no_proxy 最小化）")

# Step F: 移除壞掉的 searxng-search 目錄
searxng_dir = "/sandbox/.openclaw/extensions/searxng-search"
if os.path.exists(searxng_dir):
    shutil.rmtree(searxng_dir)
    print("Step F: searxng-search 移除（坑#77）")
else:
    print("Step F: searxng-search 不存在，跳過")

# auth-profiles.json
auth_dir = "/sandbox/.openclaw/agents/main/agent"
os.makedirs(auth_dir, exist_ok=True)
auth = {"local": {"apiKey": "ceclaw-local-key"}}
json.dump(auth, open(os.path.join(auth_dir, "auth-profiles.json"), "w"), indent=4)
print("auth-profiles.json: created")

print("=== ALL DONE ===")
PYEOF

# Step 5: 執行初始化
echo "[5/7] 執行 sandbox 初始化..."
scp -o "$SSH_OPTS" -o "$PROXY" /tmp/sandbox_init.py sandbox@ceclaw-agent:/tmp/
ssh -o "$SSH_OPTS" -o "$PROXY" sandbox@ceclaw-agent "python3 /tmp/sandbox_init.py"

# Step 6: 重啟 gateway
echo "[6/7] 重啟 gateway..."
ssh -o "$SSH_OPTS" -o "$PROXY" sandbox@ceclaw-agent \
    "pkill -9 -f 'openclaw-gatewa' 2>/dev/null; sleep 3; source ~/.bashrc; openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 & sleep 10; tail -3 /tmp/openclaw-gateway.log"

# Step 7: 自我檢查
echo "[7/7] 環境自我檢查..."
CHECK=$(ssh -o "$SSH_OPTS" -o "$PROXY" sandbox@ceclaw-agent '
echo "proxy: http_proxy=$http_proxy"
echo "gateway: $(pgrep -f openclaw-gatewa > /dev/null && echo running || echo DEAD)"
echo "router: $(curl -s -m 3 http://host.openshell.internal:8000/ceclaw/status | python3 -c "import json,sys; print(json.load(sys.stdin)[\"version\"])" 2>/dev/null || echo FAIL)"
echo "identity: $(curl -s -m 10 -X POST http://host.openshell.internal:8000/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"minimax\",\"messages\":[{\"role\":\"user\",\"content\":\"你是誰\"}],\"max_tokens\":30}" | python3 -c "import json,sys; print(json.load(sys.stdin)[\"choices\"][0][\"message\"][\"content\"][:30])" 2>/dev/null || echo FAIL)"
' 2>/dev/null)

echo "$CHECK"

echo ""
echo "✅ Restore v3.2 完成！"
echo ""
echo "驗證（在 sandbox 終端）："
echo "  tui → 問：你是誰 / 今天台北天氣如何？"
echo ""
echo "⚠️ 坑#77：searxng plugin 暫停（openclaw 2026.3.11 extensions path bug）"
echo "⚠️ 新 host 的 web_fetch 需在 openshell term approve 一次"
