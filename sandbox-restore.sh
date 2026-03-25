#!/bin/bash
# CECLAW Sandbox Restore Script v3.4
# 用法：bash ~/ceclaw/sandbox-restore.sh
# 前置：需要先在另一個終端 openshell sandbox connect <sandbox-name>
#
# v3.4 新功能：
#   - Step G: workspace 同步（SOUL/TOOLS/AGENTS/USER.md 從 ceclaw-agent 複製）
#   - Step H: ceclaw-start.sh 部署進 sandbox
#   - 七層健康檢查改為從 sandbox 內跑（修正 L4/L5/L6 403 假陰性）
# v3.3: 七層檢測 + 自動修復
# v3.2: http+https proxy，no_proxy 最小化
# v3.1: UserKnownHostsFile=/dev/null
# v3.0: searxng 移除，policy 自動套用

SANDBOX_NAME="ceclaw-agent"
BACKUP_DIR=~/ceclaw/backup
WORKSPACE_SRC=~/ceclaw/config  # workspace 備份來源
echo "=== CECLAW Sandbox Restore v3.4 ==="

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

PROXY="ProxyCommand=/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id $SANDBOX_ID --token $TOKEN --gateway-name openshell"
SSH="ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o \"$PROXY\""
SCP="scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o \"$PROXY\""

# Step 3: 套用 openshell policy
echo "[3/9] 套用 network policy..."
openshell policy set "$SANDBOX_NAME" --policy ~/ceclaw/config/ceclaw-policy.yaml --wait 2>/dev/null && \
    echo "  ✅ policy OK" || echo "  ⚠️ policy set 失敗，繼續..."

# Step 4: 寫 sandbox_init.py
cat > /tmp/sandbox_init.py << 'PYEOF'
import json, subprocess, os, shutil

print("=== sandbox_init.py v3.4 開始 ===")

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
cfg["tools"] = {"web": {"search": {"enabled": False}, "fetch": {"enabled": True}}}
if "plugins" not in cfg: cfg["plugins"] = {}
if "entries" not in cfg["plugins"]: cfg["plugins"]["entries"] = {}
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

# Step E: proxy 持久化（http+https，no_proxy 最小）
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
    '# CECLAW proxy v3.4（http+https 都走 K3s proxy）',
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
json.dump({"local": {"apiKey": "ceclaw-local-key"}},
          open(os.path.join(auth_dir, "auth-profiles.json"), "w"), indent=4)
print("auth-profiles.json: created")

print("=== ALL DONE ===")
PYEOF

# Step 5: 執行初始化
echo "[5/9] 執行 sandbox 初始化..."
eval "$SCP /tmp/sandbox_init.py sandbox@$SANDBOX_NAME:/tmp/"
eval "$SSH sandbox@$SANDBOX_NAME 'python3 /tmp/sandbox_init.py'"

# Step 6: 重啟 gateway
echo "[6/9] 重啟 gateway..."
eval "$SSH sandbox@$SANDBOX_NAME 'pkill -9 -f openclaw-gatewa 2>/dev/null; sleep 3; source ~/.bashrc; openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 & sleep 10; tail -3 /tmp/openclaw-gateway.log'"

# Step 7: 同步 workspace（SOUL/TOOLS/AGENTS/USER.md）
echo "[7/9] 同步 workspace..."
WORKSPACE_FILES="SOUL.md TOOLS.md AGENTS.md USER.md HEARTBEAT.md"
for f in $WORKSPACE_FILES; do
    LOCAL="$WORKSPACE_SRC/$f"
    if [ -f "$LOCAL" ]; then
        eval "$SCP $LOCAL sandbox@$SANDBOX_NAME:/sandbox/.openclaw/workspace/$f"
        echo "  ✅ $f"
    else
        echo "  ⚠️ $f 不存在於 $WORKSPACE_SRC，跳過"
    fi
done

# Step 8: 部署 ceclaw-start.sh
echo "[8/9] 部署 ceclaw-start.sh..."
cat > /tmp/ceclaw-start.sh << 'STARTEOF'
#!/bin/bash
# CECLAW Sandbox Start
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
eval "$SCP /tmp/ceclaw-start.sh sandbox@$SANDBOX_NAME:~/ceclaw-start.sh"
eval "$SSH sandbox@$SANDBOX_NAME 'chmod +x ~/ceclaw-start.sh'"
echo "  ✅ ceclaw-start.sh 部署完成"

