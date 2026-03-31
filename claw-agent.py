#!/usr/bin/env python3
"""
CeLaw Coding Agent - Auto Coding Edition
模式：
  一般      python3 claw-agent.py "任務描述"
  寫程式    python3 claw-agent.py --write "需求" --out output.py
  修 bug    python3 claw-agent.py --fix "錯誤訊息" --file buggy.py
  自動測試  python3 claw-agent.py --test "pytest tests/" --file src/main.py
"""
import os, sys, json, subprocess, argparse
from pathlib import Path
try:
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

DEFAULT_ENDPOINT = os.environ.get("CECLAW_ENDPOINT", "http://localhost:8000")
DEFAULT_MODEL    = os.environ.get("CECLAW_MODEL",    "ceclaw-l1")
DEFAULT_TOKEN    = os.environ.get("CECLAW_TOKEN",    "97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759")

SYSTEM_PROMPT = """You are Claude Code, an AI coding assistant by Anthropic. You help users with software engineering tasks including writing code, debugging, refactoring, explaining code, running commands, and managing projects.
## Core principles
- Read files before editing them
- Prefer editing existing files over creating new ones
- Write clean, idiomatic, production-quality code matching the project's existing style
- Be concise — lead with the action or answer, not preamble
- Run tests after making changes when appropriate
- Security: never introduce SQL injection, XSS, command injection, or other vulnerabilities
- Don't add features or refactor beyond what was asked
## Available tools
**File operations:** read_file, write_file, list_dir
**Shell:** bash
## Additional rules
- Always respond in Traditional Chinese (繁體中文)
- Never fabricate file contents — always read first
- Complete the task then say DONE"""

TOOLS = [
    {"type":"function","function":{"name":"bash","description":"執行 bash 指令","parameters":{"type":"object","properties":{"command":{"type":"string"},"timeout":{"type":"integer","default":60}},"required":["command"]}}},
    {"type":"function","function":{"name":"read_file","description":"讀取檔案","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"write_file","description":"寫入檔案","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}},
    {"type":"function","function":{"name":"list_dir","description":"列出目錄","parameters":{"type":"object","properties":{"path":{"type":"string","default":"."}},"required":[]}}}
]

def execute_tool(name, args):
    try:
        if name == "bash":
            r = subprocess.run(args["command"], shell=True, capture_output=True, text=True, timeout=args.get("timeout",60))
            out = r.stdout + r.stderr
            return (out[:4000] + "\n...[截斷]") if len(out)>4000 else out or "(無輸出)"
        elif name == "read_file":
            p = Path(args["path"]).expanduser()
            if not p.exists(): return f"錯誤：找不到 {p}"
            c = p.read_text(errors="replace")
            return (c[:8000]+"\n...[截斷]") if len(c)>8000 else c
        elif name == "write_file":
            p = Path(args["path"]).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(args["content"])
            return f"已寫入 {p} ({len(args['content'])} bytes)"
        elif name == "list_dir":
            p = Path(args.get("path",".")).expanduser()
            if not p.exists(): return f"錯誤：找不到 {p}"
            items = sorted(p.iterdir(), key=lambda x:(x.is_file(),x.name))
            return "\n".join(("📁 " if i.is_dir() else "📄 ")+i.name for i in items[:50])
        return f"未知工具：{name}"
    except subprocess.TimeoutExpired:
        return f"逾時（{args.get('timeout',60)}s）"
    except Exception as e:
        return f"錯誤：{e}"

def call_ceclaw(messages, endpoint, model, token):
    resp = requests.post(
        f"{endpoint.rstrip('/')}/v1/chat/completions",
        json={"model":model,"messages":messages,"tools":TOOLS,"tool_choice":"auto","temperature":0,"max_tokens":4096},
        headers={"Content-Type":"application/json","Authorization":f"Bearer {token}"},
        timeout=180
    )
    resp.raise_for_status()
    return resp.json()

