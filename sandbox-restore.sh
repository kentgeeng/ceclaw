#!/bin/bash
# CECLAW Sandbox Restore Script v3.3
# 用法：bash ~/ceclaw/sandbox-restore.sh
# 前置：需要先在另一個終端 openshell sandbox connect <sandbox-name>
#
# v3.3 新功能：內建七層檢測 + 自動修復
#   L1: proxy 環境變數
#   L2: openclaw.json 關鍵欄位
#   L3: gateway 是否在跑
#   L4: Router 連線
#   L5: 身份注入（CECLAW）
#   L6: 外網 web_fetch（https）
#   L7: searxng-search 目錄（避免 config invalid）
# v3.2: http+https proxy，no_proxy 最小化，環境自我檢查
# v3.1: UserKnownHostsFile=/dev/null
# v3.0: searxng 移除，policy 自動套用

SANDBOX_NAME="ceclaw-agent"
BACKUP_DIR=~/ceclaw/backup
echo "=== CECLAW Sandbox Restore v3.3 ==="

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

# Step 3: 套用 openshell policy（外網 TLD 全開）
echo "[3/7] 套用 network policy..."
openshell policy set "$SANDBOX_NAME" --policy ~/ceclaw/config/ceclaw-policy.yaml --wait 2>/dev/null && \
    echo "  ✅ policy OK" || echo "  ⚠️ policy set 失敗，繼續..."

# Step 4: 寫 sandbox_init.py（含七層檢測修復邏輯）
cat > /tmp/sandbox_init.py << 'PYEOF'
import json, subprocess, os, shutil, urllib.request, urllib.error

print("=== sandbox_init.py v3.3 開始 ===")

CFG_PATH = "/sandbox/.openclaw/openclaw.json"
bashrc_path = os.path.expanduser("~/.bashrc")
PASS = "✅"
FAIL = "❌"
WARN = "⚠️"

# ── Step A: install ceclaw plugin ───────────────────────────
r = subprocess.run(["openclaw", "plugins", "install", "/opt/ceclaw"], capture_output=True, text=True)
print("Step A:", "OK" if r.returncode == 0 else r.stderr.strip())

# ── Step B: tui alias ───────────────────────────────────────
bashrc = open(bashrc_path).read()
if "alias tui=" not in bashrc:
    with open(bashrc_path, "a") as f:
        f.write('\nalias tui=\'openclaw tui --session fresh-$(date +%s) --history-limit 20\'\n')
    print("Step B: alias added")
else:
    print("Step B: alias already exists")

# ── Step C: openclaw.json 完整 patch ────────────────────────
cfg = json.load(open(CFG_PATH))

for key in ["models", "providers", "local"]:
    pass
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

# ── Step D: gateway autostart ───────────────────────────────
bashrc = open(bashrc_path).read()
if "openclaw gateway run" not in bashrc:
    with open(bashrc_path, "a") as f:
        f.write('\nif ! pgrep -f "openclaw-gatewa" > /dev/null 2>&1; then\n    openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 &\nfi\n')
    print("Step D: gateway autostart added")
else:
    print("Step D: already exists")

# ── Step E: proxy 持久化（http+https，no_proxy 最小）──────────
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
    '# CECLAW proxy v3.3（http+https 都走 K3s proxy）',
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

# ── Step F: 移除 searxng-search 目錄（坑#77）────────────────
searxng_dir = "/sandbox/.openclaw/extensions/searxng-search"
if os.path.exists(searxng_dir):
    shutil.rmtree(searxng_dir)
    print("Step F: searxng-search 移除（坑#77）")
else:
    print("Step F: searxng-search 不存在，跳過")

# ── auth-profiles.json ───────────────────────────────────────
auth_dir = "/sandbox/.openclaw/agents/main/agent"
os.makedirs(auth_dir, exist_ok=True)
json.dump({"local": {"apiKey": "ceclaw-local-key"}},
          open(os.path.join(auth_dir, "auth-profiles.json"), "w"), indent=4)
print("auth-profiles.json: created")

print("")
print("=== ALL DONE ===")

# ══════════════════════════════════════════════════════════
# ── 七層健康檢查 ──────────────────────────────────────────
# ══════════════════════════════════════════════════════════
import subprocess, time

print("")
print("=== 七層健康檢查 ===")

# 重新 source proxy（非互動 shell 不繼承）
os.environ['http_proxy'] = 'http://10.200.0.1:3128'
os.environ['https_proxy'] = 'http://10.200.0.1:3128'
os.environ['HTTP_PROXY'] = 'http://10.200.0.1:3128'
os.environ['HTTPS_PROXY'] = 'http://10.200.0.1:3128'
os.environ.pop('no_proxy', None)
os.environ.pop('NO_PROXY', None)