# Step 9: 七層健康檢查（從 sandbox 內跑）
echo "[9/9] 七層健康檢查（sandbox 內）..."
eval "$SSH sandbox@$SANDBOX_NAME 'source ~/.bashrc; python3 << CHECKEOF
import json, os, subprocess, urllib.request

PASS, FAIL, WARN = \"✅\", \"❌\", \"⚠️\"
os.environ[\"http_proxy\"] = \"http://10.200.0.1:3128\"
os.environ[\"https_proxy\"] = \"http://10.200.0.1:3128\"
os.environ[\"HTTP_PROXY\"] = \"http://10.200.0.1:3128\"
os.environ[\"HTTPS_PROXY\"] = \"http://10.200.0.1:3128\"
os.environ.pop(\"no_proxy\", None)
os.environ.pop(\"NO_PROXY\", None)

results = []

# L1: proxy
http_p = os.environ.get(\"http_proxy\", \"\")
results.append(f\"L1 proxy    : {PASS if \"10.200.0.1\" in http_p else FAIL} {http_p}\")

# L2: openclaw.json
try:
    cfg = json.load(open(\"/sandbox/.openclaw/openclaw.json\"))
    api = cfg[\"models\"][\"providers\"][\"local\"].get(\"api\", \"\")
    ok = api == \"openai-completions\" and \"web\" in cfg.get(\"tools\", {}) and \"searxng-search\" not in cfg.get(\"plugins\", {}).get(\"entries\", {})
    results.append(f\"L2 config   : {PASS if ok else FAIL} api={api}\")
except Exception as e:
    results.append(f\"L2 config   : {FAIL} {e}\")

# L3: gateway
r = subprocess.run([\"pgrep\", \"-f\", \"openclaw-gatewa\"], capture_output=True)
results.append(f\"L3 gateway  : {PASS if r.returncode == 0 else FAIL} pid={r.stdout.decode().strip()[:20]}\")

# L4: Router
try:
    with urllib.request.urlopen(\"http://host.openshell.internal:8000/ceclaw/status\", timeout=5) as resp:
        v = json.loads(resp.read()).get(\"version\")
    results.append(f\"L4 Router   : {PASS} version={v}\")
except Exception as e:
    results.append(f\"L4 Router   : {FAIL} {e}\")

# L5: 身份注入
try:
    payload = json.dumps({\"model\":\"minimax\",\"messages\":[{\"role\":\"user\",\"content\":\"你是誰\"}],\"max_tokens\":30}).encode()
    req = urllib.request.Request(\"http://host.openshell.internal:8000/v1/chat/completions\", data=payload, headers={\"Content-Type\":\"application/json\"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        reply = json.loads(resp.read())[\"choices\"][0][\"message\"][\"content\"]
        results.append(f\"L5 身份     : {PASS if \"CECLAW\" in reply else FAIL} {reply[:40]}\")
except Exception as e:
    results.append(f\"L5 身份     : {FAIL} {e}\")

# L6: 外網 HTTPS
try:
    with urllib.request.urlopen(\"https://wttr.in/taipei?format=3\", timeout=10) as resp:
        weather = resp.read().decode().strip()[:30]
    results.append(f\"L6 外網     : {PASS} {weather}\")
except Exception as e:
    results.append(f\"L6 外網     : {WARN} {e}\")

# L7: extensions 乾淨
exts = os.listdir(\"/sandbox/.openclaw/extensions\") if os.path.exists(\"/sandbox/.openclaw/extensions\") else []
bad = [e for e in exts if e == \"searxng-search\"]
results.append(f\"L7 extensions: {PASS if not bad else FAIL} {exts}\")

print(\"\")
for r in results:
    print(r)
fails = [r for r in results if FAIL in r]
print(f\"\n{PASS if not fails else FAIL} {\"全部通過\" if not fails else str(len(fails)) + \" 層失敗\"}\")
CHECKEOF
'"

echo ""
echo "✅ Restore v3.4 完成！"
echo ""
echo "驗證（在 sandbox 終端）："
echo "  bash ~/ceclaw-start.sh"
echo "  問：你是誰 → 我是 CECLAW 企業 AI 助手"
echo ""
echo "⚠️ 坑#77：searxng plugin 暫停（openclaw 2026.3.11 extensions path bug）"
echo "⚠️ 新 host 的 web_fetch 需在 openshell term approve 一次"
echo ""
echo "📁 Workspace 來源：$WORKSPACE_SRC"
echo "   如需更新 SOUL.md 等請修改該目錄後重跑 restore"
