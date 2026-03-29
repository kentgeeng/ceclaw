#!/bin/bash
# socat: 18790 → 18789 (openclaw gateway)
pkill socat 2>/dev/null; sleep 1
socat TCP-LISTEN:18790,fork,reuseaddr TCP:127.0.0.1:18789 &
echo "[ceclaw-ui] socat started: 18790 → 18789"
