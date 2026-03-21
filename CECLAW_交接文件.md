# CECLAW 專案交接文件 v3.9
## 給下一個對話的軟工 + 總工角色說明

**總工（Kent）**：35年工程經驗，ZOE AI Digital Twin 作者，做決策、設計審核  
**軟工（下個對話）**：負責實作、測試、debug，遇困難問總工  
**原則**：SOP-002 — 每次動手前說意圖，等 Kent 確認；每步完成後 commit

---

## ⚠️ 本次對話重要進展摘要（v3.8 → v3.9）

### 已完成
1. **P5 Chain Audit Log** ✅ commit: 40ac82a
   - `router/audit.py` 新建
   - `router/proxy.py` 整合 audit
   - 200 輪燒機 + 585 條記錄鏈完整驗證通過

2. **P5 E方案（tools schema 偵測）** ✅ commit: 9d213b3, 52aa117
   - `ollama-fast` 改用 `qwen3-nothink`（Modelfile 建立）
   - openclaw 每個請求帶 tools schema，qwen2.5:7b 會亂觸發 tool_calls
   - qwen3-nothink 解決此問題

3. **P5 關鍵字補充** ✅ commit: 515c59a
   - 移除 `設計`/`design` 誤判，加入 `系統設計`/`system design` 等15個推理詞
   - 三語對齊（中/英/日）

4. **P5 Health Check 修正** ✅ commit: 65f5d89
   - `config.py` 新增 `health_check_timeout_ms: int = 15000`
   - `backends.py` 按 backend type 選 endpoint：llama.cpp → `/health`，ollama → `/models`
   - 修正長任務期間 health check 誤判 unhealthy 問題

5. **規格書 v0.3.6** ✅ commit: 68c26f9
   - 新增 3.4 商業部署架構（三層推論）
   - 5.1 更新為 smart-routing 三後端
   - P4 標記完成

### 進行中 / 待完成
1. **GB10 模型問題** 🔥 重要
   - MiniMax M2.5 228B 某些問題 reasoning 無限生成 → OOM
   - 目前 `start_llama.sh` 已修正參數（ctx-size 16384, parallel 1, KV 量化）
   - 正在下載兩個新模型測試
   
2. **新模型下載中（GB10）**
   - `~/MiniMax-M2.5-GGUF-IQ2/` — MiniMax UD-IQ2_M（78GB）
   - `~/Qwen3.5-122B/` — Qwen3.5-122B-A10B Q4_K_M（74GB，bartowski）
   - 下載完後需測試並更新 `start_llama.sh`

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

### GB10（推論機）⚠️ 模型切換中
- hostname: `gx10` / IP: `192.168.1.91`
- User: `zoe_gb`
- llama-server: port **8001**，無 auth
- **當前模型**: MiniMax-M2.5-UD-Q3_K_XL（101GB，有 reasoning OOM 問題）
- **下載中模型 1**: `~/MiniMax-M2.5-GGUF-IQ2/UD-IQ2_M/`（78GB）
- **下載中模型 2**: `~/Qwen3.5-122B/Qwen_Qwen3.5-122B-A10B-Q4_K_M/`（74GB）
- 啟動: `~/start_llama.sh`
- 備份: `~/start_llama.sh.bak`, `~/start_llama.sh.bak2`

**當前 start_llama.sh（已修正）：**
```bash
#!/bin/bash
/home/zoe_gb/llama.cpp/build/bin/llama-server \
  --model /home/zoe_gb/MiniMax-M2.5-GGUF/UD-Q3_K_XL/MiniMax-M2.5-UD-Q3_K_XL-00001-of-00004.gguf \
  --alias minimax --host 0.0.0.0 --port 8001 \
  --ctx-size 16384 --parallel 1 \
  --flash-attn on \
  --n-gpu-layers 99 \
  --threads 20 \
  --cache-type-k q4_0 --cache-type-v q4_0 \
  --n-predict 4096 \
  --temp 0.3 --top-p 0.95 --top-k 40 --min-p 0.01 --jinja
```

