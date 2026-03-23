# CECLAW 專案交接文件 v4.2
## 給下一個對話的軟工 + 總工角色說明

**總工（Kent）**：35年工程經驗，ZOE AI Digital Twin 作者，做決策、設計審核
**軟工（下個對話）**：負責實作、測試、debug，遇困難問總工
**原則**：SOP-002 — 每次動手前說意圖，等 Kent 確認；每步完成後 commit
**督察**：GLM-5 Turbo（OpenRouter）— 品質審查，$0.12/次，CP值極高

---

## ⚠️ 本次對話重要進展摘要（v4.1 → v4.2）

### 已完成 ✅

1. **#37 503 fallback 修復** ✅ commit `c894fc6`
   - `_try_local()` 改為逐一嘗試所有本地後端
   - gb10 timeout/掛掉 → 自動降級 ollama-backup，不走 cloud
   - 驗證：停 GB10 → Router log `gb10-llama ✗ → ollama-backup → 200` ✅

2. **#49 fast path 換 ministral-3:8b** ✅ commit `c853e68`
   - 繁體穩定、無 thinking、身份攻擊全擋
   - 建立 qwen2.5-zh Modelfile（後改用 doomgrave）

3. **#50 fast path 換 doomgrave/ministral-3:8b** ✅ commit `1eb09d2`
   - 速度比原版快 15%（avg 10.5s vs 12.3s）
   - 繁體穩定、身份安全優於原版
   - 3000輪燒機 100%，身份 0 洩漏，簡體 1.1%

4. **#38 P0-4b SearXNG web search 整合** ✅ commit `328d491`
   - Router 加 `/search` proxy endpoint → 轉發 SearXNG:8888
   - sandbox 安裝 `openclaw-plugin-searxng`
   - iptables 開放 port 8888
   - 測試：TUI 問天氣 → 觸發 searxng_search ✅
   - plugin tar.gz 備份：`~/ceclaw/backup/openclaw-plugin-searxng-full.tar.gz`

5. **GB10 SSH 免密碼** ✅
   - SSH key：`~/.ssh/id_gb10`
   - `~/.ssh/config` 設定 `Host gb10`
   - GB10 `sudoers` 設 NOPASSWD

6. **burnin_v2.sh** ✅
   - FAST 16題、MAIN 16題（各加 8 題）
   - 開頭加 SearXNG Proxy 驗證段落
   - 舊腳本 `burnin_routing.sh` 保留

### 當前狀態

| Phase | 項目 | 狀態 | Commit |
|-------|------|------|--------|
| P1 #37 | 503 fallback | ✅ | c894fc6 |
| P1 #38 | SearXNG 整合 | ✅ | 328d491 |
| P1 #49 | fast path ministral | ✅ | c853e68 |
| P1 #50 | fast path doomgrave | ✅ | 1eb09d2 |
| P1 #39 | Qwen2.5-72B 評估 | ⬜ | — |
| P1 #40 | reasoning 殘留 | ✗ 暫擱 | — |
| P6 | NemoClaw drop-in 驗證 | ⬜ | — |
| P7 | Skill 相容性測試 | ⬜ | — |
| P8 | UX 升級 | ⬜ | — |

---

## ⚠️ Sandbox 重建後必做清單（手動 6 步）

每次重建 sandbox 後，**先在 pop-os 執行 Step E**，再進 sandbox 執行其他步驟。

### Step E（pop-os）：傳入 SearXNG plugin
```bash
TOKEN=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "token [a-z0-9-]*" | head -1 | awk '{print $2}')
scp -o ProxyCommand="/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id f24db4d6-9135-416c-a090-dbd281ebcd75 --token $TOKEN --gateway-name openshell" \
  ~/ceclaw/backup/openclaw-plugin-searxng-full.tar.gz sandbox@ceclaw-agent:/tmp/
```

⚠️ sandbox-id `f24db4d6-9135-416c-a090-dbd281ebcd75` 固定不變（sandbox name 相同）
⚠️ token 每次 SSH session 重建會變，用上面指令動態取得

### 進 sandbox 後執行（Step A-D-F）：

