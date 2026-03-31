#!/usr/bin/env python3
"""
CeLaw Coding Agent v2
模式：
  一般      python3 claw-agent-v2.py "任務描述"
  寫程式    python3 claw-agent-v2.py --write "需求" --out output.py
  修 bug    python3 claw-agent-v2.py --fix "錯誤訊息" --file buggy.py
  自動測試  python3 claw-agent-v2.py --test "pytest tests/" --file src/main.py

v2 新增：
  - CLAW.md 專案記憶（啟動時自動讀）
  - grep tool（ripgrep / grep fallback）
  - file_edit tool（只改特定行，str_replace 模式）
  - git tool（diff / status / log）
  - 啟動時自動掃 cwd + git status
  - 危險操作確認（rm / 大檔覆寫）
  - session log（記錄改了哪些檔案）
"""
import os, sys, json, subprocess, argparse, shutil
from pathlib import Path
from datetime import datetime

try:
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

DEFAULT_ENDPOINT = os.environ.get("CECLAW_ENDPOINT", "http://localhost:8000")
DEFAULT_MODEL    = os.environ.get("CECLAW_MODEL",    "ceclaw")
DEFAULT_TOKEN    = os.environ.get("CECLAW_TOKEN",    "97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759")

# ── 危險指令模式 ──────────────────────────────────────────────────────────────
DANGEROUS_PATTERNS = ["rm -rf", "rm -f", "mkfs", "dd if=", "> /dev/", "chmod 777"]

# ── Session log ───────────────────────────────────────────────────────────────
SESSION_LOG = []
SESSION_START = datetime.now().strftime("%Y%m%d_%H%M%S")

def log_session(action, detail):
    SESSION_LOG.append({"time": datetime.now().strftime("%H:%M:%S"), "action": action, "detail": detail})

# ── 讀取 CLAW.md 專案記憶 ─────────────────────────────────────────────────────
def load_claw_md(cwd=None):
    cwd = Path(cwd or os.getcwd())
    for path in [cwd / "CLAW.md", cwd.parent / "CLAW.md", Path.home() / "CLAW.md"]:
        if path.exists():
            content = path.read_text(errors="replace")
            print(f"  \033[36m📋 CLAW.md 載入：{path}\033[0m")
            return f"\n\n## 專案背景（來自 CLAW.md）\n{content}"
    return ""

# ── 啟動時掃描專案 ────────────────────────────────────────────────────────────
def scan_project(cwd=None):
    cwd = Path(cwd or os.getcwd())
    lines = [f"\n## 當前工作目錄：{cwd}"]

    # git status
    r = subprocess.run("git status --short 2>/dev/null", shell=True, capture_output=True, text=True, cwd=cwd)
    if r.returncode == 0 and r.stdout.strip():
        lines.append(f"\n## Git Status\n```\n{r.stdout.strip()}\n```")
        # 最近 5 筆 commit
        r2 = subprocess.run("git log --oneline -5 2>/dev/null", shell=True, capture_output=True, text=True, cwd=cwd)
        if r2.stdout.strip():
            lines.append(f"\n## 最近 Commits\n```\n{r2.stdout.strip()}\n```")

    # README
    for readme in ["README.md", "README.txt", "README"]:
        p = cwd / readme
        if p.exists():
            content = p.read_text(errors="replace")[:1000]
            lines.append(f"\n## README（前 1000 字）\n{content}")
            break

    # 目錄結構（前兩層）
    items = []
    for item in sorted(cwd.iterdir())[:30]:
        if item.name.startswith(".") or item.name in ["__pycache__", "node_modules", ".git"]:
            continue
        items.append(("📁 " if item.is_dir() else "📄 ") + item.name)
    if items:
        lines.append(f"\n## 專案結構\n" + "\n".join(items))

    return "\n".join(lines)

