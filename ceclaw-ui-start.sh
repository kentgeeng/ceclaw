#!/bin/bash
# Step 1: openclaw gateway
pkill -f "openclaw gateway" 2>/dev/null
sleep 3
openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 &
for i in $(seq 1 15); do
  ss -tlnp | grep 18789 > /dev/null && break
  sleep 2
done
# Step 2: socat
pkill socat 2>/dev/null; sleep 1
socat TCP-LISTEN:18790,fork,reuseaddr TCP:127.0.0.1:18789 &
echo "[ceclaw-ui] done"