```bash
# Step A: 安裝 CECLAW plugin
openclaw plugins install /opt/ceclaw

# Step B: tui alias
grep -q "alias tui=" ~/.bashrc || echo "alias tui='openclaw tui --session fresh-\$(date +%s) --history-limit 20'" >> ~/.bashrc

# Step C: openclaw.json patch
python3 - << 'EOF'
import json
path = "/sandbox/.openclaw/openclaw.json"
cfg = json.load(open(path))
for model in cfg["models"]["providers"]["local"]["models"]:
    model["contextWindow"] = 32768
    model["maxTokens"] = 4096
cfg["agents"]["defaults"]["compaction"] = {"mode": "safeguard", "reserveTokens": 8000}
json.dump(cfg, open(path, "w"), indent=4, ensure_ascii=False)
print("done")
EOF

# Step D: gateway auto-start
grep -q "openclaw gateway run" ~/.bashrc || cat >> ~/.bashrc << 'BEOF'
if ! pgrep -f "openclaw-gatewa" > /dev/null 2>&1; then
    openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 &
fi
BEOF

# Step F: 安裝 SearXNG plugin
cd /tmp && tar xzf openclaw-plugin-searxng-full.tar.gz
rm -rf ~/.openclaw/extensions/searxng-search 2>/dev/null
openclaw plugins install /tmp/openclaw-plugin-searxng
python3 - << 'EOF'
import json
path = "/sandbox/.openclaw/openclaw.json"
cfg = json.load(open(path))
cfg["plugins"]["entries"]["searxng-search"]["config"]["baseUrl"] = "http://host.openshell.internal:8000"
json.dump(cfg, open(path, "w"), indent=4, ensure_ascii=False)
print("done")
EOF

source ~/.bashrc
```

---

## ⚠️ 坑#23：不要 docker restart openshell container

`docker restart <openshell container ID>` 會讓 K3s 內部網路混亂，sandbox SSH 連線斷掉且難恢復。

正確做法：
- 不要 restart container
- sandbox SSH 斷掉 → 等 30-60 秒，K3s pod 自己恢復
- 若等不回來 → `openshell term`（TUI 方式進入，不走 SSH）
- 最後手段 → 重建 sandbox（照上方清單補設定）

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

### GB10（推論機）✅
- 硬體：NVIDIA DGX Spark，GB10 Grace Blackwell Superchip
- 統一記憶體：128GB LPDDR5X（CPU+GPU 共享）
- hostname: `gx10` / IP: `192.168.1.91`
- User: `zoe_gb`
- SSH: `ssh gb10`（免密碼，key `~/.ssh/id_gb10`）
- sudo: NOPASSWD 已設定
- llama-server: port **8001**，無 auth
- **當前模型**: Qwen3.5-122B-A10B Q4_K_M（70GB，thinking=0）
- **備選模型**: Qwen2.5-72B Q4_K_M（47GB，待評估）
- 啟動: `~/start_llama.sh`

**⚠️ 重要硬體特性（GB10）：**
- 統一記憶體架構，`nvidia-smi` 顯示 N/A 是正常的
- 使用 DGX Dashboard（localhost:11000）監控記憶體
- Qwen3.5-122B 佔 ~86GB，接近極限（不是穩定區間）
- Qwen2.5-72B 佔 ~60GB，真正的穩定區間
- `--parallel 2` = 2個推論 slot

**當前 start_llama.sh（Qwen3.5-122B）：**
```bash
#!/bin/bash
/home/zoe_gb/llama.cpp/build/bin/llama-server \
  --model /home/zoe_gb/Qwen3.5-122B/Qwen_Qwen3.5-122B-A10B-Q4_K_M/Qwen_Qwen3.5-122B-A10B-Q4_K_M-00001-of-00002.gguf \
  --alias minimax --host 0.0.0.0 --port 8001 \
  --ctx-size 32768 --parallel 2 \
  --flash-attn on --n-gpu-layers 99 --threads 20 \
  --cache-type-k q4_0 --cache-type-v q4_0 \
  --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0.0 \
  --reasoning off --jinja
```

### OpenShell（沙盒系統）
- K3s in Docker container (ID 每次重建會變)
- 取得當前 ID: `docker ps --format "{{.ID}}" | head -1`
- Gateway endpoint: `https://127.0.0.1:8080`
- Sandbox image: `ghcr.io/kentgeeng/ceclaw-sandbox:latest`
- sandbox-id: `f24db4d6-9135-416c-a090-dbd281ebcd75`（固定）
- `host.openshell.internal` = NV 寫死解析到 `172.17.0.1`（Docker bridge，不可改）
- Session 路徑: `/sandbox/.openclaw/agents/main/sessions/`
- ⚠️ **不要 docker restart openshell container（坑#23）**

