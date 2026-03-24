#!/bin/bash
# CECLAW Health Check v1.0
# 用法：bash ~/ceclaw/ceclaw-health-check.sh

PASS="✅"
FAIL="❌"
WARN="⚠️ "

echo "╔══════════════════════════════════════╗"
echo "║     CECLAW Health Check v1.0         ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ─── Layer 1: pop-os 本地服務 ───
echo "── Layer 1: pop-os 本地服務 ──"

# Router
if systemctl is-active --quiet ceclaw-router; then
    echo "$PASS Router: running"
else
    echo "$FAIL Router: NOT running → sudo systemctl start ceclaw-router"
fi

# Router API
ROUTER_RESP=$(curl -s --max-time 3 http://localhost:8000/ceclaw/status 2>/dev/null)
if echo "$ROUTER_RESP" | grep -q "gb10"; then
    GB10_STATUS=$(echo "$ROUTER_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('backends',{}).get('gb10-llama',{}).get('healthy','?'))" 2>/dev/null)
    echo "$PASS Router API: OK (gb10-llama healthy=$GB10_STATUS)"
else
    echo "$FAIL Router API: 無回應 → 確認 ceclaw-router 服務"
fi

# SearXNG
if docker ps 2>/dev/null | grep -q searxng; then
    SEARCH_RESULT=$(curl -s --max-time 5 "http://localhost:8888/search?q=test&format=json" 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('results',[])))" 2>/dev/null)
    if [ -n "$SEARCH_RESULT" ] && [ "$SEARCH_RESULT" -gt 0 ] 2>/dev/null; then
        echo "$PASS SearXNG: running, results=$SEARCH_RESULT"
    else
        echo "$WARN SearXNG: container 在但搜尋無結果"
    fi
else
    echo "$FAIL SearXNG: container 未運行 → docker ps | grep searxng"
fi

# Router SearXNG proxy
PROXY_RESULT=$(curl -s --max-time 5 "http://localhost:8000/search?q=test&format=json" 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('results',[])))" 2>/dev/null)
if [ -n "$PROXY_RESULT" ] && [ "$PROXY_RESULT" -gt 0 ] 2>/dev/null; then
    echo "$PASS Router /search proxy: OK (results=$PROXY_RESULT)"
else
    echo "$FAIL Router /search proxy: 無結果"
fi

# Ollama fast path
if curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | grep -q "ministral-3"; then
    echo "$PASS Ollama: running, ministral-3:14b 存在"
else
    echo "$WARN Ollama: 無回應或 ministral-3:14b 未下載"
fi

echo ""

# ─── Layer 2: GB10 推論機 ───
echo "── Layer 2: GB10 推論機 ──"

if ping -c 1 -W 2 192.168.1.91 > /dev/null 2>&1; then
    echo "$PASS GB10: ping OK"
    
    GB10_MODEL=$(curl -s --max-time 10 http://192.168.1.91:8001/v1/models 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data'][0]['id'])" 2>/dev/null)
    if [ -n "$GB10_MODEL" ]; then
        echo "$PASS GB10 llama-server: running, model=$GB10_MODEL"
    else
        echo "$FAIL GB10 llama-server: 無回應 → ssh gb10 'sudo systemctl restart llama-server'"
    fi

    # ctx-size + parallel 確認
    PARALLEL=$(ssh -o ConnectTimeout=5 gb10 'grep "parallel\|ctx-size" ~/start_llama.sh 2>/dev/null' 2>/dev/null)
    if echo "$PARALLEL" | grep -q "ctx-size 65536" && echo "$PARALLEL" | grep -q "parallel 2"; then
        echo "$PASS GB10 start_llama.sh: --ctx-size 65536 --parallel 2 ✓"
    else
        echo "$WARN GB10 start_llama.sh: 參數異常 → $PARALLEL"
    fi
else
    echo "$FAIL GB10: ping 失敗 (192.168.1.91)"
fi

echo ""

# ─── Layer 3: OpenShell / Sandbox ───
echo "── Layer 3: OpenShell / Sandbox ──"

# openshell-server
if pgrep -f "openshell-server" > /dev/null; then
    echo "$PASS openshell-server: running"
else
    echo "$FAIL openshell-server: NOT running"
fi

# sandbox 狀態
SANDBOX_STATUS=$(openshell sandbox list 2>/dev/null | grep "ceclaw-agent" | awk '{print $5}')
if [ "$SANDBOX_STATUS" = "Ready" ]; then
    echo "$PASS sandbox ceclaw-agent: Ready"
else
    echo "$FAIL sandbox ceclaw-agent: $SANDBOX_STATUS (需重建)"
fi

# sandbox-id（動態）
SANDBOX_ID=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "sandbox-id [a-z0-9-]*" | head -1 | awk '{print $2}')
if [ -n "$SANDBOX_ID" ]; then
    echo "$PASS sandbox SSH session: active (id=$SANDBOX_ID)"
else
    echo "$WARN sandbox SSH session: 無活躍 session（scp/ssh 操作需先 sandbox connect）"
fi

# CoreDNS / DNS 解析
DOCKER_ID=$(docker ps --format "{{.ID}}" 2>/dev/null | head -1)
if [ -n "$DOCKER_ID" ]; then
    DNS_CHECK=$(docker exec "$DOCKER_ID" getent hosts host.openshell.internal 2>/dev/null | awk '{print $1}')
    if [ "$DNS_CHECK" = "172.17.0.1" ]; then
        echo "$PASS CoreDNS: host.openshell.internal → 172.17.0.1"
    else
        echo "$WARN CoreDNS: 解析結果=$DNS_CHECK → bash ~/nemoclaw-config/restore-coredns.sh"
    fi