**Qwen3.5 啟動腳本（下載完後用）：**
```bash
#!/bin/bash
/home/zoe_gb/llama.cpp/build/bin/llama-server \
  --model /home/zoe_gb/Qwen3.5-122B/Qwen_Qwen3.5-122B-A10B-Q4_K_M/Qwen_Qwen3.5-122B-A10B-Q4_K_M-00001-of-00002.gguf \
  --alias minimax --host 0.0.0.0 --port 8001 \
  --ctx-size 32768 --parallel 2 \
  --flash-attn on \
  --n-gpu-layers 99 \
  --threads 20 \
  --cache-type-k q4_0 --cache-type-v q4_0 \
  --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0.0 --jinja \
  --chat-template-kwargs '{"enable_thinking":false}'
```

### OpenShell（沙盒系統）
- K3s in Docker container (ID 每次重建會變)
- 取得當前 ID: `docker ps --format "{{.ID}}" | head -1`
- Gateway endpoint: `https://127.0.0.1:8080`
- Sandbox image: `ghcr.io/kentgeeng/ceclaw-sandbox:latest`
- `host.openshell.internal` = NV 寫死解析到 `172.17.0.1`（Docker bridge，不可改）
- Session 路徑: `/sandbox/.openclaw/agents/main/sessions/`

### Ollama（本地快速推論）
- 安裝版本: 0.17.0
- endpoint: `http://127.0.0.1:11434`
- 已下載模型：
  - `qwen3-nothink` — Modelfile 建立的自訂模型（基於 qwen3:8b，/nothink system prompt）
  - `qwen3:8b` — 5.2GB，backup 路徑
  - `qwen3:14b` — 9.3GB，可選
  - `qwen2.5:7b` — 4.7GB（已被 qwen3-nothink 取代 fast 路徑）
  - `llama3.1:8b` — 4.9GB（測試用，tool calls 太積極）
  - `granite3.2:8b` — 中文弱，備用
  - `phi4-mini` — 2.5GB，測試用

---

## 2. 專案檔案結構

```
~/ceclaw/
├── .venv/                    # Python venv
├── .gitignore                # 含 __pycache__/, *.pyc
├── ceclaw-router.service     # systemd service（已 enable）
├── ceclaw_monitor.sh         # 監控腳本（crontab 每5分鐘）
├── ceclaw.py                 # ceclaw CLI v0.1.0（symlink: /usr/local/bin/ceclaw）
├── burnin_routing.sh         # 燒機腳本（E方案版）
├── burnin_multi.sh           # 多後端燒機腳本
├── CECLAW_交接文件.md         # 本文件（最新版）
├── CECLAW_規格規劃說明書.md   # 規格書 v0.3.6
├── backup/
│   └── start_llama.sh.bak   # GB10 啟動腳本備份
├── router/
│   ├── config.py             # ✅ P5修改：LocalBackend 加 health_check_timeout_ms
│   ├── backends.py           # ✅ P5修改：health check 按 type 選 endpoint，qwen3-nothink
│   ├── proxy.py              # ✅ P5修改：Chain Audit Log 整合，_has_tools_in_body 移除
│   ├── audit.py              # ✅ P5新建：Chain Audit Log
│   └── main.py               # ✅ 完成
├── plugin/
│   ├── src/index.ts          # ✅ registerCommand 已確認無解（openclaw 不支援此 API）
│   ├── dist/index.js         # 已編譯
│   ├── openclaw.plugin.json  # 已加 configSchema
│   └── package.json          # 已修正
├── sandbox/
│   ├── Dockerfile            # ✅ 完成
│   └── ceclaw-start.sh       # ✅ 已修轉義 bug
└── config/
    └── ceclaw-policy.yaml    # ✅ 格式正確
```

### 設定檔（不在 repo）
```
~/.ceclaw/ceclaw.yaml         # Router 設定檔（master）
~/.ceclaw/router.log          # Router log（logrotate daily rotate 7）
~/.ceclaw/audit.log           # Chain Audit Log（新增）
~/.ceclaw/monitor.log         # 監控 log
~/nemoclaw-config/restore-coredns.sh
/etc/logrotate.d/ceclaw-router
```

---

## 3. 當前 ceclaw.yaml（最新）