### Ollama（本地快速推論）
- 安裝版本: 0.18.0
- endpoint: `http://127.0.0.1:11434`
- 已下載模型：
  - `doomgrave/ministral-3:8b` — **當前 fast path**（5.8GB，繁體穩、無 thinking）
  - `ministral-3:8b` — 保留備用（6.0GB）
  - `qwen3:8b` — backup 路徑（5.2GB）
  - `qwen3-nothink` — 舊 fast path（已換掉，可清理）
  - `qwen2.5-zh` — 舊 fast path（已換掉，可清理）
  - `phi4-mini` — 測試用（2.5GB）

### SearXNG（本地搜尋）✅ 完整整合
- Docker 部署，port 8888
- 設定：`~/ceclaw/config/searxng-settings.yml`
- pop-os 存取：`http://localhost:8888`
- Router proxy：`http://localhost:8000/search?q=...&format=json`
- sandbox 透過 Router 存取：`http://host.openshell.internal:8000/search`
- plugin：`openclaw-plugin-searxng`，備份在 `~/ceclaw/backup/openclaw-plugin-searxng-full.tar.gz`

---

## 2. 專案檔案結構

```
~/ceclaw/
├── .venv/
├── ceclaw-router.service
├── ceclaw_monitor.sh
├── ceclaw.py                 # ceclaw CLI v0.1.0
├── burnin_routing.sh         # 原版燒機腳本（8+8題）
├── burnin_v2.sh              # ✅ 新版燒機腳本（16+16題+SearXNG驗證）
├── CECLAW_交接文件.md
├── CECLAW_規格規劃說明書.md
├── router/
│   ├── config.py
│   ├── backends.py           # ✅ 身份關鍵字 + _try_local fallback
│   ├── proxy.py              # ✅ rewrite_messages + inject_system_prompt
│   ├── audit.py
│   └── main.py               # ✅ /search proxy endpoint
├── plugin/
│   ├── src/index.ts
│   ├── dist/index.js
│   ├── openclaw.plugin.json
│   └── package.json
├── sandbox/
│   ├── Dockerfile
│   └── ceclaw-start.sh
├── config/
│   ├── ceclaw-policy.yaml
│   └── searxng-settings.yml
└── backup/
    ├── ceclaw.yaml.bak
    ├── start_llama.sh.bak
    ├── restore-coredns.sh
    └── openclaw-plugin-searxng-full.tar.gz  # ✅ SearXNG plugin 備份
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
        model: doomgrave/ministral-3:8b    # ✅ 換新，繁體穩+速度快
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
| `328d491` | feat: #38 SearXNG整合完成，Router /search proxy，sandbox plugin固化SOP |
| `1eb09d2` | feat: fast path 換 doomgrave/ministral-3:8b，速度+15%，品質更好，身份更安全 |
| `c853e68` | feat: fast path 換 ministral-3:8b，身份攻擊全擋，無thinking問題 |
| `c894fc6` | fix: #37 _try_local() 改為逐一嘗試所有本地後端，gb10 timeout/掛掉自動降級 ollama-backup |
| `db24708` | fix: sandbox 重建後恢復所有設定，contextWindow=32768 + reserveTokens=8000 + gateway autostart |
| `4c1e888` | fix: P0-1 身份白標化，inject_system_prompt + 身份關鍵字強制走 gb10-llama (#19) |
| `cf44a1f` | feat: P0-4a SearXNG 自架，endpoint http://172.17.0.1:8888 (#22) |
| `903e8cc` | fix: P0-3 tui alias 加 --session fresh+history-limit 20 (#21) |
| `ada85a7` | fix: P0-2 role rewrite，developer→system, toolResult→tool, system merge (#18) |
| `06f535c` | docs: 交接文件 v4.0 + 規格書 v0.3.8，GB10切換完成+P0清單 |
| `40ac82a` | feat: P5 Chain Audit Log |

---

## 5. 詳細 TODO List（按優先級）

### ✅ P0 全部完成
### ✅ P1 部分完成

| # | 項目 | 狀態 |
|---|------|------|
| 37 | 503 fallback（gb10→ollama-backup）| ✅ c894fc6 |
| 38 | SearXNG web search 整合 | ✅ 328d491 |
| 49 | fast path doomgrave/ministral-3:8b | ✅ 1eb09d2 |
| 50 | fast path 速度優化 | ✅（done via doomgrave）|
| 39 | Qwen2.5-72B 評估 | ⬜ |
| 40 | qwen3-nothink reasoning 殘留 | ✗ 暫擱（Ollama API 限制）|
| 51 | fast path < 500ms | ⬜ 未來 |

### ⬜ P6 — 相容性驗證
- NemoClaw drop-in 驗證報告（P6 手冊 v0.2 已準備）
- 前置條件：P1 全清

### ⬜ P7 — OpenClaw Skill 相容性測試
- A 級（無網路，10個）優先

### ⬜ P8 — UX 升級
- `ceclaw onboard` 補完
- `ceclaw doctor` 診斷指令
- `ceclaw list`
- `ceclaw start / stop`
- `ceclaw destroy`

---

## 6. proxy.py 關鍵函數說明

```python
# 呼叫順序（handle_inference 內）
body = await request.body()
body = rewrite_messages(body)      # 1. role rewrite
body = inject_system_prompt(body)  # 2. 身份注入
# → _try_local() → 逐一嘗試本地後端（gb10 → backup）→ 失敗再 cloud
```

**rewrite_messages()**
- `developer` → `system`
- `toolResult` → `tool`
- mid-conversation system messages 合併到 position 0

**inject_system_prompt()**
- 若有 system message：append CECLAW prompt 在後（recency bias）
- 若無 system message：insert 新 system message

**_try_local()（v4.2 更新）**
- 逐一嘗試本地後端（最多 3 個）
- 失敗時 `_healthy[backend.name] = False`，下輪 select_backend() 自動跳過
- gb10 timeout → ollama-backup → 成功，不跳 cloud

**CECLAW_SYSTEM_PROMPT：**
```python
CECLAW_SYSTEM_PROMPT = (
    "你是 CECLAW 企業 AI 助手，由 ColdElectric 提供。"
    "嚴禁提及：Qwen、qwen3、qwen2.5、通義千問、通义千问、"
    "通義實驗室、阿里巴巴、阿里雲。"
    "當被問到「你是誰」時，回答：「我是 CECLAW 企業 AI 助手。」"
    "所有回應預設使用繁體中文。若用戶以其他語言提問，使用該語言回應。"
)
```

---

## 7. 坑記錄（完整）

**坑#10（關鍵）**: openclaw undici `EnvHttpProxyAgent` experimental，不要改 baseUrl 為 IP 或清 proxy 環境變數。保持 `baseUrl: http://host.openshell.internal:8000/v1`。

