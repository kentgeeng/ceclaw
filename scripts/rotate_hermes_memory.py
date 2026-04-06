#!/usr/bin/env python3
import re
from pathlib import Path
from datetime import datetime

MEMORY_PATH = Path.home() / ".hermes/memories/MEMORY.md"
TRIGGER_LINES = 300
MAX_POLICY = 50
MAX_OTHER = 20

BURNIN_PATTERNS = [r"工具任務成果已採納", r"burnin", r"第\d+輪"]

def is_burnin(block):
    return any(re.search(p, block) for p in BURNIN_PATTERNS)

def is_policy(block):
    return "[OpenClaw政策" in block

def rotate(dry_run=False):
    if not MEMORY_PATH.exists():
        print("MEMORY.md not found"); return
    text = MEMORY_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) <= TRIGGER_LINES:
        print(f"MEMORY.md OK ({len(lines)} lines)"); return
    blocks = [b.strip() for b in text.split("§") if b.strip()]
    burnin_count = 0
    policy_blocks = []
    other_blocks = []
    for b in blocks:
        if is_burnin(b): burnin_count += 1
        elif is_policy(b): policy_blocks.append(b)
        else: other_blocks.append(b)
    policy_kept = policy_blocks[-MAX_POLICY:]
    other_kept = other_blocks[-MAX_OTHER:]
    final_blocks = policy_kept + other_kept
    new_text = "\n§\n".join(final_blocks) + "\n§\n"
    new_lines = new_text.splitlines()
    print(f"=== MEMORY.md Rotate ===")
    print(f"原始：{len(lines)} 行，{len(blocks)} blocks")
    print(f"燒機丟棄：{burnin_count} blocks")
    print(f"政策保留：{len(policy_kept)}/{len(policy_blocks)} blocks")
    print(f"其他保留：{len(other_kept)}/{len(other_blocks)} blocks")
    print(f"結果：{len(new_lines)} 行，{len(final_blocks)} blocks")
    if dry_run:
        print("[DRY RUN] 未寫入"); return
    backup = MEMORY_PATH.with_suffix(f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    import shutil
    shutil.copy2(MEMORY_PATH, backup)
    print(f"備份：{backup.name}")
    MEMORY_PATH.write_text(new_text, encoding="utf-8")
    print("寫入完成")

if __name__ == "__main__":
    import sys
    rotate("--dry-run" in sys.argv)
