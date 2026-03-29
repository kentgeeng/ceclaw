#!/usr/bin/env python3
import sys
from pathlib import Path

BASE = Path('/home/zoe_ai/tenacitos/src')
errors = []

# P1: login/route.ts → secure: false
print("P1: login secure...")
p1 = BASE / 'app/api/auth/login/route.ts'
c = p1.read_text()
if 'secure: false' in c:
    print("  already patched")
elif 'secure: true' in c:
    p1.write_text(c.replace('secure: true', 'secure: false'))
    print("  OK")
else:
    p1.write_text(c.replace('httpOnly: true,', 'httpOnly: true,\n        secure: false,'))
    print("  OK (inserted)")

# P2: 新建 Office3DClient.tsx
print("P2: Office3DClient...")
p2 = BASE / 'components/Office3D/Office3DClient.tsx'
p2.write_text(
    "'use client';\n"
    "import dynamic from 'next/dynamic';\n"
    "\n"
    "const Office3D = dynamic(() => import('./Office3D'), {\n"
    "  ssr: false,\n"
    "  loading: () => (\n"
    "    <div style={{ color: 'white', padding: '2rem' }}>載入 3D 辦公室中...</div>\n"
    "  ),\n"
    "});\n"
    "\n"
    "export default function Office3DClient() {\n"
    "  return <Office3D />;\n"
    "}\n"
)
print("  OK")

# P3: Office3D.tsx → useEffect import + API 取代 mock
print("P3: Office3D agentStates...")
p3 = BASE / 'components/Office3D/Office3D.tsx'
c = p3.read_text()

old_import = "import { Suspense, useState } from 'react';"
new_import = "import { Suspense, useState, useEffect } from 'react';"
if old_import in c:
    c = c.replace(old_import, new_import)
    print("  useEffect import OK")
else:
    print("  WARNING: useEffect import pattern not found")

old_block = (
    "  // Mock data - TODO: Replace with real API data\n"
    "  const [agentStates] = useState<Record<string, AgentState>>({\n"
    "    main: { id: 'main', status: 'working', currentTask: 'Procesando emails', model: 'opus', tokensPerHour: 15000, tasksInQueue: 3, uptime: 12 },\n"
    "    academic: { id: 'academic', status: 'idle', model: 'sonnet', tokensPerHour: 0, tasksInQueue: 0, uptime: 8 },\n"
    "    studio: { id: 'studio', status: 'thinking', currentTask: 'Generando guión YouTube', model: 'opus', tokensPerHour: 8000, tasksInQueue: 1, uptime: 5 },\n"
    "    linkedin: { id: 'linkedin', status: 'working', currentTask: 'Redactando post', model: 'sonnet', tokensPerHour: 5000, tasksInQueue: 2, uptime: 10 },\n"
    "    social: { id: 'social', status: 'idle', model: 'sonnet', tokensPerHour: 0, tasksInQueue: 0, uptime: 7 },\n"
    "    infra: { id: 'infra', status: 'error', currentTask: 'Failed deployment', model: 'haiku', tokensPerHour: 1000, tasksInQueue: 0, uptime: 15 },\n"
    "  });"
)
new_block = (
    "  const [agentStates, setAgentStates] = useState<Record<string, AgentState>>({\n"
    "    'main': { id: 'main', status: 'idle', model: 'local', tokensPerHour: 0, tasksInQueue: 0, uptime: 0 },\n"
    "    'agent-2': { id: 'agent-2', status: 'idle', model: 'local', tokensPerHour: 0, tasksInQueue: 0, uptime: 0 },\n"
    "    'agent-3': { id: 'agent-3', status: 'idle', model: 'local', tokensPerHour: 0, tasksInQueue: 0, uptime: 0 },\n"
    "    'agent-4': { id: 'agent-4', status: 'idle', model: 'local', tokensPerHour: 0, tasksInQueue: 0, uptime: 0 },\n"
    "    'agent-5': { id: 'agent-5', status: 'idle', model: 'local', tokensPerHour: 0, tasksInQueue: 0, uptime: 0 },\n"
    "    'agent-6': { id: 'agent-6', status: 'idle', model: 'local', tokensPerHour: 0, tasksInQueue: 0, uptime: 0 },\n"
    "  });\n"
    "  useEffect(() => {\n"
    "    const fetchAgents = async () => {\n"
    "      try {\n"
    "        const res = await fetch('/api/agents');\n"
    "        if (!res.ok) return;\n"
    "        const data = await res.json();\n"
    "        if (!data.agents) return;\n"
    "        setAgentStates(prev => {\n"
    "          const next = { ...prev };\n"
    "          data.agents.forEach((agent: any) => {\n"
    "            next[agent.id] = {\n"
    "              id: agent.id,\n"
    "              status: agent.status === 'online' ? 'working' : 'idle',\n"
    "              model: 'local',\n"
    "              tokensPerHour: 0,\n"
    "              tasksInQueue: 0,\n"
    "              uptime: 0,\n"
    "            };\n"
    "          });\n"
    "          return next;\n"
    "        });\n"
    "      } catch (e) {}\n"
    "    };\n"
    "    fetchAgents();\n"
    "    const interval = setInterval(fetchAgents, 30000);\n"
    "    return () => clearInterval(interval);\n"
    "  }, []);"
)
if old_block in c:
    c = c.replace(old_block, new_block)
    p3.write_text(c)
    print("  agentStates OK")
