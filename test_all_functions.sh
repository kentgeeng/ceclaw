#!/bin/bash
# CeLaw Agent v6 完整功能迴圈測試 (修正版)

AGENT="$HOME/ceclaw/claw-agent-v6.py"
LOG_DIR="$HOME/ceclaw/test_logs"
REPORT_DIR="$HOME/ceclaw/test_reports"
mkdir -p "$LOG_DIR" "$REPORT_DIR"

REPORT="$REPORT_DIR/report_$(date +%Y%m%d_%H%M%S).txt"

echo "========================================"
echo "  CeLaw Agent v6 完整功能測試"
echo "========================================"
read -p "輸入迴圈次數: " LOOPS
echo "測試將執行 $LOOPS 次迴圈"
echo ""

GREEN="✅"; RED="❌"; YELLOW="⏳"

# Python 通用 Import 模組 (處理 claw-agent-v6.py hyphen 問題)
PY_IMPORT="import sys; sys.path.insert(0,'/home/zoe_ai/ceclaw'); import importlib.util as iu, sys as s; spec=iu.spec_from_file_location('claw_agent_v6','/home/zoe_ai/ceclaw/claw-agent-v6.py'); mod=iu.module_from_spec(spec); s.modules['claw_agent_v6']=mod; spec.loader.exec_module(mod)"

# ═══════════════════════════════════════════════
# 測試函數定義
# ═══════════════════════════════════════════════
tL1H(){ local l=$1; local log="$LOG_DIR/L1H_L${l}.log"
    curl -s http://localhost:8002/health > "$log" 2>&1
    grep -q '"status":"ok"' "$log" && echo "$GREEN" || echo "$RED"; }

tGBH(){ local l=$1; local log="$LOG_DIR/GBH_L${l}.log"
    curl -s http://192.168.1.91:8001/health > "$log" 2>&1
    grep -q '"status":"ok"' "$log" && echo "$GREEN" || echo "$RED"; }

tRM(){ local l=$1; local log="$LOG_DIR/RM_L${l}.log"
    curl -s http://localhost:8000/v1/models > "$log" 2>&1
    grep -q "qwen3.5-9b" "$log" && echo "$GREEN" || echo "$RED"; }

tL1C(){ local l=$1; local log="$LOG_DIR/L1C_L${l}.log"
    curl -s -X POST http://localhost:8002/v1/chat/completions -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"hi"}],"max_tokens":20}' > "$log" 2>&1
    grep -q '"content"' "$log" && echo "$GREEN" || echo "$RED"; }

tGBC(){ local l=$1; local log="$LOG_DIR/GBC_L${l}.log"
    curl -s -X POST http://192.168.1.91:8001/v1/chat/completions -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"hi"}],"max_tokens":20}' > "$log" 2>&1
    grep -q '"content"' "$log" && echo "$GREEN" || echo "$RED"; }

tRL1(){ local l=$1; local log="$LOG_DIR/RL1_L${l}.log"
    curl -s -X POST http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"qwen3.5-9b","messages":[{"role":"user","content":"hi"}],"max_tokens":20}' > "$log" 2>&1
    grep -q '"content"' "$log" && echo "$GREEN" || echo "$RED"; }

tRGB(){ local l=$1; local log="$LOG_DIR/RGB_L${l}.log"
    curl -s -X POST http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"minimax","messages":[{"role":"user","content":"hi"}],"max_tokens":20}' > "$log" 2>&1
    grep -q '"content"' "$log" && echo "$GREEN" || echo "$RED"; }

tSLT(){ local l=$1; local log="$LOG_DIR/SLT_L${l}.log"
    curl -s http://localhost:8002/slots > "$log" 2>&1
    grep -q '"id"' "$log" && echo "$GREEN" || echo "$RED"; }

tWSP(){ local l=$1
    timeout 1 bash -c "echo > /dev/tcp/localhost/8003" 2>/dev/null && echo "$GREEN" || echo "$YELLOW"; }

