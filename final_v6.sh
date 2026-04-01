#!/bin/bash
# CeLaw Agent v6 功能驗證與迴圈測試 (v6 - 報告存檔版)
# 修正：完整保存測試報告、修正標題、清理路徑變數

AGENT="$HOME/ceclaw/claw-agent-v6.py"
LOG_DIR="$HOME/ceclaw/test_logs/v6_func"
REPORT_DIR="$HOME/ceclaw/test_reports"
mkdir -p "$LOG_DIR" "$REPORT_DIR"

# 報告路徑
REPORT="$REPORT_DIR/report_v6_$(date +%Y%m%d_%H%M%S).txt"

echo "=========================================================="
echo "  CeLaw Agent v6 功能完整驗證"
echo "  (模式：循序驗證 × 可迴圈 × 自動存檔報表)"
echo "=========================================================="
read -p "輸入測試局數: " MAX_ROUNDS
echo "日誌目錄: $LOG_DIR"
echo "報告路徑: $REPORT"
echo "=========================================================="

TOTAL_PASS=0
TOTAL_TESTS=0

{
for round in $(seq 1 $MAX_ROUNDS); do
  WORK_DIR="/tmp/claw_run_${round}"
  mkdir -p "$WORK_DIR"
  
  echo "🚀 第 $round / $MAX_ROUNDS 局 (Dir: $WORK_DIR)"

  # 1. Write 模式
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -n "   [Write] 建立程式碼... "
  timeout 120 python3 "$AGENT" --no-ws --session-id "W${round}" --steps 8 \
    --write "Write a Python BMI calculator script" \
    --out "$WORK_DIR/bmi.py" > "$LOG_DIR/W_${round}.log" 2>&1
  
  if [ -s "$WORK_DIR/bmi.py" ]; then
     echo "✅ PASS"; TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo "❌ FAIL (檔案未生成)"; echo "     Last Log: $(tail -n 1 $LOG_DIR/W_${round}.log | tr -d '\n')"
  fi

  # 2. Fix 模式
  echo 'def broken(a, b): reutrn a + b' > "$WORK_DIR/bug.py"
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -n "   [Fix]   修復語法... "
  timeout 120 python3 "$AGENT" --no-ws --session-id "F${round}" --steps 8 \
    --fix "Fix syntax error" \
    --file "$WORK_DIR/bug.py" > "$LOG_DIR/F_${round}.log" 2>&1

  if python3 -m py_compile "$WORK_DIR/bug.py" 2>/dev/null; then
     echo "✅ PASS (py_compile OK)"; TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo "❌ FAIL (Fix failed)"; echo "     Last Log: $(tail -n 1 $LOG_DIR/F_${round}.log | tr -d '\n')"
  fi

  # 3. Test 模式 (使用絕對路徑)
  echo 'print("Mode Test OK")' > "$WORK_DIR/hello.py"
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -n "   [Test]  執行測試... "
  timeout 90 python3 "$AGENT" --no-ws --session-id "T${round}" --steps 6 \
    --test "python3 $WORK_DIR/hello.py" \
    --file "$WORK_DIR/hello.py" > "$LOG_DIR/T_${round}.log" 2>&1

  if grep -qiE "ok|pass|successful|執行成功|result" "$LOG_DIR/T_${round}.log"; then
     echo "✅ PASS"; TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo "❌ FAIL"; echo "     Last Log: $(tail -n 1 $LOG_DIR/T_${round}.log | tr -d '\n')"
  fi

  # 4. Parallel 模式
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -n "   [Par]   並行子任務... "
  timeout 120 python3 "$AGENT" --no-ws --session-id "P${round}" --steps 8 \
    --parallel "TaskA: Say Hi" "TaskB: 25+25" > "$LOG_DIR/P_${round}.log" 2>&1

  if grep -qiE "完成|done|finished|agent-0|agent-1" "$LOG_DIR/P_${round}.log"; then
     echo "✅ PASS"; TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo "❌ FAIL"; echo "     Last Log: $(tail -n 1 $LOG_DIR/P_${round}.log | tr -d '\n')"
  fi

  # 5. General/Scan 模式
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -n "   [Gen]   分析指令... "
  timeout 90 python3 "$AGENT" --no-ws --session-id "G${round}" --steps 6 \
    "List files in $WORK_DIR and count their lines" > "$LOG_DIR/G_${round}.log" 2>&1

  if grep -qiE "hello|bug|bmi|lines|def|grep" "$LOG_DIR/G_${round}.log"; then
     echo "✅ PASS"; TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo "❌ FAIL (無效輸出)"; echo "     Last Log: $(tail -n 1 $LOG_DIR/G_${round}.log | tr -d '\n')"
  fi

  echo ""
done

PERC=0
[ $TOTAL_TESTS -gt 0 ] && PERC=$((TOTAL_PASS * 100 / TOTAL_TESTS))
FAIL=$((TOTAL_TESTS - TOTAL_PASS))

echo "=========================================================="
echo "📋 測試報告摘要 - $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================================="
echo "  總任務：$TOTAL_TESTS"
echo "  通過：  $TOTAL_PASS ($PERC%)"
echo "  失敗：  $FAIL"
echo "  Log：   $LOG_DIR"
echo "=========================================================="
[ $PERC -ge 80 ] && echo "🎉 穩定！v6 核心邏輯通過驗證。" || echo "⚠️ 需檢查 Log。"
} | tee "$REPORT"

echo ""
echo "📄 詳細報告已存檔至: $REPORT"