# ── System Prompt ─────────────────────────────────────────────────────────────
BASE_SYSTEM_PROMPT = """You are CeLaw, a coding assistant by ColdElectric. You help with software engineering tasks: writing code, debugging, refactoring, explaining code, running commands, and managing projects.

## Core principles
- Always read files before editing them
- Use file_edit (str_replace) for small changes — never rewrite entire files unless necessary
- Use grep to search before assuming file contents
- Write clean, idiomatic, production-quality code
- Be concise — lead with action, not preamble
- Run tests after making changes when appropriate
- Never introduce SQL injection, XSS, command injection, or other vulnerabilities
- Don't add features beyond what was asked

## Available tools
- bash: run shell commands
- read_file: read file contents
- write_file: write entire file (use sparingly — prefer file_edit)
- file_edit: edit specific lines using str_replace (safer than write_file)
- grep: search in files using regex
- git: git operations (diff, log, status, blame)
- list_dir: list directory contents

## Rules
- Always respond in Traditional Chinese (繁體中文)
- Use Taiwan terminology: 程式碼 (not 代碼), 程式設計 (not 編程)
- Never fabricate file contents — always read first
- Complete the task then say DONE"""

# ── Tool 定義 ─────────────────────────────────────────────────────────────────
TOOLS = [
    {"type":"function","function":{"name":"bash","description":"執行 bash 指令","parameters":{"type":"object","properties":{"command":{"type":"string"},"timeout":{"type":"integer","default":60}},"required":["command"]}}},
    {"type":"function","function":{"name":"read_file","description":"讀取檔案內容","parameters":{"type":"object","properties":{"path":{"type":"string"},"start_line":{"type":"integer","description":"從第幾行開始（選填）"},"end_line":{"type":"integer","description":"到第幾行結束（選填）"}},"required":["path"]}}},
    {"type":"function","function":{"name":"write_file","description":"寫入整個檔案（大改動用）","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}},
    {"type":"function","function":{"name":"file_edit","description":"用 str_replace 只改特定部分（小改動優先用這個）","parameters":{"type":"object","properties":{"path":{"type":"string"},"old_str":{"type":"string","description":"要被取代的原始字串（必須完全匹配）"},"new_str":{"type":"string","description":"取代後的新字串"}},"required":["path","old_str","new_str"]}}},
    {"type":"function","function":{"name":"grep","description":"在檔案中搜尋 pattern","parameters":{"type":"object","properties":{"pattern":{"type":"string"},"path":{"type":"string","description":"搜尋路徑（預設當前目錄）"},"glob":{"type":"string","description":"檔案 glob 篩選，例如 *.py"},"case_insensitive":{"type":"boolean","default":False}},"required":["pattern"]}}},
    {"type":"function","function":{"name":"git","description":"git 操作","parameters":{"type":"object","properties":{"command":{"type":"string","enum":["status","diff","log","blame","show","branch"]},"args":{"type":"string","description":"額外參數，例如 HEAD~1 或 filename"}},"required":["command"]}}},
    {"type":"function","function":{"name":"find","description":"找檔案或目錄（用檔名搜尋）","parameters":{"type":"object","properties":{"name":{"type":"string","description":"檔名 pattern，例如 SOUL.md 或 *.py"},"path":{"type":"string","description":"搜尋起始路徑（預設 cwd）"},"type":{"type":"string","enum":["f","d",""],"description":"f=只找檔案，d=只找目錄"}},"required":["name"]}}},
    {"type":"function","function":{"name":"list_dir","description":"列出目錄內容","parameters":{"type":"object","properties":{"path":{"type":"string","default":"."}},"required":[]}}},
]

# ── Tool 執行 ─────────────────────────────────────────────────────────────────
def is_dangerous(command):
    return any(p in command for p in DANGEROUS_PATTERNS)

def confirm_dangerous(command):
    print(f"\n\033[31m⚠️  危險操作偵測：{command[:100]}\033[0m")
    ans = input("確認執行？(y/N) ").strip().lower()
    return ans == "y"

def execute_tool(name, args, cwd=None):
    cwd = cwd or os.getcwd()
    try:
        if name == "bash":
            cmd = args["command"]
            if is_dangerous(cmd):
                if not confirm_dangerous(cmd):
                    return "使用者取消危險操作"
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                             timeout=args.get("timeout", 60), cwd=cwd)
            out = r.stdout + r.stderr
            return (out[:4000] + "\n...[截斷]") if len(out) > 4000 else out or "(無輸出)"

        elif name == "read_file":
            p = Path(args["path"]).expanduser()
            if not p.exists():
                return f"錯誤：找不到 {p}"
            lines = p.read_text(errors="replace").splitlines()
            start = args.get("start_line", 1) - 1
            end = args.get("end_line", len(lines))
            selected = lines[start:end]
            # 加行號
            result = "\n".join(f"{start+i+1:4d}\t{l}" for i, l in enumerate(selected))
            if len(result) > 8000:
                result = result[:8000] + "\n...[截斷]"
            return result

        elif name == "write_file":
            p = Path(args["path"]).expanduser()
            # 大檔警告
            if p.exists() and p.stat().st_size > 10000:
                print(f"\n\033[33m⚠️  覆寫大檔案：{p} ({p.stat().st_size} bytes)\033[0m")
                ans = input("確認覆寫？(y/N) ").strip().lower()
                if ans != "y":
                    return "使用者取消覆寫"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(args["content"])
            log_session("write_file", str(p))
            return f"已寫入 {p} ({len(args['content'])} bytes)"

        elif name == "file_edit":
            p = Path(args["path"]).expanduser()
            if not p.exists():
                return f"錯誤：找不到 {p}"
            content = p.read_text(errors="replace")
            old_str = args["old_str"]
            new_str = args["new_str"]
            if old_str not in content:
                # 找相似
                lines = content.splitlines()
                old_lines = old_str.strip().splitlines()
                hint = f"找不到要取代的字串。前 3 行：{old_lines[:3]}"
                return f"錯誤：{hint}"
            count = content.count(old_str)
            if count > 1:
                return f"錯誤：找到 {count} 個匹配，需要唯一匹配才能安全替換"
            new_content = content.replace(old_str, new_str, 1)
            p.write_text(new_content)
            log_session("file_edit", str(p))
            changed = abs(len(new_content.splitlines()) - len(content.splitlines()))
            return f"已修改 {p}（{'新增' if len(new_content) > len(content) else '減少'} {changed} 行）"

        elif name == "grep":
            pattern = args["pattern"]
            path = args.get("path", cwd)
            glob = args.get("glob", "")
            ci = args.get("case_insensitive", False)

            # 優先用 rg，fallback grep
            if shutil.which("rg"):
                cmd = f"rg {'--ignore-case ' if ci else ''}"
                if glob:
                    cmd += f"--glob '{glob}' "
                cmd += f"-n --max-count=50 {repr(pattern)} {repr(str(path))}"
            else:
                cmd = f"grep -rn {'--ignore-case ' if ci else ''}"
                if glob:
                    cmd += f"--include='{glob}' "
                cmd += f"{repr(pattern)} {repr(str(path))} | head -50"

            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            out = r.stdout or r.stderr or "(無匹配)"
            return out[:3000]

        elif name == "git":
            cmd_map = {
                "status": "git status",
                "diff": f"git diff {args.get('args', '')}",
                "log": f"git log --oneline -20 {args.get('args', '')}",
                "blame": f"git blame {args.get('args', '')}",
                "show": f"git show {args.get('args', '')}",
                "branch": "git branch -a",
            }
            cmd = cmd_map.get(args["command"], f"git {args['command']}")
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=cwd)
            out = r.stdout + r.stderr
            return (out[:3000] + "\n...[截斷]") if len(out) > 3000 else out or "(無輸出)"

        elif name == "find":
            fname = args["name"]
            fpath = args.get("path", cwd)
            ftype = args.get("type", "")
            type_flag = f"-type {ftype}" if ftype else ""
            cmd = f"find {repr(str(fpath))} {type_flag} -name {repr(fname)} 2>/dev/null | head -50"
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return r.stdout or "(無匹配)"

        elif name == "list_dir":
            p = Path(args.get("path", cwd or ".")).expanduser()
            if not p.exists():
                return f"錯誤：找不到 {p}"
            items = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
            lines = []
            for item in items[:60]:
                if item.name.startswith("."):
                    continue
                size = f" ({item.stat().st_size:,}B)" if item.is_file() else ""
                lines.append(("📁 " if item.is_dir() else "📄 ") + item.name + size)
            return "\n".join(lines) or "(空目錄)"

        return f"未知工具：{name}"
    except subprocess.TimeoutExpired:
        return f"逾時（{args.get('timeout', 60)}s）"
    except Exception as e:
        return f"錯誤：{e}"

