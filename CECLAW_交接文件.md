# CECLAW 專案交接文件 v4.4
## 給下一個對話的軟工 + 總工角色說明

**總工（Kent）**：35年工程經驗，ZOE AI Digital Twin 作者，做決策、設計審核
**軟工（下個對話）**：負責實作、測試、debug，遇困難問總工
**原則**：SOP-002 — 每次動手前說意圖，等 Kent 確認；每步完成後 commit
**督察**：GLM-5 Turbo（OpenRouter）— 品質審查，$0.12/次，CP值極高

---

## ⚠️ 本次對話重要進展摘要（v4.3 → v4.4）

### 已完成 ✅

1. **#59 ctx-size 65536 + parallel 2** ✅ commit `9a0fac1`
   - GB10 記憶體充裕（70.5/128GB），升級支援雙並發
   - `--ctx-size 65536 --parallel 2`，每 slot 獨享 32768 tokens
   - 修復 SQL schema VARCHAR 截斷等 context 不足問題

2. **#63 fast 路徑繁體強化** ✅ commit `512177f`
   - proxy.py CECLAW_SYSTEM_PROMPT 加「嚴禁輸出簡體字」
   - 措辭：「預設使用繁體中文（台灣）回覆，嚴禁輸出簡體字。若用戶以其他語言提問，使用該語言回應。」

3. **#51 fast path 升級 ministral-3:14b** ✅ commit `2753e28`
   - 台灣本土模型全數評估完畢（全淘汰，原因見坑記錄）
   - ministral-3:14b 通過 2000 輪燒機（100%）+ 36 項手動驗收
   - fast avg ~618ms，整句簡體 0，單字簡體率 ~1.9%（已知技術債）

4. **#65 burnin Layer 2A 重構** ✅
   - 移除 `openclaw agent` CLI（有 bug，假陽性）
   - Layer 2A 改 curl `/search` endpoint，results > 0
   - Layer 2B 定義為手動 TUI 驗證
   - 加 retry 機制（sleep 10 重試），追蹤 SearXNG 穩定度

5. **#64 openclaw.json tools 覆寫根因修復** ✅ commit `b4e7ad3`
   - 根因：openclaw gateway dynamic reload 覆寫 `tools: {}`
   - 解法：明確設 `tools.web.search.enabled: True`（merge 不覆寫）
   - Step C 從 `cfg["tools"] = {}` 改為明確設值

6. **坑#25 復發修復** ✅ commit `6a78756`
   - sandbox openclaw.json tools 被覆寫，手動修復
   - 根本解法已納入 #64

7. **SSH keepalive 修復** ✅
   - `~/.ssh/config` 加 `ServerAliveInterval 30 / ServerAliveCountMax 3`
   - 解決 Broken pipe 問題

8. **SearXNG Layer 2A 查詢詞改英文** ✅
   - 根因：bash curl 不自動 percent-encode 中文，搜尋引擎拒絕
   - 改為：`NVIDIA+stock+price` / `bitcoin+price` / `taipei+weather`

9. **四份文件更新** ✅ commit `b4e7ad3`
   - EasySetup v1.7、重灌SOP v2.0、規格書 v0.4.2、交接文件 v4.4

### 當前狀態

| Phase | 項目 | 狀態 | Commit |
|-------|------|------|--------|
| P1 #53 | Step E token guard | ✅ | a2e82d1 |
| P1 #55 | REASONING_KEYWORDS 即時性 | ✅ | bd09a17 |
| P1 #56 | enable_thinking 注入 | ✅ | cf98b2b |
| P1 #57 | parallel 1 修 400 | ✅ | dbc8094 |
| P1 #58 | burnin_v3.sh Layer 2 | ✅ | 7aad6f1 |
| P1 #59 | ctx-size 65536 + parallel 2 | ✅ | 9a0fac1 |
| P1 #51 | fast path 升級 ministral-3:14b | ✅ | 2753e28 |
| P1 #63 | fast 路徑繁體強化 | ✅ | 512177f |
| P1 #64 | tools 覆寫根因修復 | ✅ | b4e7ad3 |
| P1 #65 | burnin Layer 2A 重構 | ✅ | — |
| P1 #39 | Qwen2.5-72B 評估 | ⬜ | — |
| P1 #60 | fallback warning | ⬜ | — |
| P1 #61 | 台積電/NVIDIA股價漏答 | ⬜ | — |
| P1 #62 | gb10 retry 機制 | ⬜ | — |
| P1 #66 | SearXNG 穩定性盤查 | ⬜ | — |
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
cfg["tools"] = {
    "web": {
        "search": {"enabled": True},
        "fetch": {"enabled": True}
    }
}  # 明確設 enabled:true，防止 openclaw dynamic reload 覆寫（坑#64）
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

**當前 start_llama.sh（Qwen3.5-122B，parallel 2，#59）：**
```bash
#!/bin/bash
/home/zoe_gb/llama.cpp/build/bin/llama-server \
  --model /home/zoe_gb/Qwen3.5-122B/Qwen_Qwen3.5-122B-A10B-Q4_K_M/Qwen_Qwen3.5-122B-A10B-Q4_K_M-00001-of-00002.gguf \
  --alias minimax --host 0.0.0.0 --port 8001 \
  --ctx-size 65536 --parallel 2 \
  --flash-attn on --n-gpu-layers 99 --threads 20 \
  --cache-type-k q4_0 --cache-type-v q4_0 \
  --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0.0 \
  --reasoning off --jinja
```

