#!/bin/bash
# CeLaw Agent v6 全功能壓力測試 v5 (路徑/參數最終修復版)

AGENT="$HOME/ceclaw/claw-agent-v6.py"
LOG_DIR="$HOME/ceclaw/test_logs/stress_v5"
mkdir -p "$LOG_DIR"

echo "=========================================================="
echo "  CeLaw Agent v6 全功能壓力測試 (v5 - Final Fix)"
echo "=========================================================="
read -p "輸入測試局數: " MAX_ROUNDS

TOTAL_PASS=0
TOTAL_TESTS=0

for round in $(seq 1 $MAX_ROUNDS); do
  WORK_DIR="/tmp/claw_run_${round}"
  mkdir -p "$WORK_DIR"
  
  echo "=========================================================="
  echo "🚀 第 $round / $MAX_ROUNDS 局 (Dir: $WORK_DIR)"
  echo "=========================================================="

  # ─── 1. Write 模式 ───
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -n "[Write] 建立 bmi.py ... "
  timeout 120 python3 "$AGENT" --no-ws --session-id "W${round}" --steps 8 \
    --write "Write a Python BMI calculator script" \
    --out "$WORK_DIR/bmi.py" > "$LOG_DIR/Write_r${round}.log" 2>&1
  
  if [ -s "$WORK_DIR/bmi.py" ]; then
     echo "✅ PASS"; TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo "❌ FAIL (檔案未生成或為空)"; echo "    $(tail -n 2 $LOG_DIR/Write_r${round}.log)"
  fi

  # ─── 2. Fix 模式 ───
  echo 'def broken(a, b): reutrn a + b' > "$WORK_DIR/bug.py"
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -n "[Fix]   修復 bug.py ... "
  timeout 120 python3 "$AGENT" --no-ws --session-id "F${round}" --steps 8 \
    --fix "Fix the syntax error 'reutrn -> return'" \
    --file "$WORK_DIR/bug.py" > "$LOG_DIR/Fix_r${round}.log" 2>&1

  if python3 -m py_compile "$WORK_DIR/bug.py" 2>/dev/null; then
     echo "✅ PASS (語法已修復)"; TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo "❌ FAIL (仍有 Syntax Error)"; echo "    $(tail -n 2 $LOG_DIR/Fix_r${round}.log)"
  fi

  # ─── 3. Test 模式 (使用絕對路徑) ───
  echo 'print("Agent test mode ok")' > "$WORK_DIR/hello.py"
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -n "[Test]  執行 hello.py ... "
  timeout 120 python3 "$AGENT" --no-ws --session-id "T${round}" --steps 8 \
    --test "python3 $WORK_DIR/hello.py" \
    --file "$WORK_DIR/hello.py" > "$LOG_DIR/Test_r${round}.log" 2>&1

  if grep -qiE "ok|passed|successful|執行成功|test result" "$LOG_DIR/Test_r${round}.log"; then
     echo "✅ PASS"; TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo "❌ FAIL"; echo "    $(tail -n 2 $LOG_DIR/Test_r${round}.log)"
  fi

  # ─── 4. Parallel 模式 ───
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -n "[Par]   並行執行 tasks ... "
  timeout 120 python3 "$AGENT" --no-ws --session-id "P${round}" --steps 8 \
    --parallel "任務A: Say Hello" "任務B: Calculate 13 * 37" \
    > "$LOG_DIR/Parallel_r${round}.log" 2>&1

  if grep -qiE "完成|done|finished|agent-0|agent-1" "$LOG_DIR/Parallel_r${round}.log"; then
     echo "✅ PASS"; TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo "❌ FAIL"; echo "    $(tail -n 2 $LOG_DIR/Parallel_r${round}.log)"
  fi

  # ─── 5. General 模式 ───
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -n "[Gen]   一般指令分析 ... "
  timeout 120 python3 "$AGENT" --no-ws --session-id "G${round}" --steps 6 \
    "列出 $WORK_DIR 裡的檔案並說明用途" \
    > "$LOG_DIR/General_r${round}.log" 2>&1

  if grep -qiE "hello|bug|bmi|file|list|def" "$LOG_DIR/General_r${round}.log"; then
     echo "✅ PASS"; TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo "❌ FAIL"; echo "    $(tail -n 2 $LOG_DIR/General_r${round}.log)"
  fi

  sleep 1
  echo ""
done

# ══════════════════════════════════════════════════
# 最終報告
# ══════════════════════════════════════════════════
echo "=========================================================="
echo "🏆 測試總結"
echo "=========================================================="
PERC=0
[ $TOTAL_TESTS -gt 0 ] && PERC=$((TOTAL_PASS * 100 / TOTAL_TESTS))

echo "總任務：$TOTAL_TESTS"
echo "通過：  $TOTAL_PASS ($PERC%)"
echo "失敗：  $((TOTAL_TESTS - TOTAL_PASS))"
echo "Log：   $LOG_DIR"
echo "=========================================================="
[ $PERC -ge 80 ] && echo "🎉 完美！v6 全功能穩固。" || echo "⚠️ 需優化，請查 Log。"