def run_agent(task, endpoint, model, token, max_steps=30, mode="general"):
    print(f"\n\033[36m🤖 CeLaw Agent [{mode}]\033[0m")
    print(f"   Task : {task[:80]}{'...' if len(task)>80 else ''}")
    print("─"*60)
    messages = [{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":task}]

    for step in range(max_steps):
        print(f"\n\033[90m[Step {step+1}/{max_steps}]\033[0m")
        try:
            resp = call_ceclaw(messages, endpoint, model, token)
        except requests.exceptions.ConnectionError:
            print(f"\033[31m❌ 無法連線到 {endpoint}\033[0m"); return False
        except Exception as e:
            print(f"\033[31m❌ API 錯誤：{e}\033[0m"); return False

        choice = resp["choices"][0]
        msg = choice["message"]
        messages.append(msg)

        if msg.get("content"):
            print(f"\033[32m💬 {msg['content']}\033[0m")
            if "DONE" in msg["content"]:
                print("\n\033[36m✅ 完成\033[0m"); return True

        tool_calls = msg.get("tool_calls",[])
        if not tool_calls:
            if choice.get("finish_reason") == "stop":
                print("\n\033[36m✅ 完成\033[0m"); return True
            continue

        results = []
        for tc in tool_calls:
            fn = tc["function"]["name"]
            try: fa = json.loads(tc["function"]["arguments"])
            except: fa = {}
            print(f"  🔧 {fn}({', '.join(f'{k}={repr(v)[:50]}' for k,v in fa.items())})")
            r = execute_tool(fn, fa)
            print(f"  \033[90m→ {r[:200]}{'...' if len(r)>200 else ''}\033[0m")
            results.append({"role":"tool","tool_call_id":tc["id"],"content":r})
        messages.extend(results)

    print(f"\n\033[33m⚠️  達到最大步數 {max_steps}\033[0m"); return False

# ── Auto Write ────────────────────────────────────────────────────────────────
def mode_write(requirement, outfile, endpoint, model, token):
    print(f"\n\033[35m✍️  Auto Write 模式\033[0m")
    task = f"""請根據以下需求寫程式，儲存到 {outfile}：

需求：{requirement}

步驟：
1. 寫完整可執行的程式
2. 加上適當的繁體中文註解
3. 儲存到 {outfile}
4. 用 bash 執行確認無語法錯誤
5. 完成後說 DONE"""
    run_agent(task, endpoint, model, token, max_steps=15, mode="write")

# ── Auto Fix ──────────────────────────────────────────────────────────────────
def mode_fix(error_msg, filepath, endpoint, model, token, max_retries=3):
    print(f"\n\033[35m🔧 Auto Fix 模式\033[0m  檔案：{filepath}  最多重試：{max_retries}")
    for attempt in range(1, max_retries+1):
        print(f"\n\033[90m── Fix 嘗試 {attempt}/{max_retries} ──\033[0m")
        task = f"""請修復 {filepath} 中的 bug：

錯誤訊息：{error_msg}

步驟：
1. 讀取 {filepath}
2. 分析並修復錯誤
3. 寫回檔案
4. 執行驗證
5. 成功說 DONE，否則說 STILL_FAILING"""
        run_agent(task, endpoint, model, token, max_steps=15, mode=f"fix-{attempt}")

        # 驗證
        p = Path(filepath).expanduser()
        cmd = f"python3 {p}" if p.suffix==".py" else f"bash {p}"
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            print(f"\033[32m✅ 修復成功！（{attempt} 次）\033[0m"); return True
        error_msg = r.stdout + r.stderr
        print(f"\033[31m❌ 仍有錯誤，重試...\033[0m")

    print(f"\033[31m❌ 修復失敗\033[0m"); return False

# ── Auto Test ─────────────────────────────────────────────────────────────────
def mode_test(test_cmd, filepath, endpoint, model, token, max_retries=5):
    print(f"\n\033[35m🧪 Auto Test 模式\033[0m  測試：{test_cmd}  最多重試：{max_retries}")
    for attempt in range(1, max_retries+1):
        print(f"\n\033[90m── 測試 {attempt}/{max_retries} ──\033[0m")
        print(f"  \033[33m$ {test_cmd}\033[0m")
        r = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=120)
        output = r.stdout + r.stderr
        if r.returncode == 0:
            print(f"\033[32m✅ 測試全過！（{attempt} 次）\033[0m"); return True
        print(f"\033[31m❌ 測試失敗\033[0m\n{output[:300]}")
        if attempt >= max_retries: break
        task = f"""測試失敗，請修復 {filepath}：

測試指令：{test_cmd}
失敗輸出：{output[:2000]}

讀取檔案、分析、修復、說 DONE"""
        run_agent(task, endpoint, model, token, max_steps=15, mode=f"test-{attempt}")

    print(f"\033[31m❌ 達到最大重試，測試未通過\033[0m"); return False

# ── 主程式 ────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="CeLaw Coding Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""範例：
  python3 claw-agent.py "列出 home 目錄"
  python3 claw-agent.py --write "寫 fibonacci" --out fib.py
  python3 claw-agent.py --fix "NameError: x" --file script.py
  python3 claw-agent.py --test "python3 -m pytest tests/" --file src/main.py""")
    p.add_argument("task",       nargs="?")
    p.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    p.add_argument("--model",    default=DEFAULT_MODEL)
    p.add_argument("--token",    default=DEFAULT_TOKEN)
    p.add_argument("--steps",    type=int, default=30)
    p.add_argument("--retries",  type=int, default=3)
    p.add_argument("--write",    metavar="REQ")
    p.add_argument("--out",      metavar="FILE")
    p.add_argument("--fix",      metavar="ERROR")
    p.add_argument("--file",     metavar="FILE")
    p.add_argument("--test",     metavar="CMD")
    a = p.parse_args()
    cfg = dict(endpoint=a.endpoint, model=a.model, token=a.token)

    if a.write:
        mode_write(a.write, a.out or "output.py", **cfg)
    elif a.fix:
        if not a.file: print("❌ --fix 需要 --file"); sys.exit(1)
        mode_fix(a.fix, a.file, **cfg, max_retries=a.retries)
    elif a.test:
        if not a.file: print("❌ --test 需要 --file"); sys.exit(1)
        mode_test(a.test, a.file, **cfg, max_retries=a.retries)
    elif a.task:
        run_agent(a.task, **cfg, max_steps=a.steps)
    else:
        print("\033[36mCeLaw Coding Agent (q 退出)\033[0m")
        print("指令：write/fix/test 或直接輸入任務")
        while True:
            try:
                line = input("\n📝 > ").strip()
                if not line: continue
                if line.lower() in ("q","quit","exit"): break
                parts = line.split(None,1)
                cmd = parts[0].lower()
                if cmd=="write" and len(parts)>1:
                    out = input("   輸出檔案 (output.py): ").strip() or "output.py"
                    mode_write(parts[1], out, **cfg)
                elif cmd=="fix" and len(parts)>1:
                    f = input("   目標檔案: ").strip()
                    mode_fix(parts[1], f, **cfg, max_retries=a.retries)
                elif cmd=="test" and len(parts)>1:
                    f = input("   目標檔案: ").strip()
                    mode_test(parts[1], f, **cfg, max_retries=a.retries)
                else:
                    run_agent(line, **cfg, max_steps=a.steps)
            except KeyboardInterrupt:
                break
        print("\n👋 再見")

if __name__ == "__main__":
    main()
