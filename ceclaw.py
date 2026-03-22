#!/usr/bin/env python3
"""CECLAW CLI — Secure local AI agents, your inference, your rules."""

import sys
import json
import os
import subprocess
import urllib.request
import urllib.error
import re

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not found. Run: pip install pyyaml")
    sys.exit(1)

VERSION = "0.1.0"
SANDBOX_NAME = "ceclaw-agent"
SEP = "─" * 42

def load_config():
    path = os.path.expanduser("~/.ceclaw/ceclaw.yaml")
    with open(path) as f:
        c = yaml.safe_load(f)
    host = c["router"]["listen_host"]
    if host == "0.0.0.0":
        host = "127.0.0.1"
    port = c["router"]["listen_port"]
    router_url = f"http://{host}:{port}"
    gb10_base = c["inference"]["local"]["backends"][0]["base_url"]
    gb10_url = gb10_base.rsplit("/v1", 1)[0]
    return router_url, gb10_url

def http_get(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None

def cmd_status():
    try:
        router_url, gb10_url = load_config()
    except Exception as e:
        print(f"ERROR: cannot load config: {e}")
        sys.exit(1)

    print(f"\nCECLAW Status  (v{VERSION})")
    print(SEP)

    data = http_get(f"{router_url}/ceclaw/status")
    if data:
        gb10 = data.get("backends", {}).get("gb10-llama", False)
        gb10_str = "true" if gb10 else "false (fallback active)"
        icon = "✅" if gb10 else "⚠️ "
        print(f"  Router    ✅ running   │  gb10-llama: {icon} {gb10_str}")
    else:
        print(f"  Router    ❌ no response")

    gb10_data = http_get(f"{gb10_url}/v1/models")
    if gb10_data:
        models = gb10_data.get("data", [])
        names = [m.get("id", "?") for m in models]
        print(f"  GB10      ✅ online    │  models: {', '.join(names)}")
    else:
        print(f"  GB10      ❌ no response")

    try:
        result = subprocess.run(
            ["openshell", "sandbox", "list"],
            capture_output=True, text=True, timeout=10
        )
        if SANDBOX_NAME in result.stdout:
            for line in result.stdout.splitlines():
                if SANDBOX_NAME in line:
                    parts = line.split()
                    phase = re.sub(r"\x1b\[[\d;]*m", "", parts[4]) if len(parts) > 4 else "?"
                    icon = "✅" if phase == "Ready" else "⚠️ "
                    print(f"  Sandbox   {icon} {SANDBOX_NAME}  │  {phase}")
                    break
        else:
            print(f"  Sandbox   ❌ {SANDBOX_NAME} not found")
    except Exception as e:
        print(f"  Sandbox   ❌ error: {e}")

    print(SEP)
    print(f"  Connect:  ceclaw connect")
    print(f"  Logs:     ceclaw logs")
    print(SEP)
    print()

def cmd_connect():
    print(f"Connecting to sandbox: {SANDBOX_NAME}")
    print(f"  Tip: run 'tui' to start AI agent")
    subprocess.run(["openshell", "sandbox", "connect", SANDBOX_NAME])

def cmd_logs(lines=None):
    # 支援 ceclaw logs / --follow / --lines <n>（對齊 NemoClaw 格式）
    log = os.path.expanduser("~/.ceclaw/router.log")
    if lines:
        print(f"Last {lines} lines of {log}")
        subprocess.run(["tail", f"-{lines}", log])
    else:
        print(f"Tailing {log}  (Ctrl+C to stop)")
        try:
            subprocess.run(["tail", "-f", log])
        except KeyboardInterrupt:
            print()

def cmd_start():
    try:
        router_url, gb10_url = load_config()
    except Exception as e:
        print(f"ERROR: cannot load config: {e}")
        sys.exit(1)

    print("Checking CECLAW services...")
    data = http_get(f"{router_url}/ceclaw/status")
    if data:
        print("  Router    ✅ already running")
    else:
        print("  Router    ⚠️  not running")
        print("            → sudo systemctl start ceclaw-router")

    gb10_data = http_get(f"{gb10_url}/v1/models")
    if gb10_data:
        print("  GB10      ✅ already online")
    else:
        print("  GB10      ⚠️  not responding")
        print("            → ssh zoe_gb@192.168.1.91 \"nohup ~/start_llama.sh > ~/llama.log 2>&1 &\"")

def cmd_stop():
    print(f"Deleting sandbox: {SANDBOX_NAME}")
    result = subprocess.run(
        ["openshell", "sandbox", "delete", SANDBOX_NAME],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  ✅ {SANDBOX_NAME} deleted")
    else:
        print(f"  ❌ {result.stderr.strip()}")
    print("  Router not touched — manage with: sudo systemctl [start|stop] ceclaw-router")

def cmd_onboard():
    try:
        router_url, _ = load_config()
    except Exception as e:
        print(f"ERROR: cannot load config: {e}")
        sys.exit(1)

    print("CECLAW Onboard")
    print(SEP)

    data = http_get(f"{router_url}/ceclaw/status")
    if not data:
        print("  ❌ Router not running. Start it first:")
        print("     sudo systemctl start ceclaw-router")
        sys.exit(1)
    print("  Router    ✅")

    print(f"  Creating sandbox: {SANDBOX_NAME} ...")
    home = os.path.expanduser("~")
    result = subprocess.run([
        "openshell", "sandbox", "create",
        "--name", SANDBOX_NAME,
        "--from", "ghcr.io/kentgeeng/ceclaw-sandbox:latest",
        "--policy", f"{home}/ceclaw/config/ceclaw-policy.yaml",
        "--keep"
    ], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ❌ {result.stderr.strip()}")
        sys.exit(1)
    print(f"  Sandbox   ✅")
    print(SEP)
    print(f"  ⚠️  Run: openshell term → Sandboxes → {SANDBOX_NAME} → r → A")
    print(f"      (approve policy after first ceclaw connect)")
    print(SEP)
    print(f"\n──────────────────────────────────────────")
    print(f"  Sandbox   {SANDBOX_NAME} (OpenShell + CECLAW Router)")
    print(f"  Model     MiniMax-M2.5 (Local GB10)")
    print(f"──────────────────────────────────────────")
    print(f"  Connect:  ceclaw connect")
    print(f"  Status:   ceclaw status")
    print(f"  Logs:     ceclaw logs")
    print(f"──────────────────────────────────────────\n")

def print_help():
    print(f"""
CECLAW CLI v{VERSION} — Secure local AI agents, your inference, your rules.

USAGE
  ceclaw <command>

COMMANDS
  status    Show Router, GB10, and sandbox status
  connect   Connect to the sandbox shell
  logs      Tail the Router log
  start     Check and guide service startup
  stop      Delete the sandbox (Router not touched)
  onboard   Create sandbox and guide policy approval

EXAMPLES
  ceclaw status
  ceclaw connect
  ceclaw logs
""")

COMMANDS = {
    "status":  cmd_status,
    "connect": cmd_connect,
    "logs":    cmd_logs,
    "start":   cmd_start,
    "stop":    cmd_stop,
    "onboard": cmd_onboard,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print_help()
        sys.exit(0)
    cmd = sys.argv[1]
    # 支援 ceclaw logs --follow / --lines <n>
    if cmd == "logs" and len(sys.argv) > 2:
        if sys.argv[2] == "--follow":
            cmd_logs()
            sys.exit(0)
        elif sys.argv[2] == "--lines" and len(sys.argv) > 3:
            cmd_logs(lines=sys.argv[3])
            sys.exit(0)
        elif sys.argv[2].startswith("-n") and len(sys.argv) > 3:
            cmd_logs(lines=sys.argv[3])
            sys.exit(0)
    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}")
        print_help()
        sys.exit(1)
    COMMANDS[cmd]()
