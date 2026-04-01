#!/bin/bash
# CeLaw Agent v6 並行壓力測試 (Agent 實體壓力)
# 目標：同時啟動多個 claw-agent 進程，模擬多工高負載

AGENT="$HOME/ceclaw/claw-agent-v6.py"
LOG_DIR="$HOME/ceclaw/test_logs/agent_stress"
REPORT_DIR="$HOME/ceclaw/test_reports"
mkdir -p "$LOG_DIR" "$REPORT_DIR"

REPORT="$REPORT_DIR/agent_stress_$(date +%Y%m%d_%H%M%S).txt"

echo "========================================"
echo "  CeLaw Agent v6 Agent 並行壓力測試"
echo "========================================"
read -p "輸入測試輪數 (建議 3): " ROUNDS
PARALLEL=3  # 同時跑 3 個 Agent
echo "每輪並行啟動 $PARALLEL 個 Agent 實體"
echo ""

# 定義測試任務集 (稍微複雜一點的任務)
TASKS=(
  "write_hello:Write a python function to say hello to a user by name"
  "write_calc:Write a script to calculate fibonacci of 10"
  "write_list:Write a script to list files recursively"
)

declare -A TOTAL_TASKS TOTAL_PASS TOTAL_FAIL

# 單一 Agent 執行函數
run_agent_instance() {
  local id=$1
  local round=$2
  local task_name=$3
  local task_desc=$4
  SESSION="stress_${round}_${id}"
  LOG="$LOG_DIR/${SESSION}.log"
  OUT_FILE="/tmp/stress_out_${round}_${id}.py"

  # 啟動 Agent：
  # 1. 強制 no-ws 避免 port 衝突
  # 2. 指定 session-id 避免寫入衝突
  # 3. 限制 steps 避免無窮迴圈
  # 4. 寫出檔案到指定位置以便驗證
  timeout 120 python3 "$AGENT" \
    --no-ws \
    --session-id "$SESSION" \
    --steps 4 \
    --write "$task_desc" \
    --out "$OUT_FILE" > "$LOG" 2>&1

  local exit_code=$?

  # 驗證結果
  if [ $exit_code -eq 0 ] && [ -f "$OUT_FILE" ]; then
    # 檢查檔案內容是否有效 (不只是空的)
    if [ -s "$OUT_FILE" ]; then
      echo "PASS"
      return 0
    else
      echo "FAIL_EMPTY_OUT"
      return 1
    fi
  elif [ $exit_code -eq 124 ]; then
    echo "FAIL_TIMEOUT"
    return 1
  else
    echo "FAIL_CRASH_OR_ERROR (Exit $exit_code)"
    return 1
  fi
}

OVERALL_PASS=0
OVERALL_FAIL=0

for r in $(seq 1 $ROUNDS); do
  echo "━━ 第 $r/$ROUNDS 輪並測 ━━"
  
  PIDS=()
  RESULTS_FILE="/tmp/results_${r}.txt"
  > "$RESULTS_FILE"

  # 並行啟動 P 個 Agent
  for i in $(seq 0 $((PARALLEL-1))); do
    # 循環使用 Task 
    task_id=$((i % ${#TASKS[@]}))
    task_info="${TASKS[$task_id]}"
    k="${task_info%%:*}"
    v="${task_info#*:}"

    (
      res=$(run_agent_instance $i $r "$k" "$v")
      echo "$res"
    ) > "$LOG_DIR/result_${r}_${i}.txt" &
    PIDS+=($!)
  done

  # 等待並收集結果
  for pid in "${PIDS[@]}"; do
    wait $pid
  done

  # 統計本輪結果
  round_pass=0
  round_fail=0
  
  for i in $(seq 0 $((PARALLEL-1))); do
    res=$(cat "$LOG_DIR/result_${r}_${i}.txt")
    echo "  Agent-$i ($r): $res"
    
    if [[ "$res" == "PASS" ]]; then
      round_pass=$((round_pass + 1))
    else
      round_fail=$((round_fail + 1))
    fi
  done

  OVERALL_PASS=$((OVERALL_PASS + round_pass))
  OVERALL_FAIL=$((OVERALL_FAIL + round_fail))

  echo "  [輪計] 通過: $round_pass | 失敗: $round_fail"
  echo ""
done

TOTAL=$((OVERALL_PASS + OVERALL_FAIL))
SUCCESS_RATE="0"
if [ $TOTAL -gt 0 ]; then
     SUCCESS_RATE=$(echo "scale=1; $OVERALL_PASS * 100 / $TOTAL" | bc)
fi

{
  echo "========================================"
  echo "  Agent 壓力測試報告"
  echo "========================================"
  echo "輪數: $ROUNDS | 並行度: $PARALLEL | 總任務: $TOTAL"
  echo ""
  echo "  通過: $OVERALL_PASS (成功率 ${SUCCESS_RATE}%)"
  echo "  失敗: $OVERALL_FAIL"
  echo ""
  
  echo "-- 錯誤日誌摘要 --"
  grep -r "FAIL\|Error\|Traceback\|OOM" "$LOG_DIR"/*.log | tail -10
  
  echo "========================================"
  echo "報告: $REPORT"
  echo "========================================"
} | tee "$REPORT"

read -p "按 Enter 結束... "
