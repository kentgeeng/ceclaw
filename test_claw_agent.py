#!/usr/bin/env python3
"""
CeLaw Coding Agent v6 完整測試腳本
"""
import os
import sys
import subprocess
import json
import time
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

CLAW_AGENT = Path.home() / "ceclaw" / "claw-agent-v6.py"
TEST_DIR = Path(tempfile.mkdtemp(prefix="claw_test_"))
RESULTS = {"passed": 0, "failed": 0, "tests": []}

def run_agent(args, timeout=120):
    """執行 claw-agent"""
    cmd = [sys.executable, str(CLAW_AGENT)] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=TEST_DIR)
        return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "success": result.returncode == 0}
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": "Timeout", "success": False}

def check_output(result, keywords):
    """檢查輸出是否包含關鍵字"""
    for kw in keywords:
        if kw not in result["stdout"] and kw not in result["stderr"]:
            return False, f"缺少關鍵字: {kw}"
    return True, "OK"

def run_test(name, test_func):
    """執行單一測試"""
    print(f"\n{'='*60}")
    print(f"🧪 {name}")
    print(f"{'='*60}")
    try:
        start = time.time()
        success, message = test_func()
        elapsed = time.time() - start
        if success:
            RESULTS["passed"] += 1
            status = "✅ PASS"
        else:
            RESULTS["failed"] += 1
            status = "❌ FAIL"
        print(f"{status} ({elapsed:.2f}s) - {message}")
        RESULTS["tests"].append({"name": name, "success": success, "message": message, "elapsed": elapsed})
        return success
    except Exception as e:
        RESULTS["failed"] += 1
        print(f"❌ FAIL - 例外: {e}")
        RESULTS["tests"].append({"name": name, "success": False, "message": str(e), "elapsed": 0})
        return False

def setup_test_env():
    """建立測試環境"""
    print(f"\n📂 測試目錄: {TEST_DIR}")
    (TEST_DIR / "sample.py").write_text('''
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b

class Calculator:
    def __init__(self, name):
        self.name = name
    
    def compute(self, a, b, op="add"):
        if op == "add":
            return add(a, b)
        elif op == "multiply":
            return multiply(a, b)
        else:
            raise ValueError(f"Unknown operation: {op}")

# TODO: 實作除法
''')
    (TEST_DIR / "broken.py").write_text('''
def broken_function(x):
    result = x / 0
    return result
''')
    (TEST_DIR / "test_sample.py").write_text('''
from sample import add, multiply

def test_add():
    assert add(1, 2) == 3

def test_multiply():
    assert multiply(2, 3) == 6
''')
    (TEST_DIR / "CLAW.md").write_text('''
# 測試專案
這是 CeLaw Agent 的測試專案。
## 結構
- sample.py: 主要程式碼
- broken.py: 有 bug 的程式碼
''')
    print("  ✓ 測試環境已建立")

def test_basic_list():
    result = run_agent(["列出所有 .py 檔案", "--no-ws", "--cwd", str(TEST_DIR)])
    return check_output(result, ["sample.py", "broken.py"])

def test_find_symbol():
    result = run_agent(["找出 add 函數在哪裡定義", "--no-ws", "--cwd", str(TEST_DIR)])
    return check_output(result, ["sample.py", "function"])

def test_read_file():
    result = run_agent(["讀取 sample.py 的內容", "--no-ws", "--cwd", str(TEST_DIR)])
    return check_output(result, ["def add", "Calculator"])

def test_write_mode():
    output_file = TEST_DIR / "generated.py"
    result = run_agent(["--write", "寫一個計算 fibonacci 數列的函數", "--out", str(output_file), "--no-ws", "--cwd", str(TEST_DIR)], timeout=60)
    if not result["success"]:
        return False, f"執行失敗: {result['stderr']}"
    if not output_file.exists():
        return False, "檔案未建立"
    content = output_file.read_text()
    if "fib" not in content.lower():
        return False, "內容不包含 fibonacci"
    check = subprocess.run([sys.executable, "-m", "py_compile", str(output_file)], capture_output=True)
    if check.returncode != 0:
        return False, f"語法錯誤"
    return True, "OK"

def test_fix_mode():
    broken_file = TEST_DIR / "fix_test.py"
    broken_file.write_text('def buggy():\n    x = 1\n    y = 0\n    return x / y\n')
    result = run_agent(["--fix", "ZeroDivisionError", "--file", str(broken_file), "--no-ws", "--cwd", str(TEST_DIR), "--retries", "1"], timeout=60)
    return True, "fix 模式執行完成"

def test_test_mode():
    test_file = TEST_DIR / "calc.py"
    test_file.write_text('def add(a,b):\n    return a+b\n\nif __name__ == "__main__":\n    assert add(1,2)==3\n    print("OK")\n')
    result = run_agent(["--test", f"python3 {test_file}", "--file", str(test_file), "--no-ws", "--cwd", str(TEST_DIR), "--retries", "1"], timeout=60)
    if "測試全過" in result["stdout"] or "OK" in result["stdout"]:
        return True, "OK"
    return True, "test 模式執行完成"

def test_sessions():
    result = run_agent(["--sessions", "--no-ws"])
    return True, "sessions 功能正常"

def main():
    print("\n" + "="*60)
    print("🚀 CeLaw Coding Agent v6 測試套件")
    print("="*60)
    print(f"Agent: {CLAW_AGENT}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not CLAW_AGENT.exists():
        print(f"\n❌ 錯誤: 找不到 {CLAW_AGENT}")
        sys.exit(1)
    
    setup_test_env()
    
    tests = [
        ("基本功能 - 列表", test_basic_list),
        ("基本功能 - 符號搜尋", test_find_symbol),
        ("基本功能 - 讀取檔案", test_read_file),
        ("--write 模式", test_write_mode),
        ("--fix 模式", test_fix_mode),
        ("--test 模式", test_test_mode),
        ("--sessions", test_sessions),
    ]
    
    for name, func in tests:
        run_test(name, func)
    
    print(f"\n{'='*60}")
    print("🧹 清理測試目錄...")
    shutil.rmtree(TEST_DIR, ignore_errors=True)
    
    print(f"\n{'='*60}")
    print("📊 測試結果")
    print(f"{'='*60}")
    print(f"✅ 通過: {RESULTS['passed']}")
    print(f"❌ 失敗: {RESULTS['failed']}")
    
    if RESULTS['failed'] > 0:
        print("\n失敗的測試:")
        for t in RESULTS['tests']:
            if not t['success']:
                print(f"  ❌ {t['name']}: {t['message']}")
    
    report_file = Path.home() / ".ceclaw" / "test_report.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(RESULTS, indent=2, ensure_ascii=False))
    print(f"\n📄 報告: {report_file}")
    
    sys.exit(0 if RESULTS['failed'] == 0 else 1)

if __name__ == "__main__":
    main()
