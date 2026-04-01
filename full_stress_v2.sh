#!/bin/bash
# CeLaw Agent v6 深度功能全覆蓋壓力測試 (v2)
# 特點：
# 1. 涵蓋所有模式：Write, Fix, Test, Parallel, General
# 2. 終端即時反饋：使用 Live Monitor 顯示 Agent 正在執行的步驟
# 3. 嚴格驗證：自動檢查產出物

AGENT="$HOME/ceclaw/claw-agent-v6.py"
LOG_DIR="$HOME/ceclaw/test_logs/full_stress_v2"
REPORT_DIR="$HOME/ceclaw/test_reports"
mkdir -p "$LOG_DIR" "$REPORT_DIR"

# 清除上日誌以便本次觀察乾淨
rm -f "$LOG_DIR"/*

echo "==================================================================="
echo "  CeLaw Agent v6 功能全覆蓋壓力測試 (v2)"
echo "==================================================================="
read -p "輸入測試局數 (每局約 1-2 分鐘): " ROUNDS

# ─── 準備測試素材 ───
# 為 --test 模式準備原始碼和被測檔案
mkdir -p /tmp/ceclaw_stress_test
echo 'def add(a, b): return a + b' > /tmp/ceclaw_stress_test/sample.py

# ─── 即時監控函數 (Live Monitor) ───
# 模擬 tail -f 但加上標籤以支援並行讀取
monitor() {
  local log_file=$1
  local label=$2
  local color=$3

  # 取得檔案當前行數
  local lines=$(wc -l < "$log_file" 2>/dev/null || echo "0")

  # 迴圈監聽直到主程序結束
  while true; do
    sleep 1.5 # 輪詢頻率
    
    # 若檔案有新增內容則印出
    if [ -f "$log_file" ]; then
      local new_lines=$(( $(wc -l < "$log_file") - lines ))
      if [ $new_lines -gt 0 ]; then
        # 僅取新增的最後 $new_lines 行，避免螢幕爆炸
        tail -n $new_lines "$log_file" | grep -v "^[[:space:]]*$" | \
        while IFS= read -r line; do
          echo -e "${color}[$label]${NC} $line"
        done
        lines=$(( lines + new_lines ))
      fi
      
      # 若 Agent 結束 (行程不存在) 且沒有新的輸出，則退出
      local pgid=$4
      if ! ps -p $pgid > /dev/null && [ $new_lines -eq 0 ]; then
        break
      fi
    fi
  done
}

NC='\033[0m'
CLR_CYAN='\033[36m'
CLR_YELLOW='\033[33m'
CLR_GREEN='\033[32m'

# ─── 主程式 ───
TOTAL_PASS=0
TOTAL_FAIL=0

for r in $(seq 1 $ROUNDS); do
  echo "╔══════════════════════════════════════════════════╗"
  echo "║           第 $r 局：同時啟動 4 個功能模式          ║"
  echo "╚══════════════════════════════════════════════════╝"

  WORK_DIR="/tmp/ceclaw_agent_run/${r}"
  mkdir -p "$WORK_DIR"
  
  # 任務陣列：定義 4 個並行的測試任務
  # 格式：ID|任務描述|模式指令|Log檔|驗證方式
  
  TASK_LIST=(
    "A:Write|Write a python script to calculate BMI to $WORK_DIR/bmi.py|write|--write|test -s $WORK_DIR/bmi.py"
    "B:Fix|Fix the syntax error in $WORK_DIR/bug.py|fix|--fix|python3 -c 'open(\"$WORK_DIR/bug.py\").read()'" # 驗證檔案可讀
    "C:Test|Analyze $WORK_DIR/sample.py and write a unittest script and run it|test|--test|ls $WORK_DIR/test_*"
    "D:General|Use find_symbol or grep to find 'def add' in claw-agent-v6.py|general||grep -q 'def add' $LOG_DIR/task_D_r${r}.log"
  )

  PIDS=()
  MONITOR_PIDS=()

  # 1. 動態產生 Bug 檔案 (為 Task B Fix 模式準備)
  echo 'def broken_func(x, y): reutrn x + y' > "$WORK_DIR/bug.py"  # 故意拼錯 return

  # 2. 啟動任務與 Monitor
  for task_info in "${TASK_LIST[@]}"; do
    IFS='|' read -r tag desc mode flag verify_cmd <<< "$task_info"
    
    LOG_FILE="$LOG_DIR/task_${tag}_r${r}.log"
    > "$LOG_FILE"

    # 組建 Agent 指令
    CMD="timeout 120 python3 "$AGENT" --no-ws --session-id ${tag}_r${r} --steps 8 "
    
    case "$mode" in
      write)
        CMD="$CMD --write "$desc" --out $WORK_DIR/bmi.py"
        ;;
      fix)
        CMD="$CMD --fix "$desc" --file $WORK_DIR/bug.py"
        ;;
      test)
        # Test 模式通常針對現有檔案
        CMD="$CMD --test "write and run test for $WORK_DIR/sample.py" --file $WORK_DIR/sample.py"
        ;;
      parallel)
        # 略
        ;;
      general)
        # 一般模式直接接 Task 描述
        CMD="$CMD "$desc""
        ;;
    esac

    # 啟動 Agent 並導向 Log
    echo -e "\033[34m[啟動] Task $tag ($mode)\033[0m"
    $CMD > "$LOG_FILE" 2>&1 &
    PID=$!
    PIDS+=("$tag:$PID")
    
    # 啟動對應的 Monitor (背景跑)
    # 注意：monitor 函式無法直接在 subshell 被 export 給 background 使用
    # 這裡改用簡單的 while 迴圈做 tail -f 效果顯示在當前 terminal
    (
      lines=0
      while ps -p $PID > /dev/null || [ -f "$LOG_FILE" ]; do
         if [ -f "$LOG_FILE" ]; then
           cur_lines=$(wc -l < "$LOG_FILE")
           if [ $cur_lines -gt $lines ]; then
             tail -n $((cur_lines - lines)) "$LOG_FILE" | \
             sed "s/^/\033[36m[$tag]\033[0m /"
             lines=$cur_lines
           fi
         fi
         sleep 1
         if ! ps -p $PID > /dev/null; then
            # Process 結束，印出剩餘部分後退出
            tail -n $(( $(wc -l < "$LOG_FILE") - lines )) "$LOG_FILE" | \
            sed "s/^/\033[36m[$tag]\033[0m /"
            break
         fi
      done
    ) &
    MONITOR_PIDS+=($!)
  done

  # 3. 等待 Agent 完成
  # 簡單判斷：等待所有背景 Agent 退出
  for pair in "${PIDS[@]}"; do
    IFS=':' read -r tag pid <<< "$pair"
    wait $pid
    echo "✅ [Task $tag] 完成"
  done

  # 殺掉 Monitor (如果還在跑)
  for mp in "${MONITOR_PIDS[@]}"; do
    kill $mp 2>/dev/null
  done
  wait

  echo ""
  echo "🔍 [驗證階段] 正在檢查結果..."
  
  # 4. 驗證結果
  # Task A: Write -> bmi.py 存在且非空
  if [ -s "$WORK_DIR/bmi.py" ]; then
     echo -e "  ${CLR_GREEN}[Pass]${NC} Task A (Write): bmi.py 生成成功"
     TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo -e "  ${CLR_RED}[Fail]${NC} Task A (Write): 檔案為空或未生成"
     TOTAL_FAIL=$((TOTAL_FAIL + 1))
  fi

  # Task B: Fix -> bug.py 應該被修正 (檢查 'return' 是否正確拼寫)
  if grep -q "return" "$WORK_DIR/bug.py" && ! grep -q "reutrn" "$WORK_DIR/bug.py"; then
     echo -e "  ${CLR_GREEN}[Pass]${NC} Task B (Fix): 語法錯誤已修復"
     TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo -e "  ${CLR_RED}[Fail]${NC} Task B (Fix): 修復失敗或改錯了"
     TOTAL_FAIL=$((TOTAL_FAIL + 1))
  fi

  # Task C: Test -> Log 中應該有 test 執行成功的跡象
  if grep -q "PASSED\|OK\|1 passed\|test.*py" "$LOG_DIR/task_C_r${r}.log"; then
     echo -e "  ${CLR_GREEN}[Pass]${NC} Task C (Test): 測試邏輯似乎執行成功"
     TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo -e "  ${CLR_RED}[Fail]${NC} Task C (Test): 測試似乎失敗或沒跑起來"
     TOTAL_FAIL=$((TOTAL_FAIL + 1))
  fi

  # Task D: General -> 應該有呼叫工具或找到結果
  if grep -q "grep\|find\|result" "$LOG_DIR/task_D_r${r}.log"; then
     echo -e "  ${CLR_GREEN}[Pass]${NC} Task D (General/Scan): 搜尋/掃描工具呼叫成功"
     TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo -e "  ${CLR_RED}[Fail]${NC} Task D (General/Scan): 沒看到有效的工具呼叫輸出"
     TOTAL_FAIL=$((TOTAL_FAIL + 1))
  fi
  
  echo "----------------------------------------------"
done

echo ""
echo "================================================================"
echo "                     🏁 最終報告"
echo "================================================================"
echo "總運行次數: $((ROUNDS * 4))"
echo -e "✅ 通過: ${CLR_GREEN}$TOTAL_PASS${NC}"
echo -e "❌ 失敗: ${CLR_RED}$TOTAL_FAIL${NC}"
if [ $TOTAL_FAIL -eq 0 ]; then
  echo -e "🎉 完美！所有模式與功能皆正常運行。"
else
  echo "⚠️ 有任務失敗，請檢查上方錯誤資訊。"
fi
echo "Log 位置: $LOG_DIR"