else:
    idx = c.find('Mock data')
    if idx >= 0:
        print(f"  Context: {repr(c[idx:idx+200])}")
    print("  ERROR: agentStates pattern not found")
    errors.append("P3")

# P4: TopBar.tsx → CeClaw OS by Tenacit
print("P4: TopBar...")
p4 = BASE / 'components/TenacitOS/TopBar.tsx'
c = p4.read_text()
if 'CeClaw OS by Tenacit' in c:
    print("  already patched")
elif 'TenacitOS' in c:
    p4.write_text(c.replace('TenacitOS', 'CeClaw OS by Tenacit', 1))
    print("  OK")
else:
    print("  ERROR: TenacitOS not found")
    errors.append("P4")

# P5: agents/route.ts → heartbeat 邏輯
print("P5: agents heartbeat...")
p5 = BASE / 'app/api/agents/route.ts'
c = p5.read_text()
old_mem = (
    '      const memoryPath = join(agent.workspace, "memory");\n'
    '      let lastActivity = undefined;\n'
    '      let status: "online" | "offline" = "offline";\n'
    '\n'
    '      try {\n'
    '        const today = new Date().toISOString().split("T")[0];\n'
    '        const memoryFile = join(memoryPath, `${today}.md`);\n'
    '        const stat = require("fs").statSync(memoryFile);\n'
    '        lastActivity = stat.mtime.toISOString();\n'
    '        // Consider online if activity within last 5 minutes\n'
    '        status =\n'
    '          Date.now() - stat.mtime.getTime() < 5 * 60 * 1000\n'
    '            ? "online"\n'
    '            : "offline";\n'
    '      } catch (e) {\n'
    '        // No recent activity\n'
    '      }'
)
new_hb = (
    '      const agentWorkspace = agent.workspace || "/home/zoe_ai/.openclaw/workspace";\n'
    '      const heartbeatPath = join(agentWorkspace, "HEARTBEAT.md");\n'
    '      let lastActivity = undefined;\n'
    '      let status: "online" | "offline" = "offline";\n'
    '\n'
    '      try {\n'
    '        const stat = require("fs").statSync(heartbeatPath);\n'
    '        lastActivity = stat.mtime.toISOString();\n'
    '        // Consider online if heartbeat within last 5 minutes\n'
    '        status =\n'
    '          Date.now() - stat.mtime.getTime() < 5 * 60 * 1000\n'
    '            ? "online"\n'
    '            : "offline";\n'
    '      } catch (e) {\n'
    '        // No heartbeat file\n'
    '      }'
)
if old_mem in c:
    p5.write_text(c.replace(old_mem, new_hb))
    print("  OK")
else:
    print("  ERROR: memory pattern not found")
    errors.append("P5")

if errors:
    print(f"\nFAILED patches: {errors}")
    sys.exit(1)
else:
    print("\nAll patches OK")
