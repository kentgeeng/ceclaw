#!/bin/bash
# CECLAW P4 Smart Routing 燒機腳本 v3
# 新增：SearXNG Layer 2 AI 決策觸發驗證
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
    "好的"
    "謝謝"
    "translate hello to chinese"
    "what day is today"
    "give me a number between 1 and 10"
    "say goodbye"
    "what is 2+2"
    "ok got it"
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
    "解釋什麼是機器學習"
    "幫我寫一封商業郵件"
    "什麼是 CAP theorem"
    "compare REST API vs GraphQL"
    "解釋 Kubernetes 的架構"
    "幫我分析這季財報的風險"
    "what is the difference between TCP and UDP"
    "設計一個簡單的資料庫 schema"
)

FAST_LEN=${#FAST_QUERIES[@]}
MAIN_LEN=${#MAIN_QUERIES[@]}

echo "CECLAW P4 Smart Routing 燒機 v3 — ${ROUNDS} 輪"
echo "fast 路徑 ${FAST_LEN} 題 / main 路徑 ${MAIN_LEN} 題 輪流"
echo "=================================================="

# === SearXNG Layer 1：Proxy 連通驗證 ===
echo "=== SearXNG Layer 1：Proxy 連通驗證 ==="
SEARCH_RESP=$(curl -s --max-time 10 "http://host.openshell.internal:8000/search?q=test&format=json")
SEARCH_COUNT=$(echo "$SEARCH_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('results',[])))" 2>/dev/null)
if [ -n "$SEARCH_COUNT" ] && [ "$SEARCH_COUNT" -gt 0 ]; then
    echo "Layer 1: ✅ SearXNG Proxy 正常（results=${SEARCH_COUNT}）"
else
    echo "Layer 1: ⚠️  無結果或連線失敗（繼續燒機）"
fi

# === SearXNG Layer 2：AI 決策觸發驗證 ===
echo ""
echo "=== SearXNG Layer 2：AI 決策觸發驗證 ==="
echo "發送即時性 prompt，驗證 AI 是否上網搜尋..."

L2_QUERIES=("NVIDIA 股價現在多少？" "比特幣今天價格" "台北今天天氣如何")
L2_PASS=0
L2_FAIL=0

for Q in "${L2_QUERIES[@]}"; do
    echo -n "  問：${Q} → "
    RESP=$(openclaw agent --agent main --session-id "burnin-l2-$(date +%s)" -m "$Q" --timeout 90 2>/dev/null)
    # 有數字（股價/溫度/幣價）或有具體地名/時間 = 有搜尋結果
    if echo "$RESP" | grep -qE '[0-9]+\.[0-9]+|[0-9]{3,}|°C|USD|TWD|台北|天氣|多雲|晴'; then
        echo "✅ 有實質回應"
        L2_PASS=$((L2_PASS+1))
    else
        echo "⚠️  無實質資料（可能未觸發搜尋）"
        L2_FAIL=$((L2_FAIL+1))
    fi
    sleep 3
done

if [ "$L2_PASS" -gt 0 ]; then
    echo "Layer 2: ✅ ${L2_PASS}/${#L2_QUERIES[@]} 題有上網並回傳有效資料"
else
    echo "Layer 2: ❌ 全部無效（SearXNG 整合可能有問題）"
fi
echo "=========================="
echo ""

# === 主燒機迴圈 ===
for i in $(seq 1 $ROUNDS); do
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

    START=$(date +%s%3N)
    RESP=$(curl -s --max-time 60 -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Authorization: $AUTH" \
        -d "{\"model\":\"minimax\",\"messages\":[{\"role\":\"user\",\"content\":\"$Q\"}],\"max_tokens\":50}" 2>/dev/null)
    END=$(date +%s%3N)
    ms=$((END - START))

    CONTENT=$(echo "$RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['choices'][0]['message']['content'][:40])" 2>/dev/null)
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

    # 每 100 輪做一次 Layer 2 驗證
    if [ $((i % 100)) -eq 0 ]; then
        echo ""
        echo "=== 第 ${i} 輪 SearXNG Layer 2 定期驗證 ==="
        L2_PASS_MID=0
        for Q2 in "${L2_QUERIES[@]}"; do
            echo -n "  問：${Q2} → "
            RESP2=$(openclaw agent --agent main --session-id "burnin-mid-$(date +%s)" -m "$Q2" --timeout 90 2>/dev/null)
            if echo "$RESP2" | grep -qE '[0-9]+\.[0-9]+|[0-9]{3,}|°C|USD|TWD|台北|天氣|多雲|晴'; then
                echo "✅"
                L2_PASS_MID=$((L2_PASS_MID+1))
            else
                echo "⚠️  無實質資料"
            fi
            sleep 3
        done
        if [ "$L2_PASS_MID" -gt 0 ]; then
            echo "Layer 2 @ ${i}: ✅ ${L2_PASS_MID}/3"
        else
            echo "Layer 2 @ ${i}: ❌ SearXNG 可能失效"
        fi
        echo "=========================="
        echo ""
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
