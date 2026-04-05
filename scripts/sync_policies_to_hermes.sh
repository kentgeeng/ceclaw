#!/bin/bash
# P2：Hermes 定時主動拉取 OpenClaw policies
# 掃描 ~/.ceclaw/knowledge/bridge/policies/ 新檔案
# append 到 ~/.hermes/memories/MEMORY.md

POLICIES_DIR=~/.ceclaw/knowledge/bridge/policies
MEMORY_FILE=~/.hermes/memories/MEMORY.md
STATE_FILE=~/.ceclaw/knowledge/bridge/.sync_state

# 讀取上次同步時間
LAST_SYNC=0
if [ -f "$STATE_FILE" ]; then
    LAST_SYNC=$(cat "$STATE_FILE")
fi

NEW_COUNT=0
for f in $(ls -t "$POLICIES_DIR"/*.txt 2>/dev/null); do
    MTIME=$(stat -c %Y "$f")
    if [ "$MTIME" -gt "$LAST_SYNC" ]; then
        CONTENT=$(cat "$f")
        TS=$(date '+%Y-%m-%d %H:%M:%S')
        echo -e "\n§\n[${TS}] [OpenClaw政策同步]\n${CONTENT}" >> "$MEMORY_FILE"
        NEW_COUNT=$((NEW_COUNT+1))
    fi
done

# 更新同步時間
date +%s > "$STATE_FILE"

if [ $NEW_COUNT -gt 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') synced $NEW_COUNT policies to Hermes MEMORY.md"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') no new policies"
fi
