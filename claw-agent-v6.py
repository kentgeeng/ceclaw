#!/usr/bin/env python3
from __future__ import annotations
"""
CeLaw Coding Agent v6
模式：
  一般      python3 claw-agent-v6.py "任務描述"
  寫程式    python3 claw-agent-v6.py --write "需求" --out output.py
  修 bug    python3 claw-agent-v6.py --fix "錯誤訊息" --file buggy.py
  自動測試  python3 claw-agent-v6.py --test "pytest tests/" --file src/main.py
  多 agent  python3 claw-agent-v6.py --parallel "任務A" "任務B" "任務C"
  恢復      python3 claw-agent-v6.py --resume session_id

v4 新增（相較 v3）：
  - OpenClawAgent 基類（execute/cancel/get_status 標準介面）
  - WebSocket server :8003，即時推送事件
  - /ws/{session_id}：每個 session 獨立頻道
  - /ws/latest：debug 用，看最新 session
  - --session-id 參數對應 WS 頻道，多人不串台
  - emit()：step_start / tool_call / tool_result / done / error / cancelled
"""
import os, sys, json, subprocess, argparse, shutil, ast, re, threading, hashlib, asyncio
from pathlib import Path
from datetime import datetime
from collections import deque

try:
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

try:
    from websockets.asyncio.server import serve as ws_serve
except ImportError:
    try:
        from websockets.server import serve as ws_serve
    except ImportError:
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "websockets", "-q"])
            try:
                from websockets.asyncio.server import serve as ws_serve
            except ImportError:
                from websockets.server import serve as ws_serve
        except ImportError:
            ws_serve = None
            print("⚠️ websockets 未安裝，WebSocket 功能將停用")

import socket

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

DEFAULT_ENDPOINT = os.environ.get("CECLAW_ENDPOINT", "http://localhost:8000")
DEFAULT_MODEL    = os.environ.get("CECLAW_MODEL",    "ceclaw")
DEFAULT_TOKEN    = os.environ.get("CECLAW_TOKEN",    "97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759")
WS_HOST          = "0.0.0.0"
WS_PORT          = 8003
WS_LAN_IP        = os.environ.get("CECLAW_WS_IP", get_lan_ip())

SESSION_DIR      = Path.home() / ".ceclaw" / "sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)

DANGEROUS_PATTERNS  = ["rm -rf", "rm -f", "mkfs", "dd if=", "> /dev/", "chmod 777"]
MAX_TOOL_RESULT_LEN = 2000
MAX_CONTEXT_TOKENS  = 12000
COMPACT_CLEARED     = "[舊工具輸出已壓縮]"
SESSION_LOG         = []

def log_session(action, detail):
    SESSION_LOG.append({"time": datetime.now().strftime("%H:%M:%S"), "action": action, "detail": detail})

# ══════════════════════════════════════════════════════════════════════════════
# 1. WS Broker（多 session 獨立頻道）
# ══════════════════════════════════════════════════════════════════════════════
class WSBroker:
    def __init__(self):
        self.clients: dict[str, set] = {}   # session_id → set of websockets
        self.latest_sid: str | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def publish(self, session_id: str, msg: dict):
        """推送事件到對應 session 頻道 + /ws/latest 訂閱者"""
        self.latest_sid = session_id
        if not self._loop:
            return
        # /ws/latest 收到所有 session 的事件（debug 用）
        with self._lock:
            targets = (
                self.clients.get(session_id, set()) |
                self.clients.get("latest", set())
            )
        payload = json.dumps(msg, ensure_ascii=False)
        for ws in list(targets):
            asyncio.run_coroutine_threadsafe(
                ws.send(payload), self._loop
            )

ws_broker = WSBroker()

async def _ws_handler(websocket):
    """WebSocket 連線處理：/ws/{session_id} 或 /ws/latest"""
    path = websocket.request.path          # websockets 15.x API
    sid = path.split("/ws/")[-1].strip("/") or "latest"
    ws_broker.clients.setdefault(sid, set()).add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        ws_broker.clients.get(sid, set()).discard(websocket)

async def _ws_server_main():
    loop = asyncio.get_running_loop()
    ws_broker.set_loop(loop)
    async with ws_serve(_ws_handler, WS_HOST, WS_PORT):
        print(f"  \033[36m🔌 WS: ws://{WS_LAN_IP}:{WS_PORT}/ws/{{session_id}}\033[0m")
        print(f"  \033[90m   debug: ws://{WS_LAN_IP}:{WS_PORT}/ws/latest\033[0m")
        await asyncio.Future()

