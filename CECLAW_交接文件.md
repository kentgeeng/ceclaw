# CECLAW 專案交接文件
## 給下一個對話的軟工 + 總工角色說明

**總工（Kent）**：35年工程經驗，ZOE AI Digital Twin 作者，做決策、設計審核  
**軟工（下個對話）**：負責實作、測試、debug，遇困難問總工  
**原則**：SOP-002 — 每次動手前說意圖，等 Kent 確認；每步完成後 commit

---

## 1. 系統環境

### pop-os（主工作站）
- OS: Pop!_OS 22.04 LTS
- User: `zoe_ai`
- IP: 192.168.1.210
- GPU: RTX 5070 Ti (16GB VRAM)
- Docker: 26.1.3
- Python: 3.10（venv 在 `~/ceclaw/.venv`）
- Node.js: v22（系統）

### GB10（推論機）
- hostname: `gx10` / IP: `192.168.1.91`
- User: `zoe_gb`
- llama-server: port **8001**，無 auth
- 模型: MiniMax-M2.5-UD-Q3_K_XL (GGUF)，228B 參數
- alias: `minimax`
- 啟動: `~/start_llama.sh`（`--parallel 2`）
- 備份: `~/ceclaw/backup/start_llama.sh.bak`

### OpenShell（沙盒系統）
- K3s in Docker container (ID 每次重建會變)
- 取得當前 ID: `docker ps --format "{{.ID}}" | head -1`
- Gateway endpoint: `https://127.0.0.1:8080`
- Sandbox image: `ghcr.io/kentgeeng/ceclaw-sandbox:latest`（已推上 ghcr.io）
- `host.openshell.internal` = NV 寫死解析到 `172.17.0.1`（Docker bridge，不可改）

### Ollama（本地快速推論）
- 安裝版本: 0.17.0
- endpoint: `http://127.0.0.1:11434`
- 已下載模型：
  - `qwen2.5:7b` — 4.7GB，熱啟動 0.19s，fast 路徑
  - `qwen3:8b` — 5.2GB，熱啟動 1.3s（`think:false`），backup 路徑
  - `qwen3:14b` — 9.3GB，熱啟動 3.8s，可選
  - `qwen2.5-coder:32b` — 19GB，offload，較慢
- ✅ **VRAM 確認（P4）**：系統待機 446MB，qwen2.5:7b(4.7GB) + qwen3:8b(5.2GB) 合計 ~10.5GB，剩餘 ~5.7GB，兩模型可同時常駐

---

## 2. CECLAW 專案位置

```
~/ceclaw/
├── .venv/                    # Python venv
├── ceclaw-router.service     # systemd service（已 enable）
├── ceclaw_monitor.sh         # ✅ 監控腳本（crontab 每5分鐘執行）
├── ceclaw.py                 # ✅ ceclaw CLI v0.1.0（symlink: /usr/local/bin/ceclaw）
├── backup/
│   └── start_llama.sh.bak   # GB10 啟動腳本備份
├── router/
│   ├── config.py             # ✅ 完成（待 P4 擴充 multi-backend schema）
│   ├── backends.py           # ✅ 完成（待 P4 加 Ollama adapter）
│   ├── proxy.py              # ✅ 完成
│   └── main.py               # ✅ 完成
├── plugin/
│   ├── src/index.ts          # ✅ 完成（registerCommand disabled，坑#5）
│   ├── dist/index.js         # ✅ 已編譯
│   ├── openclaw.plugin.json  # ✅ 已加 configSchema
│   └── package.json          # ✅ 已修正
├── sandbox/
│   ├── Dockerfile            # ✅ 完成
│   └── ceclaw-start.sh       # ✅ 已修轉義 bug
└── config/
    └── ceclaw-policy.yaml    # ✅ 格式正確
```

