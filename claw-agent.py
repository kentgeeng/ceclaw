#!/usr/bin/env python3
"""
CeLaw Coding Agent - POC
參考 Claude Code 架構，接 CECLAW backend
"""
import os, sys, json, subprocess, argparse
from pathlib import Path
try:
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# ── 設定 ──────────────────────────────────────────────────────────────────────
DEFAULT_ENDPOINT = os.environ.get("CECLAW_ENDPOINT", "http://localhost:8080")
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
You have access to a rich set of tools:
**File operations:** read_file, write_file, list_dir
**Shell:** bash
## Workflow guidance
- Use TodoWrite to track multi-step plans
- Always read a file before editing it
- Complete the task then say DONE
## Additional rules
- Always respond in Traditional Chinese (繁體中文)
- Never fabricate file contents — always read first
- After each tool result, decide the next step carefully"""

# ── Tools 定義（參考 Claude Code tools/ 架構）────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "執行 bash 指令，返回 stdout/stderr",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要執行的指令"},
                    "timeout": {"type": "integer", "description": "超時秒數", "default": 30}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "讀取檔案內容",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "檔案路徑"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "寫入檔案（覆蓋）",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "檔案路徑"},
                    "content": {"type": "string", "description": "檔案內容"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "列出目錄內容",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目錄路徑", "default": "."}
                },
                "required": []
            }
        }
    }
]

# ── Tool 執行器 ───────────────────────────────────────────────────────────────
def execute_tool(name: str, args: dict) -> str:
    try:
        if name == "bash":
            cmd = args["command"]
            timeout = args.get("timeout", 30)
            print(f"  \033[33m$ {cmd}\033[0m")
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout
            )
            output = result.stdout + result.stderr
            if len(output) > 4000:
                output = output[:4000] + "\n...[截斷]"
            return output or "(無輸出)"

        elif name == "read_file":
            path = Path(args["path"]).expanduser()
            if not path.exists():
                return f"錯誤：檔案不存在 {path}"
            content = path.read_text(errors="replace")
            if len(content) > 8000:
                content = content[:8000] + "\n...[截斷]"
            return content

        elif name == "write_file":
            path = Path(args["path"]).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args["content"])
            return f"已寫入 {path} ({len(args['content'])} bytes)"

        elif name == "list_dir":
            path = Path(args.get("path", ".")).expanduser()
            if not path.exists():
                return f"錯誤：目錄不存在 {path}"
            items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
            lines = []
            for item in items[:50]:
                prefix = "📁 " if item.is_dir() else "📄 "
                lines.append(f"{prefix}{item.name}")
            return "\n".join(lines)

        else:
            return f"未知工具：{name}"

    except subprocess.TimeoutExpired:
        return f"錯誤：指令超時（{args.get('timeout', 30)}s）"
    except Exception as e:
        return f"錯誤：{e}"

# ── CECLAW API 呼叫 ───────────────────────────────────────────────────────────
def call_ceclaw(messages: list, endpoint: str, model: str, token: str) -> dict:
    url = f"{endpoint.rstrip('/')}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "temperature": 0,
        "max_tokens": 4096
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=120)
    resp.raise_for_status()
    return resp.json()

# ── Agent Loop（參考 Claude Code LocalMainSessionTask）────────────────────────
def run_agent(task: str, endpoint: str, model: str, token: str, max_steps: int = 20):
    print(f"\n\033[36m🤖 CeLaw Agent\033[0m")
    print(f"   Endpoint : {endpoint}")
    print(f"   Model    : {model}")
    print(f"   Task     : {task}")
    print("─" * 60)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task}
    ]

    for step in range(max_steps):
        print(f"\n\033[90m[Step {step+1}]\033[0m")

        try:
            response = call_ceclaw(messages, endpoint, model, token)
        except requests.exceptions.ConnectionError:
            print(f"\033[31m❌ 無法連線到 {endpoint}\033[0m")
            print("請確認 CECLAW 正在運行，或設定 CECLAW_ENDPOINT 環境變數")
            return
        except Exception as e:
            print(f"\033[31m❌ API 錯誤：{e}\033[0m")
            return

        choice = response["choices"][0]
        msg = choice["message"]

        # 加入 assistant 回應到 history
        messages.append(msg)

        # 有文字回應就顯示
        if msg.get("content"):
            print(f"\033[32m💬 {msg['content']}\033[0m")
            # 完成判斷
            if "DONE" in msg["content"]:
                print("\n\033[36m✅ 任務完成\033[0m")
                return

        # 處理 tool calls
        tool_calls = msg.get("tool_calls", [])
        if not tool_calls:
            # 沒有工具呼叫也沒有 DONE，繼續
            if choice.get("finish_reason") == "stop":
                print("\n\033[36m✅ 完成\033[0m")
                return
            continue

        # 執行每個 tool call
        tool_results = []
        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            try:
                fn_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                fn_args = {}

            print(f"  🔧 {fn_name}({', '.join(f'{k}={repr(v)[:50]}' for k,v in fn_args.items())})")
            result = execute_tool(fn_name, fn_args)
            print(f"  \033[90m→ {result[:200]}{'...' if len(result)>200 else ''}\033[0m")

            tool_results.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result
            })

        messages.extend(tool_results)

    print(f"\n\033[33m⚠️  達到最大步數 {max_steps}\033[0m")

# ── 主程式 ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="CeLaw Coding Agent POC")
    parser.add_argument("task", nargs="?", help="要執行的任務")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="CECLAW API endpoint")
    parser.add_argument("--model",    default=DEFAULT_MODEL,    help="模型名稱")
    parser.add_argument("--token",    default=DEFAULT_TOKEN,    help="API token")
    parser.add_argument("--steps",    type=int, default=20,     help="最大步數")
    args = parser.parse_args()

    if args.task:
        run_agent(args.task, args.endpoint, args.model, args.token, args.steps)
    else:
        # 互動模式
        print("\033[36mCeLaw Coding Agent (輸入 q 退出)\033[0m")
        while True:
            try:
                task = input("\n📝 任務 > ").strip()
                if task.lower() in ("q", "quit", "exit"):
                    break
                if task:
                    run_agent(task, args.endpoint, args.model, args.token, args.steps)
            except KeyboardInterrupt:
                break
        print("\n👋 再見")

if __name__ == "__main__":
    main()
