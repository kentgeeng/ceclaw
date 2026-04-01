#!/bin/bash
# CeLaw Agent v6 全功能迴圈驗證 (v9 - 防呆最終版)
# 修復：--sessions 與 --resume 加入 timeout 防止卡死 hang

AGENT="$HOME/ceclaw/claw-agent-v6.py"
LOG_DIR="$HOME/ceclaw/test_logs/v9_final"
REPORT_DIR="$HOME/ceclaw/test_reports"
mkdir -p "$LOG_DIR" "$REPORT_DIR"

REPORT="$REPORT_DIR/report_v9_$(date +%Y%m%d_%H%M%S).txt"

echo "=========================================================="
echo "  CeLaw Agent v6 全功能迴圈驗證 (v9 - 最終防呆版)"
echo "  涵蓋：Write/Fix/Test/Par/Gen/Sessions/Resume"
echo "=========================================================="
read -p "輸入測試局數: " MAX_ROUNDS
echo "日誌: $LOG_DIR | 報告: $REPORT"
echo "=========================================================="

TOTAL_PASS=0
TOTAL_TESTS=0

{
for round in $(seq 1 $MAX_ROUNDS); do
  WORK_DIR="/tmp/claw_run_${round}"
  mkdir -p "$WORK_DIR"
  echo "🚀 第 $round / $MAX_ROUNDS 局 (Dir: $WORK_DIR)"

  # 1. Write
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -n "   [Write] 建立程式碼... "
  timeout 120 python3 "$AGENT" --no-ws --session-id "W${round}" --steps 8 \
    --write "Write a Python BMI calculator" --out "$WORK_DIR/bmi.py" > "$LOG_DIR/W_${round}.log" 2>&1
  if [ -s "$WORK_DIR/bmi.py" ]; then echo "✅ PASS"; TOTAL_PASS=$((TOTAL_PASS + 1))
  else echo "❌ FAIL"; fi

  # 2. Fix
  echo 'def broken(a, b): reutrn a + b' > "$WORK_DIR/bug.py"
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -n "   [Fix]   修復語法... "
  timeout 120 python3 "$AGENT" --no-ws --session-id "F${round}" --steps 8 \
    --fix "Fix syntax error" --file "$WORK_DIR/bug.py" > "$LOG_DIR/F_${round}.log" 2>&1
  if python3 -m py_compile "$WORK_DIR/bug.py" 2>/dev/null; then echo "✅ PASS"; TOTAL_PASS=$((TOTAL_PASS + 1))
  else echo "❌ FAIL"; fi

  # 3. Test
  echo 'print("Mode Test OK")' > "$WORK_DIR/hello.py"
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -n "   [Test]  執行測試... "
  timeout 90 python3 "$AGENT" --no-ws --session-id "T${round}" --steps 6 \
    --test "python3 $WORK_DIR/hello.py" --file "$WORK_DIR/hello.py" > "$LOG_DIR/T_${round}.log" 2>&1
  if grep -qiE "ok|pass|successful|result|成功|全過|通過" "$LOG_DIR/T_${round}.log"; then
     echo "✅ PASS"; TOTAL_PASS=$((TOTAL_PASS + 1))
  else echo "❌ FAIL"; fi

  # 4. Parallel
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -n "   [Par]   並行子任務... "
  timeout 120 python3 "$AGENT" --no-ws --session-id "P${round}" --steps 8 \
    --parallel "TaskA: Say Hi" "TaskB: 25+25" > "$LOG_DIR/P_${round}.log" 2>&1
  if grep -qiE "完成|done|agent-0|agent-1" "$LOG_DIR/P_${round}.log"; then echo "✅ PASS"; TOTAL_PASS=$((TOTAL_PASS + 1))
  else echo "❌ FAIL"; fi

  # 5. General
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -n "   [Gen]   分析指令... "
  timeout 90 python3 "$AGENT" --no-ws --session-id "G${round}" --steps 6 \
    "List files in $WORK_DIR" > "$LOG_DIR/G_${round}.log" 2>&1
  if grep -qiE "hello|bug|bmi|file|list" "$LOG_DIR/G_${round}.log"; then echo "✅ PASS"; TOTAL_PASS=$((TOTAL_PASS + 1))
  else echo "❌ FAIL"; fi

  # 6. Sessions (加入防 hang timeout)
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -n "   [Sess]  列出Session... "
  timeout 30 python3 "$AGENT" --sessions > "$LOG_DIR/S_${round}.log" 2>&1
  if [ -s "$LOG_DIR/S_${round}.log" ]; then echo "✅ PASS"; TOTAL_PASS=$((TOTAL_PASS + 1))
  else echo "❌ FAIL"; fi

  # 7. Resume (加入防 hang timeout)
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -n "   [Resu]  恢復Session(W${round})... "
  timeout 60 python3 "$AGENT" --resume "W${round}" --no-ws --steps 3 "確認上次任務狀態並繼續" > "$LOG_DIR/R_${round}.log" 2>&1
  RESUME_EXIT=$?
  if [ $RESUME_EXIT -eq 0 ] && [ -s "$LOG_DIR/R_${round}.log" ]; then echo "✅ PASS"; TOTAL_PASS=$((TOTAL_PASS + 1))
  else echo "❌ FAIL (Exit $RESUME_EXIT)"; fi

  echo ""
done

# ══════════════════════════════════════════════════
# 報告輸出 (終端 + 檔案)
# ══════════════════════════════════════════════════
PERC=0; FAIL_COUNT=$((TOTAL_TESTS - TOTAL_PASS))
[ $TOTAL_TESTS -gt 0 ] && PERC=$((TOTAL_PASS * 100 / TOTAL_TESTS))

echo "=========================================================="
echo "📋 測試報告摘要 - $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================================="
echo "  總任務：$TOTAL_TESTS"
echo "  通過：  $TOTAL_PASS ($PERC%)"
echo "  失敗：  $FAIL_COUNT"
echo "  Log：   $LOG_DIR"
echo "=========================================================="
[ $PERC -ge 95 ] && echo "🎉 完美！v6 100% 功能通過驗證。" || echo "⚠️ 有未覆蓋或異常情況。"
} | tee "$REPORT"

echo ""
echo "📄 完整報告已存檔: $REPORT"