# ── API 呼叫 ──────────────────────────────────────────────────────────────────
def call_ceclaw(messages, endpoint, model, token):
    resp = requests.post(
        f"{endpoint.rstrip('/')}/v1/chat/completions",
        json={"model": model, "messages": messages, "tools": TOOLS,
              "tool_choice": "auto", "temperature": 0, "max_tokens": 4096},
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        timeout=180
    )
    resp.raise_for_status()
    return resp.json()

# ── Agent loop ────────────────────────────────────────────────────────────────
def run_agent(task, endpoint, model, token, max_steps=30, mode="general", cwd=None):
    cwd = cwd or os.getcwd()
    print(f"\n\033[36m🤖 CeLaw Agent v2 [{mode}]\033[0m")
    print(f"   Task  : {task[:80]}{'...' if len(task) > 80 else ''}")
    print(f"   CWD   : {cwd}")
    print("─" * 60)

    # 組合 system prompt：base + CLAW.md + 專案掃描
    project_ctx = load_claw_md(cwd) + scan_project(cwd)
    system = BASE_SYSTEM_PROMPT + project_ctx

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": task}
    ]

    for step in range(max_steps):
        print(f"\n\033[90m[Step {step+1}/{max_steps}]\033[0m")
        try:
            resp = call_ceclaw(messages, endpoint, model, token)
        except requests.exceptions.ConnectionError:
            print(f"\033[31m❌ 無法連線到 {endpoint}\033[0m")
            return False
        except Exception as e:
            print(f"\033[31m❌ API 錯誤：{e}\033[0m")
            return False

        choice = resp["choices"][0]
        msg = choice["message"]
        messages.append(msg)

        if msg.get("content"):
            print(f"\033[32m💬 {msg['content']}\033[0m")
            if "DONE" in msg["content"]:
                print("\n\033[36m✅ 完成\033[0m")
                _print_session_log()
                return True

        tool_calls = msg.get("tool_calls", [])
        if not tool_calls:
            if choice.get("finish_reason") == "stop":
                print("\n\033[36m✅ 完成\033[0m")
                _print_session_log()
                return True
            continue

        results = []
        for tc in tool_calls:
            fn = tc["function"]["name"]
            try:
                fa = json.loads(tc["function"]["arguments"])
            except:
                fa = {}
            print(f"  🔧 {fn}({', '.join(f'{k}={repr(v)[:50]}' for k, v in fa.items())})")
            r = execute_tool(fn, fa, cwd=cwd)
            print(f"  \033[90m→ {r[:200]}{'...' if len(r) > 200 else ''}\033[0m")
            results.append({"role": "tool", "tool_call_id": tc["id"], "content": r})
        messages.extend(results)

    print(f"\n\033[33m⚠️  達到最大步數 {max_steps}\033[0m")
    _print_session_log()
    return False