### 設定檔
```
~/.ceclaw/ceclaw.yaml         # Router 設定檔（master，不在 repo）
~/.ceclaw/router.log          # Router log（logrotate daily rotate 7）
~/.ceclaw/monitor.log         # 監控 log
~/nemoclaw-config/restore-coredns.sh
/etc/logrotate.d/ceclaw-router
```

---

## 3. 已完成的功能 ✅

### CECLAW Inference Router（核心）
- FastAPI，systemd，開機自啟
- 本地優先 + 雲端降級，60s timeout
- **燒機**: 3500 輪 100%（avg 1842ms），99999 輪燒機進行中

### P2 Plugin 整合 ✅（commit: 6ebea02）
### B方案 rebuild image ✅（commit: 2dfab79）
### P3 CoreDNS 持久化 ✅（commit: 1bffd63）
### P3 監控 + logrotate + GB10備份 ✅（commit: 70175b6）
### P3 ceclaw CLI v0.1.0 ✅（commit: c412038）
- `ceclaw status/connect/logs/start/stop/onboard`
- 所有 URL 從 ceclaw.yaml 讀取，零硬編碼
- symlink: `/usr/local/bin/ceclaw`

### 文件更新 ✅（commit: eb17d1c, fdd87c4）

---

## 4. 啟動方式

```bash
# Terminal 1
openshell sandbox connect ceclaw-agent
# 看到 [gateway] agent model: local/minimax = 成功

# Terminal 2
openshell sandbox connect ceclaw-agent
openclaw tui
```

---

## 5. 關鍵技術知識（踩坑記錄）

> ⚠️ **坑#10 最重要，繼任者請優先閱讀。**

**坑#1**: `/opt/ceclaw` 唯讀，需 cp 出來修改。

**坑#2**: `openclaw.extensions` 必須巢狀格式。

**坑#3**: sandbox 擋外網，npm install 會 E403。

**坑#4**: `openclaw.plugin.json` 必須有 `configSchema`。

**坑#5**: `registerCommand` TypeError，已 disable，Phase 5 待修。

**坑#6**: plugin name/id/目錄名三者必須一致。

**坑#7**: `ceclaw-start.sh` 轉義 bug，用 heredoc + os.environ 修正。

**坑#8**: openclaw gateway 必須前景執行，不能 systemd。

**坑#9**: MiniMax 冷啟動慢，timeout 已調高到 60000。

> ⚠️ **坑#10（關鍵）**: openclaw undici `EnvHttpProxyAgent` experimental，不要改 baseUrl 為 IP 或清 proxy 環境變數。保持 `baseUrl: http://host.openshell.internal:8000/v1` + `api: openai-completions`。

**坑#11（無解）**: TUI 底部 `local/minimax` 寫死，無法改。

**坑#12（無解）**: OpenShell auto-approve 無 CLI 指令，安全設計。

**坑#13**: openclaw TUI 預設用 `main` session，歷史累積後 replay 造成 Connection error。解法：清空 session 檔案或用 `--session fresh-$(date +%s)` 開新 session。長期解法 P4/P5 處理。

---

## 6. P4 設計（下個對話第一件事）

### 背景
目前 Router 只支援 `llama.cpp` 一個後端。P4 要加 Ollama 支援，實現 multi-backend + smart routing。

### 本地模型評估結果

| 模型 | 速度 | 能力 | 用途 |
|------|------|------|------|
| qwen2.5:7b | 0.19s | 快但題型識別弱 | fast 路徑 |
| qwen3:8b | 1.3s（think:false）| 能力強，懂題型 | backup 路徑 |
| GB10 MiniMax | 1.8s | 最強 | 主力 |

⚠️ **關鍵發現**：qwen2.5:7b 把「圓湖怪獸數學題」當生存題回答，qwen3:8b 正確識別為數學問題。能力差距在題型識別，不只是速度。