def start_ws_thread():
    """在背景 thread 啟動 WS server"""
    if ws_serve is None:
        print("  [33m⚠️ WebSocket 功能停用（websockets 套件未安裝）[0m")
        return
    def _run():
        asyncio.run(_ws_server_main())
    t = threading.Thread(target=_run, daemon=True)
    t.start()

# ══════════════════════════════════════════════════════════════════════════════
# 2. OpenClawAgent 基類
# ══════════════════════════════════════════════════════════════════════════════
class OpenClawAgent:
    """openclaw agent 標準介面"""

    def __init__(self, session_id: str, endpoint: str, model: str, token: str):
        self.session_id  = session_id
        self.endpoint    = endpoint
        self.model       = model
        self.token       = token
        self._cancelled  = False

    def cancel(self):
        """取消正在執行的任務"""
        self._cancelled = True

    def close_ws(self):
        """優雅關閉：推送 closed 事件讓 client 知道可以斷線"""
        ws_broker.publish(self.session_id, {"event": "closed", "ts": datetime.now().isoformat()})

    def get_status(self) -> dict:
        return {"session_id": self.session_id, "cancelled": self._cancelled}

    def emit(self, event: str, data: dict):
        """推送事件到 WS broker"""
        ws_broker.publish(self.session_id, {"event": event, "ts": datetime.now().isoformat(), **data})

# ══════════════════════════════════════════════════════════════════════════════
# 3. Token 估算
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
# 4. Micro-compact
# ══════════════════════════════════════════════════════════════════════════════
def micro_compact_messages(messages):
    result = []
    tool_msgs = [(i, m) for i, m in enumerate(messages) if m.get("role") == "tool"]
    recent_ids = {i for i, _ in tool_msgs[-6:]}
    for i, m in enumerate(messages):
        if m.get("role") == "tool" and i not in recent_ids:
            content = m.get("content", "")
            if len(content) > MAX_TOOL_RESULT_LEN:
                m = dict(m, content=content[:MAX_TOOL_RESULT_LEN] + f"\n{COMPACT_CLEARED}")
        result.append(m)
    return result

# ══════════════════════════════════════════════════════════════════════════════
# 5. Full compact
# ══════════════════════════════════════════════════════════════════════════════
def full_compact(messages, endpoint, model, token):
    if len(messages) <= 12:
        return messages
    system_msg   = messages[0]
    old_msgs     = messages[1:-10]
    recent_msgs  = messages[-10:]
    old_text = []
    for m in old_msgs:
        role    = m.get("role", "")
        content = m.get("content", "")
        if isinstance(content, str) and content:
            old_text.append(f"[{role}]: {content[:500]}")
    if not old_text:
        return messages
    summary_prompt = (
        "請用繁體中文摘要以下對話的重點，包含：已完成的工作、修改了哪些檔案、目前狀態。200字以內。\n\n"
        + "".join(old_text)[:3000]
    )
    try:
        resp = requests.post(
            f"{endpoint.rstrip('/')}/v1/chat/completions",
            json={"model": model, "messages": [{"role": "user", "content": summary_prompt}],
                  "max_tokens": 500, "temperature": 0},
            headers={"Authorization": f"Bearer {token}"},
            timeout=60
        )
        summary = resp.json()["choices"][0]["message"]["content"]
    except Exception:
        summary = "（舊對話已壓縮）"
    print(f"  \033[90m🗜️  Compact：壓縮 {len(old_msgs)} 條舊訊息\033[0m")
    return [
        system_msg,
        {"role": "user",      "content": f"[對話摘要]\n{summary}"},
        {"role": "assistant", "content": "了解，繼續執行。"},
    ] + recent_msgs

# ══════════════════════════════════════════════════════════════════════════════
# 6. Session 儲存/恢復
# ══════════════════════════════════════════════════════════════════════════════
def save_session(session_id, messages, cwd, task):
    path = SESSION_DIR / f"{session_id}.json"
    path.write_text(json.dumps({
        "id": session_id, "time": datetime.now().isoformat(),
        "cwd": str(cwd), "task": task,
        "messages": messages, "log": SESSION_LOG,
    }, ensure_ascii=False, indent=2))
    return path

