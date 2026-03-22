# CECLAW 專案交接文件 v4.1
## 給下一個對話的軟工 + 總工角色說明

**總工（Kent）**：35年工程經驗，ZOE AI Digital Twin 作者，做決策、設計審核  
**軟工（下個對話）**：負責實作、測試、debug，遇困難問總工  
**原則**：SOP-002 — 每次動手前說意圖，等 Kent 確認；每步完成後 commit  
**督察**：GLM-5 Turbo（OpenRouter）— 品質審查，$0.12/次，CP值極高

---

## ⚠️ 本次對話重要進展摘要（v4.0 → v4.1）

### 已完成 ✅

1. **P0-2 Role 相容性修復** ✅ commit `ada85a7`, `4715d5e`
   - `proxy.py` 加入 `rewrite_messages()`
   - `developer` → `system`，`toolResult` → `tool`
   - mid-conversation system messages 合併到 position 0
   - 驗證：Router log 確認 rewrite 觸發

2. **P0-3 history-limit 預設化** ✅ commit `903e8cc`
   - sandbox `~/.bashrc` 加 `alias tui='openclaw tui --session fresh-$(date +%s) --history-limit 20'`
   - `ceclaw.py` `cmd_connect()` 加 Tip 提示
   - 根因：`maxInjectedChars` 是假 key，不存在於 openclaw

3. **P0-1 身份白標化** ✅ commit `4c1e888`
   - `proxy.py` 加入 `inject_system_prompt()`，每個 request 注入 CECLAW 身份
   - `backends.py` `REASONING_KEYWORDS` 加入身份問題關鍵字 → 強制走 gb10-llama
   - `qwen3-nothink` Modelfile 更新 SYSTEM 指令
   - 驗證：「你是誰」→「我是 CECLAW 企業 AI 助手」✅，「你是通義千問嗎」→「不是」✅

4. **P0-4a SearXNG 自架** ✅ commit `cf44a1f`
   - Docker 部署：`docker run -d --name searxng -p 8888:8080 searxng/searxng`
   - 設定檔：`~/ceclaw/config/searxng-settings.yml`
   - endpoint：`http://172.17.0.1:8888`（sandbox 可達）
   - P0-4b（Router 攔截 tool call）待做

5. **contextWindow 32768 修正** ✅ commit `db24708`
   - sandbox `openclaw.json` 改 `contextWindow: 32768`（原 131072）
   - `reserveTokens: 8000` — compaction 提早觸發
   - TUI 底部顯示從 `?/131k` → `?/33k` ✅

6. **30 題壓力測試通過** ✅
   - 身份正確，繁體中文，無 503
   - tokens ?/33k 全程穩定

7. **Sandbox 重建完成** ✅
   - docker restart openshell container → sandbox SSH 死掉 → 重建
   - 重建後補全所有設定（見下方清單）

### 當前狀態

**P0 全部完成 ✅**

| P0 項目 | 狀態 | Commit |
|--------|------|--------|
| P0-1 身份白標化 | ✅ | 4c1e888 |
| P0-2 Role 相容性 | ✅ | ada85a7, 4715d5e |
| P0-3 history-limit | ✅ | 903e8cc |
| P0-4a SearXNG 自架 | ✅ | cf44a1f |
| P0-4b Router 攔截 web_search | ⬜ | P1 再做 |
| contextWindow 修正 | ✅ | db24708 |

---

## ⚠️ Sandbox 重建後必做清單（手動 4 步）

每次重建 sandbox 後，連進去執行：

```bash
# Step 1: 安裝 CECLAW plugin
openclaw plugins install /opt/ceclaw

# Step 2: tui alias
grep -q "alias tui=" ~/.bashrc || echo "alias tui='openclaw tui --session fresh-\$(date +%s) --history-limit 20'" >> ~/.bashrc

# Step 3: openclaw.json patch
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

# Step 4: gateway auto-start
grep -q "openclaw gateway run" ~/.bashrc || cat >> ~/.bashrc << 'BEOF'
if ! pgrep -f "openclaw-gatewa" > /dev/null 2>&1; then
    openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 &
fi
BEOF

source ~/.bashrc
```

⚠️ Step 3 之後需要 `openclaw plugins install /opt/ceclaw` 重新觸發 gateway reload（plugin install 會自動重啟 gateway）。

---

## ⚠️ 坑#23：不要 docker restart openshell container

