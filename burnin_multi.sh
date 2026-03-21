#!/bin/bash
# CECLAW P4 多後端燒機腳本
# 交替測試 ollama-fast（短問題）和 gb10-llama（推理問題）

ROUNDS=${1:-200}
ENDPOINT="http://host.openshell.internal:8000/v1/chat/completions"
AUTH="Bearer ceclaw-local"

fast_ok=0; fast_fail=0; fast_total_ms=0
main_ok=0; main_fail=0; main_total_ms=0

echo "CECLAW P4 多後端燒機 — ${ROUNDS} 輪"
echo "=================================================="

for i in $(seq 1 $ROUNDS); do
    # 奇數輪：短問題 → 應走 ollama-fast
    if [ $((i % 2)) -eq 1 ]; then
        Q="hi"
        TYPE="fast"
        PAYLOAD="{\"model\":\"minimax\",\"messages\":[{\"role\":\"user\",\"content\":\"${Q}\"}],\"max_tokens\":20}"
    else
        # 偶數輪：推理問題 → 應走 gb10-llama
        Q="why is the sky blue"
        TYPE="main"
        PAYLOAD="{\"model\":\"minimax\",\"messages\":[{\"role\":\"user\",\"content\":\"${Q}\"}],\"max_tokens\":30}"
    fi

    t0=$(date +%s%3N)
    RESP=$(curl -s -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Authorization: $AUTH" \
        -d "$PAYLOAD")
    t1=$(date +%s%3N)
    ms=$((t1 - t0))

    CONTENT=$(echo "$RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); m=d.get('choices',[{}])[0].get('message',{}); print((m.get('content','') or m.get('reasoning_content',''))[:20])" 2>/dev/null)

    if [ -n "$CONTENT" ]; then
        echo "[$(printf '%04d' $i)] ✅ ${ms}ms [${TYPE}] '${Q}' → '${CONTENT}'"
        if [ "$TYPE" = "fast" ]; then
            fast_ok=$((fast_ok+1)); fast_total_ms=$((fast_total_ms+ms))
        else
            main_ok=$((main_ok+1)); main_total_ms=$((main_total_ms+ms))
        fi
    else
        echo "[$(printf '%04d' $i)] ❌ ${ms}ms [${TYPE}] '${Q}'"
        if [ "$TYPE" = "fast" ]; then
            fast_fail=$((fast_fail+1))
        else
            main_fail=$((main_fail+1))
        fi
    fi
done

echo "=================================================="
fast_total=$((fast_ok+fast_fail))
main_total=$((main_ok+main_fail))
[ $fast_ok -gt 0 ] && fast_avg=$((fast_total_ms/fast_ok)) || fast_avg=0
[ $main_ok -gt 0 ] && main_avg=$((main_total_ms/main_ok)) || main_avg=0

echo "ollama-fast: ${fast_ok}/${fast_total} 成功，avg=${fast_avg}ms"
echo "gb10-llama:  ${main_ok}/${main_total} 成功，avg=${main_avg}ms"
echo "總計: $((fast_ok+main_ok))/${ROUNDS} 成功"
