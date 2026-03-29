#!/bin/bash
# Step 1: openshell forward
openshell forward start 18789 test-net -d
sleep 5

# Step 2: socat
socat TCP-LISTEN:18790,fork,reuseaddr TCP:127.0.0.1:18789 &

# Step 3: TOKEN retry loop（最多等 20 秒）
for i in $(seq 1 10); do
  TOKEN=$(ps aux | grep 'openshell ssh-proxy' | grep -v grep | \
    grep -o 'token [a-z0-9-]*' | head -1 | awk '{print $2}')
  [ -n "$TOKEN" ] && break
  sleep 2
done
[ -z "$TOKEN" ] && echo "ERROR: TOKEN empty" && exit 1

# Step 4: 清掉舊 tunnel
kill $(lsof -t -i:3004 2>/dev/null) 2>/dev/null
sleep 1

# Step 5: autossh tunnel for TenacitOS
AUTOSSH_GATETIME=0 autossh -M 0 -N \
  -L 0.0.0.0:3004:localhost:3000 \
  -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -o "ProxyCommand=openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh \
--sandbox-id b73f31ea-d582-45a0-9a2d-ec2b3d9593a2 \
--token $TOKEN --gateway-name openshell" \
  sandbox@test-net &