`docker restart 64a2b20468a5` 會讓 K3s 內部網路混亂，sandbox SSH 連線斷掉且難恢復。

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

### GB10（推論機）✅ 已切換完成
- 硬體：NVIDIA DGX Spark，GB10 Grace Blackwell Superchip
- 統一記憶體：128GB LPDDR5X（CPU+GPU 共享）
- hostname: `gx10` / IP: `192.168.1.91`
- User: `zoe_gb`
- llama-server: port **8001**，無 auth
- **當前模型**: Qwen3.5-122B-A10B Q4_K_M（70GB，thinking=0）
- **備選模型 1**: Qwen2.5-72B Q4_K_M（47GB，尚未測試）
- **備選模型 2**: MiniMax IQ2_M（78GB，已淘汰）
- **舊模型（可清）**: MiniMax Q3_K_XL（95GB，`~/MiniMax-M2.5-GGUF/UD-Q3_K_XL/`）
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
- `host.openshell.internal` = NV 寫死解析到 `172.17.0.1`（Docker bridge，不可改）
- Session 路徑: `/sandbox/.openclaw/agents/main/sessions/`
- ⚠️ **不要 docker restart openshell container（坑#23）**

### Ollama（本地快速推論）
- 安裝版本: 0.17.0
- endpoint: `http://127.0.0.1:11434`
- 已下載模型：
  - `qwen3-nothink` — Modelfile 建立（CECLAW 身份已寫入 SYSTEM 指令）
  - `qwen3:8b` — 5.2GB，backup 路徑
  - `qwen3:14b` — 9.3GB，可選
  - `qwen2.5:7b` — 4.7GB（已被 qwen3-nothink 取代）

### SearXNG（本地搜尋）✅ 新增
- Docker 部署，port 8888
- 設定：`~/ceclaw/config/searxng-settings.yml`
- sandbox 可達：`http://172.17.0.1:8888`
- 狀態：起來，JSON API 正常
- P0-4b（Router 攔截）待做

---

## 2. 專案檔案結構

```
~/ceclaw/
├── .venv/
├── ceclaw-router.service
├── ceclaw_monitor.sh
├── ceclaw.py                 # ceclaw CLI v0.1.0
├── burnin_routing.sh
├── CECLAW_交接文件.md
├── CECLAW_規格規劃說明書.md
├── router/
│   ├── config.py
│   ├── backends.py           # ✅ 身份關鍵字加入 REASONING_KEYWORDS
│   ├── proxy.py              # ✅ rewrite_messages + inject_system_prompt
│   ├── audit.py
│   └── main.py
├── plugin/
│   ├── src/index.ts
│   ├── dist/index.js
│   ├── openclaw.plugin.json
│   └── package.json
├── sandbox/
│   ├── Dockerfile
│   └── ceclaw-start.sh
└── config/
    ├── ceclaw-policy.yaml
    └── searxng-settings.yml  # ✅ 新增
```

### 設定檔（不在 repo）
```
~/.ceclaw/ceclaw.yaml         # Router 設定檔（master）
~/.ceclaw/router.log
~/.ceclaw/audit.log
~/.ceclaw/monitor.log
~/searxng-config/settings.yml # SearXNG 設定
/sandbox/.openclaw/openclaw.json  # sandbox 設定（重建後需手動 patch）
/etc/systemd/system/llama-server.service  # GB10 systemd
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
        model: qwen3-nothink
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
| `db24708` | fix: sandbox 重建後恢復所有設定，contextWindow=32768 + reserveTokens=8000 + gateway autostart |
| `4c1e888` | fix: P0-1 身份白標化，inject_system_prompt + 身份關鍵字強制走 gb10-llama (#19) |
| `cf44a1f` | feat: P0-4a SearXNG 自架，endpoint http://172.17.0.1:8888 (#22) |
| `903e8cc` | fix: P0-3 tui alias 加 --session fresh+history-limit 20 (#21) |
| `4715d5e` | fix: P0-2 加 rewrite log，P0-3 cmd_connect Tip + sandbox tui alias (#21) |
| `ada85a7` | fix: P0-2 role rewrite，developer→system, toolResult→tool, system merge (#18) |
| `06f535c` | docs: 交接文件 v4.0 + 規格書 v0.3.8，GB10切換完成+P0清單 |
| `d34d766` | docs: 交接文件 v3.9 + 規格書 v0.3.7 |
| `52aa117` | config: ceclaw.yaml ollama-fast 改用 qwen3-nothink |
| `9d213b3` | feat: E方案完成 |
| `40ac82a` | feat: P5 Chain Audit Log |

---

## 5. 詳細 TODO List（按優先級）

### ✅ P0 全部完成

### ⬜ P1（P0 完成後）

**P1-1：P0-4b web_search Router 攔截**
- SearXNG 已起（`http://172.17.0.1:8888`）
- 需要在 `proxy.py` 攔截 openclaw 的 tool call，轉發到 SearXNG
- openclaw tool call 格式需要研究

