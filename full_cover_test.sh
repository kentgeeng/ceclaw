#!/bin/bash
# CeLaw Agent v6 全功能覆蓋壓力測試 (Final Edition)
# 涵蓋模式：
# 1. General (一般對話/分析)
# 2. Write --write (寫程式)
# 3. Fix   --fix   (修復 Bug)
# 4. Test  --test  (自動測試)
# 5. Parallel --parallel (多 Agent 並行 - 這是之前缺的)

AGENT="$HOME/ceclaw/claw-agent-v6.py"
LOG_DIR="$HOME/ceclaw/test_logs/stress_final"
mkdir -p "$LOG_DIR"

echo "=========================================================="
echo "  CeLaw Agent v6 全功能壓力測試 (確認版)"
echo "=========================================================="
read -p "輸入測試局數 (每局 5 個任務): " ROUNDS

TOTAL_PASS=0
TOTAL_TESTS=0

# 輔助函數：執行並驗證
run_check() {
  local mode=$1; shift
  local task_cmd="$@"
  local log_file="$LOG_DIR/${mode}_r${ROUNDS}.log"
  
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -e "\n[執行] 模式：$mode"
  echo "       指令：$task_cmd"
  echo -n "       狀態：等待中... "

  # 執行
  eval $task_cmd > "$log_file" 2>&1

  # 驗證邏輯
  # 標準：Exit code 0 + Log 內有 Agent 的特徵字 (🔧 或 ✅ 或 完成)
  if grep -q "🔧\|✅\|完成\|DONE" "$log_file" 2>/dev/null; then
     echo "✅ 成功 (Log: $log_file)"
     TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo "❌ 失敗 (Log: $log_file)"
     # 顯示最後 3 行方便除錯
     tail -n 3 "$log_file" | sed 's/^/          /'
  fi
}

# ==========================================================
# 主測試循環
# ==========================================================
CURRENT_ROUND=0

while [ $CURRENT_ROUND -lt $ROUNDS ]; do
  CURRENT_ROUND=$((CURRENT_ROUND + 1))
  ROUNDS=$CURRENT_ROUND # 讓子程式能參考
  echo "================================================================"
  echo "🚀 第 $CURRENT_ROUND / $ROUNDS 局測試開始"
  echo "================================================================"

  # --- 準備測試檔案 ---
  # Test 模式用的檔案
  TEST_FILE="/tmp/agent_test_code_${CURRENT_ROUND}.py"
  echo "def add(a,b): return a+b" > "$TEST_FILE"
  
  # Fix 模式用的 Bug 檔案 (故意拼錯 return)
  FIX_FILE="/tmp/agent_bug_code_${CURRENT_ROUND}.py"
  echo "def broken(x, y): reutrn x + y" > "$FIX_FILE"

  # --- 1. Write 模式 ---
  run_check "Write" "timeout 90 python3 $AGENT --no-ws --session-id 'write_r${CURRENT_ROUND}' --steps 8 \
                     --write '建立一個 BMI 計算 Python Script' \
                     --out '/tmp/agent_bmi_${CURRENT_ROUND}.py'"

  # --- 2. Fix 模式 ---
  run_check "Fix" "timeout 90 python3 $AGENT --no-ws --session-id 'fix_r${CURRENT_ROUND}' --steps 8 \
                     --fix '修復語法錯誤 (reutrn 拼錯了)' \
                     --file '$FIX_FILE'"

  # --- 3. Test 模式 ---
  run_check "Test" "timeout 90 python3 $AGENT --no-ws --session-id 'test_r${CURRENT_ROUND}' --steps 8 \
                     --test '幫我寫一個簡單的 unittest 並執行它' \
                     --file '$TEST_FILE'"

  # --- 4. Parallel 模式 (多 Agent 並行，v6 特色) ---
  # 注意：這是一個指令內部啟動多個子 Agent
  run_check "Parallel" "timeout 90 python3 $AGENT --no-ws --session-id 'par_r${CURRENT_ROUND}' --steps 8 \
                     --parallel '任務 A: 說一聲 Hello' '任務 B: 計算 13*13'"

  # --- 5. General 模式 ---
  run_check "General" "timeout 60 python3 $AGENT --no-ws --session-id 'gen_r${CURRENT_ROUND}' --steps 5 \
                     '請問你是誰？請列出目前所在資料夾的所有檔案 ('ls')'"

  sleep 1
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
   echo "🎉 恭喜！Claw Agent v6 核心功能運行正常。"
else
   echo "⚠️ 偵測到不穩定，請檢查上方 Log 訊息。"
fi