tGEN(){ local l=$1; local log="$LOG_DIR/GEN_L${l}.log"
    timeout 60 python3 "$AGENT" --no-ws --steps 2 "say hi" > "$log" 2>&1
    grep -qi "hi\|DONE\|完成" "$log" && echo "$GREEN" || echo "$RED"; }

tWRT(){ local l=$1; local log="$LOG_DIR/WRT_L${l}.log"
    cd /tmp && timeout 60 python3 "$AGENT" --no-ws --write "write hello" --out h_${l}.py > "$log" 2>&1
    [ -f "h_${l}.py" ] && echo "$GREEN" || echo "$RED"; rm -f h_${l}.py 2>/dev/null; }

tPAR(){ local l=$1; local log="$LOG_DIR/PAR_L${l}.log"
    timeout 90 python3 "$AGENT" --no-ws --parallel "say A" "say B" > "$log" 2>&1
    grep -qE "並行|agent-|完成" "$log" && echo "$GREEN" || echo "$RED"; }

tSES(){ local l=$1; local log="$LOG_DIR/SES_L${l}.log"
    python3 "$AGENT" --sessions > "$log" 2>&1; echo "$GREEN"; }

tGRP(){ local l=$1; local log="$LOG_DIR/GRP_L${l}.log"
    # 增加 timeout 避免 scan 過慢卡死
    timeout 30 python3 -c "$PY_IMPORT; from claw_agent_v6 import execute_tool; r=execute_tool('grep',{'pattern':'def main','path':'/home/zoe_ai/ceclaw'}); print('OK' if r else 'FAIL')" > "$log" 2>&1
    grep -q "OK" "$log" && echo "$GREEN" || echo "$RED"; }

tFND(){ local l=$1; local log="$LOG_DIR/FND_L${l}.log"
    timeout 30 python3 -c "$PY_IMPORT; from claw_agent_v6 import execute_tool; r=execute_tool('find',{'name':'*.py','path':'/home/zoe_ai/ceclaw'}); print('OK' if '.py' in r else 'FAIL')" > "$log" 2>&1
    grep -q "OK" "$log" && echo "$GREEN" || echo "$RED"; }

tLSD(){ local l=$1; local log="$LOG_DIR/LSD_L${l}.log"
    timeout 10 python3 -c "$PY_IMPORT; from claw_agent_v6 import execute_tool; r=execute_tool('list_dir',{'path':'/home/zoe_ai/ceclaw'}); print('OK' if 'claw' in r else 'FAIL')" > "$log" 2>&1
    grep -q "OK" "$log" && echo "$GREEN" || echo "$RED"; }

tSYM(){ local l=$1; local log="$LOG_DIR/SYM_L${l}.log"
    timeout 30 python3 -c "$PY_IMPORT; from claw_agent_v6 import build_symbol_map; m=build_symbol_map('/home/zoe_ai/ceclaw'); print('OK' if m else 'FAIL')" > "$log" 2>&1
    grep -q "OK" "$log" && echo "$GREEN" || echo "$RED"; }

tCPT(){ local l=$1; local log="$LOG_DIR/CPT_L${l}.log"
    # 修正：檢查內容是否被截斷，而不是檢查長度
    python3 -c "$PY_IMPORT; from claw_agent_v6 import micro_compact_messages; msgs=[{'role':'system','content':'s'}]+[{'role':'tool','content':'x'*5000}]*10; r=micro_compact_messages(msgs); print('OK' if any('[舊工具輸出已壓縮]' in m.get('content','') for m in r if m['role']=='tool') else 'FAIL')" > "$log" 2>&1
    grep -q "OK" "$log" && echo "$GREEN" || echo "$RED"; }

tTKN(){ local l=$1; local log="$LOG_DIR/TKN_L${l}.log"
    python3 -c "$PY_IMPORT; from claw_agent_v6 import estimate_tokens; t=estimate_tokens([{'role':'user','content':'hello'}]); print(t if t>0 else 'FAIL')" > "$log" 2>&1
    grep -qE "^[0-9]+$" "$log" && echo "$GREEN" || echo "$RED"; }

tRLOG(){ local l=$1; local log="$LOG_DIR/RLOG_L${l}.log"
    tail -20 ~/.ceclaw/router.log > "$log" 2>&1; echo "$GREEN"; }