**P1-2：身份關鍵字補充**
- 「你是通義千問嗎」走 gb10-llama ✅
- 「你是用什麼模型訓練的」→ 還是洩漏（走 ollama-fast）
- 需要加：`"訓練的", "什麼模型", "based on", "trained on"`

**P1-3：Qwen2.5-72B 評估**
- 47GB，~60GB 記憶體，穩定區間
- 需跑 8 題 + GLM-5 Turbo 審查
- 若通過替換 Qwen3.5-122B（釋放 26GB）

**P1-4：qwen3-nothink reasoning 殘留過濾**
- 約 11% 機率洩漏 `<think>` 內容
- 在 proxy.py 加 middleware 過濾

**P1-5：tokens ?/131k → ?/33k 顯示修正**
- ✅ 已修（contextWindow=32768）

### ⬜ P6 — 相容性驗證
- NemoClaw drop-in 驗證報告
- 前置條件：P0 全修完 ✅

### ⬜ P7 — OpenClaw Skill 相容性測試
- A 級（無網路，10個）優先

### ⬜ P8 — UX 升級
- `ceclaw onboard` 補完（plugin install + gateway autostart）
- `ceclaw doctor` 診斷指令
- sandbox 重建後自動化（目前還是手動 4 步）

---

## 6. proxy.py 關鍵函數說明

```python
# 呼叫順序（handle_inference 內）
body = await request.body()
body = rewrite_messages(body)      # 1. role rewrite
body = inject_system_prompt(body)  # 2. 身份注入
# → forward to backend
```

**rewrite_messages()**
- `developer` → `system`
- `toolResult` → `tool`
- mid-conversation system messages 合併到 position 0

**inject_system_prompt()**
- 若有 system message：append CECLAW prompt 在後（recency bias）
- 若無 system message：insert 新 system message
- openclaw 自己會注入巨大 system prompt，CECLAW prompt 放在最後蓋掉身份

**CECLAW_SYSTEM_PROMPT（頂層常數）：**
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

**坑#1~#9**：見 v3.x 交接文件

**坑#10（關鍵）**: openclaw undici `EnvHttpProxyAgent` experimental，不要改 baseUrl 為 IP 或清 proxy 環境變數。保持 `baseUrl: http://host.openshell.internal:8000/v1`。

**坑#11（無解）**: TUI 底部 `local/minimax` 寫死。

**坑#12（無解）**: OpenShell auto-approve 無 CLI 指令，安全設計。

**坑#13**: openclaw TUI 預設用 `main` session，歷史累積後 replay 造成發瘋。正式解法：`tui` alias 每次開 fresh session。

**坑#14（已解）**: MiniMax 228B reasoning 無限生成 → OOM。已換 Qwen3.5-122B。

**坑#15**: GB10 llama-server 載入大模型需要幾分鐘。

**坑#16**: qwen3-nothink 偶爾有 reasoning 殘留（約 11-12%）。

**坑#17**: 燒機腳本 bash `$()` 變數有大小限制，用 tmpfile。

**坑#18（✅ 已解）**: openclaw Role 相容性，`developer`/`toolResult` Qwen3.5 不認識。解法：`rewrite_messages()` in proxy.py。

**坑#19（✅ 已解）**: 身份洩漏 100%。解法：`inject_system_prompt()` + 身份關鍵字強制走 gb10-llama + qwen3-nothink Modelfile 更新。

**坑#20（✅ 已解）**: `maxInjectedChars` 是假 key，不存在。真正解法：`contextWindow: 32768` + `reserveTokens: 8000`。

**坑#21（✅ 已解）**: `--history-limit 20` 沒有預設。解法：`tui` alias 加 `--session fresh-$(date +%s) --history-limit 20`。

**坑#22（部分解）**: web_search 過度觸發。SearXNG 已自架，Router 攔截待做（P1-1）。

