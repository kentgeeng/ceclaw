#!/bin/bash
# law_rag_burnin.sh — 法律RAG燒機測試
# 用法：bash law_rag_burnin.sh [次數]

ROUNDS=${1:-10}
TOKEN="97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759"
URL="http://localhost:8000/v1/chat/completions"
LOG="$HOME/.ceclaw/law_rag_burnin_$(date +%Y%m%d_%H%M%S).log"

PASS=0; FAIL=0; RAG_HIT=0; RAG_MISS=0

declare -a QUESTIONS=(
  "懷孕員工可以解雇嗎？"
  "公司蒐集員工個資需要什麼程序？"
  "員工離職後可以帶走自己寫的程式碼嗎？"
  "員工偷公司機密資料會有什麼刑事責任？"
)

echo "=== 法律RAG燒機 × ${ROUNDS} 輪 ===" | tee "$LOG"
echo "開始時間：$(date)" | tee -a "$LOG"
echo "" | tee -a "$LOG"

for ((r=1; r<=ROUNDS; r++)); do
  echo "--- 第 ${r}/${ROUNDS} 輪 ---" | tee -a "$LOG"
  for q in "${QUESTIONS[@]}"; do
    RESULT=$(curl -s --max-time 30 -X POST "$URL" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"model\":\"ceclaw\",\"messages\":[{\"role\":\"user\",\"content\":\"$q\"}]}" \
      | python3 -c "
import json, sys, re
try:
    d = json.load(sys.stdin)
    c = d['choices'][0]['message']['content']
    hit = '✅ RAG' if re.search(r'第\s*\d+\s*條|【.+法', c) else '⚠️  NO-RAG'
    print(hit + ' | ' + c[:60].replace('\n', ' '))
except Exception as e:
    print('❌ ERROR | ' + str(e))
" 2>&1)

    echo "  [Q] $q" | tee -a "$LOG"
    echo "  [A] $RESULT" | tee -a "$LOG"

    if echo "$RESULT" | grep -q "❌ ERROR"; then
      ((FAIL++))
    else
      ((PASS++))
      echo "$RESULT" | grep -q "✅ RAG" && ((RAG_HIT++)) || ((RAG_MISS++))
    fi
    sleep 1
  done
  echo "" | tee -a "$LOG"
done

TOTAL=$((PASS + FAIL))
echo "==============================" | tee -a "$LOG"
echo "完成時間：$(date)" | tee -a "$LOG"
echo "總請求：$TOTAL | 成功：$PASS | 失敗：$FAIL" | tee -a "$LOG"
echo "RAG觸發：$RAG_HIT | 未觸發：$RAG_MISS" | tee -a "$LOG"
echo "成功率：$(python3 -c "print(f'{$PASS/$TOTAL*100:.1f}%')")" | tee -a "$LOG"
echo "RAG觸發率：$(python3 -c "print(f'{$RAG_HIT/$PASS*100:.1f}%')" 2>/dev/null || echo 'N/A')" | tee -a "$LOG"
echo "Log：$LOG" | tee -a "$LOG"