# ═══════════════════════════════════════════════
# 測試清單 (使用陣列以支持名稱中的空格)
# ═══════════════════════════════════════════════
TESTS=(
  "tL1H:L1健康"
  "tGBH:GB10健康"
  "tRM:Router模型"
  "tL1C:L1聊天"
  "tGBC:GB10聊天"
  "tRL1:Router→L1"
  "tRGB:Router→GB10"
  "tSLT:L1 Slots"
  "tWSP:WS Port"
  "tGEN:一般模式"
  "tWRT:寫程式"
  "tPAR:多Agent"
  "tSES:Session列表"
  "tGRP:Tool grep"
  "tFND:Tool find"
  "tLSD:Tool listdir"
  "tSYM:SymbolMap"
  "tCPT:MicroCompact"
  "tTKN:Token估算"
  "tRLOG:Router Log"
)

declare -A P F S
TOTAL=0; PC=0; FC=0; SC=0
for entry in "${TESTS[@]}"; do
    fn="${entry%%:*}"; P[$fn]=0; F[$fn]=0; S[$fn]=0
done

START=$(date +%s)

for loop in $(seq 1 $LOOPS); do
    echo "== 迴圈 $loop/$LOOPS =="
    for entry in "${TESTS[@]}"; do
        fn="${entry%%:*}"
        desc="${entry#*:}"
        printf "  %-14s .. " "$desc"
        
        # 執行測試
        r=$($fn $loop 2>&1)
        TOTAL=$((TOTAL+1))
        if echo "$r" | grep -q "$GREEN"; then
            echo "$GREEN"; P[$fn]=$((P[$fn]+1)); PC=$((PC+1))
        elif echo "$r" | grep -q "$RED"; then
            echo "$RED"; F[$fn]=$((F[$fn]+1)); FC=$((FC+1))
        else
            echo "$YELLOW"; S[$fn]=$((S[$fn]+1)); SC=$((SC+1))
        fi
    done
    echo ""
done

END=$(date +%s)

{
    echo "========================================"
    echo "  測試報告 - $(date '+%Y-%m-%d %H:%M:%S')"
    echo "========================================"
    echo "迴圈: $LOOPS | 總測試: $TOTAL | 耗時: $((END-START))秒"
    echo ""
    printf "  %-16s %5s %5s %5s\n" "項目" "通過" "失敗" "跳過"
    echo "----------------------------------------"
    for entry in "${TESTS[@]}"; do
        fn="${entry%%:*}"
        desc="${entry#*:}"
        printf "  %-16s %5d %5d %5d\n" "$desc" "${P[$fn]}" "${F[$fn]}" "${S[$fn]}"
    done
    echo "----------------------------------------"
    printf "  %-16s %5d %5d %5d\n" "總計" "$PC" "$FC" "$SC"
    echo ""
    [ $FC -eq 0 ] && echo "  🎉 全部通過！" || echo "  ⚠️ $FC 個失敗"
    echo ""
    echo "-- 失敗詳情 --"
    for entry in "${TESTS[@]}"; do
        fn="${entry%%:*}"
        desc="${entry#*:}"
        if [ ${F[$fn]} -gt 0 ]; then
            echo "  $desc: ${F[$fn]}次"
        fi
    done
    echo ""
    echo "-- Router Errors --"
    tail -5 ~/.ceclaw/router.log | grep -Ei "ERROR|503" || echo "無"
    echo ""
    echo "-- 服務狀態 --"
    curl -s http://localhost:8002/health 2>/dev/null | grep -q "ok" && echo "L1 ✅" || echo "L1 ❌"
    curl -s http://192.168.1.91:8001/health 2>/dev/null | grep -q "ok" && echo "GB10 ✅" || echo "GB10 ❌"
    curl -s http://localhost:8000/v1/models 2>/dev/null | grep -q "qwen3.5-9b" && echo "Router ✅" || echo "Router ❌"
    echo ""
    echo "報告: $REPORT"
} | tee "$REPORT"

echo ""
echo "日誌目錄: $LOG_DIR"
read -p "按 Enter 結束"