results = []

# L1: proxy 環境變數
http_p = os.environ.get('http_proxy', '')
l1 = PASS if '10.200.0.1' in http_p else FAIL
results.append(f"L1 proxy env    : {l1} http_proxy={http_p}")

# L2: openclaw.json 關鍵欄位
try:
    cfg2 = json.load(open(CFG_PATH))
    api = cfg2['models']['providers']['local'].get('api', '')
    has_tools = 'web' in cfg2.get('tools', {})
    no_searxng = 'searxng-search' not in cfg2.get('plugins', {}).get('entries', {})
    l2 = PASS if api == 'openai-completions' and has_tools and no_searxng else FAIL
    results.append(f"L2 openclaw.json: {l2} api={api} tools={has_tools} no_searxng={no_searxng}")
except Exception as e:
    results.append(f"L2 openclaw.json: {FAIL} {e}")

# L3: gateway 是否在跑
r = subprocess.run(['pgrep', '-f', 'openclaw-gatewa'], capture_output=True)
l3 = PASS if r.returncode == 0 else FAIL
results.append(f"L3 gateway       : {l3} pid={r.stdout.decode().strip()[:20]}")

# L4: Router 連線
try:
    req = urllib.request.Request('http://host.openshell.internal:8000/ceclaw/status')
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read())
        l4 = PASS
        results.append(f"L4 Router        : {l4} version={data.get('version')}")
except Exception as e:
    l4 = FAIL
    results.append(f"L4 Router        : {FAIL} {e}")

# L5: 身份注入
try:
    payload = json.dumps({"model": "minimax", "messages": [{"role": "user", "content": "你是誰"}], "max_tokens": 30}).encode()
    req = urllib.request.Request(
        'http://host.openshell.internal:8000/v1/chat/completions',
        data=payload,
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
        reply = data['choices'][0]['message']['content']
        is_ceclaw = 'CECLAW' in reply
        l5 = PASS if is_ceclaw else FAIL
        results.append(f"L5 身份注入      : {l5} reply={reply[:40]}")
except Exception as e:
    results.append(f"L5 身份注入      : {FAIL} {e}")

# L6: 外網 HTTPS（wttr.in）
try:
    req = urllib.request.Request('https://wttr.in/taipei?format=3')
    with urllib.request.urlopen(req, timeout=10) as resp:
        weather = resp.read().decode().strip()[:30]
        l6 = PASS
        results.append(f"L6 外網 https    : {l6} {weather}")
except Exception as e:
    results.append(f"L6 外網 https    : {WARN} {e}")

# L7: extensions 目錄乾淨
exts = os.listdir('/sandbox/.openclaw/extensions') if os.path.exists('/sandbox/.openclaw/extensions') else []
bad = [e for e in exts if e == 'searxng-search']
l7 = PASS if not bad else FAIL
results.append(f"L7 extensions    : {l7} dirs={exts}")

print("")
for r in results:
    print(r)

# 總結
fails = [r for r in results if FAIL in r]
print("")
if not fails:
    print(f"{PASS} 全部 7 層通過，sandbox 狀態正常")
else:
    print(f"{FAIL} {len(fails)} 層失敗，請檢查以上項目")

PYEOF

# Step 5: 執行初始化
echo "[5/7] 執行 sandbox 初始化..."
scp -o "$SSH_OPTS" -o "$PROXY" /tmp/sandbox_init.py sandbox@ceclaw-agent:/tmp/
ssh -o "$SSH_OPTS" -o "$PROXY" sandbox@ceclaw-agent "python3 /tmp/sandbox_init.py"

# Step 6: 重啟 gateway（source .bashrc 後再啟動）
echo "[6/7] 重啟 gateway..."
ssh -o "$SSH_OPTS" -o "$PROXY" sandbox@ceclaw-agent \
    "pkill -9 -f 'openclaw-gatewa' 2>/dev/null; sleep 3; source ~/.bashrc; openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 & sleep 10; tail -3 /tmp/openclaw-gateway.log"

echo "[7/7] 完成"
echo ""
echo "✅ Restore v3.3 完成！"
echo ""
echo "驗證（在 sandbox 終端）："
echo "  tui → 問：你是誰 / 今天台北天氣如何？"
echo ""
echo "⚠️ 坑#77：searxng plugin 暫停（openclaw 2026.3.11 extensions path bug）"
echo "⚠️ 新 host 的 web_fetch 需在 openshell term approve 一次"
