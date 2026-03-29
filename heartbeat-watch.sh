#!/bin/bash
export http_proxy=http://10.200.0.1:3128
export https_proxy=http://10.200.0.1:3128
while true; do
  touch /sandbox/.openclaw/workspace/HEARTBEAT.md
  sleep 120
done