def load_session(session_id):
    path = SESSION_DIR / f"{session_id}.json"
    if not path.exists():
        sessions = sorted(SESSION_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if sessions and session_id == "last":
            path = sessions[0]
        else:
            print(f"❌ 找不到 session：{session_id}")
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
            data  = json.loads(s.read_text())
            steps = len([m for m in data["messages"] if m.get("role") == "assistant"])
            print(f"  {s.stem}  {data['time'][:16]}  [{steps} steps]  {data['task'][:50]}")
        except Exception:
            pass

# ══════════════════════════════════════════════════════════════════════════════
# 7. Symbol Map
# ══════════════════════════════════════════════════════════════════════════════
SYMBOL_CACHE = {}

def build_symbol_map(cwd):
    cwd      = Path(cwd)
    cache_key = str(cwd)
    if cache_key in SYMBOL_CACHE:
        return SYMBOL_CACHE[cache_key]
    symbols = {}
    for py_file in list(cwd.rglob("*.py"))[:100]:
        if any(p in str(py_file) for p in ["__pycache__", ".git", "node_modules"]):
            continue
        try:
            tree = ast.parse(py_file.read_text(errors="replace"))
            rel  = str(py_file.relative_to(cwd))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.setdefault(node.name, []).append(
                        {"file": rel, "line": node.lineno, "type": "function"})
                elif isinstance(node, ast.ClassDef):
                    symbols.setdefault(node.name, []).append(
                        {"file": rel, "line": node.lineno, "type": "class"})
        except Exception:
            pass
    js_patterns = [
        (r'(?:function|async function)\s+(\w+)\s*\(', "function"),
        (r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(', "function"),
        (r'class\s+(\w+)', "class"),
    ]
    for ext in ["*.js", "*.ts", "*.jsx", "*.tsx"]:
        for js_file in list(cwd.rglob(ext))[:100]:
            if any(p in str(js_file) for p in [".git", "node_modules", "dist", "build"]):
                continue
            try:
                content = js_file.read_text(errors="replace")
                rel     = str(js_file.relative_to(cwd))
                for i, line in enumerate(content.splitlines(), 1):
                    for pattern, sym_type in js_patterns:
                        m = re.search(pattern, line)
                        if m and m.group(1) and len(m.group(1)) > 2:
                            symbols.setdefault(m.group(1), []).append(
                                {"file": rel, "line": i, "type": sym_type})
            except Exception as parse_err:
                pass  # chunk 不完整，跳過
    SYMBOL_CACHE[cache_key] = symbols
    return symbols

def find_symbol(name, cwd):
    symbols = build_symbol_map(cwd)
    results = symbols.get(name, [])
    if not results:
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
    cwd     = Path(cwd)
    results = []
    for ext in ["*.py", "*.js", "*.ts", "*.jsx", "*.tsx"]:
        for f in list(cwd.rglob(ext))[:200]:
            if any(p in str(f) for p in [".git", "node_modules", "dist"]):
                continue
            try:
                content = f.read_text(errors="replace")
                rel     = str(f.relative_to(cwd))
                for i, line in enumerate(content.splitlines(), 1):
                    if name in line and f"def {name}" not in line and f"class {name}" not in line:
                        results.append(f"  {rel}:{i}: {line.strip()[:80]}")
            except Exception:
                pass
    if not results:
        return f"找不到 '{name}' 的呼叫"
    return f"找到 {len(results)} 個呼叫：\n" + "\n".join(results[:20])

# ══════════════════════════════════════════════════════════════════════════════
# 8. CLAW.md + 專案掃描
# ══════════════════════════════════════════════════════════════════════════════
def load_claw_md(cwd=None, silent=False):
    cwd = Path(cwd or os.getcwd())
    for path in [cwd / "CLAW.md", cwd.parent / "CLAW.md", Path.home() / "CLAW.md"]:
        if path.exists():
            content = path.read_text(errors="replace")
            if not silent:
                print(f"  \033[36m📋 CLAW.md 載入：{path}\033[0m")
            return f"\n\n## 專案背景（來自 CLAW.md）\n{content}"
    return ""

def scan_project(cwd=None):
    cwd   = Path(cwd or os.getcwd())
    lines = [f"\n## 當前工作目錄：{cwd}"]
    r = subprocess.run("git status --short 2>/dev/null", shell=True,
                       capture_output=True, text=True, cwd=cwd)
    if r.returncode == 0 and r.stdout.strip():
        lines.append(f"\n## Git Status\n```\n{r.stdout.strip()}\n```")
        r2 = subprocess.run("git log --oneline -5 2>/dev/null", shell=True,
                            capture_output=True, text=True, cwd=cwd)
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
# 9. System Prompt
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
# 10. Tool 定義
# ══════════════════════════════════════════════════════════════════════════════
TOOLS = [
    {"type":"function","function":{"name":"bash","description":"執行 bash 指令","parameters":{"type":"object","properties":{"command":{"type":"string"},"timeout":{"type":"integer","default":60}},"required":["command"]}}},
    {"type":"function","function":{"name":"read_file","description":"讀取檔案（帶行號）","parameters":{"type":"object","properties":{"path":{"type":"string"},"start_line":{"type":"integer"},"end_line":{"type":"integer"}},"required":["path"]}}},
    {"type":"function","function":{"name":"write_file","description":"寫入整個檔案（大改動）","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}},
    {"type":"function","function":{"name":"file_edit","description":"str_replace 只改特定部分（優先用）","parameters":{"type":"object","properties":{"path":{"type":"string"},"old_str":{"type":"string"},"new_str":{"type":"string"}},"required":["path","old_str","new_str"]}}},
    {"type":"function","function":{"name":"grep","description":"regex 搜尋檔案內容","parameters":{"type":"object","properties":{"pattern":{"type":"string"},"path":{"type":"string"},"glob":{"type":"string"},"case_insensitive":{"type":"boolean"}},"required":["pattern"]}}},
    {"type":"function","function":{"name":"find","description":"用檔名找檔案","parameters":{"type":"object","properties":{"name":{"type":"string"},"path":{"type":"string"},"type":{"type":"string","enum":["f","d",""]}},"required":["name"]}}},
    {"type":"function","function":{"name":"find_symbol","description":"找函數/類別定義位置（Python & JS/TS）","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
    {"type":"function","function":{"name":"find_refs","description":"找所有呼叫某函數的地方","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
    {"type":"function","function":{"name":"git","description":"git 操作","parameters":{"type":"object","properties":{"command":{"type":"string","enum":["status","diff","log","blame","show","branch"]},"args":{"type":"string"}},"required":["command"]}}},
    {"type":"function","function":{"name":"list_dir","description":"列出目錄","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":[]}}},
    {"type":"function","function":{"name":"subagent","description":"派出子 agent 執行子任務，回傳結果","parameters":{"type":"object","properties":{"task":{"type":"string"},"context":{"type":"string"}},"required":["task"]}}},
]

# ══════════════════════════════════════════════════════════════════════════════
# 11. Tool 執行
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
            timeout = args.get("timeout", 60)
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                               timeout=timeout, cwd=cwd)
            out = r.stdout + r.stderr
            if len(out) > MAX_TOOL_RESULT_LEN:
                out = out[:MAX_TOOL_RESULT_LEN] + f"\n{COMPACT_CLEARED}"
            result = out or "(無輸出)"
            if r.returncode != 0:
                result += f"\n[Exit Code: {r.returncode}]"
            return result

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
            content  = p.read_text(errors="replace")
            old_str  = args["old_str"]
            new_str  = args["new_str"]
            if old_str not in content:
                return "找不到要替換的字串，請用 read_file 確認後再試"
            count = content.count(old_str)
            if count > 1:
                return f"找到 {count} 個匹配，需要唯一匹配"
            p.write_text(content.replace(old_str, new_str, 1))
            log_session("file_edit", str(p))
            return f"已修改 {p}"

        elif name == "grep":
            pattern = args["pattern"]
            path    = args.get("path", cwd)
            glob    = args.get("glob", "")
            ci      = args.get("case_insensitive", False)
            if shutil.which("rg"):
                cmd = f"rg {'--ignore-case ' if ci else ''}{f'--glob {repr(glob)} ' if glob else ''}-n --max-count=50 {repr(pattern)} {repr(str(path))}"
            else:
                cmd = f"grep -rn {'--ignore-case ' if ci else ''}{f'--include={repr(glob)} ' if glob else ''}{repr(pattern)} {repr(str(path))} | head -50"
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            result = (r.stdout or "(無匹配)")[:3000]
            if r.returncode != 0 and r.stderr:
                result += f"\n[Stderr: {r.stderr.strip()[:300]}]"
            return result

        elif name == "find":
            fname = args["name"]
            fpath = str(Path(args.get("path", cwd)).expanduser())
            ftype = args.get("type", "")
            cmd   = f"find {repr(fpath)} {f'-type {ftype}' if ftype else ''} -name {repr(fname)}"
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            result = r.stdout.strip() or "(無匹配)"
            if r.returncode != 0 and r.stderr:
                result = f"錯誤：{r.stderr.strip()[:300]}"
            return result

        elif name == "find_symbol":
            return find_symbol(args["name"], cwd)

        elif name == "find_refs":
            return find_references(args["name"], cwd)

        elif name == "git":
            cmd_map = {
                "status": "git status",
                "diff":   f"git diff {args.get('args', '')}",
                "log":    f"git log --oneline -20 {args.get('args', '')}",
                "blame":  f"git blame {args.get('args', '')}",
                "show":   f"git show {args.get('args', '')}",
                "branch": "git branch -a",
            }
            r = subprocess.run(cmd_map[args["command"]], shell=True,
                               capture_output=True, text=True, timeout=30, cwd=cwd)
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
                task    = args["task"]
                ctx     = args.get("context", "")
                full_task = f"{task}\n\n背景：{ctx}" if ctx else task
                print(f"  \033[35m🤖 子 agent：{task[:60]}\033[0m")
                sub = CeLawCoderAgent(
                    session_id=f"sub_{datetime.now().strftime('%H%M%S')}",
                    endpoint=endpoint, model=model, token=token
                )
                result = sub.run(full_task, cwd=cwd, max_steps=10, silent=True)
                return result if isinstance(result, str) else "子任務完成"
            return "子 agent 未設定 endpoint"

        return f"未知工具：{name}"
    except subprocess.TimeoutExpired as te:
        return f"指令逾時（{te.timeout:.0f} 秒）"
    except Exception as e:
        return f"錯誤：{e}"

# ══════════════════════════════════════════════════════════════════════════════
# 12. Streaming API 呼叫
# ══════════════════════════════════════════════════════════════════════════════
def call_ceclaw_stream(messages, endpoint, model, token, silent=False):
    resp = requests.post(
        f"{endpoint.rstrip('/')}/v1/chat/completions",
        json={"model": model, "messages": messages, "tools": TOOLS,
              "tool_choice": "auto", "temperature": 0, "max_tokens": 4096,
              "stream": True},
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        stream=True, timeout=180
    )
    resp.raise_for_status()

    content_parts  = []
    tool_calls_raw = {}
    finish_reason  = None

    if not silent:
        print("  \033[32m", end="", flush=True)
    for line in resp.iter_lines():
        if not line: continue
        if line.startswith(b"data: "):
            data = line[6:]
            if data == b"[DONE]": break
            try:
                chunk        = json.loads(data)
                delta        = chunk["choices"][0].get("delta", {})
                finish_reason = chunk["choices"][0].get("finish_reason") or finish_reason
                if delta.get("content"):
                    content_parts.append(delta["content"])
                    if not silent:
                        print(delta["content"], end="", flush=True)
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
            except Exception:
                pass
    if not silent:
        print("\033[0m", flush=True)

    msg = {"role": "assistant", "content": "".join(content_parts) or None}
    if tool_calls_raw:
        msg["tool_calls"] = [tool_calls_raw[i] for i in sorted(tool_calls_raw)]
        msg["content"]    = msg["content"] or ""
    return {"choices": [{"message": msg, "finish_reason": finish_reason}]}

# ══════════════════════════════════════════════════════════════════════════════
# 13. 卡死偵測
# ══════════════════════════════════════════════════════════════════════════════
def make_call_fingerprint(tool_calls):
    if not tool_calls: return None
    parts = []
    for tc in tool_calls:
        fn = tc.get("function", {})
        parts.append(f"{fn.get('name')}:{fn.get('arguments', '')[:100]}")
    return hashlib.md5("|".join(parts).encode()).hexdigest()

# ══════════════════════════════════════════════════════════════════════════════
# 14. CeLawCoderAgent（繼承 OpenClawAgent，加 emit()）
# ══════════════════════════════════════════════════════════════════════════════
class CeLawCoderAgent(OpenClawAgent):

    def run(self, task: str, cwd=None, max_steps=30, mode="general", silent=False):
        cwd = str(cwd or os.getcwd())

        if not silent:
            print(f"\n\033[35m🤖 CeLaw Agent v6 [{self.session_id}]\033[0m")
            print(f"   Task  : {task[:80]}{'...' if len(task) > 80 else ''}")
            print(f"   CWD   : {cwd}")
            print(f"   WS    : ws://{WS_LAN_IP}:{WS_PORT}/ws/{self.session_id}")
            print("─" * 60)

        # symbol map 背景建立
        threading.Thread(target=build_symbol_map, args=(cwd,), daemon=True).start()

        project_ctx = load_claw_md(cwd, silent=silent) + scan_project(cwd)
        system      = BASE_SYSTEM_PROMPT + project_ctx
        messages    = [
            {"role": "system", "content": system},
            {"role": "user",   "content": task},
        ]

        recent_fps      = deque(maxlen=5)
        last_result_text = ""
        last_content = ""

        self.emit("task_start", {"task": task, "cwd": cwd})

        for step in range(max_steps):
            if self._cancelled:
                self.emit("cancelled", {"step": step})
                return False

            if not silent:
                print(f"\n\033[90m[Step {step+1}/{max_steps}]\033[0m")

            self.emit("step_start", {"step": step + 1, "max_steps": max_steps})

            # Compact 檢查
            tokens = estimate_tokens(messages)
            if tokens > MAX_CONTEXT_TOKENS:
                if not silent:
                    print(f"  \033[33m⚡ Context {tokens} tokens，觸發 compact\033[0m")
                messages = micro_compact_messages(messages)
                if estimate_tokens(messages) > MAX_CONTEXT_TOKENS:
                    messages = full_compact(messages, self.endpoint, self.model, self.token)

            try:
                resp = call_ceclaw_stream(messages, self.endpoint, self.model, self.token, silent=silent)
            except requests.exceptions.ConnectionError:
                self.emit("error", {"error": f"無法連線到 {self.endpoint}"})
                if not silent:
                    print(f"\033[31m❌ 無法連線到 {self.endpoint}\033[0m")
                save_session(self.session_id, messages, cwd, task)
                return last_content or last_result_text or False
            except Exception as e:
                self.emit("error", {"error": str(e)})
                if not silent:
                    print(f"\033[31m❌ API 錯誤：{e}\033[0m")
                save_session(self.session_id, messages, cwd, task)
                return last_content or last_result_text or False

            choice = resp["choices"][0]
            msg    = choice["message"]
            messages.append(msg)
            content = msg.get("content") or ""

            if content:
                last_content = content
                if "DONE" in content:
                    if not silent:
                        print(f"\n\033[36m✅ 完成\033[0m")
                        _print_session_log()
                    self.emit("done", {"result": last_result_text or content})
                    self.close_ws()
                    save_session(self.session_id, messages, cwd, task)
                    return last_result_text or content

            tool_calls = msg.get("tool_calls", [])

            if not tool_calls:
                if choice.get("finish_reason") == "stop":
                    if not silent:
                        print(f"\n\033[36m✅ 完成\033[0m")
                        _print_session_log()
                    self.emit("done", {"result": content})
                    self.close_ws()
                    save_session(self.session_id, messages, cwd, task)
                    return content or True
                continue

            # 卡死偵測
            fp = make_call_fingerprint(tool_calls)
            if fp and fp in recent_fps:
                if not silent:
                    print(f"\n\033[33m⚠️  偵測到重複 tool call，跳出迴圈\033[0m")
                self.emit("error", {"error": "卡死偵測，跳出迴圈"})
                save_session(self.session_id, messages, cwd, task)
                return last_content or last_result_text or False
            if fp:
                recent_fps.append(fp)

            results = []
            for tc in tool_calls:
                fn = tc["function"]["name"]
                try:
                    fa = json.loads(tc["function"]["arguments"])
                except Exception:
                    fa = {}

                self.emit("tool_call", {
                    "tool": fn,
                    "args": {k: str(v)[:100] for k, v in fa.items()}
                })

                if not silent:
                    print(f"  🔧 {fn}({', '.join(f'{k}={repr(v)[:40]}' for k, v in fa.items())})")

                r = execute_tool(fn, fa, cwd=cwd,
                                 endpoint=self.endpoint, model=self.model, token=self.token)

                self.emit("tool_result", {
                    "tool":   fn,
                    "result": r[:500]
                })

                if not silent:
                    print(f"  \033[90m→ {r[:150]}{'...' if len(r) > 150 else ''}\033[0m")

                last_result_text = r
                results.append({"role": "tool", "tool_call_id": tc["id"], "content": r})

            messages.extend(results)

        if not silent:
            print(f"\n\033[33m⚠️  達到最大步數 {max_steps}\033[0m")
            _print_session_log()

        self.emit("error", {"error": f"達到最大步數 {max_steps}"})
        save_session(self.session_id, messages, cwd, task)
        return last_content or last_result_text or False

def _print_session_log():
    if not SESSION_LOG: return
    print(f"\n\033[90m── Session Log ──")
    for e in SESSION_LOG:
        print(f"  {e['time']} [{e['action']}] {e['detail']}")
    print(f"────────────────\033[0m")

# ══════════════════════════════════════════════════════════════════════════════
# 15. Multi-agent 並行（v3 修正版：silent 模式正確 return content）
# ══════════════════════════════════════════════════════════════════════════════
def run_parallel_agents(tasks, endpoint, model, token, cwd=None):
    print(f"\n\033[36m🤖 Multi-agent：{len(tasks)} 個子任務並行\033[0m")
    results = [None] * len(tasks)

    # parallel 任務送 GB10（多 slot），不搶 L1
    parallel_endpoint = os.environ.get("CECLAW_PARALLEL_ENDPOINT", "http://192.168.1.91:8001")
    parallel_model    = os.environ.get("CECLAW_PARALLEL_MODEL", "ceclaw")

    def run_one(i, task):
        sid = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + f"_parallel-{i+1}"
        print(f"  \033[35m[agent-{i+1}] 開始：{task[:50]}\033[0m")
        agent = CeLawCoderAgent(session_id=sid, endpoint=parallel_endpoint, model=parallel_model, token=token)
        r = agent.run(task, cwd=cwd, max_steps=30, mode=f"parallel-{i+1}", silent=True)
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
# 16. 模式函數
# ══════════════════════════════════════════════════════════════════════════════
def mode_write(requirement, outfile, endpoint, model, token, cwd=None, session_id=None):
    task  = (f"請根據以下需求寫程式，儲存到 {outfile}：\n\n{requirement}\n\n"
             f"步驟：\n1. 寫完整可執行程式（加繁體中文註解）\n2. 儲存到 {outfile}\n"
             f"3. 執行確認無語法錯誤\n4. DONE")
    sid   = session_id or datetime.now().strftime("%Y%m%d_%H%M%S") + "_write"
    agent = CeLawCoderAgent(session_id=sid, endpoint=endpoint, model=model, token=token)
    agent.run(task, cwd=cwd, max_steps=15, mode="write")

def mode_fix(error_msg, filepath, endpoint, model, token, max_retries=3, cwd=None, session_id=None):
    print(f"\n\033[35m🔧 Auto Fix 模式\033[0m  檔案：{filepath}")
    for attempt in range(1, max_retries + 1):
        print(f"\n\033[90m── Fix {attempt}/{max_retries} ──\033[0m")
        task  = (f"修復 {filepath} 的 bug：\n\n錯誤：{error_msg}\n\n"
                 f"步驟：1.read_file 讀取 2.find_symbol 找定義 "
                 f"3.用 file_edit 修復（不要整個覆寫）4.執行驗證 5.DONE")
        sid   = session_id or datetime.now().strftime("%Y%m%d_%H%M%S_%f") + f"_fix-{attempt}"
        agent = CeLawCoderAgent(session_id=sid, endpoint=endpoint, model=model, token=token)
        agent.run(task, cwd=cwd, max_steps=15, mode=f"fix-{attempt}")
        p = Path(filepath).expanduser()
        if p.suffix == ".py":
            cmd = f"python3 -m py_compile {p} && echo OK"
        else:
            cmd = f"bash -n {p} && echo OK"
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            print(f"\033[32m✅ 修復成功！（{attempt} 次）\033[0m")
            return True
        error_msg = r.stdout + r.stderr
        print(f"\033[31m❌ 仍有錯誤\033[0m")
    print(f"\033[31m❌ 修復失敗\033[0m")
    return False

def mode_test(test_cmd, filepath, endpoint, model, token, max_retries=5, cwd=None, session_id=None):
    print(f"\n\033[35m🧪 Auto Test 模式\033[0m  測試：{test_cmd}")
    for attempt in range(1, max_retries + 1):
        r = subprocess.run(test_cmd, shell=True, capture_output=True, text=True,
                           timeout=120, cwd=cwd)
        if r.returncode == 0:
            print(f"\033[32m✅ 測試全過！（{attempt} 次）\033[0m")
            return True
        output = r.stdout + r.stderr
        print(f"\033[31m❌ 失敗\033[0m\n{output[:200]}")
        if attempt >= max_retries: break
        task  = (f"測試失敗，用 file_edit 修復 {filepath}：\n\n"
                 f"測試：{test_cmd}\n失敗：{output[:1500]}\n\nDONE")
        sid   = session_id or datetime.now().strftime("%Y%m%d_%H%M%S_%f") + f"_test-{attempt}"
        agent = CeLawCoderAgent(session_id=sid, endpoint=endpoint, model=model, token=token)
        agent.run(task, cwd=cwd, max_steps=15, mode=f"test-{attempt}")
    print(f"\033[31m❌ 達到最大重試\033[0m")
    return False

# ══════════════════════════════════════════════════════════════════════════════
# 17. 主程式
# ══════════════════════════════════════════════════════════════════════════════
def main():
    p = argparse.ArgumentParser(
        description="CeLaw Coding Agent v6",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""範例：
  python3 claw-agent-v6.py "找出所有 TODO"
  python3 claw-agent-v6.py --write "寫 fibonacci" --out fib.py
  python3 claw-agent-v6.py --fix "NameError" --file script.py
  python3 claw-agent-v6.py --test "pytest tests/" --file src/main.py
  python3 claw-agent-v6.py --parallel "審查 auth.py" "審查 api.py"
  python3 claw-agent-v6.py --resume last
  python3 claw-agent-v6.py --sessions
  python3 claw-agent-v6.py --no-ws "任務"  # 不啟動 WS server""")
    p.add_argument("task",         nargs="?")
    p.add_argument("--endpoint",   default=DEFAULT_ENDPOINT)
    p.add_argument("--model",      default=DEFAULT_MODEL)
    p.add_argument("--token",      default=DEFAULT_TOKEN)
    p.add_argument("--steps",      type=int, default=30)
    p.add_argument("--retries",    type=int, default=3)
    p.add_argument("--cwd",        default=None)
    p.add_argument("--session-id", default=None, dest="session_id",
                   help="WS 頻道 ID，多人使用時避免串台")
    p.add_argument("--no-ws",      action="store_true",
                   help="不啟動 WebSocket server")
    p.add_argument("--write",      metavar="REQ")
    p.add_argument("--out",        metavar="FILE")
    p.add_argument("--fix",        metavar="ERROR")
    p.add_argument("--file",       metavar="FILE")
    p.add_argument("--test",       metavar="CMD")
    p.add_argument("--parallel",   nargs="+", metavar="TASK")
    p.add_argument("--resume",     metavar="SESSION_ID")
    p.add_argument("--sessions",   action="store_true")
    a = p.parse_args()

    # 啟動 WS server（除非 --no-ws）
    if not a.no_ws:
        start_ws_thread()
        import time; time.sleep(0.3)  # 等 WS server 就緒

    cwd = a.cwd or os.getcwd()
    sid = a.session_id or datetime.now().strftime("%Y%m%d_%H%M%S")

    def make_agent(mode_suffix="general"):
        return CeLawCoderAgent(
            session_id=f"{sid}_{mode_suffix}",
            endpoint=a.endpoint, model=a.model, token=a.token
        )

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
            agent = CeLawCoderAgent(
                session_id=a.resume + "_resumed",
                endpoint=a.endpoint, model=a.model, token=a.token
            )
            agent.run(task, cwd=cwd, max_steps=a.steps)

    elif a.parallel:
        run_parallel_agents(a.parallel, **cfg)

    elif a.write:
        mode_write(a.write, a.out or "output.py",
                   session_id=f"{sid}_write", **cfg)

    elif a.fix:
        if not a.file:
            print("❌ --fix 需要 --file"); sys.exit(1)
        mode_fix(a.fix, a.file, max_retries=a.retries,
                 session_id=f"{sid}_fix", **cfg)

    elif a.test:
        if not a.file:
            print("❌ --test 需要 --file"); sys.exit(1)
        mode_test(a.test, a.file, max_retries=a.retries,
                  session_id=f"{sid}_test", **cfg)

    elif a.task:
        agent = make_agent("general")
        agent.run(a.task, cwd=cwd, max_steps=a.steps)

    else:
        print(f"\033[36mCeLaw Coding Agent v6 (q 退出, sessions 列出歷史)\033[0m")
        print(f"\033[90m WS: ws://{WS_LAN_IP}:{WS_PORT}/ws/{{session_id}}\033[0m")
        while True:
            try:
                line = input("\n📝 > ").strip()
                if not line: continue
                if line.lower() in ("q", "quit"): break
                if line == "sessions": list_sessions(); continue
                agent = make_agent("interactive")
                agent.run(line, cwd=cwd, max_steps=a.steps)
            except KeyboardInterrupt:
                break
        print("\n👋 再見")

if __name__ == "__main__":
    main()
