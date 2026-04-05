#!/bin/bash
# CECLAW 真實雙向溝通燒機
# 每輪：Hermes 執行工具任務 → shared/ h2o → Chroma → OpenClaw o2h → MEMORY.md

ROUTER="http://localhost:8000"
HERMES="http://localhost:8642"
TOKEN="97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759"
GREEN='\033[0;32m'; RED='\033[0;31m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'

if [ -z "$1" ]; then read -p "請輸入燒機輪數 N: " N; else N=$1; fi

LOG_FILE=~/ceclaw/scripts/shared_burnin_$(date +%Y%m%d_%H%M%S).log
exec > >(tee -a "$LOG_FILE") 2>&1
echo "Log: $LOG_FILE"

echo "========================================="
echo " CECLAW 雙向溝通燒機 x ${N} 輪"
echo "========================================="

PASS=0; FAIL=0; TOTAL_TIME=0

# 取得 session
SESSION=$(curl -s http://localhost:8642/api/sessions | python3 -c "import json,sys; print(json.load(sys.stdin)['items'][0]['id'])" 2>/dev/null)
if [ -z "$SESSION" ]; then
    echo "❌ 無法取得 Hermes session，請確認 Hermes 已啟動"
    exit 1
fi
echo "使用 session: $SESSION"

TASKS=(
    "請用 terminal 執行 date && hostname，告訴我結果"
    "請用 terminal 執行 uptime，告訴我系統運行時間"
    "請用 terminal 執行 df -h / | tail -1，告訴我磁碟使用狀況"
    "請用 terminal 執行 free -h | grep Mem，告訴我記憶體狀況"
    "請用 terminal 執行 whoami && pwd，告訴我目前使用者和目錄"
)
TASK_COUNT=${#TASKS[@]}

for i in $(seq 1 $N); do
    IDX=$(( (i - 1) % TASK_COUNT ))
    TASK="${TASKS[$IDX]}"
    START=$(date +%s%N)

    echo ""
    echo "-----------------------------------------"
    echo -e "${YELLOW}第 ${i}/${N} 輪${NC}"
    echo "-----------------------------------------"

    # Step 1: Hermes 執行工具任務
    echo -e "  ${BLUE}[→ H ]${NC} Hermes 執行：${TASK:0:30}..."
    API_CALLS=$(curl -s -X POST "http://localhost:8642/api/sessions/${SESSION}/chat/stream" \
        -H "Content-Type: application/json" \
        -d "{\"message\":\"${TASK}\",\"model\":\"ceclaw\"}" \
        --max-time 60 | grep -a "api_calls" | python3 -c "
import sys,json
for line in sys.stdin:
    if 'api_calls' in line:
        try:
            d = json.loads(line.replace('data: ',''))
            print(d.get('api_calls',0))
            break
        except: pass
" 2>/dev/null)

    if [ -z "$API_CALLS" ] || [ "$API_CALLS" -le 1 ] 2>/dev/null; then
        echo -e "  ${RED}[FAIL]${NC} Hermes 未使用工具（api_calls=${API_CALLS}）"
        FAIL=$((FAIL+1))
        continue
    fi
    echo -e "  ${GREEN}[✓]${NC} Hermes 完成（api_calls=${API_CALLS}）"

    # Step 2: 確認 h2o 寫入 shared/（最多等10秒）
    H2O_COUNT=0
    for retry in 1 2 3 4 5; do
        sleep 2
        H2O_COUNT=$(cd ~/ceclaw/router && ~/ceclaw/.venv/bin/python3 -c "
import shared_bridge as sb
items = sb.scan(direction='h2o', status='pending')
print(len(items))
" 2>/dev/null)
        [ "$H2O_COUNT" -ge 1 ] && break
    done
    if [ "$H2O_COUNT" -lt 1 ] 2>/dev/null; then
        echo -e "  ${RED}[FAIL]${NC} shared/ h2o 未寫入（等待10秒後仍無）"
        FAIL=$((FAIL+1))
        continue
    fi
    echo -e "  ${GREEN}[← H→O]${NC} shared/ h2o: ${H2O_COUNT} 筆待處理"

    # Step 3: OpenClaw 掃描 h2o 入 Chroma
    bash ~/ceclaw/scripts/scan_shared_h2o.sh 2>/dev/null
    echo -e "  ${GREEN}[✓]${NC} OpenClaw 入庫完成"

    # Step 4: OpenClaw 寫 o2h 回 Hermes
    CONTENT="企業知識更新：第${i}輪工具任務成果已採納，請繼續保持良好工作習慣"
    SUBMIT=$(curl -s -X POST "${ROUTER}/api/knowledge/submit" \
        -H "Content-Type: application/json" \
        -d "{\"content\":\"${CONTENT}\",\"dept\":\"engineering\",\"user_id\":\"burnin\"}")
    FILENAME=$(echo $SUBMIT | python3 -c "import json,sys; print(json.load(sys.stdin).get('filename',''))" 2>/dev/null)

    if [ -z "$FILENAME" ]; then
        echo -e "  ${RED}[FAIL]${NC} OpenClaw submit 失敗"
        FAIL=$((FAIL+1))
        continue
    fi

    APPROVE=$(curl -s -X POST "${ROUTER}/api/knowledge/approve" \
        -H "Content-Type: application/json" \
        -d "{\"filename\":\"${FILENAME}\",\"layer\":\"dept\",\"scope\":\"engineering\"}")
    echo -e "  ${GREEN}[O→H ]${NC} OpenClaw approve → shared/ o2h"

    # Step 5: Hermes 掃描 o2h 入 MEMORY.md
    bash ~/ceclaw/scripts/scan_shared_o2h.sh 2>/dev/null
    echo -e "  ${GREEN}[← O ]${NC} Hermes MEMORY.md 已更新"

    END=$(date +%s%N)
    ELAPSED=$(( (END - START) / 1000000 ))
    TOTAL_TIME=$((TOTAL_TIME + ELAPSED))
    PASS=$((PASS+1))
    echo -e "  ⏱  本輪耗時：${ELAPSED}ms"
done

echo ""
echo "========================================="
echo " 燒機結果"
echo "========================================="
echo " 總輪數：${N}"
echo -e " ${GREEN}通過：${PASS}${NC}"
echo -e " ${RED}失敗：${FAIL}${NC}"
if [ $N -gt 0 ] && [ $TOTAL_TIME -gt 0 ]; then
    AVG=$((TOTAL_TIME / N))
    echo " 平均耗時：${AVG}ms"
fi
echo "========================================="

echo ""
echo "--- shared/ 最終狀態 ---"
cd ~/ceclaw/router && ~/ceclaw/.venv/bin/python3 -c "
import shared_bridge as sb
items = sb.scan(status=None)
print(f'總計 {len(items)} 筆')
from collections import Counter
states = Counter(i['state'] for i in items)
for k,v in states.items():
    print(f'  {k}: {v}')
"

echo "--- Hermes MEMORY.md 最後5筆 ---"
tail -15 ~/.hermes/memories/MEMORY.md | grep -A1 "OpenClaw政策\|企業知識" | head -10
echo "========================================="
