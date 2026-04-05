#!/bin/bash
# Hermes 掃描 shared/ 讀取 OpenClaw 政策（o2h），入 MEMORY.md
MEMORY_FILE=~/.hermes/memories/MEMORY.md

~/ceclaw/.venv/bin/python3 - << 'PYEOF'
import sys
sys.path.insert(0, "/home/zoe_ai/ceclaw/router")
import shared_bridge as sb
from datetime import datetime
from pathlib import Path

MEMORY_FILE = Path.home() / ".hermes" / "memories" / "MEMORY.md"
items = sb.scan(direction="o2h", status="pending")
count = 0
for item in items:
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"\n§\n[{ts}] [OpenClaw政策 v{item.get('version',1)} {item.get('priority','normal')}]\n{item['content']}"
        with open(MEMORY_FILE, "a", encoding="utf-8") as f:
            f.write(entry)
        sb.classify(item["id"], new_status="approved", new_state="applied", classified_by="hermes")
        count += 1
    except Exception as e:
        sb.classify(item["id"], new_status="rejected", new_state="failed", classified_by="hermes")
        print(f"FAIL {item['id']}: {e}")

print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} scan_o2h: processed {count} items")
PYEOF
