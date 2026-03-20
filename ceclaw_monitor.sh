#!/bin/bash
# CECLAW 監控腳本 v1.0
# 用法：bash ceclaw_monitor.sh
# 建議：加入 crontab，每 5 分鐘跑一次
# crontab -e → */5 * * * * bash ~/ceclaw/ceclaw_monitor.sh >> ~/.ceclaw/monitor.log 2>&1

LOG=~/.ceclaw/monitor.log
TS=$(date "+%Y-%m-%d %H:%M:%S")

check_router() {
    RESP=$(curl -s --max-time 5 http://localhost:8000/ceclaw/status)
    if [ $? -ne 0 ] || [ -z "$RESP" ]; then
        echo "[$TS] ❌ ROUTER DOWN" | tee -a $LOG
        return 1
    fi
    GB10=$(echo $RESP | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['backends']['gb10-llama'])" 2>/dev/null)
    if [ "$GB10" != "True" ] && [ "$GB10" != "true" ]; then
        echo "[$TS] ⚠️  ROUTER UP / GB10 DOWN (fallback active)" | tee -a $LOG
        return 2
    fi
    echo "[$TS] ✅ ROUTER UP / GB10 UP" | tee -a $LOG
    return 0
}

check_gb10() {
    RESP=$(curl -s --max-time 5 http://192.168.1.91:8001/v1/models)
    if [ $? -ne 0 ] || [ -z "$RESP" ]; then
        echo "[$TS] ❌ GB10 直連失敗 (192.168.1.91:8001)" | tee -a $LOG
        return 1
    fi
    echo "[$TS] ✅ GB10 直連 OK" | tee -a $LOG
    return 0
}

check_sandbox() {
    STATUS=$(openshell sandbox list 2>/dev/null | grep "ceclaw-agent" | awk "{print \$2}")
    if [ -z "$STATUS" ]; then
        echo "[$TS] ❌ SANDBOX ceclaw-agent 不存在" | tee -a $LOG
        return 1
    fi
    echo "[$TS] ✅ SANDBOX $STATUS" | tee -a $LOG
    return 0
}

echo "[$TS] === CECLAW 監控開始 ===" >> $LOG
check_router
ROUTER_STATUS=$?
check_gb10
check_sandbox

if [ $ROUTER_STATUS -eq 1 ]; then
    echo "[$TS] 🚨 建議執行：sudo systemctl restart ceclaw-router" | tee -a $LOG
fi
if [ $ROUTER_STATUS -eq 2 ]; then
    echo "[$TS] 🚨 建議執行：ssh zoe_gb@192.168.1.91 "nohup ~/start_llama.sh > ~/llama.log 2>&1 &"" | tee -a $LOG
fi
echo "[$TS] === 監控結束 ===" >> $LOG
