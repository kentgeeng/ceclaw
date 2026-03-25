#!/bin/bash
# CECLAW Sandbox Restore Script v3.1
# 用法：bash ~/ceclaw/sandbox-restore.sh
# 前置：需要先在另一個終端 openshell sandbox connect <sandbox-name>
# v3.1 修正：UserKnownHostsFile=/dev/null，避免 known_hosts 衝突
# v3.0 修正：proxy 只設 https_proxy，searxng 移除，policy 自動套用

SANDBOX_NAME="ceclaw-agent"
BACKUP_DIR=~/ceclaw/backup
echo "=== CECLAW Sandbox Restore v3.1 ==="

# Step 1: 確認 sandbox
echo "[1/7] 確認 sandbox..."
openshell sandbox list | grep -q "$SANDBOX_NAME" || { echo "ERROR: $SANDBOX_NAME 不存在"; exit 1; }

# Step 2: 動態取 sandbox-id + token（支援環境變數覆蓋）
echo "[2/7] 取得 sandbox-id + token..."
SANDBOX_ID=${SANDBOX_ID:-$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "sandbox-id [a-z0-9-]*" | head -1 | awk '{print $2}')}
TOKEN=${TOKEN:-$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "token [a-z0-9-]*" | head -1 | awk '{print $2}')}

if [ -z "$TOKEN" ] || [ -z "$SANDBOX_ID" ]; then
    echo ""
    echo "ERROR: 需要先建立 SSH session"
    echo "請在另一個終端執行："
    echo "  openshell sandbox connect $SANDBOX_NAME"
    echo "然後重新執行此腳本"
    exit 1
fi
echo "  sandbox-id: $SANDBOX_ID"
echo "  token: OK"

PROXY="ProxyCommand=/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id $SANDBOX_ID --token $TOKEN --gateway-name openshell"
SSH_OPTS="StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"

# Step 3: 套用 openshell policy（外網全開放 TLD）
echo "[3/7] 套用 network policy..."
openshell policy set "$SANDBOX_NAME" --policy ~/ceclaw/config/ceclaw-policy.yaml --wait 2>/dev/null && \
    echo "  policy 套用 OK" || echo "  policy set 失敗（可能是舊版 openshell），繼續..."

# Step 4: 寫 sandbox_init.py
cat > /tmp/sandbox_init.py << 'PYEOF'
import json, subprocess, os, shutil

print("=== sandbox_init.py v3.1 開始 ===")

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

# tools（web_fetch 啟用，web_search 停用）
cfg["tools"] = {
    "web": {
        "search": {"enabled": False},
        "fetch": {"enabled": True}
    }
}

# plugins（移除 searxng-search，坑#77：extensions path bug）
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

# Step E: proxy 持久化（只設 https_proxy，不設 http_proxy 避免攔截 Router）
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
    '# CECLAW proxy - 只走 https_proxy（不設 http_proxy 避免攔截 Router）',
    'unset ALL_PROXY HTTPS_PROXY HTTP_PROXY http_proxy https_proxy grpc_proxy no_proxy NO_PROXY',
    'export https_proxy=http://10.200.0.1:3128',
    'export no_proxy="host.openshell.internal,172.17.0.1,127.0.0.1,localhost"',
    'export NO_PROXY="host.openshell.internal,172.17.0.1,127.0.0.1,localhost"',
]
with open(bashrc_path, 'w') as f:
    f.write('\n'.join(clean_lines) + '\n')
print("Step E: proxy 設定寫入完成")

# Step F: 移除壞掉的 searxng-search 目錄
searxng_dir = "/sandbox/.openclaw/extensions/searxng-search"
if os.path.exists(searxng_dir):
    shutil.rmtree(searxng_dir)
    print("Step F: searxng-search 目錄已移除（坑#77）")
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
    "pkill -f 'openclaw-gatewa' 2>/dev/null || true; sleep 2; openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 & sleep 8; tail -5 /tmp/openclaw-gateway.log"

echo "[7/7] 完成"
echo ""
echo "✅ Restore v3.1 完成！"
echo ""
echo "驗證（在 sandbox 終端）："
echo "  source ~/.bashrc && tui"
echo "  問：你是誰 → 我是 CECLAW 企業 AI 助手"
echo "  問：今天台北天氣如何 → 真實天氣數據"
echo ""
echo "⚠️ 坑#77：searxng plugin 暫停，openclaw 2026.3.11 extensions path bug"
echo "⚠️ 新 host 的 web_fetch 需在 openshell term approve 一次"
