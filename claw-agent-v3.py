#!/usr/bin/env python3
"""
CeLaw Coding Agent v3
模式：
  一般      python3 claw-agent-v3.py "任務描述"
  寫程式    python3 claw-agent-v3.py --write "需求" --out output.py
  修 bug    python3 claw-agent-v3.py --fix "錯誤訊息" --file buggy.py
  自動測試  python3 claw-agent-v3.py --test "pytest tests/" --file src/main.py
  多 agent  python3 claw-agent-v3.py --parallel "任務A" "任務B" "任務C"
  恢復      python3 claw-agent-v3.py --resume session_id

v3 新增（相較 v2）：
  - Streaming 即時輸出（不再等待）
  - Compact：tool result 超長自動壓縮，context 超限自動摘要
  - 卡死偵測：重複 tool call 自動跳出
  - Session 恢復：儲存/載入對話狀態
  - Symbol Map：ctags 建立函數索引，find_symbol tool
  - LSP 簡化版：Python ast + JS regex 解析
  - Multi-agent：並行子 agent，結果回傳主 agent
"""
import os, sys, json, subprocess, argparse, shutil, ast, re, threading, hashlib
from pathlib import Path
from datetime import datetime
from collections import deque

try:
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

DEFAULT_ENDPOINT = os.environ.get("CECLAW_ENDPOINT", "http://localhost:8000")
DEFAULT_MODEL    = os.environ.get("CECLAW_MODEL",    "ceclaw")
DEFAULT_TOKEN    = os.environ.get("CECLAW_TOKEN",    "97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759")

SESSION_DIR      = Path.home() / ".ceclaw" / "sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)

DANGEROUS_PATTERNS = ["rm -rf", "rm -f", "mkfs", "dd if=", "> /dev/", "chmod 777"]
MAX_TOOL_RESULT_LEN = 2000   # 超過就 micro-compact
MAX_CONTEXT_TOKENS  = 12000  # 估算超過就觸發 compact（L1 context 16384 留 4k buffer）
COMPACT_CLEARED     = "[舊工具輸出已壓縮]"

SESSION_LOG = []

def log_session(action, detail):
    SESSION_LOG.append({"time": datetime.now().strftime("%H:%M:%S"), "action": action, "detail": detail})

# ══════════════════════════════════════════════════════════════════════════════
# 1. Token 估算（粗估：1 token ≈ 4 chars）
# ══════════════════════════════════════════════════════════════════════════════
def estimate_tokens(messages):
    total = 0
    for m in messages:
        if isinstance(m.get("content"), str):
            total += len(m["content"]) // 4
        elif isinstance(m.get("content"), list):
            for b in m["content"]:
                if isinstance(b, dict) and b.get("text"):
                    total += len(b["text"]) // 4
    return total

# ══════════════════════════════════════════════════════════════════════════════
# 2. Micro-compact：壓縮太長的 tool result
# ══════════════════════════════════════════════════════════════════════════════
def micro_compact_messages(messages):
    """把舊的 tool result 截短，保留最近 6 輪完整"""
    result = []
    tool_msgs = [(i, m) for i, m in enumerate(messages) if m.get("role") == "tool"]
    recent_ids = {i for i, _ in tool_msgs[-6:]}  # 最近 6 個 tool result 保留完整

    for i, m in enumerate(messages):
        if m.get("role") == "tool" and i not in recent_ids:
            content = m.get("content", "")
            if len(content) > MAX_TOOL_RESULT_LEN:
                m = dict(m, content=content[:MAX_TOOL_RESULT_LEN] + f"\n{COMPACT_CLEARED}")
        result.append(m)
    return result