### ceclaw.yaml 新 schema（待實作）
```yaml
inference:
  strategy: smart-routing        # 新增策略
  timeout_local_ms: 60000

  local:
    backends:
      - name: gb10-llama         # 現有，主力
        type: llama.cpp
        base_url: http://192.168.1.91:8001/v1
        priority: 2
        models:
          - id: minimax
            alias: default
            context_window: 32768

      - name: ollama-fast        # 新增
        type: ollama
        base_url: http://127.0.0.1:11434/v1
        priority: 1
        model: qwen2.5:7b
        use_for: [simple_query]

      - name: ollama-backup      # 新增
        type: ollama
        base_url: http://127.0.0.1:11434/v1
        priority: 3
        model: qwen3:8b
        options:
          think: false
        use_for: [fallback]
```

### Smart Routing 邏輯
```python
def needs_reasoning(query):
    keywords = {
        # 中文
        "證明", "推導", "如何逃脫", "最優解",
        "為什麼", "分析", "比較", "策略",
        # English
        "prove", "derive", "escape", "optimal",
        "why", "analyze", "compare", "strategy",
        "reasoning", "explain", "how to", "solve",
        # 日文
        "証明", "導出", "最適", "なぜ", "分析", "比較", "戦略",
    }
    return any(kw in query.lower() for kw in keywords)

def route(query, tokens):
    if tokens > 80:
        pass  # 長問題不賭關鍵字，直接走 main
    elif not needs_reasoning(query):
        return "ollama-fast"      # qwen2.5:7b（短 + 無推理需求）
    if is_healthy("gb10-llama"):
        return "gb10-llama"       # MiniMax 主力
    if is_healthy("ollama-backup"):
        return "ollama-backup"    # qwen3:8b 備援
    return "cloud"                # 雲端最後防線
```

> ⚠️ **設計決策（總工批准）**：`tokens > 80` 時不依賴關鍵字，直接走 gb10-llama。避免長問題因關鍵字未命中誤落 fast 路徑（qwen2.5:7b 能力弱）。

### P4 開工順序
1. `curl http://127.0.0.1:11434/api/tags` 確認 Ollama 可達
2. `nvidia-smi` 確認 VRAM 用量（已確認 ✅）
3. config.py 擴充 LocalBackend 新欄位（priority/model/options/use_for）
4. Ollama adapter（router/backends.py）
5. Backend health check 更新
6. Smart routing 實作
7. 燒機驗證
8. 最後才寫入新 ceclaw.yaml（code 認識新欄位後才能更新）

---

## 7. TODO List

### P4（進行中）
- [x] VRAM 確認 ✅（待機 446MB，兩模型同時常駐 ~10.5GB，剩餘 5.7GB）
- [x] config.py LocalBackend 擴充 ✅（priority/model/options/use_for，等燒機完寫入）
- [ ] Ollama adapter（backends.py）
- [ ] Backend health check 更新
- [ ] Smart routing 實作
- [ ] ceclaw.yaml 寫入新 schema（code 完成後才動）
- [ ] 多後端燒機驗證

### P5
- [ ] Chain Audit Log（hash chain）
- [ ] Streaming 完整測試
- [ ] 雲端降級完整測試
- [ ] registerCommand bug（坑#5）
- [ ] session 持久化（坑#13 長期解法）
- [ ] `ceclaw logs --follow`（對齊 NemoClaw `--follow` flag，小改動）

### P6
- [ ] NemoClaw drop-in 相容性驗證
- [ ] 指令對照表輸出（已完成草稿，待正式驗證）

### P7（OpenClaw Skill 相容性測試）
> 原則：測試用 API key、隔離 sandbox、安裝前確認來源

- [ ] A 級 — 無網路需求（優先）
  - [ ] Self-Improving Agent（112.9k）
  - [ ] Capability Evolver（35k）
  - [ ] Nano Pdf（37.7k）
  - [ ] Obsidian（35.1k）
  - [ ] Mcporter（28.6k）
  - [ ] Skill Creator（25.1k）
  - [ ] Openai Whisper（31.9k）
  - [ ] Model Usage（20.1k）
  - [ ] Apple Notes（16.2k）
  - [ ] Apple Reminders（14.0k）
