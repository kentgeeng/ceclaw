#!/bin/bash
# CECLAW P4 Smart Routing 燒機腳本
# 驗證 fast / main 兩條路徑各自穩定

ROUNDS=${1:-100}
ENDPOINT="http://host.openshell.internal:8000/v1/chat/completions"
AUTH="Bearer ceclaw-local"
ROUTER_LOG="$HOME/.ceclaw/router.log"

fast_ok=0; fast_fail=0; fast_wrong=0; fast_total_ms=0
main_ok=0; main_fail=0; main_wrong=0; main_total_ms=0

FAST_QUERIES=(
    "hi"
    "hello"
    "what time is it"
    "tell me a joke"
    "name a color"
    "say ok"
    "what is python"
    "1+1=?"
)

MAIN_QUERIES=(
    "為什麼天空是藍色的"
    "幫我寫一份報告大綱"
    "這個演算法的複雜度"
    "debug this performance issue"
    "design a REST API architecture"
    "explain recursion"
    "什麼是財務風險"
    "how to implement binary search"
)

FAST_LEN=${#FAST_QUERIES[@]}
MAIN_LEN=${#MAIN_QUERIES[@]}

echo "CECLAW P4 Smart Routing 燒機 — ${ROUNDS} 輪"
echo "fast 路徑 8 題 / main 路徑 8 題 輪流"
echo "=================================================="

for i in $(seq 1 $ROUNDS); do
    # 奇數輪 fast，偶數輪 main
    if [ $((i % 2)) -eq 1 ]; then
        IDX=$(( ((i-1)/2) % FAST_LEN ))
        Q="${FAST_QUERIES[$IDX]}"
        TYPE="fast"
        EXPECTED="ollama-fast"
    else
        IDX=$(( ((i-2)/2) % MAIN_LEN ))
        Q="${MAIN_QUERIES[$IDX]}"
        TYPE="main"
        EXPECTED="gb10-llama"
    fi

    PAYLOAD="{\"model\":\"minimax\",\"messages\":[{\"role\":\"user\",\"content\":\"${Q}\"}],\"max_tokens\":200}"

    t0=$(date +%s%3N)
    RESP=$(curl -s -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Authorization: $AUTH" \
        -d "$PAYLOAD")
    t1=$(date +%s%3N)
    ms=$((t1 - t0))

    CONTENT=$(echo "$RESP" | python3 -c "
import json,sys
m=json.load(sys.stdin).get('choices',[{}])[0].get('message',{})
print((m.get('content','') or m.get('reasoning_content',''))[:25])
" 2>/dev/null)

    # 從 log 抓最後一筆 backend
    ACTUAL=$(tail -5 "$ROUTER_LOG" 2>/dev/null | grep "\[local\]" | tail -1 | grep -o "ollama-fast\|gb10-llama\|ollama-backup" | head -1)

    if [ -z "$CONTENT" ]; then
        echo "[$(printf '%05d' $i)] ❌ ${ms}ms [${TYPE}] '${Q}'"
        [ "$TYPE" = "fast" ] && fast_fail=$((fast_fail+1)) || main_fail=$((main_fail+1))
    elif [ -n "$ACTUAL" ] && [ "$ACTUAL" != "$EXPECTED" ]; then
        echo "[$(printf '%05d' $i)] ⚠️  ${ms}ms [${TYPE}] '${Q}' → wrong backend: ${ACTUAL} (expected ${EXPECTED})"
        [ "$TYPE" = "fast" ] && fast_wrong=$((fast_wrong+1)) || main_wrong=$((main_wrong+1))
    else
        echo "[$(printf '%05d' $i)] ✅ ${ms}ms [${TYPE}] '${Q}' → '${CONTENT}'"
        if [ "$TYPE" = "fast" ]; then
            fast_ok=$((fast_ok+1)); fast_total_ms=$((fast_total_ms+ms))
        else
            main_ok=$((main_ok+1)); main_total_ms=$((main_total_ms+ms))
        fi
    fi
done

echo "=================================================="
fast_total=$((fast_ok+fast_fail+fast_wrong))
main_total=$((main_ok+main_fail+main_wrong))
[ $fast_ok -gt 0 ] && fast_avg=$((fast_total_ms/fast_ok)) || fast_avg=0
[ $main_ok -gt 0 ] && main_avg=$((main_total_ms/main_ok)) || main_avg=0

echo "ollama-fast: ${fast_ok}/${fast_total} 成功，wrong_backend=${fast_wrong}，avg=${fast_avg}ms"
echo "gb10-llama:  ${main_ok}/${main_total} 成功，wrong_backend=${main_wrong}，avg=${main_avg}ms"
echo "總計: $((fast_ok+main_ok))/$((fast_total+main_total)) 成功"
