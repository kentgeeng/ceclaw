#!/bin/bash
set -e

# 1. 跑 openclaw setup
openclaw setup

# 2. 安裝 CECLAW plugin
openclaw plugins install /opt/ceclaw 2>/dev/null || true

# 3. 設定 provider 指向 CECLAW Router（從環境變數讀，零硬編碼）
ROUTER_HOST="${CECLAW_ROUTER_HOST:-host.openshell.internal}"
ROUTER_PORT="${CECLAW_ROUTER_PORT:-8000}"
MODEL_ID="${CECLAW_MODEL_ID:-minimax}"

python3 -c "
import json, os
path = os.path.expanduser('~/.openclaw/openclaw.json')
try:
    with open(path) as f:
        c = json.load(f)
except:
    c = {}
c.setdefault('models', {}).setdefault('providers', {})['local'] = {
    'baseUrl': f'http://${ROUTER_HOST}:${ROUTER_PORT}/v1',
    'apiKey': 'ceclaw-local',
    'api': 'openai-completions',
    'models': [{'id': '${MODEL_ID}', 'name': 'CECLAW Local', 'contextWindow': 131072, 'maxTokens': 8192, 'cost': {'input': 0, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0}, 'reasoning': False, 'input': ['text']}]
}
c.setdefault('agents', {}).setdefault('defaults', {})['model'] = {'primary': 'local/${MODEL_ID}'}
with open(path, 'w') as f:
    json.dump(c, f, indent=2)
"

# 4. 啟動 openclaw gateway
exec openclaw gateway