⚠️ **`--parallel 2 --ctx-size 65536` 是關鍵**：每 slot 獨享 32768 tokens，支援雙並發。（#59 commit `9a0fac1`）

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
  - `ministral-3:14b` — **當前 fast path**（9.1GB，整句簡體0，2000輪驗收通過）
  - `ministral-3:8b` — 保留備用（6.0GB）
  - `qwen3:8b` — backup 路徑（5.2GB）
  - `qwen3-nothink` — 舊 fast path（已換掉，可清理）
  - `qwen2.5-zh` — 舊 fast path（已換掉，可清理）
  - `phi4-mini` — 測試用（2.5GB）

### SearXNG（本地搜尋）✅ E2E 完整通
- Docker 部署，port 8888
- 設定：`~/searxng-config/settings.yml`（⚠️ 擁有者 uid 977，需 sudo 修改）
- 啟用引擎：duckduckgo + brave + bing
- pop-os 存取：`http://localhost:8888`
- Router proxy：`http://localhost:8000/search?q=...&format=json`
- sandbox 透過 Router 存取：`http://host.openshell.internal:8000/search`
- plugin：`openclaw-plugin-searxng`，備份在 `~/ceclaw/backup/openclaw-plugin-searxng-full.tar.gz`
- ⚠️ plugin 需要 `dist/index.js`（esbuild 編譯），sandbox 重建後要從 pop-os 重新 build + scp

---

## 2. 專案檔案結構

```
~/ceclaw/
├── .venv/
├── ceclaw-router.service
├── ceclaw_monitor.sh
├── ceclaw.py                 # ceclaw CLI v0.1.0
├── burnin_routing.sh         # 原版燒機腳本（8+8題）
├── burnin_v2.sh              # 燒機腳本（16+16題+SearXNG Layer1驗證）
├── burnin_v3.sh              # ✅ 新版燒機腳本（Layer1+Layer2 AI決策觸發驗證）
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
        model: ministral-3:14b             # ✅ #51 升級，整句簡體0，avg ~650ms
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
| `7aad6f1` | feat: burnin_v3.sh 加 SearXNG Layer 2 AI 決策觸發驗證 |
| `dbc8094` | fix: #57 --parallel 1，修 context exceed 400，清 debug log |
| `92eb564` | fix: #57 enable_thinking 強制覆蓋，修 tool call 第二輪 gb10 400 |
| `cf98b2b` | fix: #56 inject enable_thinking:false，對齊 ZengboJamesWang proxy |
| `bd09a17` | feat: #55 REASONING_KEYWORDS 加即時性關鍵字，強制走 gb10-llama |
| `a2e82d1` | fix: #53 Step E token 空值 guard，避免靜默失敗 |
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
| 53 | Step E token 空值 guard | ✅ a2e82d1 |
| 55 | REASONING_KEYWORDS 即時性關鍵字 | ✅ bd09a17 |
| 56 | enable_thinking:false 注入 | ✅ cf98b2b |
| 57 | parallel 1 修 context exceed 400 | ✅ dbc8094 |
| 58 | burnin_v3.sh Layer 2 驗證 | ✅ 7aad6f1 |
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

**坑#25**: `openclaw.json tools.profile: "coding"` 把 searxng_search 擋掉。sandbox 重建後 Step C 必須加 `cfg["tools"] = {}`。

**坑#26**: SearXNG plugin 只有 `index.ts`，沒有 `dist/index.js`。sandbox 無法安裝 esbuild（npmjs.org 被封）。解法：在 pop-os 側 build 後 scp 進 sandbox。build 指令：
```bash
cd /tmp && tar xzf ~/ceclaw/backup/openclaw-plugin-searxng-full.tar.gz
cd openclaw-plugin-searxng
npm install
npx esbuild index.ts --bundle --format=esm --outfile=dist/index.js --external:@sinclair/typebox
```

**坑#27**: `--parallel 2` 讓每 slot 只有 `ctx-size ÷ 2 = 16384` tokens。搜尋結果 + 對話歷史超過就 400。POC 用 `--parallel 1`。

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
| 52 | burnin_v2.sh（16+16+SearXNG Layer1）| P1 | ✅ | 020e797 |
| 53 | Step E token 空值 guard | P1 | ✅ | a2e82d1 |
| 55 | REASONING_KEYWORDS 即時性關鍵字 | P1 | ✅ | bd09a17 |
| 56 | enable_thinking:false 注入 | P1 | ✅ | cf98b2b |
| 57 | parallel 1 修 context exceed 400 | P1 | ✅ | dbc8094 |
| 58 | burnin_v3.sh Layer 2 AI 決策觸發 | P1 | ✅ | 7aad6f1 |

**完成：49/58 ✅ | 待做：6 ⬜ | 無解/暫擱：3 ✗**

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
*文件版本: v4.4 | 日期: 2026-03-24*
*P1✅ P2✅ B方案✅ P3✅ P4✅ P5✅ GB10✅ P0全✅ P1大部分✅ | 下一步: P1#39→P6 | 最新commit: 7aad6f1*