```yaml
version: 1
router:
  listen_host: "0.0.0.0"
  listen_port: 8000
  tls: false
  reload_on_sighup: true
inference:
  strategy: smart-routing
  timeout_local_ms: 60000
  local:
    backends:
      - name: ollama-fast
        type: ollama
        base_url: http://127.0.0.1:11434/v1
        priority: 1
        model: qwen3-nothink          # ⚠️ 注意：不是 qwen2.5:7b
        use_for: [simple_query]

      - name: gb10-llama
        type: llama.cpp
        base_url: http://192.168.1.91:8001/v1
        priority: 2
        models:
          - id: minimax
            alias: default
            context_window: 32768

      - name: ollama-backup
        type: ollama
        base_url: http://127.0.0.1:11434/v1
        priority: 3
        model: qwen3:8b
        options:
          think: false
        use_for: [fallback]

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

## 4. Git Commit 歷史（完整）

| Commit | 說明 |
|--------|------|
| `52aa117` | config: ceclaw.yaml ollama-fast 改用 qwen3-nothink |
| `9d213b3` | feat: E方案完成，ollama-fast 改用 qwen3-nothink，移除 has_tools 特殊分支 |
| `fe09ec6` | feat: P5 tools schema 偵測，含 tools 請求強制走 gb10-llama（已被 9d213b3 取代）|
| `95e3fe3` | test: P5 Chain Audit Log 燒機200輪驗證 |
| `40ac82a` | feat: P5 Chain Audit Log，streaming 錯誤狀態修正 |
| `515c59a` | feat: P5 關鍵字補充，移除「設計」誤判，新增15個推理詞，三語對齊 |
| `65f5d89` | fix: health check 配置化15s，llama.cpp 走/health，ollama 走/models |
| `212aa59` | docs: 交接文件 v3.8，E方案完成+坑#14記錄 |
| `68c26f9` | docs: 規格書 v0.3.6，5.1 更新三後端 yaml，P4 標記完成 |
| `4ee3caa` | docs: 交接文件 v3.7，坑#13 正式解法鎖定 |
| `43cefc7` | docs: 交接文件 v3.6 + 規格 v0.3.5 |
| `f115bd2` | feat: ceclaw logs --lines |
| `575d488` | feat: ceclaw logs --follow |
| `986a7b5` | feat: routing 驗證腳本 |
| `0c09325` | feat: 關鍵字擴充（辦公室/coding/日文）|
| `3bac2a5` | test: 多後端燒機200輪 |
| `756a1a0` | fix: Ollama model 替換修正 |
| `2576338` | feat: proxy.py smart-routing 接入 |
| `f40fa4f` | feat: backends.py Ollama adapter |
| `454d088` | feat: config.py LocalBackend 擴充 |
| `c412038` | feat: ceclaw CLI v0.1.0 |
| `70175b6` | feat: P3 監控+logrotate+備份 |
| `1bffd63` | feat: P3 CoreDNS 持久化 |
| `2dfab79` | fix: B方案 5個 image bug |
| `6ebea02` | feat: P2 Plugin 整合 |

---

## 5. 詳細 TODO List

### 🔥 最優先：GB10 模型切換（下載完成後立刻做）

**Step 1：確認下載狀態**
```bash
# SSH 進 GB10
ssh zoe_gb@192.168.1.91

# 確認兩個下載進度
ls -lh ~/MiniMax-M2.5-GGUF-IQ2/.cache/huggingface/download/UD-IQ2_M/
ls -lh ~/Qwen3.5-122B/.cache/huggingface/download/Qwen_Qwen3.5-122B-A10B-Q4_K_M/
```

**Step 2：測試 Qwen3.5-122B（推薦先測這個）**
```bash
# 停現有 llama-server
sudo pkill -9 -f llama-server
sleep 5

# 啟動 Qwen3.5
/home/zoe_gb/llama.cpp/build/bin/llama-server \
  --model /home/zoe_gb/Qwen3.5-122B/Qwen_Qwen3.5-122B-A10B-Q4_K_M-00001-of-00002.gguf \
  --alias minimax --host 0.0.0.0 --port 8001 \
  --ctx-size 32768 --parallel 2 \
  --flash-attn on --n-gpu-layers 99 --threads 20 \
  --cache-type-k q4_0 --cache-type-v q4_0 \
  --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0.0 --jinja \
  --chat-template-kwargs '{"enable_thinking":false}' &
```

**Step 3：測試高風險 prompt（之前 MiniMax 會卡死的）**
```bash
# GB10 本機測試
curl -s --max-time 60 http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"minimax","messages":[{"role":"user","content":"how to implement binary search"}]}' \
  -o /tmp/test.json -w "Time: %{time_total}s\n"