**坑#11（無解）**: TUI 底部 `local/minimax` 寫死。

**坑#12（無解）**: OpenShell auto-approve 無 CLI 指令，安全設計。

**坑#13**: openclaw TUI 預設用 `main` session，歷史累積後 replay 造成發瘋。正式解法：`tui` alias 每次開 fresh session。

**坑#16**: doomgrave/ministral-3:8b 偶爾有簡體殘留（約 1.1%），集中在 `what is python`、`name a color` 等英文短問題。

**坑#23（關鍵）**: **不要 `docker restart` openshell container**。會讓 K3s 網路亂掉，sandbox SSH 死掉。正確做法：等 pod 自己恢復，或用 `openshell term`。

**坑#24**: sandbox SearXNG plugin 每次重建後消失，需手動執行 Step E+F（見重建清單）。sandbox-id 固定，token 每次從 `ps aux` 取。

---

## 8. Debug SOP

### Router 問題
```bash
ceclaw status
curl http://localhost:8000/ceclaw/status | python3 -m json.tool
sudo journalctl -u ceclaw-router -f
sudo systemctl restart ceclaw-router
```

### GB10 問題
```bash
curl -s --max-time 10 http://192.168.1.91:8001/v1/models | python3 -m json.tool | grep n_vocab
ssh gb10 'sudo systemctl status llama-server'
ssh gb10 'sudo systemctl restart llama-server'
```

### SearXNG 問題
```bash
# pop-os
docker ps | grep searxng
curl -s "http://localhost:8888/search?q=test&format=json" | head -3
# Router proxy
curl -s "http://localhost:8000/search?q=test&format=json" | head -3
```

### Sandbox 連線問題
```bash
openshell sandbox list        # 確認 Ready
openshell term                # 用 TUI 方式進入（不走 SSH）
# 最後手段：重建 sandbox（照上方 6 步清單）
```

### TUI 問題
```bash
# session 發瘋 → 用 tui alias（已自動開 fresh session）
tui
# 503 → 確認後端
curl http://localhost:8000/ceclaw/status
curl -s http://192.168.1.91:8001/health
```

### Audit Log 驗證
```bash
python3 -c "
import sys; sys.path.insert(0, '/home/zoe_ai/ceclaw')
from router.audit import verify
ok, msg = verify()
print(msg)
"
```

