#!/bin/bash
# CECLAW Sandbox Restore Script v3.5-net
# 用法：bash ~/ceclaw/sandbox-restore.sh
# 前置：需要先在另一個終端 openshell sandbox connect <sandbox-name>
#
# v3.5-net 新功能：
#   - 支援 test-net（base image，無 /opt/ceclaw）
#   - Step C: fetch: false（讓 drawliin-searxng 接管）
#   - Step C: 加入 searxng-search plugin 指向 Router /search
#   - Step F: 保留 drawliin-searxng 目錄，只移除舊的 searxng-search
#   - SSH/SCP 目標改用 SANDBOX_NAME 變數
# v3.4: workspace 同步，ceclaw-start.sh 部署，sandbox 內健康檢查
# v3.3: 七層檢測 + 自動修復
# v3.2: http+https proxy，no_proxy 最小化
# v3.1: UserKnownHostsFile=/dev/null
# v3.0: searxng 移除，policy 自動套用

SANDBOX_NAME="${SANDBOX_NAME:-test-net}"
WORKSPACE_SRC=~/ceclaw/config
echo "=== CECLAW Sandbox Restore v3.5-net ==="
echo "  target: $SANDBOX_NAME"

# Step 1: 確認 sandbox
echo "[1/9] 確認 sandbox..."
openshell sandbox list | grep -q "$SANDBOX_NAME" || { echo "ERROR: $SANDBOX_NAME 不存在"; exit 1; }

# Step 2: 動態取 sandbox-id + token
echo "[2/9] 取得 sandbox-id + token..."
SANDBOX_ID=${SANDBOX_ID:-$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "sandbox-id [a-z0-9-]*" | head -1 | awk '{print $2}')}
TOKEN=${TOKEN:-$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "token [a-z0-9-]*" | head -1 | awk '{print $2}')}

if [ -z "$TOKEN" ] || [ -z "$SANDBOX_ID" ]; then
    echo "ERROR: 需要先建立 SSH session"
    echo "  openshell sandbox connect $SANDBOX_NAME"
    exit 1
fi
echo "  sandbox-id: $SANDBOX_ID"
echo "  token: OK"

PROXY_CMD="/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id $SANDBOX_ID --token $TOKEN --gateway-name openshell"
SSH_BASE="ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
SCP_BASE="scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"

run_ssh() {
    $SSH_BASE -o "ProxyCommand=$PROXY_CMD" sandbox@"$SANDBOX_NAME" "$@"
}
run_scp() {
    local src=$1; local dst=$2
    $SCP_BASE -o "ProxyCommand=$PROXY_CMD" "$src" sandbox@"$SANDBOX_NAME":"$dst"
}

# Step 3: 套用 openshell policy
echo "[3/9] 套用 network policy..."
openshell policy set "$SANDBOX_NAME" --policy ~/ceclaw/config/ceclaw-policy.yaml --wait 2>/dev/null && \
    echo "  ✅ policy OK" || echo "  ⚠️ policy set 失敗，繼續..."

# Step 4: 寫 sandbox_init.py
cat > /tmp/sandbox_init.py << 'PYEOF'
import json, subprocess, os, shutil

print("=== sandbox_init.py v3.5-net 開始 ===")

CFG_PATH = "/sandbox/.openclaw/openclaw.json"
bashrc_path = os.path.expanduser("~/.bashrc")

# Step A: install ceclaw plugin（base image 可能沒有 /opt/ceclaw，跳過）
if os.path.exists("/opt/ceclaw"):
    r = subprocess.run(["openclaw", "plugins", "install", "/opt/ceclaw"], capture_output=True, text=True)
    print("Step A:", "OK" if r.returncode == 0 else r.stderr.strip())
else:
    print("Step A: /opt/ceclaw 不存在（base image），跳過")

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
if "models" not in cfg: cfg["models"] = {}
if "providers" not in cfg["models"]: cfg["models"]["providers"] = {}
if "local" not in cfg["models"]["providers"]: cfg["models"]["providers"]["local"] = {}

local = cfg["models"]["providers"]["local"]
local["baseUrl"] = "http://host.openshell.internal:8000/v1"
local["apiKey"] = "ceclaw-local-key"
local["api"] = "openai-completions"
if "models" not in local: local["models"] = []
minimax = next((m for m in local["models"] if m.get("id") == "minimax"), None)
if minimax is None:
    local["models"].append({"id": "minimax", "name": "minimax", "contextWindow": 32768, "maxTokens": 4096})
else:
    minimax["contextWindow"] = 32768
    minimax["maxTokens"] = 4096

