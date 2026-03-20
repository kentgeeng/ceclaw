#!/bin/bash
set -e
# 0. 讓 cluster IP 不走 proxy
export no_proxy="${no_proxy},10.43.0.0/16,10.200.0.0/16,172.17.0.0/16,host.openshell.internal"
export NO_PROXY="${no_proxy}"
# 1. 跑 openclaw setup
openclaw setup
# 2. 安裝 CECLAW plugin
openclaw plugins install /opt/ceclaw 2>/dev/null || true
# 3. 設定 provider 指向 CECLAW Router（從環境變數讀，零硬編碼）
python3 << 'PYEOF'
import json, os
path = os.path.expanduser('~/.openclaw/openclaw.json')
try:
    with open(path) as f:
        c = json.load(f)
except:
    c = {}
router_host = os.environ.get('CECLAW_ROUTER_HOST', 'host.openshell.internal')
router_port = os.environ.get('CECLAW_ROUTER_PORT', '8000')
model_id = os.environ.get('CECLAW_MODEL_ID', 'minimax')
c.setdefault('models', {}).setdefault('providers', {})['local'] = {
    'baseUrl': f'http://{router_host}:{router_port}/v1',
    'apiKey': 'ceclaw-local',
    'api': 'openai-completions',
    'models': [{'id': model_id, 'name': 'CECLAW Local', 'contextWindow': 131072,
                'maxTokens': 8192, 'cost': {'input': 0, 'output': 0, 'cacheRead': 0,
                'cacheWrite': 0}, 'reasoning': False, 'input': ['text']}]
}
c.setdefault('agents', {}).setdefault('defaults', {})['model'] = {'primary': f'local/{model_id}'}
with open(path, 'w') as f:
    json.dump(c, f, indent=2)
print('openclaw.json patched')
PYEOF
# 4. 啟動 openclaw gateway
exec openclaw gateway