- [ ] B 級 — 有網路需求（次優先，15個）
- [ ] C 級 — 功能補完（25個）

---

## 8. 關鍵指令速查

```bash
# CECLAW CLI
ceclaw status
ceclaw connect
ceclaw logs
ceclaw start
ceclaw stop
ceclaw onboard

# Router 管理
sudo systemctl status ceclaw-router
sudo systemctl restart ceclaw-router
tail -f ~/.ceclaw/router.log

# Ollama
ollama list
curl http://127.0.0.1:11434/api/tags
ollama run qwen2.5:7b "hi"

# 監控
bash ~/ceclaw/ceclaw_monitor.sh

# OpenShell sandbox
openshell sandbox list
openshell sandbox create --name ceclaw-agent \
  --from ghcr.io/kentgeeng/ceclaw-sandbox:latest \
  --policy ~/ceclaw/config/ceclaw-policy.yaml --keep
openshell sandbox connect ceclaw-agent
openshell term

# CoreDNS restore
bash ~/nemoclaw-config/restore-coredns.sh

# GB10 備份
scp zoe_gb@192.168.1.91:~/start_llama.sh ~/ceclaw/backup/start_llama.sh.bak
```

---

## 9. 設定檔內容

### `~/.ceclaw/ceclaw.yaml`（master，不在 repo）
```yaml
version: 1
router:
  listen_host: "0.0.0.0"
  listen_port: 8000
  tls: false
  reload_on_sighup: true
inference:
  strategy: local-first
  timeout_local_ms: 60000
  local:
    backends:
      - name: gb10-llama
        type: llama.cpp
        base_url: http://192.168.1.91:8001/v1
        models:
          - id: minimax
            alias: default
            context_window: 32768
  cloud_fallback:
    enabled: true
    priority:
      - provider: groq
        env_key: GROQ_API_KEY
        models: [llama-3.3-70b-versatile]
      - provider: anthropic
        env_key: ANTHROPIC_API_KEY
        models: [claude-sonnet-4-6]
      - provider: openai
        env_key: OPENAI_API_KEY
        models: [gpt-4.1]
      - provider: nvidia
        env_key: NVIDIA_API_KEY
        models: [nvidia/nemotron-3-super-120b-a12b]
```

---

## 10. Debug SOP

1. `ceclaw status` — 三項狀態一覽
2. `curl http://localhost:8000/ceclaw/status` — Router 詳細
3. `curl http://192.168.1.91:8001/v1/models` — GB10
4. sandbox 內：`curl -v http://host.openshell.internal:8000/ceclaw/status`
5. `openshell term` → ceclaw-agent → `r` → `A`
6. `tail -f ~/.ceclaw/router.log`
7. ⚠️ Connection error → **不要**改 baseUrl，見坑#10
8. TUI 一堆 Connection error → 清 session 歷史，見坑#13

---

## 11. 運維

```bash
# 監控（每5分鐘自動）
*/5 * * * * bash ~/ceclaw/ceclaw_monitor.sh

# logrotate
/etc/logrotate.d/ceclaw-router — daily rotate 7

# VRAM 監控
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free --format=csv
```

---

## 12. 相關連結

- OpenShell docs: https://docs.nvidia.com/openshell/latest/
- NemoClaw GitHub: https://github.com/NVIDIA/NemoClaw
- CECLAW sandbox image: ghcr.io/kentgeeng/ceclaw-sandbox:latest
- Kent GitHub: kentgeeng

---

*CECLAW — Secure local AI agents, your inference, your rules.*  
*總工: Kent | 軟工: 下個對話 Claude | 文件版本: v3.4 | 日期: 2026-03-21*  
*P1✅ P2✅ B方案✅ P3✅ 燒機進行中 | 下一步: P4 multi-backend | commit: eb17d1c*