python3 -c "
import json
d=json.load(open('/tmp/test.json'))
print('finish_reason:', d['choices'][0]['finish_reason'])
print('content len:', len(d['choices'][0]['message']['content']))
print('content:', d['choices'][0]['message']['content'][:200])
"
```

**Step 4：更新 start_llama.sh**
```bash
cat > ~/start_llama.sh << 'EOF'
#!/bin/bash
/home/zoe_gb/llama.cpp/build/bin/llama-server \
  --model /home/zoe_gb/Qwen3.5-122B/Qwen_Qwen3.5-122B-A10B-Q4_K_M/Qwen_Qwen3.5-122B-A10B-Q4_K_M-00001-of-00002.gguf \
  --alias minimax --host 0.0.0.0 --port 8001 \
  --ctx-size 32768 --parallel 2 \
  --flash-attn on --n-gpu-layers 99 --threads 20 \
  --cache-type-k q4_0 --cache-type-v q4_0 \
  --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0.0 --jinja \
  --chat-template-kwargs '{"enable_thinking":false}'
EOF
chmod +x ~/start_llama.sh
```

**Step 5：更新 pop-os 的 ceclaw.yaml**
```bash
# pop-os 上執行
# 確認 GB10 正常後重啟 Router
sudo systemctl restart ceclaw-router
# 跑燒機驗證
bash ~/ceclaw/burnin_routing.sh 200
```

---

### P5 剩餘項目

| 項目 | 狀態 | 優先度 | 說明 |
|------|------|--------|------|
| GB10 模型切換 | 🔥 緊急 | 1 | 見上方詳細步驟 |
| MiniMax TUI 實際測試 | ⬜ | 2 | 坑#14：TUI 中 `how to implement binary search` 是否會卡，待驗證 |
| 時間閾值方案B | ⬜ | 3 | rolling avg health check，燒機穩定後再做 |
| 雲端降級完整測試 | ⏸️ | 4 | 需要有效 API key（Groq 有免費額度） |
| registerCommand bug | ✗ | N/A | 已確認無解：openclaw 不支援 `registerCommand` API |
| session 持久化 | ⬜ | P8 | 長期解法，P8 再議 |

---

### P6：NemoClaw drop-in 驗證
- 已確認結論：核心 CLI 100% 對齊
- 需要正式跑驗證腳本出報告

### P7：OpenClaw Skill 相容性測試
- 等 GB10 穩定後開始
- A 級（無網路）優先：Self-Improving Agent, Capability Evolver 等10個

### P8：UX 升級
- 前置條件：P4~P7 全部完成

---

## 6. 關鍵技術知識（踩坑記錄）

> ⚠️ **坑#10 最重要**

**坑#1**: `/opt/ceclaw` 唯讀，需 cp 出來修改。

**坑#2**: `openclaw.extensions` 必須巢狀格式。

**坑#3**: sandbox 擋外網，npm install 會 E403。

**坑#4**: `openclaw.plugin.json` 必須有 `configSchema`。

**坑#5（無解）**: `registerCommand` openclaw 2026.3.11 不支援此 API，`api.registerCommand?.()` 靜默跳過。`ceclaw` CLI 正常運作不受影響。

**坑#6**: plugin name/id/目錄名三者必須一致。

**坑#7**: `ceclaw-start.sh` 轉義 bug，用 heredoc + os.environ 修正。

**坑#8**: openclaw gateway 必須前景執行，不能 systemd。

**坑#9**: MiniMax 冷啟動慢，timeout 已調高到 60000。

> ⚠️ **坑#10（關鍵）**: openclaw undici `EnvHttpProxyAgent` experimental，不要改 baseUrl 為 IP 或清 proxy 環境變數。保持 `baseUrl: http://host.openshell.internal:8000/v1` + `api: openai-completions`。

**坑#11（無解）**: TUI 底部 `local/minimax` 寫死，無法改。

**坑#12（無解）**: OpenShell auto-approve 無 CLI 指令，安全設計。

**坑#13**: openclaw TUI 預設用 `main` session，歷史累積後 replay 造成 Connection error。
正式解法：`openclaw tui --history-limit 20`
備用：`--session fresh-$(date +%s)` 或清空 `/sandbox/.openclaw/agents/main/sessions/`