def _print_session_log():
    if not SESSION_LOG:
        return
    print(f"\n\033[90m── Session Log ──")
    for entry in SESSION_LOG:
        print(f"  {entry['time']} [{entry['action']}] {entry['detail']}")
    print(f"──────────────────\033[0m")

# ── 模式函數 ──────────────────────────────────────────────────────────────────
def mode_write(requirement, outfile, endpoint, model, token, cwd=None):
    task = f"請根據以下需求寫程式，儲存到 {outfile}：\n\n需求：{requirement}\n\n步驟：\n1. 寫完整可執行程式\n2. 加繁體中文註解\n3. 儲存到 {outfile}\n4. 執行確認無語法錯誤\n5. 完成說 DONE"
    run_agent(task, endpoint, model, token, max_steps=15, mode="write", cwd=cwd)

def mode_fix(error_msg, filepath, endpoint, model, token, max_retries=3, cwd=None):
    print(f"\n\033[35m🔧 Auto Fix 模式\033[0m  檔案：{filepath}  最多重試：{max_retries}")
    for attempt in range(1, max_retries + 1):
        print(f"\n\033[90m── Fix 嘗試 {attempt}/{max_retries} ──\033[0m")
        task = f"請修復 {filepath} 中的 bug：\n\n錯誤訊息：{error_msg}\n\n步驟：\n1. 讀取檔案（用 read_file）\n2. 用 grep 搜尋相關程式碼\n3. 用 file_edit（str_replace）修復，不要整個覆寫\n4. 執行驗證\n5. 成功說 DONE，否則說 STILL_FAILING"
        run_agent(task, endpoint, model, token, max_steps=15, mode=f"fix-{attempt}", cwd=cwd)

        p = Path(filepath).expanduser()
        cmd = f"python3 {p}" if p.suffix == ".py" else f"bash {p}"
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            print(f"\033[32m✅ 修復成功！（{attempt} 次）\033[0m")
            return True
        error_msg = r.stdout + r.stderr
        print(f"\033[31m❌ 仍有錯誤，重試...\033[0m")

    print(f"\033[31m❌ 修復失敗\033[0m")
    return False

