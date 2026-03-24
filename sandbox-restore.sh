#!/bin/bash
# CECLAW Sandbox Restore Script v1.2
# 用法：bash ~/ceclaw/sandbox-restore.sh
# 前置：需要先在另一個終端 openshell sandbox connect ceclaw-agent

BACKUP_DIR=~/ceclaw/backup
echo "=== CECLAW Sandbox Restore v1.2 ==="

# Step 1: 確認 sandbox
echo "[1/6] 確認 sandbox..."
openshell sandbox list | grep -q "ceclaw-agent" || { echo "ERROR: ceclaw-agent 不存在"; exit 1; }

# Step 2: 動態取 sandbox-id + token
echo "[2/6] 取得 sandbox-id + token..."
SANDBOX_ID=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "sandbox-id [a-z0-9-]*" | head -1 | awk '{print $2}')
TOKEN=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "token [a-z0-9-]*" | head -1 | awk '{print $2}')

if [ -z "$TOKEN" ] || [ -z "$SANDBOX_ID" ]; then
    echo ""
    echo "ERROR: 需要先建立 SSH session"
    echo "請在另一個終端執行："
    echo "  openshell sandbox connect ceclaw-agent"
    echo "然後重新執行此腳本"
    exit 1
fi
echo "  sandbox-id: $SANDBOX_ID"
echo "  token: OK"

PROXY="ProxyCommand=/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id $SANDBOX_ID --token $TOKEN --gateway-name openshell"

# Step 3: Build plugin
echo "[3/6] Build SearXNG plugin..."
cd /tmp
rm -rf openclaw-plugin-searxng 2>/dev/null
tar xzf $BACKUP_DIR/openclaw-plugin-searxng-full.tar.gz
cd openclaw-plugin-searxng
npm install --silent 2>/dev/null
npx esbuild index.ts --bundle --format=esm --outfile=dist/index.js --external:@sinclair/typebox --log-level=silent
[ -f dist/index.js ] && echo "  build OK" || { echo "ERROR: build failed"; exit 1; }

# Step 4: 傳入 sandbox
echo "[4/6] 傳入檔案..."
scp -o "$PROXY" $BACKUP_DIR/openclaw-plugin-searxng-full.tar.gz sandbox@ceclaw-agent:/tmp/
ssh -o "$PROXY" sandbox@ceclaw-agent "mkdir -p /sandbox/.openclaw/extensions/searxng-search/dist"
scp -o "$PROXY" /tmp/openclaw-plugin-searxng/dist/index.js sandbox@ceclaw-agent:/sandbox/.openclaw/extensions/searxng-search/dist/index.js
echo "  傳入完成"

# Step 5: 寫 sandbox_init.py
cat > /tmp/sandbox_init.py << 'PYEOF'
import json, subprocess, os, shutil

print("=== sandbox_init.py v1.2 開始 ===")

CFG_PATH = "/sandbox/.openclaw/openclaw.json"

# Step A: install ceclaw plugin
r = subprocess.run(["openclaw", "plugins", "install", "/opt/ceclaw"], capture_output=True, text=True)
print("Step A:", "OK" if r.returncode == 0 else r.stderr.strip())

# Step B: tui alias
bashrc_path = os.path.expanduser("~/.bashrc")
bashrc = open(bashrc_path).read()
if "alias tui=" not in bashrc:
    with open(bashrc_path, "a") as f:
        f.write('\nalias tui=\'openclaw tui --session fresh-$(date +%s) --history-limit 20\'\n')
    print("Step B: alias added")
else:
    print("Step B: alias already exists")

# Step C: openclaw.json 完整 patch
cfg = json.load(open(CFG_PATH))

# models（防止 KeyError，全新 sandbox 可能無此 key）
if "models" not in cfg:
    cfg["models"] = {}
if "providers" not in cfg["models"]:
    cfg["models"]["providers"] = {}
if "local" not in cfg["models"]["providers"]:
    cfg["models"]["providers"]["local"] = {}

local = cfg["models"]["providers"]["local"]
local["baseUrl"] = "http://host.openshell.internal:8000/v1"
local["apiKey"] = "ceclaw-local-key"
local["api"] = "openai-completions"   # 坑#69 關鍵欄位
if "models" not in local:
    local["models"] = []
minimax = next((m for m in local["models"] if m.get("id") == "minimax"), None)
if minimax is None:
    local["models"].append({"id": "minimax", "name": "minimax", "contextWindow": 32768, "maxTokens": 4096})
else:
    minimax["contextWindow"] = 32768
    minimax["maxTokens"] = 4096

# gateway
if "gateway" not in cfg:
    cfg["gateway"] = {}