**坑#14（重要，待驗證）**: MiniMax 228B 某些問題（`how to implement binary search`, `design a REST API architecture`, `explain recursion`）reasoning 無限生成，導致：
1. KV cache OOM → llama-server 崩潰
2. 或 content 為空（reasoning 吃完所有 token）
- 根本原因：MiniMax 228B 太大，剩餘 KV cache 不足
- 已修正 `start_llama.sh` 參數（ctx 16384, parallel 1, KV 量化）
- 長期解法：換 Qwen3.5-122B（下載中）
- TUI 實際使用需驗證是否受影響

**坑#15**: GB10 llama-server 載入 228B 模型需要 10+ 分鐘，期間系統幾乎無回應，是正常現象。

**坑#16**: qwen3-nothink 是用 Modelfile 建立的自訂 Ollama 模型（system prompt 加 `/nothink`），`think:false` 在含 tools 的 API 請求中無效，只能靠 Modelfile workaround。偶爾還是會有 reasoning 殘留。

**坑#17**: 燒機腳本 bash `$()` 變數有大小限制，大 JSON 回應（MiniMax 長回答）會截斷。已修正為使用 tmpfile + `os.environ['TMPFILE']`。

---

## 7. Debug SOP

### Router 問題
```bash
# 1. 基本狀態
ceclaw status
curl http://localhost:8000/ceclaw/status | python3 -m json.tool

# 2. 詳細 log
tail -f ~/.ceclaw/router.log

# 3. 重啟
sudo systemctl restart ceclaw-router
sudo systemctl status ceclaw-router
```

### GB10 問題
```bash
# 確認 GB10 活著
curl -s --max-time 10 http://192.168.1.91:8001/v1/models | head -3

# GB10 VRAM 狀態
ssh zoe_gb@192.168.1.91 'nvidia-smi | grep MiB'

# GB10 llama-server 進程
ssh zoe_gb@192.168.1.91 'ps aux | grep llama-server | grep -v grep'

# GB10 崩潰/OOM 處理
ssh zoe_gb@192.168.1.91 'sudo pkill -9 -f llama-server && sleep 10 && bash ~/start_llama.sh &'
```

### TUI 問題
```bash
# Connection error → 清 session
# sandbox 內執行：
openclaw tui --session fresh-$(date +%s)
# 或清除 session 歷史：
rm /sandbox/.openclaw/agents/main/sessions/*

# tool_calls 亂觸發 → 正常，qwen3-nothink 偶爾會有 reasoning
# 如果內容完全空白 → GB10 可能 OOM，去 GB10 重啟 llama-server
```

### Audit Log 驗證
```bash
# pop-os 上執行
python3 -c "
import sys; sys.path.insert(0, '/home/zoe_ai/ceclaw')
from router.audit import verify
ok, msg = verify()
print(msg)
"

# 查看最新記錄
tail -5 ~/.ceclaw/audit.log | python3 -m json.tool | grep -E '"seq"|"backend"|"status"'
```

### Smart Routing 驗證
```bash
# sandbox 內執行
# 簡單問題 → 應走 ollama-fast
curl -s http://host.openshell.internal:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"minimax","messages":[{"role":"user","content":"hi"}],"max_tokens":50}' \
  | python3 -m json.tool | grep content

# 複雜問題 → 應走 gb10-llama
curl -s http://host.openshell.internal:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"minimax","messages":[{"role":"user","content":"為什麼天空是藍色的"}]}' \
  | python3 -m json.tool | grep -A2 content
```

---

## 8. 關鍵指令速查

```bash
# CECLAW CLI
ceclaw status
ceclaw connect
ceclaw logs --follow
ceclaw logs --lines 50
ceclaw start / stop / onboard

# Router 管理
sudo systemctl status/restart ceclaw-router
tail -f ~/.ceclaw/router.log
curl http://localhost:8000/ceclaw/status
curl http://localhost:8000/ceclaw/reload  # 熱重載 yaml（POST）

# Ollama
ollama list
ollama run qwen3-nothink "你是誰"

# qwen3-nothink Modelfile（如需重建）
cat > /tmp/Modelfile-qwen3-nothink << 'EOF'
FROM qwen3:8b
SYSTEM "/nothink You are a helpful assistant. Respond directly without showing thinking process."
EOF
ollama create qwen3-nothink -f /tmp/Modelfile-qwen3-nothink

# GB10 管理
ssh zoe_gb@192.168.1.91
sudo pkill -9 -f llama-server
bash ~/start_llama.sh &

# 燒機
# sandbox 內：
bash /tmp/burnin_routing.sh 200

# Audit verify（pop-os）
python3 -c "import sys; sys.path.insert(0,'/home/zoe_ai/ceclaw'); from router.audit import verify; ok,msg=verify(); print(msg)"

# OpenShell sandbox
openshell sandbox list
openshell sandbox connect ceclaw-agent
openclaw tui --session fresh-$(date +%s)
openshell term

# CoreDNS restore
bash ~/nemoclaw-config/restore-coredns.sh
```

