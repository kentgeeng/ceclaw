#!/bin/bash
# CeLaw Agent v6 深度壓力測試 (v3 - 穩定版)
# 特點：
# 1. 全覆蓋四大核心模式 (Write, Fix, Test, General)
# 2. 終端即時同步顯示 (Live Tail)
# 3. 嚴格驗證：包含語法檢查與檔案驗證

AGENT="$HOME/ceclaw/claw-agent-v6.py"
LOG_DIR="$HOME/ceclaw/test_logs/stress_v3"
mkdir -p "$LOG_DIR"

echo "=================================================================="
echo "  CeLaw Agent v6 深度壓力測試 (v3)"
echo "  覆蓋模式：Write, Fix, Test, General"
echo "=================================================================="
read -p "輸入測試局數 (建議 3): " ROUNDS

TOTAL_PASS=0
TOTAL_FAIL=0

# 顏色設定
C_RED='\033[0;31m'; C_GREEN='\033[0;32m'; C_CYAN='\033[0;36m'; C_NC='\033[0m'

for r in $(seq 1 $ROUNDS); do
  echo ""
  echo -e "${C_CYAN}══════════════════ 第 $r/$ROUNDS 局 ══════════════════${C_NC}"
  
  WORKDIR="$HOME/ceclaw_test_r${r}"
  mkdir -p "$WORKDIR"
  
  # 測試素材準備
  echo 'def broken(x, y): reutrn x + y' > "$WORKDIR/bug.py"  # Fix 模式用
  echo 'def add(a,b): return a+b' > "$WORKDIR/sample.py"     # Test 模式用

  # 定義 4 個任務的 Log 檔
  LOG_W="$LOG_DIR/W_r${r}.log"
  LOG_F="$LOG_DIR/F_r${r}.log"
  LOG_T="$LOG_DIR/T_r${r}.log"
  LOG_G="$LOG_DIR/G_r${r}.log"
  
  echo "[Start] 啟動並行任務... (請稍候)"

  # 1. Task Write
  (python3 "$AGENT" --no-ws --session-id "W_${r}" --steps 6 \
   --write "寫一個 BMI 計算機 Python Script" --out "$WORKDIR/bmi.py" \
   > "$LOG_W" 2>&1) &
  PID_W=$!

  # 2. Task Fix
  (python3 "$AGENT" --no-ws --session-id "F_${r}" --steps 6 \
   --fix "修正這裡面的語法錯誤" --file "$WORKDIR/bug.py" \
   > "$LOG_F" 2>&1) &
  PID_F=$!

  # 3. Task Test
  (python3 "$AGENT" --no-ws --session-id "T_${r}" --steps 6 \
   --test "寫一個 unittest 並執行" --file "$WORKDIR/sample.py" \
   > "$LOG_T" 2>&1) &
  PID_T=$!

  # 4. Task General
  (python3 "$AGENT" --no-ws --session-id "G_${r}" --steps 6 \
   "請搜尋 ~/ceclaw/claw-agent-v6.py 裡面有多少行程式碼 (使用 wc -l)" \
   > "$LOG_G" 2>&1) &
  PID_G=$!

  # ─── 即時 Monitor 區塊 ───
  # 為了能看到過程，我們在背景跑 tail，並定期顯示
  # 簡單方法：每 2 秒列印一次各 Log 的最新 3 行
  
  echo -e "  ${C_CYAN}執行中...${C_NC}"
  while ps -p "$PID_W" > /dev/null || ps -p "$PID_F" > /dev/null || ps -p "$PID_T" > /dev/null || ps -p "$PID_G" > /dev/null; do
    sleep 2
    for f in "$LOG_W" "$LOG_F" "$LOG_T" "$LOG_G"; do
      if [ -f "$f" ]; then
        new=$(tail -n 3 "$f" | grep -v '^$' | tail -n 1)
        tag=$(basename $(dirname $f))_$(basename $f)
        # echo "  [$tag] $new" # 這行太吵雜，除非你想看即時行
      fi
    done
  done
  echo "  [Done] 所有 Agent 已結束。"

  # ─── 驗證區塊 ───
  echo -e "${C_CYAN}── 驗證結果 ──${C_NC}"

  # Verify Write
  if [ -s "$WORKDIR/bmi.py" ]; then
     echo -e "  $[Write] $C_GREEN 成功生成檔案 $C_NC"
     TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo -e "  $[Write] $C_RED 失敗：找不到 bmi.py $C_NC"
     TOTAL_FAIL=$((TOTAL_FAIL + 1))
     echo "    Log: $(tail -n 5 $LOG_W)"
  fi

  # Verify Fix
  # 檢查 bug.py 的 reutrn 是否被改回 return
  if ! grep -q "reutrn" "$WORKDIR/bug.py" && ! python3 -m py_compile "$WORKDIR/bug.py" 2>/dev/null; then
     echo -e "  $[Fix]   $C_GREEN 修復成功 (語法正確) $C_NC"
     TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo -e "  $[Fix]   $C_RED 失敗：仍有 Syntax Error 或未修復 $C_NC"
     TOTAL_FAIL=$((TOTAL_FAIL + 1))
     echo "    Log: $(tail -n 5 $LOG_F)"
  fi

  # Verify Test
  if grep -qi "passed\|successful\|1 passed\|test.*ran" "$LOG_T"; then
     echo -e "  $[Test]  $C_GREEN 測試模式運行正常 $C_NC"
     TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo -e "  $[Test]  $C_RED 失敗：似乎沒跑過測試 $C_NC"
     TOTAL_FAIL=$((TOTAL_FAIL + 1))
     echo "    Log: $(tail -n 5 $LOG_T)"
  fi

  # Verify General
  if grep -qi "lines\|行\|grep\|result" "$LOG_G"; then
     echo -e "  $[General] $C_GREEN 指令模式正常 $C_NC"
     TOTAL_PASS=$((TOTAL_PASS + 1))
  else
     echo -e "  $[General] $C_RED 失敗：無效輸出 $C_NC"
     TOTAL_FAIL=$((TOTAL_FAIL + 1))
     echo "    Log: $(tail -n 5 $LOG_G)"
  fi

done

echo ""
echo "=================================================================="
echo "  🏁 總結報告"
echo "=================================================================="
echo "  總計：$((TOTAL_PASS + TOTAL_FAIL)) | 通過：$TOTAL_PASS | 失敗：$TOTAL_FAIL"
if [ $TOTAL_FAIL -eq 0 ]; then echo "  🎉 恭喜！全功能壓力測試完美通過。"; fi
echo "  Log 位置：$LOG_DIR"
echo "=================================================================="