---

## 9. 關鍵指令速查

```bash
# CECLAW CLI
ceclaw status
ceclaw connect
ceclaw logs --follow

# Router 管理
sudo systemctl status/restart ceclaw-router
tail -f ~/.ceclaw/router.log

# Ollama
ollama list
ollama run doomgrave/ministral-3:8b "你是誰"

# GB10 管理（免密碼）
ssh gb10 'sudo systemctl status llama-server'
ssh gb10 'sudo systemctl restart llama-server'

# SearXNG
docker ps | grep searxng
curl -s "http://localhost:8888/search?q=test&format=json" | python3 -m json.tool | head -5
curl -s "http://localhost:8000/search?q=test&format=json" | python3 -m json.tool | head -5

# Sandbox
openshell sandbox connect ceclaw-agent
tui

# 燒機（sandbox 內）
bash /tmp/burnin_v2.sh 200

# Audit verify（pop-os）
python3 -c "import sys; sys.path.insert(0,'/home/zoe_ai/ceclaw'); from router.audit import verify; ok,msg=verify(); print(msg)"

# CoreDNS restore
bash ~/nemoclaw-config/restore-coredns.sh

# SCP plugin 到 sandbox
TOKEN=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "token [a-z0-9-]*" | head -1 | awk '{print $2}')
scp -o ProxyCommand="/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id f24db4d6-9135-416c-a090-dbd281ebcd75 --token $TOKEN --gateway-name openshell" \
  ~/ceclaw/backup/openclaw-plugin-searxng-full.tar.gz sandbox@ceclaw-agent:/tmp/
```

---

## 10. 進度表

| # | 項目 | Phase | 狀態 | Commit |
|---|------|-------|------|--------|
| 1-35 | 歷史完成項 | P1~P5 | ✅ | — |
| 36 | 2000輪燒機 | P1 | ✅ | — |
| 37 | 503 fallback 修復 | P1 | ✅ | c894fc6 |
| 38 | SearXNG 整合 | P1 | ✅ | 328d491 |
| 39 | Qwen2.5-72B 評估 | P1 | ⬜ | — |
| 40 | reasoning 殘留 | P1 | ✗ 暫擱 | — |
| 41 | NemoClaw drop-in 驗證 | P6 | ⬜ | — |
| 42-43 | Skill 相容性測試 | P7 | ⬜ | — |
| 44-48 | UX 升級 | P8 | ⬜ | — |
| 49 | fast path ministral-3:8b | P1 | ✅ | c853e68 |
| 50 | fast path doomgrave/ministral-3:8b | P1 | ✅ | 1eb09d2 |
| 51 | fast path < 500ms | P1 | ⬜ 未來 | — |

**完成：41/51 ✅ | 待做：7 ⬜ | 無解/暫擱：3 ✗**

---

## 11. GLM-5 Turbo 督察使用指南

### 督察 Prompt
```
你是一位資深AI系統評審員，負責評估一個本地部署的LLM的輸出品質。
硬體環境：NVIDIA DGX Spark (GB10)，128GB 統一記憶體
模型：[填入模型名稱]，[填入量化等級]
POC 階段，量產走 vLLM + 滿級模型
評分：✅ 通過 / ⚠️ 勉強 / ❌ 不通過
```

費用：約 $0.12 / 次完整評審，透過 OpenRouter 使用

---

## 12. 相關連結

- OpenShell docs: https://docs.nvidia.com/openshell/latest/
- NemoClaw GitHub: https://github.com/NVIDIA/NemoClaw
- CECLAW sandbox image: ghcr.io/kentgeeng/ceclaw-sandbox:latest
- Kent GitHub: kentgeeng
- Qwen3.5-122B GGUF: https://huggingface.co/bartowski/Qwen_Qwen3.5-122B-A10B-GGUF
- Qwen2.5-72B GGUF: https://huggingface.co/bartowski/Qwen2.5-72B-Instruct-GGUF
- GLM-5 Turbo（督察）: OpenRouter → zhipuai/glm-5-turbo

---

*CECLAW — Secure local AI agents, your inference, your rules.*
*總工: Kent | 軟工: 下個對話 Claude | 督察: GLM-5 Turbo*
*文件版本: v4.2 | 日期: 2026-03-23*
*P1✅ P2✅ B方案✅ P3✅ P4✅ P5✅ GB10✅ P0全✅ P1部分✅ | 下一步: P1#39→P6 | 最新commit: 328d491*
