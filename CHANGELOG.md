~/.hermes/config.yaml 已加 api_server toolsets: openclaw_agent
~/.openclaw/openclaw.json 已加 gateway.tools.allow: sessions_send + tools.sessions.visibility: all

## P1-2 完成（2026-04-14）
- ~/.openclaw/workspace-ceclaw-legal/SOUL.md 改寫為台灣法律顧問版
- ~/.openclaw/workspace-ceclaw-hr/SOUL.md 改寫為台灣人資顧問版
- ~/.hermes/SOUL.md 加入 CECLAW Agent 委派規則（法律→ceclaw-legal，人資→ceclaw-hr）

## ceclaw-finance 完成（2026-04-14）
- openclaw agents add ceclaw-finance
- ~/.openclaw/workspace/ceclaw-finance/SOUL.md 台灣財務顧問版
- ~/.hermes/SOUL.md 加入財務委派規則
- call_openclaw_agent description 更新

## 委派規則修正（2026-04-14）
- ~/.hermes/SOUL.md 財務委派規則加入課稅/扣稅/所得稅關鍵字
- 測試確認 ceclaw-finance 正確被路由

## Agent 命名統一（2026-04-14）
- main → CECLAW 指揮官
- ceclaw-legal → 法律小幫手
- ceclaw-hr → 人資小幫手（原有）
- ceclaw-finance → 財務小幫手
- 修改位置：openclaw.json agents.list[].name

## ceclaw-compliance 完成（2026-04-14）
- openclaw agents add ceclaw-compliance（合規小幫手）
- SOUL.md 台灣合規版
- Hermes 委派規則加入個資/合規關鍵字
- call_openclaw_agent description 更新

## 已知限制記錄（2026-04-14）
- Hermes 自動路由在 GB10 單節點速度限制下，傾向使用 web search 而非 call_openclaw_agent
- 直接 sessions_send 呼叫各 Agent 完全正常，品質驗證通過
- 根本原因：GB10 ~15 tok/s，Agent 呼叫超時 Hermes 改走 web search
- 解決時機：B70 到位後 ~140 tok/s，Agent 回應穩定
