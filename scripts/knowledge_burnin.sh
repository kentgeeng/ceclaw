#!/bin/bash
# CECLAW 雙向知識庫燒機測試
# 用法：bash knowledge_burnin.sh [N輪]

ROUTER="http://localhost:8000"
TOKEN="97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759"
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ -z "$1" ]; then
    read -p "請輸入燒機輪數 N: " N
else
    N=$1
fi

echo ""
echo "========================================="
echo " CECLAW 雙向知識庫燒機 x ${N} 輪"
echo "========================================="

PASS=0
FAIL=0
TOTAL_TIME=0
LOG_FILE=~/ceclaw/scripts/burnin_$(date +%Y%m%d_%H%M%S).log
exec > >(tee -a "$LOG_FILE") 2>&1
echo "Log: $LOG_FILE"

CONTENTS=(
    "客服部門規範：所有投訴案件必須在24小時內回覆"
    "行銷部門規範：所有對外文案發布前需主管審核"
    "業務部門規範：報價單需附上有效期限，最長30天"
    "HR部門規範：新進員工試用期為三個月"
    "研發部門規範：所有 PR 必須有兩位以上 reviewer 才能合併"
    "資安規範：禁止將公司資料上傳至個人雲端儲存服務"
    "財務規範：單筆採購超過一萬元需主管簽核"
    "研發部門規範：每週五下午進行 code review 會議"
)
QUESTIONS=(
    "客服部門投訴案件的回覆時限是多久？"
    "行銷文案發布前需要什麼程序？"
    "業務報價單的有效期限規定是什麼？"
    "新進員工試用期多長？"
    "PR 合併需要幾位 reviewer？"
    "公司資料可以上傳個人雲端嗎？"
    "採購多少金額以上需要主管簽核？"
    "code review 會議什麼時候開？"
)
KEYWORDS=(
    "24"
    "主管審核"
    "30"
    "三個月"
    "兩位"
    "禁止"
    "一萬"
    "週五"
)
DEPTS=(
    "customer-support"
    "marketing"
    "sales"
    "hr"
    "engineering"
    "security"
    "finance"
    "engineering"
)

CONTENT_COUNT=${#CONTENTS[@]}

for i in $(seq 1 $N); do
    IDX=$(( (i - 1) % CONTENT_COUNT ))
    CONTENT="${CONTENTS[$IDX]}"
    QUESTION="${QUESTIONS[$IDX]}"
    KEYWORD="${KEYWORDS[$IDX]}"
    DEPT="${DEPTS[$IDX]}"

    echo ""
    echo "-----------------------------------------"
    echo -e "${YELLOW}第 ${i}/${N} 輪 | 部門：${DEPT}${NC}"
    echo "-----------------------------------------"

    START=$(date +%s%N)

    # Step 1: Hermes → OpenClaw (submit)
    echo -e "  ${BLUE}[→ IN ]${NC} Hermes 提交：${CONTENT:0:30}..."
    SUBMIT=$(curl -s -X POST "${ROUTER}/api/knowledge/submit" \
        -H "Content-Type: application/json" \
        -d "{\"content\":\"${CONTENT}\",\"dept\":\"${DEPT}\",\"user_id\":\"burnin\",\"source\":\"hermes\"}")
    FILENAME=$(echo $SUBMIT | python3 -c "import json,sys; print(json.load(sys.stdin).get('filename',''))" 2>/dev/null)

    if [ -z "$FILENAME" ]; then
        echo -e "  ${RED}[FAIL]${NC} submit 失敗"
        FAIL=$((FAIL+1))
        continue
    fi
    echo -e "  ${GREEN}[✓]${NC} pending: ${FILENAME}"

    # Step 2: 主管審核 (approve)
    echo -e "  ${BLUE}[→ IN ]${NC} 主管審核 approve..."
    APPROVE=$(curl -s -X POST "${ROUTER}/api/knowledge/approve" \
        -H "Content-Type: application/json" \
        -d "{\"filename\":\"${FILENAME}\",\"layer\":\"dept\",\"scope\":\"${DEPT}\"}")
    APPROVE_STATUS=$(echo $APPROVE | python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)

    if [ "$APPROVE_STATUS" != "ok" ]; then
        echo -e "  ${RED}[FAIL]${NC} approve 失敗"
        FAIL=$((FAIL+1))
        continue
    fi
    echo -e "  ${GREEN}[✓]${NC} 已入庫 dept/${DEPT}"

    # Step 3: RAG 驗證
    echo -e "  ${BLUE}[← OUT]${NC} RAG 查詢：${QUESTION}"
    ANSWER=$(curl -s "${ROUTER}/v1/chat/completions" \
        -H "Authorization: Bearer ${TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"model\":\"ceclaw\",\"messages\":[{\"role\":\"user\",\"content\":\"${QUESTION}\"}],\"stream\":false}" \
        | python3 -c "import json,sys; print(json.load(sys.stdin)['choices'][0]['message']['content'][:80])" 2>/dev/null)

    if echo "$ANSWER" | grep -q "$KEYWORD"; then
        echo -e "  ${GREEN}[← OUT]${NC} AI 正確引用：${ANSWER:0:60}..."
        RAG_OK=1
    else
        echo -e "  ${YELLOW}[~ OUT]${NC} 未命中關鍵字「${KEYWORD}」：${ANSWER:0:60}..."
        RAG_OK=0
    fi

    # Step 4: OpenClaw → Hermes (sync-policies)
    POLICY="[企業政策更新] ${CONTENT}"
    echo -e "  ${BLUE}[→ OUT]${NC} OpenClaw 推送政策到 Hermes..."
    SYNC=$(curl -s -X POST "${ROUTER}/api/knowledge/sync-policies" \
        -H "Content-Type: application/json" \
        -d "{\"content\":\"${POLICY}\",\"title\":\"burnin round ${i}\"}")
    SYNC_STATUS=$(echo $SYNC | python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)

    if [ "$SYNC_STATUS" == "ok" ]; then
        echo -e "  ${GREEN}[← IN ]${NC} Hermes MEMORY.md 已更新"
        PASS=$((PASS+1))
    else
        echo -e "  ${RED}[FAIL]${NC} sync-policies 失敗"
        FAIL=$((FAIL+1))
        continue
    fi

    END=$(date +%s%N)
    ELAPSED=$(( (END - START) / 1000000 ))
    TOTAL_TIME=$((TOTAL_TIME + ELAPSED))
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

# ── 雙側證據 dump ──────────────────────────────
echo ""
echo "========================================="
echo " 雙向溝通證據"
echo "========================================="
echo ""
echo "--- CECLAW 側（approved 入庫記錄）---"
ls -lt ~/.ceclaw/knowledge/bridge/approved/*.json 2>/dev/null | head -20
echo ""
echo "--- CECLAW 側（policies 推送記錄）---"
ls -lt ~/.ceclaw/knowledge/bridge/policies/*.txt 2>/dev/null | head -10
echo ""
echo "--- Hermes 側（MEMORY.md 最新10筆）---"
tail -30 ~/.hermes/memories/MEMORY.md 2>/dev/null | grep -A2 "企業政策更新\|企業規則" | head -30
echo "========================================="