# ══════════════════════════════════════════════════════════════════════════════
# 3. Full compact：對話太長時，用 AI 摘要舊對話
# ══════════════════════════════════════════════════════════════════════════════
def full_compact(messages, endpoint, model, token):
    """把前半段對話摘要成一段文字，保留最近 10 條訊息"""
    if len(messages) <= 12:
        return messages

    system_msg = messages[0]
    old_msgs = messages[1:-10]
    recent_msgs = messages[-10:]

    # 把舊對話文字化
    old_text = []
    for m in old_msgs:
        role = m.get("role", "")
        content = m.get("content", "")
        if isinstance(content, str) and content:
            old_text.append(f"[{role}]: {content[:500]}")

    if not old_text:
        return messages

    # 呼叫 AI 摘要
    summary_prompt = f"請用繁體中文摘要以下對話的重點，包含：已完成的工作、修改了哪些檔案、目前狀態。200字以內。\n\n{''.join(old_text[:3000])}"
    try:
        resp = requests.post(
            f"{endpoint.rstrip('/')}/v1/chat/completions",
            json={"model": model, "messages": [
                {"role": "user", "content": summary_prompt}
            ], "max_tokens": 500, "temperature": 0},
            headers={"Authorization": f"Bearer {token}"},
            timeout=60
        )
        summary = resp.json()["choices"][0]["message"]["content"]
    except:
        summary = "（舊對話已壓縮）"

    print(f"  \033[90m🗜️  Compact：壓縮 {len(old_msgs)} 條舊訊息\033[0m")

    compacted = [
        system_msg,
        {"role": "user", "content": f"[對話摘要]\n{summary}"},
        {"role": "assistant", "content": "了解，繼續執行。"},
    ] + recent_msgs

    return compacted