if "gateway" not in cfg: cfg["gateway"] = {}
cfg["gateway"]["mode"] = "local"
if "agents" not in cfg: cfg["agents"] = {}
if "defaults" not in cfg["agents"]: cfg["agents"]["defaults"] = {}
cfg["agents"]["defaults"]["compaction"] = {"mode": "safeguard", "reserveTokens": 8000}
cfg["agents"]["defaults"]["model"] = {"primary": "local/minimax"}

# fetch: false → drawliin-searxng 接管
cfg["tools"] = {"web": {"search": {"enabled": False}, "fetch": {"enabled": False}}}

if "plugins" not in cfg: cfg["plugins"] = {}
if "entries" not in cfg["plugins"]: cfg["plugins"]["entries"] = {}
cfg["plugins"].pop("allow", None)

# 移除舊 plugin 名稱
for old_key in ["ceclaw", "@drawliin/searxng-search", "drawliin-searxng"]:
    cfg["plugins"]["entries"].pop(old_key, None)

# 加入正確 plugin（名稱 searxng-search，指向 Router）
cfg["plugins"]["entries"]["searxng-search"] = {
    "enabled": True,
    "config": {
        "searxngUrl": "http://host.openshell.internal:8000/search"
    }
}

json.dump(cfg, open(CFG_PATH, "w"), indent=4, ensure_ascii=False)
print("Step C: openclaw.json patched")
print("  tools.web.fetch:", cfg["tools"]["web"]["fetch"])
print("  plugins:", list(cfg["plugins"]["entries"].keys()))

# Step D: gateway autostart
bashrc = open(bashrc_path).read()
if "openclaw gateway run" not in bashrc:
    with open(bashrc_path, "a") as f:
        f.write('\nif ! pgrep -f "openclaw-gatewa" > /dev/null 2>&1; then\n    openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 &\nfi\n')
    print("Step D: gateway autostart added")
else:
    print("Step D: already exists")

# Step E: proxy 持久化
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
    '# CECLAW proxy v3.5-net',
    'unset ALL_PROXY HTTPS_PROXY HTTP_PROXY http_proxy https_proxy grpc_proxy no_proxy NO_PROXY',
    'export http_proxy=http://10.200.0.1:3128',
    'export https_proxy=http://10.200.0.1:3128',
    'export HTTP_PROXY=http://10.200.0.1:3128',
    'export HTTPS_PROXY=http://10.200.0.1:3128',
    'export no_proxy="127.0.0.1,localhost"',
    'export NO_PROXY="127.0.0.1,localhost"',
]
with open(bashrc_path, 'w') as f:
    f.write('\n'.join(clean_lines) + '\n')
print("Step E: proxy 設定寫入完成")

# Step F: 只移除舊的 searxng-search 目錄，保留 drawliin-searxng
OLD_DIR = "/sandbox/.openclaw/extensions/searxng-search"
KEEP_DIR = "/sandbox/.openclaw/extensions/drawliin-searxng"
if os.path.exists(OLD_DIR):
    shutil.rmtree(OLD_DIR)
    print("Step F: 舊 searxng-search 目錄移除（坑#77）")
else:
    print("Step F: 舊 searxng-search 不存在，跳過")

if os.path.exists(KEEP_DIR):
    print(f"Step F: drawliin-searxng 已存在，保留 ✅")
else:
    print(f"Step F: ⚠️ drawliin-searxng 不存在，請手動安裝：")
    print(f"  cd ~/.openclaw/extensions")
    print(f"  git clone https://github.com/drawliin/openclaw-searxng drawliin-searxng")
    print(f"  cd drawliin-searxng && npm install && npm run build")

# auth-profiles.json
auth_dir = "/sandbox/.openclaw/agents/main/agent"
os.makedirs(auth_dir, exist_ok=True)
json.dump({"local": {"apiKey": "ceclaw-local-key"}},
          open(os.path.join(auth_dir, "auth-profiles.json"), "w"), indent=4)
print("auth-profiles.json: created")

print("=== ALL DONE ===")
PYEOF

# Step 5: 執行初始化
echo "[5/9] 執行 sandbox 初始化..."
run_scp /tmp/sandbox_init.py /tmp/sandbox_init.py
run_ssh "python3 /tmp/sandbox_init.py"

# Step 6: 重啟 gateway
echo "[6/9] 重啟 gateway..."
run_ssh "pkill -9 -f openclaw-gatewa 2>/dev/null; sleep 3; source ~/.bashrc; openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 & sleep 10; tail -3 /tmp/openclaw-gateway.log"

# Step 7: 同步 workspace
echo "[7/9] 同步 workspace..."
for f in SOUL.md TOOLS.md AGENTS.md USER.md HEARTBEAT.md; do
    LOCAL="$WORKSPACE_SRC/$f"
    if [ -f "$LOCAL" ]; then
        run_scp "$LOCAL" "/sandbox/.openclaw/workspace/$f" && echo "  ✅ $f" || echo "  ❌ $f 同步失敗"
    else
        echo "  ⚠️ $f 不存在於 $WORKSPACE_SRC，跳過"
    fi
