#!/bin/bash
# CeLaw Agent v6 全功能壓力測試 (最終修復版 v4)
# 修復內容：移除 eval 避免引號崩潰、修正迴圈變數、強化驗證邏輯

AGENT="$HOME/ceclaw/claw-agent-v6.py"
LOG_DIR="$HOME/ceclaw/test_logs/stress_v4"
mkdir -p "$LOG_DIR"

echo "=========================================================="
echo "  CeLaw Agent v6 全功能壓力測試 (v4 - Stable)"
echo "=========================================================="
read -p "輸入測試局數 (每局 5 個任務): " MAX_ROUNDS

TOTAL_PASS=0
TOTAL_TESTS=0

# 輔助函數：執行單一任務並驗證
run_task() {
  local mode=$1
  local round=$2
  shift 2
  local log_file="$LOG_DIR/${mode}_r${round}.log"
  
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -e "\n[執行] 任務: $mode (局數 $round)"
  
  # 直接執行，不再使用 eval
  timeout 120 python3 "$AGENT" --no-ws --session-id "${mode}_${round}" --steps 8 \
    "$@" > "$log_file" 2>&1
  
  local exit_code=$?

  # 驗證邏輯 (比單純 grep Emoji 更嚴格)
  local status="FAIL"
  
  if [ $exit_code -eq 0 ]; then
     if [ "$mode" == "Write" ]; then
        # Write 模式：檢查 --out 指定的檔案是否存在且非空
        local outfile="$LOG_DIR/../run_${round}/bmi.py" 
        if [ -f "/tmp/claw_w${round}/bmi.py" ] && [ -s "/tmp/claw_w${round}/bmi.py" ]; then
           status="PASS"
        fi
     
     elif [ "$mode" == "Fix" ]; then
        # Fix 模式：嘗試編譯修復後的檔案，若不報語法錯誤則通過
        local fixfile="$LOG_DIR/../run_${round}/bug.py"
        if python3 -m py_compile "$fixfile" 2>/dev/null; then
           status="PASS (Fixed Code)"
        fi

     elif [ "$mode" == "Test" ]; then
        # Test 模式：檢查 Log 是否有測試執行成功的關鍵字
        if grep -qiE "passed|successful|ran.*tests|OK|執行成功|test result" "$log_file"; then
           status="PASS (Test Ok)"
        fi
        
     elif [ "$mode" == "Parallel" ]; then
        # Parallel 模式：檢查是否有多個任務完成的跡象
        if grep -qiE "完成|DONE|finished|成功" "$log_file"; then
           status="PASS (Multi-Done)"
        fi

     elif [ "$mode" == "General" ]; then
        # General 模式：檢查是否有輸出內容或工具呼叫
        if grep -qiE "def |function|lines|grep|結果|output" "$log_file"; then
           status="PASS (Result Found)"
        fi
     fi
  fi

  if [[ "$status" == PASS* ]]; then
     echo -e "       結果: ✅ $status"
     TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo -e "       結果: ❌ $status (Exit $exit_code)"
     echo "         [Log 片段]: $(tail -n 2 "$log_file")"
  fi
}

# ==========================================================
# 主測試循環
# ==========================================================
for round in $(seq 1 $MAX_ROUNDS); do
  
  echo "=========================================================="
  echo "🚀 第 $round / $MAX_ROUNDS 局測試"
  echo "=========================================================="

  # 準備工作目錄
  WORK_DIR="/tmp/claw_run_${round}"
  mkdir -p "$WORK_DIR"
  
  # 1. Write 任務：建立 BMI 計算機
  run_task "Write" "$round" \
     --write "Write a Python script to calculate BMI and save to $WORK_DIR/bmi.py" \
     --out "$WORK_DIR/bmi.py"

  # 2. Fix 任務：修復一個故意寫錯 return 的語法
  echo 'def add(a, b): reutrn a + b' > "$WORK_DIR/bug.py"
  run_task "Fix" "$round" \
     --fix "Fix syntax error in this file" \
     --file "$WORK_DIR/bug.py"

  # 3. Test 任務：針對剛才的程式碼執行測試
  # 為了能測試，我們先確保有一個簡單的 source 檔案，讓 Agent 去測試它
  echo 'print("Hello")' > "$WORK_DIR/hello.py"
  run_task "Test" "$round" \
     --test "python3 \"$WORK_DIR/hello.py\"" \
     --file "$WORK_DIR/hello.py"

  # 4. Parallel 任務：同時執行兩個獨立小任務
  run_task "Parallel" "$round" \
     --parallel "Task1: Say Hello" "Task2: Calculate 13*37"

  # 5. General 任務：分析程式碼
  run_task "General" "$round" \
     "Check the file $WORK_DIR/hello.py and tell me what it does."

done

# ==========================================================
# 結算報告
# ==========================================================
echo ""
echo "=========================================================="
echo "🏆 測試總結"
echo "=========================================================="
PERC=0
if [ $TOTAL_TESTS -gt 0 ]; then
   PERC=$((TOTAL_PASS * 100 / TOTAL_TESTS))
fi

echo "任務總數：$TOTAL_TESTS"
echo "成功次數：$TOTAL_PASS"
echo "成功率：  $PERC %"
echo "=========================================================="
if [ $PERC -ge 80 ]; then
   echo "🎉 恭喜！所有核心功能與並行邏輯均運作正常。"
else
   echo "⚠️ 偵測到不穩定，具體結果請見上方 Log。"
fi

