#!/bin/bash
# OpenClaw 掃描 shared/ 讀取 Hermes 經驗（h2o），入 Chroma DB
cd ~/ceclaw/router
~/ceclaw/.venv/bin/python3 - << 'PYEOF'
import shared_bridge as sb
import knowledge_service as ks

items = sb.scan(direction="h2o", status="pending")
count = 0
for item in items:
    try:
        ks.add_document(
            content=item["content"],
            layer="dept" if item.get("dept") else "company",
            scope=item.get("dept", ""),
            metadata={"source": "hermes", "user_id": item.get("user_id", ""), "shared_id": item["id"]}
        )
        sb.classify(item["id"], new_status="approved", new_state="applied", classified_by="openclaw")
        count += 1
    except Exception as e:
        sb.classify(item["id"], new_status="rejected", new_state="failed", classified_by="openclaw")
        print(f"FAIL {item['id']}: {e}")

print(f"{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')} scan_h2o: processed {count} items")
PYEOF