---

## 9. 燒機腳本說明

### burnin_routing.sh（最新版，E方案）
位置：`~/ceclaw/burnin_routing.sh`（也在 sandbox `/tmp/burnin_routing.sh`）

特點：
- 70% fast（含 tools schema）/ 30% main（無 tools）
- fast queries: `你是誰`, `hi`, `1+1=?`, `你好`, `tell me a joke` 等
- main queries: `為什麼天空是藍色的`, `解釋量子力學`, `寫一份報告大綱` 等
- 使用 tmpfile 避免 bash 變數截斷
- 燒機完成後提示執行 audit verify

**注意**：main 路徑不設 max_tokens，讓 MiniMax 自行決定（TUI 實際行為）

---

## 10. 模型架構說明（Smart Routing）

```
Request 進來
     │
     ▼
_extract_query_info() → query, tokens
     │
     ▼
select_backend()
     │
     ├── not query（空字串）→ gb10-llama（保守路由）
     │
     ├── needs_reasoning(query)=True → gb10-llama
     │   觸發關鍵字（中/英/日）：
     │   中：系統設計、架構設計、實作、計算、差異、為什麼、分析...
     │   英：system design、calculate、difference、summarize、why...
     │   日：実装、違い、まとめ、システム設計...
     │
     └── needs_reasoning=False → ollama-fast（qwen3-nothink）
          │
          └── ollama-fast 掛掉 → gb10-llama
               │
               └── gb10-llama 掛掉 → ollama-backup（qwen3:8b）
                    │
                    └── 全掛 → cloud fallback
```

**重要**：qwen3-nothink 支援 tools schema，不會亂觸發 tool_calls（qwen2.5:7b 的問題）

---

## 11. 檔案依賴關係

```
ceclaw.yaml（master config）
    └── config.py（CECLAWConfig, LocalBackend, CloudProvider）
         ├── backends.py（check_backend, select_backend, check_all）
         │    └── 用到 LocalBackend.health_check_timeout_ms
         ├── proxy.py（handle_inference, _try_local, _try_cloud）
         │    ├── 用到 backends.select_backend, get_healthy_backend
         │    └── 用到 audit.append_entry, audit.new_request_id
         ├── audit.py（append_entry, verify, new_request_id）
         │    └── 獨立模組，只依賴 Python 標準庫
         └── main.py（FastAPI app，整合以上所有）
```

---

## 12. 技術債

1. **Session replay**（坑#13）— P8 處理
2. **GB10 自啟** — llama-server 需手動 SSH 啟動（或加 systemd）
3. **registerCommand**（坑#5）— openclaw 不支援，無解
4. **undici EnvHttpProxyAgent** — experimental，長期關注
5. **MiniMax reasoning token budget**（坑#14）— 換 Qwen3.5 後應解決
6. **difference between 冗餘** — `difference` 已包含 `difference between`，可清理
7. **qwen3-nothink reasoning 殘留** — Modelfile workaround 非完美解，偶爾有 reasoning 輸出

---

## 13. 相關連結

- OpenShell docs: https://docs.nvidia.com/openshell/latest/
- NemoClaw GitHub: https://github.com/NVIDIA/NemoClaw
- CECLAW sandbox image: ghcr.io/kentgeeng/ceclaw-sandbox:latest
- Kent GitHub: kentgeeng
- Qwen3.5-122B GGUF: https://huggingface.co/bartowski/Qwen_Qwen3.5-122B-A10B-GGUF
- MiniMax M2.5 GGUF: https://huggingface.co/unsloth/MiniMax-M2.5-GGUF

---

*CECLAW — Secure local AI agents, your inference, your rules.*  
*總工: Kent | 軟工: 下個對話 Claude | 文件版本: v3.9 | 日期: 2026-03-21*  
*P1✅ P2✅ B方案✅ P3✅ P4✅ P5進行中 | 下一步: GB10換模型→燒機驗證 | commit: 212aa59*
