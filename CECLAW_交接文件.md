# CECLAW 交接文件 v4.7
**更新日期：2026-03-26**

---

## 系統現況

### Router
- 版本：0.1.0
- 位置：pop-os `~/ceclaw/router/main.py`
- 服務：`sudo systemctl status ceclaw-router`
- Log：`~/.ceclaw/router.log`
- 端口：8000

### Sandbox 清單
| Sandbox | ID | 狀態 |
|---------|-----|------|
| ceclaw-agent | 2e04e3db-259d-4820-ae39-af385c5d0ce1 | ✅ 正常 |
| ceclaw-agent-v2 | 35c0ad04-bb06-434c-a07d-a9a2413ee90c | ✅ 正常 |

### 最新 Git Commits
```
6eec5d0  fix: hostname 變數修正
81a14ce  feat: sandbox-restore v3.4
a225015  feat: sandbox-restore v3.3
4ac166a  feat: sandbox-restore v3.2
96af449  fix: sandbox-restore v3.1
d443c13  feat: sandbox-restore v3.0
0ef2dfe  feat: /v1/fetch endpoint
48258cd  fix: 日期幻覺禁令
e054a22  docs: 四份文件更新
```

---

## 架構

```
Sandbox → K3s proxy (10.200.0.1:3128) → Router (pop-os:8000)
                                       → 外網 HTTPS
Router → proxy.py (inject CECLAW 身份)
       → ollama-fast (minimax)
       → gb10-llama (192.168.1.91:8001)
```

---

## 關鍵檔案

### pop-os
- `~/ceclaw/sandbox-restore.sh` — v3.4 主修復腳本
- `~/ceclaw/router/main.py` — Router（已回滾，無 tcp_mux）
- `~/ceclaw/router/proxy.py` — 身份注入 + 日期幻覺禁令
- `~/ceclaw/config/` — workspace 備份（SOUL/TOOLS/AGENTS/USER.md）
- `~/ceclaw/config/ceclaw-policy.yaml` — 外網 policy

### Sandbox
- `/sandbox/.openclaw/openclaw.json` — 核心設定
- `/sandbox/.openclaw/extensions/ceclaw/` — CECLAW plugin
- `/sandbox/.openclaw/workspace/` — AI 記憶 workspace
- `~/.bashrc` — proxy 設定
- `~/ceclaw-start.sh` — 乾淨啟動

---

## Proxy 設定（.bashrc）

```bash
# 關鍵：http+https 都設，no_proxy 不含 host.openshell.internal
export http_proxy=http://10.200.0.1:3128
export https_proxy=http://10.200.0.1:3128
export HTTP_PROXY=http://10.200.0.1:3128
export HTTPS_PROXY=http://10.200.0.1:3128
export no_proxy="127.0.0.1,localhost"
export NO_PROXY="127.0.0.1,localhost"
```

---

## 已知問題

| 問題 | 狀態 |
|------|------|
| web_fetch 模型不主動呼叫 | ❌ P1 待修 |
| L4/L5 健康檢查 403 假陰性 | ⚠️ 已知，可接受 |
| searxng plugin（坑#77）| ❌ 暫停 |
| TOOLS.md 未優化 | ❌ P0 待修 |

---

## 重要坑

| 坑# | 說明 |
|-----|------|
| #69 | openclaw.json 必須有 `api: openai-completions` |
| #77 | openclaw 2026.3.11 extensions path bug |
| #78 | no_proxy 不能含 host.openshell.internal |
| #79 | gateway 必須在 source .bashrc 後啟動 |
| #80 | SSH known_hosts 衝突，用 UserKnownHostsFile=/dev/null |
| #81 | bash script 用 `openclaw tui` 不能用 alias `tui` |
| #82 | scp/ssh `-o "$SSH_OPTS"` 語法錯誤，需展開 |

---

## Restore 用法

```bash
# ceclaw-agent
bash ~/ceclaw/sandbox-restore.sh

# ceclaw-agent-v2
SANDBOX_ID=35c0ad04-bb06-434c-a07d-a9a2413ee90c \
TOKEN=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep "35c0ad04" | grep -o "token [a-z0-9-]*" | head -1 | awk '{print $2}') \
bash ~/ceclaw/sandbox-restore.sh
```

---

## P0 待辦

1. TOOLS.md 加入 web_fetch 強制呼叫指示
2. 更新後 restore 兩個 sandbox
3. 驗證 TUI 主動呼叫 web_fetch