else
    echo "$WARN Docker: 無法取得 container ID"
fi

echo ""

# ─── Layer 4: iptables 網路規則 ───
echo "── Layer 4: iptables 網路規則 ──"

check_iptables() {
    sudo iptables -L FORWARD -n 2>/dev/null | grep -q "$1" && echo "$PASS FORWARD $1" || echo "$FAIL FORWARD $1 缺少"
}
check_input() {
    sudo iptables -L INPUT -n 2>/dev/null | grep -q "$1" && echo "$PASS INPUT $1" || echo "$FAIL INPUT $1 缺少"
}

check_iptables "172.20.0.0/16"
check_iptables "172.19.0.0/16"
check_iptables "10.200.0.0/16"
check_input "172.19.0.0/16"

UFW_ROUTED=$(sudo ufw status verbose 2>/dev/null | grep "Default:" | grep -oP "routed: \K\w+")
if [ "$UFW_ROUTED" = "allow" ]; then
    echo "$PASS UFW routed: allow"
else
    echo "$FAIL UFW routed: $UFW_ROUTED → sudo ufw default allow routed"
fi

echo ""

# ─── Layer 5: sandbox 內部設定（需 SSH session）───
echo "── Layer 5: sandbox 內部設定 ──"

if [ -n "$SANDBOX_ID" ]; then
    TOKEN=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "token [a-z0-9-]*" | head -1 | awk '{print $2}')
    PROXY="ProxyCommand=/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id $SANDBOX_ID --token $TOKEN --gateway-name openshell"

    SANDBOX_CHECK=$(ssh -o "$PROXY" -o ConnectTimeout=10 sandbox@ceclaw-agent 'python3 - << '"'"'PYEOF'"'"'
import json, os
cfg = json.load(open("/sandbox/.openclaw/openclaw.json"))
local = cfg.get("models",{}).get("providers",{}).get("local",{})
plugins = cfg.get("plugins",{})
tools = cfg.get("tools",{})
results = []
results.append("api=" + local.get("api","MISSING"))
results.append("gateway=" + cfg.get("gateway",{}).get("mode","MISSING"))
results.append("model=" + cfg.get("agents",{}).get("defaults",{}).get("model",{}).get("primary","MISSING"))
results.append("tools.search=" + str(tools.get("web",{}).get("search",{}).get("enabled","MISSING")))
results.append("plugins.allow=" + str(plugins.get("allow","MISSING")))
results.append("searxng.baseUrl=" + str(plugins.get("entries",{}).get("searxng-search",{}).get("config",{}).get("baseUrl","MISSING")))
dist_ok = os.path.exists("/sandbox/.openclaw/extensions/searxng-search/dist/index.js")
results.append("searxng.dist=" + str(dist_ok))
auth_ok = os.path.exists("/sandbox/.openclaw/agents/main/agent/auth-profiles.json")
results.append("auth-profiles=" + str(auth_ok))
gw_running = os.system("pgrep -f openclaw-gatewa > /dev/null 2>&1") == 0
results.append("gateway.running=" + str(gw_running))
print("|".join(results))
PYEOF' 2>/dev/null)

    if [ -n "$SANDBOX_CHECK" ]; then
        IFS='|' read -ra ITEMS <<< "$SANDBOX_CHECK"
        for item in "${ITEMS[@]}"; do
            key="${item%%=*}"
            val="${item##*=}"
            case "$key:$val" in
                "api:openai-completions")   echo "$PASS sandbox $key: $val" ;;
                "api:"*)                    echo "$FAIL sandbox $key: $val → 需要 openai-completions (坑#69)" ;;
                "gateway:local")            echo "$PASS sandbox $key: $val" ;;
                "gateway:"*)               echo "$FAIL sandbox $key: $val → 需要 local" ;;
                "model:local/minimax")      echo "$PASS sandbox $key: $val" ;;
                "tools.search:True")        echo "$PASS sandbox $key: $val" ;;
                "tools.search:"*)           echo "$FAIL sandbox $key: $val → 需要 True (坑#64)" ;;
                "plugins.allow:"*searxng*)  echo "$PASS sandbox $key: $val" ;;
                "plugins.allow:"*)          echo "$FAIL sandbox $key: $val → 需要 [searxng-search, ceclaw] (坑#74)" ;;
                "searxng.dist:True")        echo "$PASS sandbox $key: $val" ;;
                "searxng.dist:False")       echo "$FAIL sandbox $key: dist/index.js 不存在 (坑#26)" ;;
                "auth-profiles:True")       echo "$PASS sandbox $key: $val" ;;
                "auth-profiles:False")      echo "$FAIL sandbox $key: auth-profiles.json 不存在" ;;
                "gateway.running:True")     echo "$PASS sandbox gateway: running" ;;
                "gateway.running:False")    echo "$FAIL sandbox gateway: NOT running → openclaw gateway run &" ;;
                *)                         echo "$WARN sandbox $key: $val" ;;
            esac
        done
    else
        echo "$FAIL sandbox 內部檢查失敗（SSH 無法執行）"
    fi
else
    echo "$WARN 跳過（無活躍 SSH session）"
fi

echo ""
echo "══════════════════════════════════════"
echo "  體檢完成。❌ = 需修復，⚠️  = 注意"
echo "  快速修復：bash ~/ceclaw/sandbox-restore.sh"
echo "══════════════════════════════════════"
