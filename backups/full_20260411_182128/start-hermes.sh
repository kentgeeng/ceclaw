#!/bin/bash
echo "=== 清除所有相關進程 ==="
kill $(lsof -ti:2337) 2>/dev/null
python3 ~/ceclaw/scripts/rotate_hermes_memory.py
kill -9 $(lsof -ti:8642) 2>/dev/null
kill -9 $(lsof -ti:3000) 2>/dev/null
kill -9 $(lsof -ti:3001) 2>/dev/null
kill -9 $(lsof -ti:3002) 2>/dev/null
sleep 2

echo "=== 啟動 SearXNG adapter ==="
cd ~/ceclaw/router
source ~/ceclaw/.venv/bin/activate
python3 searxng_adapter.py &
sleep 2

echo "=== 啟動 webapi ==="
cd ~/hermes-agent-fork
env -u OPENAI_API_KEY -u OPENAI_BASE_URL -u ANTHROPIC_API_KEY \
  API_SERVER_PORT=8642 \
  HERMES_INFERENCE_PROVIDER=custom \
  HERMES_BASE_URL=http://localhost:8000/v1 \
  HERMES_API_KEY=97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759 \
  venv/bin/python -m gateway.run &
sleep 3

echo "=== 啟動 workspace ==="
cd ~/hermes-workspace
pnpm dev --host &
sleep 3

echo "=== 完成 ==="
ss -tlnp | grep -E "8642|3000|2337"