done

# Step 8: 部署 ceclaw-start.sh
echo "[8/9] 部署 ceclaw-start.sh..."
cat > /tmp/ceclaw-start.sh << 'STARTEOF'
#!/bin/bash
echo "🔄 清除殘留進程..."
pkill -9 -f 'openclaw' 2>/dev/null
sleep 3
echo "🔌 載入環境..."
source ~/.bashrc
echo "🚀 啟動 gateway..."
openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 &
sleep 10
echo "✅ 進入 TUI"
openclaw tui --session fresh-$(date +%s) --history-limit 20
STARTEOF
run_scp /tmp/ceclaw-start.sh ~/ceclaw-start.sh
run_ssh "chmod +x ~/ceclaw-start.sh"
echo "  ✅ ceclaw-start.sh 部署完成"

# Step 9: 七層健康檢查（sandbox 內）
echo "[9/9] 七層健康檢查（sandbox 內）..."
run_ssh "source ~/.bashrc; python3 << 'CHECKEOF'
import json, os, subprocess, urllib.request

PASS, FAIL, WARN = '✅', '❌', '⚠️'
os.environ['http_proxy'] = 'http://10.200.0.1:3128'
os.environ['https_proxy'] = 'http://10.200.0.1:3128'
os.environ.pop('no_proxy', None)
os.environ.pop('NO_PROXY', None)
results = []

# L1: proxy
http_p = os.environ.get('http_proxy', '')
results.append(f'L1 proxy    : {PASS if \"10.200.0.1\" in http_p else FAIL} {http_p}')

# L2: openclaw.json
try:
    cfg = json.load(open('/sandbox/.openclaw/openclaw.json'))
    api = cfg['models']['providers']['local'].get('api', '')
    fetch_off = not cfg.get('tools', {}).get('web', {}).get('fetch', {}).get('enabled', True)
    has_searxng = 'searxng-search' in cfg.get('plugins', {}).get('entries', {})
    ok = api == 'openai-completions' and fetch_off and has_searxng
    results.append(f'L2 config   : {PASS if ok else FAIL} api={api} fetch_off={fetch_off} searxng={has_searxng}')
except Exception as e:
    results.append(f'L2 config   : {FAIL} {e}')

# L3: gateway
r = subprocess.run(['pgrep', '-f', 'openclaw-gatewa'], capture_output=True)
results.append(f'L3 gateway  : {PASS if r.returncode == 0 else FAIL} pid={r.stdout.decode().strip()[:20]}')

# L4: Router
try:
    with urllib.request.urlopen('http://host.openshell.internal:8000/ceclaw/status', timeout=5) as resp:
        v = json.loads(resp.read()).get('version')
    results.append(f'L4 Router   : {PASS} version={v}')
except Exception as e:
    results.append(f'L4 Router   : {FAIL} {e}')

# L5: 身份注入
try:
    payload = json.dumps({'model':'minimax','messages':[{'role':'user','content':'你是誰'}],'max_tokens':30}).encode()
    req = urllib.request.Request('http://host.openshell.internal:8000/v1/chat/completions', data=payload, headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        reply = json.loads(resp.read())['choices'][0]['message']['content']
        results.append(f'L5 身份     : {PASS if \"CECLAW\" in reply else FAIL} {reply[:40]}')
except Exception as e:
    results.append(f'L5 身份     : {FAIL} {e}')

# L6: 外網 HTTPS
try:
    with urllib.request.urlopen('https://wttr.in/taipei?format=3', timeout=10) as resp:
        weather = resp.read().decode().strip()[:30]
    results.append(f'L6 外網     : {PASS} {weather}')
except Exception as e:
    results.append(f'L6 外網     : {WARN} {e}')

# L7: drawliin-searxng 目錄存在
exts_path = '/sandbox/.openclaw/extensions'
exts = os.listdir(exts_path) if os.path.exists(exts_path) else []
has_drawliin = 'drawliin-searxng' in exts
results.append(f'L7 extensions: {PASS if has_drawliin else FAIL} {exts}')

print()
for r in results:
    print(r)
fails = [r for r in results if FAIL in r]
print()
if not fails:
    print(f'{PASS} 全部通過')
else:
    print(f'{FAIL} {len(fails)} 層失敗')
CHECKEOF
"

echo ""
echo "✅ Restore v3.5-net 完成！"
echo ""
echo "驗證（在 sandbox 終端）："
echo "  bash ~/ceclaw-start.sh"
echo "  問：你是誰 → 我是 CECLAW 企業 AI 助手"
echo "  問：台積電今天股價 → 應觸發 web_search"
echo ""
echo "📁 Workspace 來源：$WORKSPACE_SRC"