def mode_test(test_cmd, filepath, endpoint, model, token, max_retries=5, cwd=None):
    print(f"\n\033[35m🧪 Auto Test 模式\033[0m  測試：{test_cmd}  最多重試：{max_retries}")
    for attempt in range(1, max_retries + 1):
        print(f"\n\033[90m── 測試 {attempt}/{max_retries} ──\033[0m")
        r = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=120, cwd=cwd)
        if r.returncode == 0:
            print(f"\033[32m✅ 測試全過！（{attempt} 次）\033[0m")
            return True
        output = r.stdout + r.stderr
        print(f"\033[31m❌ 測試失敗\033[0m\n{output[:300]}")
        if attempt >= max_retries:
            break
        task = f"測試失敗，請修復 {filepath}：\n\n測試：{test_cmd}\n失敗：{output[:2000]}\n\n用 file_edit 修復（不要整個覆寫），說 DONE"
        run_agent(task, endpoint, model, token, max_steps=15, mode=f"test-{attempt}", cwd=cwd)

    print(f"\033[31m❌ 達到最大重試\033[0m")
    return False

# ── 主程式 ────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="CeLaw Coding Agent v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""範例：
  python3 claw-agent-v2.py "列出 home 目錄"
  python3 claw-agent-v2.py --write "寫 fibonacci" --out fib.py
  python3 claw-agent-v2.py --fix "NameError: x" --file script.py
  python3 claw-agent-v2.py --test "pytest tests/" --file src/main.py
  python3 claw-agent-v2.py --cwd ~/myproject "找出所有 TODO 並整理成清單"

提示：在專案目錄放一個 CLAW.md，agent 啟動時會自動讀取專案背景。""")
    p.add_argument("task",       nargs="?")
    p.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    p.add_argument("--model",    default=DEFAULT_MODEL)
    p.add_argument("--token",    default=DEFAULT_TOKEN)
    p.add_argument("--steps",    type=int, default=30)
    p.add_argument("--retries",  type=int, default=3)
    p.add_argument("--cwd",      default=None, help="工作目錄（預設當前目錄）")
    p.add_argument("--write",    metavar="REQ")
    p.add_argument("--out",      metavar="FILE")
    p.add_argument("--fix",      metavar="ERROR")
    p.add_argument("--file",     metavar="FILE")
    p.add_argument("--test",     metavar="CMD")
    a = p.parse_args()

    cwd = a.cwd or os.getcwd()
    cfg = dict(endpoint=a.endpoint, model=a.model, token=a.token, cwd=cwd)

    if a.write:
        mode_write(a.write, a.out or "output.py", **cfg)
    elif a.fix:
        if not a.file:
            print("❌ --fix 需要 --file")
            sys.exit(1)
        mode_fix(a.fix, a.file, **cfg, max_retries=a.retries)
    elif a.test:
        if not a.file:
            print("❌ --test 需要 --file")
            sys.exit(1)
        mode_test(a.test, a.file, **cfg, max_retries=a.retries)
    elif a.task:
        run_agent(a.task, **cfg, max_steps=a.steps)
    else:
        print("\033[36mCeLaw Coding Agent v2 (q 退出)\033[0m")
        while True:
            try:
                line = input("\n📝 > ").strip()
                if not line:
                    continue
                if line.lower() in ("q", "quit", "exit"):
                    break
                run_agent(line, **cfg, max_steps=a.steps)
            except KeyboardInterrupt:
                break
        print("\n👋 再見")

if __name__ == "__main__":
    main()