**坑#23（新）**: **不要 `docker restart` openshell container**。會讓 K3s 網路亂掉，sandbox SSH 死掉。正確做法：等 pod 自己恢復，或用 `openshell term`。

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
# n_vocab: 248320 = Qwen3.5 ✅
ssh zoe_gb@192.168.1.91 'sudo systemctl status llama-server'
ssh zoe_gb@192.168.1.91 'sudo systemctl restart llama-server'
```

### Sandbox 連線問題
```bash
# SSH 連不進去 → 不要 docker restart！
openshell sandbox list        # 確認 Ready
openshell term                # 用 TUI 方式進入（不走 SSH）
# 最後手段：重建 sandbox（照上方 4 步清單）
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
ceclaw connect          # 進 sandbox，顯示 Tip: run 'tui'
ceclaw logs --follow
ceclaw logs --lines 50

# Router 管理
sudo systemctl status/restart ceclaw-router
tail -f ~/.ceclaw/router.log

# Ollama
ollama list
ollama run qwen3-nothink "你是誰"  # 應回 CECLAW 企業 AI 助手

# GB10 管理
ssh zoe_gb@192.168.1.91
sudo systemctl status llama-server

# SearXNG
docker ps | grep searxng
curl -s "http://localhost:8888/search?q=test&format=json" | python3 -m json.tool | head -5

# Sandbox（用 tui alias）
openshell sandbox connect ceclaw-agent
tui

# 燒機（sandbox 內）
bash /tmp/burnin_routing.sh 200

# Audit verify（pop-os）
python3 -c "import sys; sys.path.insert(0,'/home/zoe_ai/ceclaw'); from router.audit import verify; ok,msg=verify(); print(msg)"

# CoreDNS restore
bash ~/nemoclaw-config/restore-coredns.sh
```

---

## 10. 進度表

| Phase | 項目 | 狀態 | Commit/備注 |
|-------|------|------|------------|
| P1 | Inference Router | ✅ | |
| P1 | GB10 連線 | ✅ | |
| P1 | OpenShell Policy | ✅ | |
| P2 | Plugin 整合 | ✅ | 6ebea02 |
| B方案 | image bug 修正 | ✅ | 2dfab79 |
| P3 | CoreDNS 持久化 | ✅ | 1bffd63 |
| P3 | ceclaw CLI v0.1.0 | ✅ | c412038 |
| P4 | Smart Routing | ✅ | |
| P4 | 多後端燒機 200 輪 | ✅ | 3bac2a5 |
| P5 | Chain Audit Log | ✅ | 40ac82a |
| P5 | E方案 qwen3-nothink | ✅ | 9d213b3 |
| P5 | 燒機 2000 輪 | ✅ | 2000/2000 100% |
| GB10 | Qwen3.5-122B 切換 | ✅ | POC 主力確認 |
| GB10 | 開機自啟 systemd | ✅ | |
| GB10 | GLM-5 Turbo 評審 | ✅ | 8/8 |
| **P0-2** | **Role 相容性** | ✅ | ada85a7 |
| **P0-3** | **history-limit 預設化** | ✅ | 903e8cc |
| **P0-1** | **身份白標化** | ✅ | 4c1e888 |
| **P0-4a** | **SearXNG 自架** | ✅ | cf44a1f |
| **context** | **32768 修正** | ✅ | db24708 |
| **壓測** | **30題不崩潰** | ✅ | |
| P0-4b | Router 攔截 web_search | ⬜ | P1 再做 |
| P1 | Qwen2.5-72B 評估 | ⬜ | P0後 |
| P6 | NemoClaw drop-in 驗證 | ⬜ | P0後 |
| P7 | Skill 測試 | ⬜ | |
| P8 | UX 升級（onboard 自動化）| ⬜ | |

完成：43/52 ✅ | 待做：9項 ⬜

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
- ZengboJames GB10 參考 repo: https://github.com/ZengboJamesWang/Qwen3.5-35B-A3B-openclaw-dgx-spark
- GLM-5 Turbo（督察）: OpenRouter → zhipuai/glm-5-turbo

---

*CECLAW — Secure local AI agents, your inference, your rules.*  
*總工: Kent | 軟工: 下個對話 Claude | 督察: GLM-5 Turbo*  
*文件版本: v4.1 | 日期: 2026-03-22*  
*P1✅ P2✅ B方案✅ P3✅ P4✅ P5✅ GB10✅ P0全✅ | 下一步: P1→P6 | 最新commit: db24708*
