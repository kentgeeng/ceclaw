#!/bin/bash
# CECLAW Sandbox Restore Script
# 用法：bash ~/ceclaw/sandbox-restore.sh
# 前置：需要先在另一個終端 openshell sandbox connect ceclaw-agent

BACKUP_DIR=~/ceclaw/backup
echo "=== CECLAW Sandbox Restore ==="

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

# Step 5: 寫 sandbox init Python script（避免 heredoc 巢狀問題）
cat > /tmp/sandbox_init.py << 'PYEOF'
import json, subprocess, os, shutil

print("=== sandbox_init.py 開始 ===")

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

# Step C: openclaw.json patch
path = "/sandbox/.openclaw/openclaw.json"
cfg = json.load(open(path))
for model in cfg["models"]["providers"]["local"]["models"]:
    model["contextWindow"] = 32768
    model["maxTokens"] = 4096
cfg["agents"]["defaults"]["compaction"] = {"mode": "safeguard", "reserveTokens": 8000}
cfg["tools"] = {"web": {"search": {"enabled": True}, "fetch": {"enabled": True}}}
json.dump(cfg, open(path, "w"), indent=4, ensure_ascii=False)
print("Step C: openclaw.json patched")

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

# 複製 dist/index.js（plugin install 可能沒有）
dist_src = "/sandbox/.openclaw/extensions/searxng-search/dist"
os.makedirs(dist_src, exist_ok=True)
# dist 已由 pop-os scp 進來，確認存在
if os.path.exists(dist_src + "/index.js"):
    print("Step F dist: index.js OK")
else:
    print("Step F dist: WARNING - index.js not found!")

# Fix package.json
pkg_path = "/sandbox/.openclaw/extensions/searxng-search/package.json"
if os.path.exists(pkg_path):
    pkg = json.load(open(pkg_path))
    pkg["name"] = "searxng-search"
    pkg["openclaw"]["extensions"] = ["./dist/index.js"]
    json.dump(pkg, open(pkg_path, "w"), indent=2, ensure_ascii=False)
    print("Step F package.json: fixed")

# Fix openclaw.json plugin config
cfg = json.load(open(path))
if "searxng-search" not in cfg["plugins"]["entries"]:
    cfg["plugins"]["entries"]["searxng-search"] = {"enabled": True}
if "config" not in cfg["plugins"]["entries"]["searxng-search"]:
    cfg["plugins"]["entries"]["searxng-search"]["config"] = {}
cfg["plugins"]["entries"]["searxng-search"]["config"]["baseUrl"] = "http://host.openshell.internal:8000"
json.dump(cfg, open(path, "w"), indent=4, ensure_ascii=False)
print("Step F openclaw.json: baseUrl set")

print("=== ALL DONE ===")
PYEOF

# Step 6: 執行
echo "[5/6] 執行 sandbox 初始化..."
scp -o "$PROXY" /tmp/sandbox_init.py sandbox@ceclaw-agent:/tmp/
ssh -o "$PROXY" sandbox@ceclaw-agent "python3 /tmp/sandbox_init.py"

echo "[6/6] 重啟 gateway..."
ssh -o "$PROXY" sandbox@ceclaw-agent "pkill -f 'openclaw-gatewa' 2>/dev/null || true; sleep 2; openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 & sleep 6; tail -4 /tmp/openclaw-gateway.log"

echo ""
echo "✅ Restore 完成！"
echo ""
echo "驗證（在 sandbox 終端）："
echo "  tui → 問：你是誰 / 今天台北天氣如何？"
