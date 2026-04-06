# CECLAW OpenShell Sandbox 量產規劃
**狀態：Draft — 量產前驗證**
**更新：2026-04-06**

## 目標架構

OpenShell sandbox（ceclaw-poc）
  - OpenClaw gateway :18789
  - Hermes webapi :8642
  - Hermes workspace :3000

Policy Engine out-of-process enforcement，agent compromise 也無法 override。

## systemd unit

見 ~/ceclaw/scripts/ceclaw-sandbox.service

## 驗證規劃（量產前執行）

Phase 1 sandbox 建立
- [ ] openshell sandbox create 不報錯
- [ ] openshell sandbox inspect ceclaw-poc 顯示 running
- [ ] policy 載入確認

Phase 2 服務啟動
- [ ] systemctl start ceclaw-sandbox
- [ ] 三個 port 全開（18789/8642/3000）
- [ ] health check 全過

Phase 3 out-of-process policy（核心）
- [ ] sandbox 內存取 allowlist 外網路 → block
- [ ] sandbox 內寫 /etc → block
- [ ] 模擬 compromise → policy 仍生效

Phase 4 reboot（取代 NemoClaw #910）
- [ ] systemctl enable ceclaw-sandbox
- [ ] sudo reboot
- [ ] 開機後 30 秒內三個 port 自動恢復

Phase 5 壓力
- [ ] Auto Demo 200 輪不中斷
- [ ] GB10 OOM 時 sandbox 行為正常
- [ ] Router :8000 可呼叫 GB10 :8001

## 待確認（執行前）

openshell sandbox create --help | grep -E "policy|network|fs"
確認 flag 名稱後調整 unit。