cfg["gateway"]["mode"] = "local"

# agents
if "agents" not in cfg:
    cfg["agents"] = {}
if "defaults" not in cfg["agents"]:
    cfg["agents"]["defaults"] = {}
cfg["agents"]["defaults"]["compaction"] = {"mode": "safeguard", "reserveTokens": 8000}
cfg["agents"]["defaults"]["model"] = {"primary": "local/minimax"}

# tools（Bug#3修復：停用內建 web search，強制模型只能用 searxng_search）
# 注意：plugins.allow 不設（Bug#1修復：設了反而讓 plugin 不載入，用 auto-load）
cfg["tools"] = {
    "web": {
        "search": {"enabled": False},  # 停用內建 Brave，模型才會選 searxng_search
        "fetch": {"enabled": False}
    }
}

# plugins（不設 allow，讓 auto-load 生效）
if "plugins" not in cfg:
    cfg["plugins"] = {}
if "entries" not in cfg["plugins"]:
    cfg["plugins"]["entries"] = {}
# 移除 allow key（如果存在）
cfg["plugins"].pop("allow", None)

json.dump(cfg, open(CFG_PATH, "w"), indent=4, ensure_ascii=False)
print("Step C: openclaw.json patched (api/apiKey/gateway/model, tools disabled, no allow)")

# Step D: gateway autostart
bashrc = open(bashrc_path).read()
if "openclaw gateway run" not in bashrc:
    with open(bashrc_path, "a") as f:
        f.write('\nif ! pgrep -f "openclaw-gatewa" > /dev/null 2>&1; then\n    openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 &\nfi\n')
    print("Step D: gateway autostart added")
else:
    print("Step D: already exists")

# Step F: install searxng plugin
shutil.rmtree(os.path.expanduser("~/.openclaw/extensions/searxng-search"), ignore_errors=True)
r = subprocess.run(["openclaw", "plugins", "install", "/tmp/openclaw-plugin-searxng"], capture_output=True, text=True)
print("Step F install:", "OK" if r.returncode == 0 else r.stderr.strip())

# 確認 dist/index.js（由 pop-os scp 進來）
dist_path = "/sandbox/.openclaw/extensions/searxng-search/dist/index.js"
if os.path.exists(dist_path):
    print("Step F dist: index.js OK")
else:
    print("Step F dist: WARNING - index.js not found!")

# Fix package.json（Bug#2修復：用 dist/index.js 不是 ./dist/index.js）
pkg_path = "/sandbox/.openclaw/extensions/searxng-search/package.json"
if os.path.exists(pkg_path):
    pkg = json.load(open(pkg_path))
    pkg["name"] = "searxng-search"
    pkg["openclaw"]["extensions"] = ["dist/index.js"]  # 不加 ./，避免 escapes package directory 錯誤
    json.dump(pkg, open(pkg_path, "w"), indent=2, ensure_ascii=False)
    print("Step F package.json: fixed")

# Fix openclaw.json plugin config
cfg = json.load(open(CFG_PATH))
entry = cfg["plugins"]["entries"].setdefault("searxng-search", {})
entry["enabled"] = True
entry.setdefault("config", {})["baseUrl"] = "http://host.openshell.internal:8000"
json.dump(cfg, open(CFG_PATH, "w"), indent=4, ensure_ascii=False)
print("Step F openclaw.json: searxng baseUrl set")

# auth-profiles.json（無此檔 → No API key found）
auth_dir = "/sandbox/.openclaw/agents/main/agent"
os.makedirs(auth_dir, exist_ok=True)
auth_path = os.path.join(auth_dir, "auth-profiles.json")
auth = {"local": {"apiKey": "ceclaw-local-key"}}
json.dump(auth, open(auth_path, "w"), indent=4)
print("auth-profiles.json: created")

print("=== ALL DONE ===")
PYEOF

# Step 6: 執行
echo "[5/6] 執行 sandbox 初始化..."
scp -o "$PROXY" /tmp/sandbox_init.py sandbox@ceclaw-agent:/tmp/
ssh -o "$PROXY" sandbox@ceclaw-agent "python3 /tmp/sandbox_init.py"

echo "[6/6] 重啟 gateway..."
ssh -o "$PROXY" sandbox@ceclaw-agent "pkill -f 'openclaw-gatewa' 2>/dev/null || true; sleep 2; openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 & sleep 8; tail -5 /tmp/openclaw-gateway.log"

echo ""
echo "✅ Restore 完成！"
echo "驗證（在 sandbox 終端）："
echo "  tui → 問：你是誰 / 今天台北天氣如何？"