# ══════════════════════════════════════════════════════════════════════════════
# 4. Session 儲存/恢復
# ══════════════════════════════════════════════════════════════════════════════
def save_session(session_id, messages, cwd, task):
    path = SESSION_DIR / f"{session_id}.json"
    data = {
        "id": session_id,
        "time": datetime.now().isoformat(),
        "cwd": str(cwd),
        "task": task,
        "messages": messages,
        "log": SESSION_LOG,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return path

def load_session(session_id):
    path = SESSION_DIR / f"{session_id}.json"
    if not path.exists():
        # 嘗試列出最近的 session
        sessions = sorted(SESSION_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if sessions and session_id == "last":
            path = sessions[0]
        else:
            print(f"❌ 找不到 session：{session_id}")
            print("可用的 sessions：")
            for s in sessions[:5]:
                data = json.loads(s.read_text())
                print(f"  {s.stem}  {data['time'][:16]}  {data['task'][:50]}")
            return None, None, None
    data = json.loads(path.read_text())
    print(f"  \033[36m📂 恢復 session：{data['id']} ({data['time'][:16]})\033[0m")
    print(f"     任務：{data['task'][:60]}")
    return data["messages"], data["cwd"], data["task"]

def list_sessions():
    sessions = sorted(SESSION_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not sessions:
        print("沒有儲存的 session")
        return
    print("\n儲存的 Sessions：")
    for s in sessions[:10]:
        try:
            data = json.loads(s.read_text())
            steps = len([m for m in data["messages"] if m.get("role") == "assistant"])
            print(f"  {s.stem}  {data['time'][:16]}  [{steps} steps]  {data['task'][:50]}")
        except:
            pass

# ══════════════════════════════════════════════════════════════════════════════
# 5. Symbol Map（ctags + Python AST + JS regex）
# ══════════════════════════════════════════════════════════════════════════════
SYMBOL_CACHE = {}

def build_symbol_map(cwd):
    cwd = Path(cwd)
    cache_key = str(cwd)
    if cache_key in SYMBOL_CACHE:
        return SYMBOL_CACHE[cache_key]

    symbols = {}  # name -> [{file, line, type}]

    # Python AST 解析
    for py_file in list(cwd.rglob("*.py"))[:100]:
        if any(p in str(py_file) for p in ["__pycache__", ".git", "node_modules"]):
            continue
        try:
            tree = ast.parse(py_file.read_text(errors="replace"))
            rel = str(py_file.relative_to(cwd))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.setdefault(node.name, []).append(
                        {"file": rel, "line": node.lineno, "type": "function"})
                elif isinstance(node, ast.ClassDef):
                    symbols.setdefault(node.name, []).append(
                        {"file": rel, "line": node.lineno, "type": "class"})
        except:
            pass

    # JS/TS regex 解析
    js_patterns = [
        (r'(?:function|async function)\s+(\w+)\s*\(', "function"),
        (r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(', "function"),
        (r'class\s+(\w+)', "class"),
        (r'(?:export\s+)?(?:default\s+)?(?:const|function)\s+(\w+)', "export"),
    ]
    for ext in ["*.js", "*.ts", "*.jsx", "*.tsx"]:
        for js_file in list(cwd.rglob(ext))[:100]:
            if any(p in str(js_file) for p in [".git", "node_modules", "dist", "build"]):
                continue
            try:
                content = js_file.read_text(errors="replace")
                rel = str(js_file.relative_to(cwd))
                for i, line in enumerate(content.splitlines(), 1):
                    for pattern, sym_type in js_patterns:
                        m = re.search(pattern, line)
                        if m and m.group(1):
                            name = m.group(1)
                            if len(name) > 2:  # 跳過太短的名稱
                                symbols.setdefault(name, []).append(
                                    {"file": rel, "line": i, "type": sym_type})
            except:
                pass

    SYMBOL_CACHE[cache_key] = symbols
    return symbols

def find_symbol(name, cwd):
    symbols = build_symbol_map(cwd)
    results = symbols.get(name, [])
    if not results:
        # 模糊搜尋
        fuzzy = [(k, v) for k, v in symbols.items() if name.lower() in k.lower()][:5]
        if fuzzy:
            lines = [f"找不到 '{name}'，相似的："]
            for k, v in fuzzy:
                lines.append(f"  {k}: {v[0]['file']}:{v[0]['line']} ({v[0]['type']})")
            return "\n".join(lines)
        return f"找不到符號：{name}"
    lines = [f"找到 {len(results)} 個定義："]
    for r in results[:10]:
        lines.append(f"  {r['file']}:{r['line']} ({r['type']})")
    return "\n".join(lines)

def find_references(name, cwd):
    """找所有呼叫某函數/類別的地方"""
    cwd = Path(cwd)
    results = []
    for ext in ["*.py", "*.js", "*.ts", "*.jsx", "*.tsx"]:
        for f in list(cwd.rglob(ext))[:200]:
            if any(p in str(f) for p in [".git", "node_modules", "dist"]):
                continue
            try:
                content = f.read_text(errors="replace")
                rel = str(f.relative_to(cwd))
                for i, line in enumerate(content.splitlines(), 1):
                    if name in line and f"def {name}" not in line and f"class {name}" not in line:
                        results.append(f"  {rel}:{i}: {line.strip()[:80]}")
            except:
                pass
    if not results:
        return f"找不到 '{name}' 的呼叫"
    return f"找到 {len(results)} 個呼叫：\n" + "\n".join(results[:20])

# ══════════════════════════════════════════════════════════════════════════════
# 6. CLAW.md + 專案掃描
# ══════════════════════════════════════════════════════════════════════════════
def load_claw_md(cwd=None):
    cwd = Path(cwd or os.getcwd())
    for path in [cwd / "CLAW.md", cwd.parent / "CLAW.md", Path.home() / "CLAW.md"]:
        if path.exists():
            content = path.read_text(errors="replace")
            print(f"  \033[36m📋 CLAW.md 載入：{path}\033[0m")
            return f"\n\n## 專案背景（來自 CLAW.md）\n{content}"
    return ""

def scan_project(cwd=None):
    cwd = Path(cwd or os.getcwd())
    lines = [f"\n## 當前工作目錄：{cwd}"]

    r = subprocess.run("git status --short 2>/dev/null", shell=True, capture_output=True, text=True, cwd=cwd)
    if r.returncode == 0 and r.stdout.strip():
        lines.append(f"\n## Git Status\n```\n{r.stdout.strip()}\n```")
        r2 = subprocess.run("git log --oneline -5 2>/dev/null", shell=True, capture_output=True, text=True, cwd=cwd)
        if r2.stdout.strip():
            lines.append(f"\n## 最近 Commits\n```\n{r2.stdout.strip()}\n```")

    for readme in ["README.md", "README.txt"]:
        p = cwd / readme
        if p.exists():
            lines.append(f"\n## README（前 800 字）\n{p.read_text(errors='replace')[:800]}")
            break

    items = []
    for item in sorted(cwd.iterdir())[:30]:
        if item.name.startswith(".") or item.name in ["__pycache__", "node_modules", ".git"]:
            continue
        items.append(("📁 " if item.is_dir() else "📄 ") + item.name)
    if items:
        lines.append(f"\n## 專案結構\n" + "\n".join(items))

    return "\n".join(lines)

# ══════════════════════════════════════════════════════════════════════════════
# 7. System Prompt
# ══════════════════════════════════════════════════════════════════════════════
BASE_SYSTEM_PROMPT = """You are CeLaw, a coding assistant by ColdElectric. You help with software engineering tasks: writing code, debugging, refactoring, explaining code, and managing projects.

## Core principles
- Always read files before editing them
- Use file_edit (str_replace) for small changes — NEVER rewrite entire files
- Use grep/find_symbol to search before assuming file contents
- Write clean, production-quality code matching the project's style
- Be concise — lead with action, not preamble
- Run tests after making changes
- Never introduce security vulnerabilities
- Don't add features beyond what was asked

## Available tools
- bash: run shell commands
- read_file: read file (with line numbers)
- write_file: write entire file (large changes only)
- file_edit: str_replace for small edits (preferred)
- grep: search content by regex
- find: find files by name
- find_symbol: find function/class definition (Python & JS/TS)
- find_refs: find all call sites of a function
- git: git operations
- list_dir: list directory
- subagent: spawn a sub-agent for a subtask

## Rules
- Always respond in Traditional Chinese (繁體中文)
- Taiwan terminology: 程式碼 (not 代碼)
- Never fabricate file contents
- Complete the task then say DONE"""

# ══════════════════════════════════════════════════════════════════════════════
# 8. Tool 定義
# ══════════════════════════════════════════════════════════════════════════════
TOOLS = [
    {"type":"function","function":{"name":"bash","description":"執行 bash 指令","parameters":{"type":"object","properties":{"command":{"type":"string"},"timeout":{"type":"integer","default":60}},"required":["command"]}}},
    {"type":"function","function":{"name":"read_file","description":"讀取檔案（帶行號）","parameters":{"type":"object","properties":{"path":{"type":"string"},"start_line":{"type":"integer"},"end_line":{"type":"integer"}},"required":["path"]}}},
    {"type":"function","function":{"name":"write_file","description":"寫入整個檔案（大改動）","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}},
    {"type":"function","function":{"name":"file_edit","description":"str_replace 只改特定部分（優先用）","parameters":{"type":"object","properties":{"path":{"type":"string"},"old_str":{"type":"string"},"new_str":{"type":"string"}},"required":["path","old_str","new_str"]}}},
    {"type":"function","function":{"name":"grep","description":"regex 搜尋檔案內容","parameters":{"type":"object","properties":{"pattern":{"type":"string"},"path":{"type":"string"},"glob":{"type":"string"},"case_insensitive":{"type":"boolean"}},"required":["pattern"]}}},
    {"type":"function","function":{"name":"find","description":"用檔名找檔案","parameters":{"type":"object","properties":{"name":{"type":"string"},"path":{"type":"string"},"type":{"type":"string","enum":["f","d",""]}},"required":["name"]}}},
    {"type":"function","function":{"name":"find_symbol","description":"找函數/類別定義位置（Python & JS/TS）","parameters":{"type":"object","properties":{"name":{"type":"string","description":"函數或類別名稱"}},"required":["name"]}}},
    {"type":"function","function":{"name":"find_refs","description":"找所有呼叫某函數的地方","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
    {"type":"function","function":{"name":"git","description":"git 操作","parameters":{"type":"object","properties":{"command":{"type":"string","enum":["status","diff","log","blame","show","branch"]},"args":{"type":"string"}},"required":["command"]}}},
    {"type":"function","function":{"name":"list_dir","description":"列出目錄","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":[]}}},
    {"type":"function","function":{"name":"subagent","description":"派出子 agent 執行子任務，回傳結果","parameters":{"type":"object","properties":{"task":{"type":"string","description":"子任務描述"},"context":{"type":"string","description":"需要的背景資訊"}},"required":["task"]}}},
]

# ══════════════════════════════════════════════════════════════════════════════
# 9. Tool 執行
# ══════════════════════════════════════════════════════════════════════════════
def is_dangerous(cmd):
    return any(p in cmd for p in DANGEROUS_PATTERNS)

def confirm_dangerous(cmd):
    print(f"\n\033[31m⚠️  危險操作：{cmd[:100]}\033[0m")
    return input("確認？(y/N) ").strip().lower() == "y"

def execute_tool(name, args, cwd=None, endpoint=None, model=None, token=None):
    cwd = str(cwd or os.getcwd())
    try:
        if name == "bash":
            cmd = args["command"]
            if is_dangerous(cmd) and not confirm_dangerous(cmd):
                return "使用者取消"
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                             timeout=args.get("timeout", 60), cwd=cwd)
            out = r.stdout + r.stderr
            if len(out) > MAX_TOOL_RESULT_LEN:
                out = out[:MAX_TOOL_RESULT_LEN] + f"\n{COMPACT_CLEARED}"
            return out or "(無輸出)"

        elif name == "read_file":
            p = Path(args["path"]).expanduser()
            if not p.exists():
                return f"找不到：{p}"
            lines = p.read_text(errors="replace").splitlines()
            s = args.get("start_line", 1) - 1
            e = args.get("end_line", len(lines))
            result = "\n".join(f"{s+i+1:4d}\t{l}" for i, l in enumerate(lines[s:e]))
            return result[:8000] + ("\n...[截斷]" if len(result) > 8000 else "")

        elif name == "write_file":
            p = Path(args["path"]).expanduser()
            if p.exists() and p.stat().st_size > 10000:
                print(f"\n\033[33m⚠️  覆寫大檔案：{p}\033[0m")
                if input("確認？(y/N) ").strip().lower() != "y":
                    return "取消"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(args["content"])
            log_session("write_file", str(p))
            return f"已寫入 {p}"

        elif name == "file_edit":
            p = Path(args["path"]).expanduser()
            if not p.exists():
                return f"找不到：{p}"
            content = p.read_text(errors="replace")
            old_str, new_str = args["old_str"], args["new_str"]
            if old_str not in content:
                return f"找不到要替換的字串，請用 read_file 確認後再試"
            count = content.count(old_str)
            if count > 1:
                return f"找到 {count} 個匹配，需要唯一匹配"
            p.write_text(content.replace(old_str, new_str, 1))
            log_session("file_edit", str(p))
            return f"已修改 {p}"

        elif name == "grep":
            pattern = args["pattern"]
            path = args.get("path", cwd)
            glob = args.get("glob", "")
            ci = args.get("case_insensitive", False)
            if shutil.which("rg"):
                cmd = f"rg {'--ignore-case ' if ci else ''}{f'--glob {repr(glob)} ' if glob else ''}-n --max-count=50 {repr(pattern)} {repr(str(path))}"
            else:
                cmd = f"grep -rn {'--ignore-case ' if ci else ''}{f'--include={repr(glob)} ' if glob else ''}{repr(pattern)} {repr(str(path))} | head -50"
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return (r.stdout or "(無匹配)")[:3000]

        elif name == "find":
            fname = args["name"]
            fpath = args.get("path", cwd)
            ftype = args.get("type", "")
            cmd = f"find {repr(str(fpath))} {f'-type {ftype}' if ftype else ''} -name {repr(fname)} 2>/dev/null | head -50"
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return r.stdout or "(無匹配)"

        elif name == "find_symbol":
            return find_symbol(args["name"], cwd)

        elif name == "find_refs":
            return find_references(args["name"], cwd)

        elif name == "git":
            cmd_map = {
                "status": "git status",
                "diff": f"git diff {args.get('args', '')}",
                "log": f"git log --oneline -20 {args.get('args', '')}",
                "blame": f"git blame {args.get('args', '')}",
                "show": f"git show {args.get('args', '')}",
                "branch": "git branch -a",
            }
            r = subprocess.run(cmd_map[args["command"]], shell=True, capture_output=True, text=True, timeout=30, cwd=cwd)
            out = r.stdout + r.stderr
            return out[:3000] + ("\n...[截斷]" if len(out) > 3000 else "")

        elif name == "list_dir":
            p = Path(args.get("path", cwd)).expanduser()
            if not p.exists():
                return f"找不到：{p}"
            items = []
            for item in sorted(p.iterdir())[:60]:
                if item.name.startswith("."): continue
                size = f" ({item.stat().st_size:,}B)" if item.is_file() else ""
                items.append(("📁 " if item.is_dir() else "📄 ") + item.name + size)
            return "\n".join(items) or "(空)"

        elif name == "subagent":
            if endpoint and model and token:
                task = args["task"]
                ctx = args.get("context", "")
                full_task = f"{task}\n\n背景：{ctx}" if ctx else task
                print(f"  \033[35m🤖 子 agent：{task[:60]}\033[0m")
                result = run_agent(full_task, endpoint, model, token,
                                  max_steps=10, mode="subagent", cwd=cwd,
                                  silent=True)
                return result if isinstance(result, str) else "子任務完成"
            return "子 agent 未設定 endpoint"

        return f"未知工具：{name}"
    except subprocess.TimeoutExpired:
        return "逾時"
    except Exception as e:
        return f"錯誤：{e}"

# ══════════════════════════════════════════════════════════════════════════════
# 10. Streaming API 呼叫
# ══════════════════════════════════════════════════════════════════════════════
def call_ceclaw_stream(messages, endpoint, model, token):
    """Streaming 模式，即時印出 token，回傳完整 message"""
    resp = requests.post(
        f"{endpoint.rstrip('/')}/v1/chat/completions",
        json={"model": model, "messages": messages, "tools": TOOLS,
              "tool_choice": "auto", "temperature": 0, "max_tokens": 4096,
              "stream": True},
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        stream=True, timeout=180
    )
    resp.raise_for_status()

    content_parts = []
    tool_calls_raw = {}
    finish_reason = None

    print("  \033[32m", end="", flush=True)
    for line in resp.iter_lines():
        if not line:
            continue
        if line.startswith(b"data: "):
            data = line[6:]
            if data == b"[DONE]":
                break
            try:
                chunk = json.loads(data)
                delta = chunk["choices"][0].get("delta", {})
                finish_reason = chunk["choices"][0].get("finish_reason") or finish_reason

                # 文字 token
                if delta.get("content"):
                    content_parts.append(delta["content"])
                    print(delta["content"], end="", flush=True)

                # tool call chunks
                for tc in delta.get("tool_calls", []):
                    idx = tc.get("index", 0)
                    if idx not in tool_calls_raw:
                        tool_calls_raw[idx] = {"id": "", "type": "function",
                                               "function": {"name": "", "arguments": ""}}
                    if tc.get("id"):
                        tool_calls_raw[idx]["id"] = tc["id"]
                    if tc.get("function", {}).get("name"):
                        tool_calls_raw[idx]["function"]["name"] += tc["function"]["name"]
                    if tc.get("function", {}).get("arguments"):
                        tool_calls_raw[idx]["function"]["arguments"] += tc["function"]["arguments"]
            except:
                pass

    print("\033[0m", flush=True)

    # 組合完整 message
    msg = {"role": "assistant", "content": "".join(content_parts) or None}
    if tool_calls_raw:
        msg["tool_calls"] = [tool_calls_raw[i] for i in sorted(tool_calls_raw)]
        msg["content"] = msg["content"] or ""

    return {"choices": [{"message": msg, "finish_reason": finish_reason}]}

# ══════════════════════════════════════════════════════════════════════════════
# 11. 卡死偵測
# ══════════════════════════════════════════════════════════════════════════════
def make_call_fingerprint(tool_calls):
    """產生 tool call 的指紋，用於偵測重複"""
    if not tool_calls:
        return None
    parts = []
    for tc in tool_calls:
        fn = tc.get("function", {})
        parts.append(f"{fn.get('name')}:{fn.get('arguments', '')[:100]}")
    return hashlib.md5("|".join(parts).encode()).hexdigest()

# ══════════════════════════════════════════════════════════════════════════════
# 12. Agent loop
# ══════════════════════════════════════════════════════════════════════════════
def run_agent(task, endpoint, model, token, max_steps=30, mode="general",
              cwd=None, session_id=None, silent=False):
    cwd = cwd or os.getcwd()

    if not silent:
        print(f"\n\033[36m🤖 CeLaw Agent v3 [{mode}]\033[0m")
        print(f"   Task  : {task[:80]}{'...' if len(task) > 80 else ''}")
        print(f"   CWD   : {cwd}")
        print("─" * 60)

    # 建立 symbol map（背景）
    threading.Thread(target=build_symbol_map, args=(cwd,), daemon=True).start()

    # Session ID
    if not session_id:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + mode

    # 組合 system prompt
    project_ctx = load_claw_md(cwd) + scan_project(cwd)
    system = BASE_SYSTEM_PROMPT + project_ctx

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": task}
    ]

    recent_fingerprints = deque(maxlen=3)
    last_result_text = ""

    for step in range(max_steps):
        if not silent:
            print(f"\n\033[90m[Step {step+1}/{max_steps}]\033[0m")

        # Compact 檢查
        tokens = estimate_tokens(messages)
        if tokens > MAX_CONTEXT_TOKENS:
            if not silent:
                print(f"  \033[33m⚡ Context {tokens} tokens，觸發 compact\033[0m")
            messages = micro_compact_messages(messages)
            if estimate_tokens(messages) > MAX_CONTEXT_TOKENS:
                messages = full_compact(messages, endpoint, model, token)

        try:
            resp = call_ceclaw_stream(messages, endpoint, model, token)
        except requests.exceptions.ConnectionError:
            if not silent:
                print(f"\033[31m❌ 無法連線到 {endpoint}\033[0m")
            return False
        except Exception as e:
            if not silent:
                print(f"\033[31m❌ API 錯誤：{e}\033[0m")
            return False

        choice = resp["choices"][0]
        msg = choice["message"]
        messages.append(msg)

        content = msg.get("content") or ""
        if content and not silent:
            if "DONE" in content:
                print(f"\n\033[36m✅ 完成\033[0m")
                _print_session_log()
                save_session(session_id, messages, cwd, task)
                return last_result_text or True

        tool_calls = msg.get("tool_calls", [])

        if not tool_calls:
            if choice.get("finish_reason") == "stop":
                if not silent:
                    print(f"\n\033[36m✅ 完成\033[0m")
                    _print_session_log()
                save_session(session_id, messages, cwd, task)
                return content or True
            continue

        # 卡死偵測
        fp = make_call_fingerprint(tool_calls)
        if fp and fp in recent_fingerprints:
            if not silent:
                print(f"\n\033[33m⚠️  偵測到重複 tool call，跳出迴圈\033[0m")
            save_session(session_id, messages, cwd, task)
            return False
        if fp:
            recent_fingerprints.append(fp)

        results = []
        for tc in tool_calls:
            fn = tc["function"]["name"]
            try:
                fa = json.loads(tc["function"]["arguments"])
            except:
                fa = {}
            if not silent:
                print(f"  🔧 {fn}({', '.join(f'{k}={repr(v)[:40]}' for k, v in fa.items())})")
            r = execute_tool(fn, fa, cwd=cwd, endpoint=endpoint, model=model, token=token)
            if not silent:
                print(f"  \033[90m→ {r[:150]}{'...' if len(r) > 150 else ''}\033[0m")
            last_result_text = r
            results.append({"role": "tool", "tool_call_id": tc["id"], "content": r})
        messages.extend(results)

    if not silent:
        print(f"\n\033[33m⚠️  達到最大步數 {max_steps}\033[0m")
        _print_session_log()
    save_session(session_id, messages, cwd, task)
    return False

def _print_session_log():
    if not SESSION_LOG:
        return
    print(f"\n\033[90m── Session Log ──")
    for e in SESSION_LOG:
        print(f"  {e['time']} [{e['action']}] {e['detail']}")
    print(f"────────────────\033[0m")

# ══════════════════════════════════════════════════════════════════════════════
# 13. Multi-agent 並行
# ══════════════════════════════════════════════════════════════════════════════
def run_parallel_agents(tasks, endpoint, model, token, cwd=None):
    """並行跑多個子 agent，收集結果"""
    print(f"\n\033[36m🤖 Multi-agent：{len(tasks)} 個子任務並行\033[0m")
    results = [None] * len(tasks)

    def run_one(i, task):
        print(f"  \033[35m[agent-{i+1}] 開始：{task[:50]}\033[0m")
        r = run_agent(task, endpoint, model, token,
                     max_steps=10, mode=f"parallel-{i+1}", cwd=cwd, silent=True)
        results[i] = r
        print(f"  \033[32m[agent-{i+1}] 完成\033[0m")

    threads = [threading.Thread(target=run_one, args=(i, t)) for i, t in enumerate(tasks)]
    for t in threads: t.start()
    for t in threads: t.join()

    print(f"\n\033[36m── 並行結果 ──\033[0m")
    for i, (task, result) in enumerate(zip(tasks, results)):
        print(f"\n[{i+1}] {task[:50]}")
        print(f"  {str(result)[:200]}")
    return results

# ══════════════════════════════════════════════════════════════════════════════
# 14. 模式函數
# ══════════════════════════════════════════════════════════════════════════════
def mode_write(requirement, outfile, endpoint, model, token, cwd=None):
    task = f"請根據以下需求寫程式，儲存到 {outfile}：\n\n{requirement}\n\n步驟：\n1. 寫完整可執行程式（加繁體中文註解）\n2. 儲存到 {outfile}\n3. 執行確認無語法錯誤\n4. DONE"
    run_agent(task, endpoint, model, token, max_steps=15, mode="write", cwd=cwd)

def mode_fix(error_msg, filepath, endpoint, model, token, max_retries=3, cwd=None):
    print(f"\n\033[35m🔧 Auto Fix 模式\033[0m  檔案：{filepath}")
    for attempt in range(1, max_retries + 1):
        print(f"\n\033[90m── Fix {attempt}/{max_retries} ──\033[0m")
        task = (f"修復 {filepath} 的 bug：\n\n錯誤：{error_msg}\n\n"
                f"步驟：1.read_file 讀取 2.find_symbol 找定義 3.用 file_edit 修復（不要整個覆寫）4.執行驗證 5.DONE")
        run_agent(task, endpoint, model, token, max_steps=15, mode=f"fix-{attempt}", cwd=cwd)

        p = Path(filepath).expanduser()
        cmd = f"python3 {p}" if p.suffix == ".py" else f"bash {p}"
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            print(f"\033[32m✅ 修復成功！（{attempt} 次）\033[0m")
            return True
        error_msg = r.stdout + r.stderr
        print(f"\033[31m❌ 仍有錯誤\033[0m")
    print(f"\033[31m❌ 修復失敗\033[0m")
    return False

def mode_test(test_cmd, filepath, endpoint, model, token, max_retries=5, cwd=None):
    print(f"\n\033[35m🧪 Auto Test 模式\033[0m  測試：{test_cmd}")
    for attempt in range(1, max_retries + 1):
        r = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=120, cwd=cwd)
        if r.returncode == 0:
            print(f"\033[32m✅ 測試全過！（{attempt} 次）\033[0m")
            return True
        output = r.stdout + r.stderr
        print(f"\033[31m❌ 失敗\033[0m\n{output[:200]}")
        if attempt >= max_retries: break
        task = f"測試失敗，用 file_edit 修復 {filepath}：\n\n測試：{test_cmd}\n失敗：{output[:1500]}\n\nDONE"
        run_agent(task, endpoint, model, token, max_steps=15, mode=f"test-{attempt}", cwd=cwd)
    print(f"\033[31m❌ 達到最大重試\033[0m")
    return False

# ══════════════════════════════════════════════════════════════════════════════
# 15. 主程式
# ══════════════════════════════════════════════════════════════════════════════
def main():
    p = argparse.ArgumentParser(description="CeLaw Coding Agent v3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""範例：
  python3 claw-agent-v3.py "找出所有 TODO"
  python3 claw-agent-v3.py --write "寫 fibonacci" --out fib.py
  python3 claw-agent-v3.py --fix "NameError" --file script.py
  python3 claw-agent-v3.py --test "pytest tests/" --file src/main.py
  python3 claw-agent-v3.py --parallel "審查 auth.py" "審查 api.py" "審查 db.py"
  python3 claw-agent-v3.py --resume last
  python3 claw-agent-v3.py --sessions""")
    p.add_argument("task",       nargs="?")
    p.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    p.add_argument("--model",    default=DEFAULT_MODEL)
    p.add_argument("--token",    default=DEFAULT_TOKEN)
    p.add_argument("--steps",    type=int, default=30)
    p.add_argument("--retries",  type=int, default=3)
    p.add_argument("--cwd",      default=None)
    p.add_argument("--write",    metavar="REQ")
    p.add_argument("--out",      metavar="FILE")
    p.add_argument("--fix",      metavar="ERROR")
    p.add_argument("--file",     metavar="FILE")
    p.add_argument("--test",     metavar="CMD")
    p.add_argument("--parallel", nargs="+", metavar="TASK")
    p.add_argument("--resume",   metavar="SESSION_ID")
    p.add_argument("--sessions", action="store_true")
    a = p.parse_args()

    cwd = a.cwd or os.getcwd()
    cfg = dict(endpoint=a.endpoint, model=a.model, token=a.token, cwd=cwd)

    if a.sessions:
        list_sessions()
    elif a.resume:
        messages, saved_cwd, task = load_session(a.resume)
        if messages:
            cwd = saved_cwd or cwd
            resume_task = input(f"繼續任務「{task[:40]}」還是輸入新指令？(Enter 繼續) ").strip()
            if resume_task:
                task = resume_task
            run_agent(task, a.endpoint, a.model, a.token,
                     max_steps=a.steps, cwd=cwd, session_id=a.resume + "_resumed")
    elif a.parallel:
        run_parallel_agents(a.parallel, **cfg)
    elif a.write:
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
        print("\033[36mCeLaw Coding Agent v3 (q 退出, sessions 列出歷史)\033[0m")
        while True:
            try:
                line = input("\n📝 > ").strip()
                if not line: continue
                if line.lower() in ("q", "quit"): break
                if line == "sessions": list_sessions(); continue
                run_agent(line, **cfg, max_steps=a.steps)
            except KeyboardInterrupt:
                break
        print("\n👋 再見")

if __name__ == "__main__":
    main()
