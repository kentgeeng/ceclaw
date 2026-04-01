#!/bin/bash
# CeLaw Agent v6 深度功能與壓力混合測試 (Full Stress Test)
# 目標：同時執行 3 個不同模式的 Agent，觸發 Tool Call、修復邏輯、檔案 I/O。

AGENT="$HOME/ceclaw/claw-agent-v6.py"
LOG_DIR="$HOME/ceclaw/test_logs/full_stress"
REPORT_DIR="$HOME/ceclaw/test_reports"
mkdir -p "$LOG_DIR" "$REPORT_DIR"

echo "==================================================================="
echo "  CeLaw Agent v6 深度壓力測試"
echo "==================================================================="
echo "測試涵蓋模式："
echo "1. [Write]  建立新程式碼並驗證檔案生成"
echo "2. [General] 分析專案結構與搜尋程式碼 (強制觸發 Tool Call)"
echo "3. [Fix]    植入 Bug 並要求 Agent 修復 (驗證邏輯與自動編譯)"
echo "4. [Parallel] 3 個 Agent 同時併發執行"
echo "==================================================================="
read -p "輸入測試總局數 (建議 3 局，耗時較長): " ROUNDS

TOTAL_PASS=0
TOTAL_FAIL=0
START_TIME=$(date +%s)

# 驗證結果函數 (自動檢查)
check_result() {
  local mode=$1
  local label=$2
  local log_file=$3
  local check_file=$4
  
  local status="✅ PASS"
  
  # 依據模式檢查結果
  if [ "$mode" == "WRITE" ]; then
    if [ ! -s "$check_file" ]; then status="❌ FAIL (Output file empty/missing)"; fi
  
  elif [ "$mode" == "GENERAL" ]; then
    # 檢查是否真的有輸出內容
    if ! grep -qE "def |print|class|Found|lines" "$log_file"; then 
       status="❌ FAIL (No useful output)"; fi

  elif [ "$mode" == "FIX" ]; then
    # 核心檢查：Agent 修完後，程式碼必須能通過 Python 語法檢查！
    if [ -f "$check_file" ]; then
       if python3 -m py_compile "$check_file" 2>/dev/null; then
          status="✅ PASS (Code Fixed!)"
       else
          status="❌ FAIL (Syntax Error Still Exists)";
       fi
    else
       status="❌ FAIL (File Missing)"
    fi
  fi

  # 顯示內容 (透明度)
  echo ""
  echo ">> [$status] $label"
  echo "-------------------------------------------------------"
  if [ -f "$log_file" ]; then
     tail -n 30 "$log_file" | sed 's/^/   /'
  else
     echo "   (Log file missing)"
  fi
  echo "-------------------------------------------------------"
  
  if [[ "$status" == *"PASS"* ]]; then return 0; else return 1; fi
}

# ===================================================================
# 主迴圈
# ===================================================================

for r in $(seq 1 $ROUNDS); do
  echo ""
  echo "###################################################################"
  echo "# 第 $r/$ROUNDS 局 - 開始並發測試"
  echo "###################################################################"
  
  # 準備工作目錄
  WORK_DIR="/tmp/ceclaw_stress_r${r}"
  mkdir -p "$WORK_DIR"
  
  # 任務 1: General (分析原始碼，測試 Grep/Scan)
  LOG_1="$LOG_DIR/r${r}_general.log"
  TASK_1="Read file ~/ceclaw/claw-agent-v6.py and count how many functions ('def ') are defined in it."
  
  # 任務 2: Write (寫程式)
  LOG_2="$LOG_DIR/r${r}_write.log"
  OUT_FILE="$WORK_DIR/fib.py"
  TASK_2="Write a python script to calculate Fibonacci sequence."
  
  # 任務 3: Fix (自動植入 Bug 讓 Agent 修)
  BUG_FILE="$WORK_DIR/buggy.py"
  LOG_3="$LOG_DIR/r${r}_fix.log"
  echo 'def calculate(a, b): return a + ' > "$BUG_FILE" # Syntax Error (incomplete expression)
  TASK_3="Fix the syntax error in this file: $BUG_FILE"

  # --- 同時啟動 3 個 Agent (Stress Point) ---
  echo "[Running 3 Agents in parallel...]"
  
  # Agent 1: General
  timeout 90 python3 "$AGENT" --no-ws --session-id "gen_r${r}" --steps 6 "$TASK_1" > "$LOG_1" 2>&1 &
  P1=$!
  
  # Agent 2: Write
  timeout 90 python3 "$AGENT" --no-ws --session-id "wrt_r${r}" --steps 6 --write "$TASK_2" --out "$OUT_FILE" > "$LOG_2" 2>&1 &
  P2=$!

  # Agent 3: Fix (針對 buggy.py)
  # 加上 --file 參數
  timeout 90 python3 "$AGENT" --no-ws --session-id "fix_r${r}" --steps 6 --fix "$TASK_3" --file "$BUG_FILE" > "$LOG_3" 2>&1 &
  P3=$!

  # --- 等待並驗證 ---
  wait $P1; check_result "GENERAL" "Task: Count Functions (Round $r)" "$LOG_1" "" && ((TOTAL_PASS++)) || ((TOTAL_FAIL++))
  wait $P2; check_result "WRITE"   "Task: Write Script   (Round $r)" "$LOG_2" "$OUT_FILE" && ((TOTAL_PASS++)) || ((TOTAL_FAIL++))
  wait $P3; check_result "FIX"     "Task: Fix Bug        (Round $r)" "$LOG_3" "$BUG_FILE" && ((TOTAL_PASS++)) || ((TOTAL_FAIL++))
  
  # 休息一秒
  sleep 1
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "==================================================================="
echo "  最終報告"
echo "==================================================================="
echo "總局數: $ROUNDS | 總測試數: $((ROUNDS * 3)) | 耗時: ${DURATION}s"
echo ""
echo "✅ 通過: $TOTAL_PASS"
echo "❌ 失敗: $TOTAL_FAIL"
echo ""
if [ $TOTAL_FAIL -eq 0 ]; then echo "🎉 Agent v6 壓力測試完美通過!"; else echo "⚠️ 檢測到不穩定，請檢查上述 Log。"; fi
echo "檔案位置: $REPORT_DIR"

