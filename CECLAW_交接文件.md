# CECLAW 專案交接文件 v4.0
## 給下一個對話的軟工 + 總工角色說明

**總工（Kent）**：35年工程經驗，ZOE AI Digital Twin 作者，做決策、設計審核  
**軟工（下個對話）**：負責實作、測試、debug，遇困難問總工  
**原則**：SOP-002 — 每次動手前說意圖，等 Kent 確認；每步完成後 commit  
**督察**：GLM-5 Turbo（OpenRouter）— 品質審查，$0.12/次，CP值極高

---

## ⚠️ 本次對話重要進展摘要（v3.9 → v4.0）

### 已完成 ✅

1. **GB10 模型切換完成**
   - 淘汰：MiniMax Q3_K_XL（OOM）、MiniMax IQ2_M（日文崩潰、Q4空白）
   - 確認：**Qwen3.5-122B Q4_K_M** 為 POC 主力後端
   - GLM-5 Turbo 評審：8/8 ✅，超出預期

2. **GB10 systemd 開機自啟** ✅
   - service: `/etc/systemd/system/llama-server.service`
   - 描述已改為：`LLaMA Server (Qwen3.5-122B)`
   - ExecStart: `~/start_llama.sh`
   - 重開機驗證通過

3. **燒機 2000 輪 100%** ✅
   - 第1輪：1000/1000，fast avg=1153ms，main avg=24619ms
   - 第2輪：1000/1000，fast avg=1160ms，main avg=25036ms
   - Audit verify：2900 條記錄，鏈完整

4. **雙模型比較測試完成** ✅
   - 10題標準測試 + 8題高難度測試
   - GLM-5 Turbo head-to-head 評審
   - 結論：Qwen3.5 勝，MiniMax IQ2_M 淘汰

5. **Qwen2.5-72B Q4_K_M 下載完成** ✅
   - 路徑：`~/Qwen2.5-72B/Qwen2.5-72B-Instruct-Q4_K_M.gguf`
   - 大小：47.4GB（單檔）
   - 尚未測試，備選方案

### 新發現問題（P0 待修）🔴

1. **坑#19：身份洩漏 100%** — 最高優先
   - `你是誰` → 100% 回「我是通義千問/阿里巴巴」
   - 簡繁混用嚴重，企業場景不可接受
   - 修法：system prompt 白標化（雙 Path）

2. **坑#20：Context 膨脹 → session 發瘋**
   - session JSONL 膨脹到 470KB → 模型發瘋
   - 修法：`openclaw.json` 加 `memory.qmd.limits.maxInjectedChars: 8000`

3. **坑#21：history-limit 沒有預設**
   - 用戶需要手動帶 `--history-limit 20`，不實際
   - 修法：`ceclaw.py` 的 TUI 呼叫預設加此參數

4. **坑#22：web_search 每次都 call Brave API**
   - 所有 prompt 都嘗試觸發 web_search
   - 修法候選：SearXNG 自架（免費）或 Brave API key
   - 注意：中文 locale 送 `zh` 會 422，要送 `zh-hant`

5. **坑#18 升級：Role 相容性**
   - openclaw 送 `developer`/`toolResult` role
   - Qwen3.5 chat template 不認識 → HTTP 500
   - 參考：ZengboJamesWang/Qwen3.5-35B-A3B-openclaw-dgx-spark
   - 注意：proxy 方案是**下下策**，先試 openclaw.json 設定解決

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
- 備份: `~/start_llama.sh.bak`, `~/start_llama.sh.bak2`, `~/start_llama.sh.bak3`

**⚠️ 重要硬體特性（GB10）：**
- 統一記憶體架構，`nvidia-smi` 顯示 N/A 是正常的
- 使用 DGX Dashboard（localhost:11000）監控記憶體
- Blackwell compute capability 12.1，llama.cpp 已支援
- Qwen3.5-122B 佔 ~86GB，接近極限（不是穩定區間）
- Qwen2.5-72B 佔 ~60GB，真正的穩定區間
- `--parallel 2` = 2個推論 slot，第3個排隊等（不是TCP連線數）

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

**Qwen2.5-72B 啟動腳本（備用，尚未測試）：**
```bash
#!/bin/bash
/home/zoe_gb/llama.cpp/build/bin/llama-server \
  --model /home/zoe_gb/Qwen2.5-72B/Qwen2.5-72B-Instruct-Q4_K_M.gguf \
  --alias minimax --host 0.0.0.0 --port 8001 \
  --ctx-size 32768 --parallel 2 \
  --flash-attn on --n-gpu-layers 99 --threads 20 \
  --cache-type-k q4_0 --cache-type-v q4_0 \
  --temp 0.7 --top-p 0.9 --top-k 40 --min-p 0.0 --jinja
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

---

## 2. 專案檔案結構

```
~/ceclaw/
├── .venv/                    # Python venv
├── .gitignore
├── ceclaw-router.service     # systemd service（已 enable）
├── ceclaw_monitor.sh         # 監控腳本（crontab 每5分鐘）
├── ceclaw.py                 # ceclaw CLI v0.1.0（symlink: /usr/local/bin/ceclaw）
├── burnin_routing.sh         # 燒機腳本（E方案版，sandbox 內跑）
├── burnin_multi.sh           # 多後端燒機腳本
├── model_compare.sh          # 模型比較腳本（10題，CSV輸出）
├── model_compare_hard.sh     # 高難度模型比較（8題，JSON輸出）
├── qwen35_full_output.sh     # 完整內容輸出腳本（供 GLM-5 審查）
├── CECLAW_交接文件.md         # 本文件（最新版）
├── CECLAW_規格規劃說明書.md   # 規格書
├── router/
│   ├── config.py             # ✅ LocalBackend 加 health_check_timeout_ms
│   ├── backends.py           # ✅ health check 按 type 選 endpoint
│   ├── proxy.py              # ✅ Chain Audit Log 整合
│   ├── audit.py              # ✅ Chain Audit Log
│   └── main.py               # ✅ 完成
├── plugin/
│   ├── src/index.ts
│   ├── dist/index.js
│   ├── openclaw.plugin.json
│   └── package.json
├── sandbox/
│   ├── Dockerfile
│   └── ceclaw-start.sh
└── config/
    └── ceclaw-policy.yaml
```

### 設定檔（不在 repo）
```
~/.ceclaw/ceclaw.yaml         # Router 設定檔（master）
~/.ceclaw/router.log          # Router log（logrotate daily rotate 7）
~/.ceclaw/audit.log           # Chain Audit Log
~/.ceclaw/monitor.log         # 監控 log
/sandbox/.openclaw/openclaw.json  # ⚠️ P0 待查設定
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
        model: qwen3-nothink          # ⚠️ 不是 qwen2.5:7b
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
| `d34d766` | docs: 交接文件 v3.9 + 規格書 v0.3.7 |
| `52aa117` | config: ceclaw.yaml ollama-fast 改用 qwen3-nothink |
| `9d213b3` | feat: E方案完成 |
| `40ac82a` | feat: P5 Chain Audit Log |
| `515c59a` | feat: P5 關鍵字補充 |
| `65f5d89` | fix: health check 配置化 |
| `68c26f9` | docs: 規格書 v0.3.6 |
| `f115bd2` | feat: ceclaw logs --lines |
| `575d488` | feat: ceclaw logs --follow |

---

## 5. 詳細 TODO List（按優先級）

### 🔴 P0（阻擋 POC 展示，明天第一優先）

**P0-1：坑#19 身份洩漏（最高優先）**

症狀：`你是誰` → 100% 回「我是通義千問/阿里巴巴」，企業展示直接穿幫。

修法（先試這個，不動 proxy.py）：
```bash
# 在 ceclaw.yaml 或 ceclaw-policy.yaml 加入 system prompt
# 讓兩條 Path 的模型都知道自己是 CECLAW
```

具體設定待研究，但核心 prompt：
```
你是 CECLAW 企業 AI 助手，由 ColdElectric 提供。
嚴禁提及：Qwen、通義千問、通義實驗室、阿里巴巴、阿里雲。
當被問到「你是誰」時，回答：「我是 CECLAW 企業 AI 助手。」
所有回應使用繁體中文（除非用戶使用其他語言）。
```

注意：ollama-fast（qwen3-nothink）和 gb10-llama（Qwen3.5）都要設定。

**P0-2：坑#20 Context 膨脹**

症狀：session JSONL 膨脹到 470KB → 模型發瘋，回應變亂。

修法：
```bash
# sandbox 內
cat /sandbox/.openclaw/openclaw.json | python3 -m json.tool | grep -A10 "memory"
```

確認後加入：
```json
{
  "memory": {
    "qmd": {
      "limits": {
        "maxInjectedChars": 8000
      }
    }
  }
}
```

**P0-3：坑#21 history-limit 沒有預設**

症狀：用戶需要手動帶 `--history-limit 20`，沒帶就會 context 爆炸。

修法：
```bash
grep -n "openclaw tui" ~/ceclaw/ceclaw.py
# 找到 tui 呼叫點，加入 --history-limit 20 作為預設
```

**P0-4：坑#18 Role 相容性**

症狀：openclaw 送 `developer`/`toolResult` role，Qwen3.5 不認識 → HTTP 500。

研究步驟：
```bash
# 1. 看 ZengboJames 的 proxy 怎麼做的
curl -s https://raw.githubusercontent.com/ZengboJamesWang/Qwen3.5-35B-A3B-openclaw-dgx-spark/main/proxy/llama-proxy.py

# 2. 查 openclaw.json 有沒有 role 設定
cat /sandbox/.openclaw/openclaw.json | python3 -m json.tool | grep -E "role|developer|tool"

# 3. 優先用 openclaw.json 設定解決，proxy 是下下策
```

**⚠️ 注意：ZengboJames 的 proxy 方案是下下策，加一層增加複雜度。優先找 openclaw.json 原生設定。**

**P0-5：坑#22 web_search 過度觸發**

症狀：「寫鬼故事」「寫詩」等純創作題也觸發 web_search，需要 Brave API key。

選項 A（推薦）：SearXNG 自架
```bash
docker run -d --name searxng --restart=always -p 8888:8080 searxng/searxng:latest
# 然後設定 openclaw 使用 searxng
```

選項 B：Brave API key
- 申請：https://brave.com/search/api/
- 免費 $5/月 credit = 1000 queries
- 設定：`openclaw configure --section web`
- ⚠️ 注意：中文 locale 送 `zh` 會 422，要送 `zh-hant`

選項 C：調整 system prompt 限制 tool-use 時機

**P0 修完後必做：TUI 測試驗證**
```bash
openshell sandbox connect ceclaw-agent
openclaw tui --session fresh-$(date +%s) --history-limit 20
# 測試：你是誰 / 寫首詩 / 為什麼天空是藍色的
```

---

### 🟡 P1（Qwen2.5-72B 評估）

**為什麼要評估 Qwen2.5-72B？**

Qwen3.5-122B 在 GB10 是極限操作（~86GB/128GB），不是穩定區間：
- KV cache 成長快（attention 更重）
- 長期負載可能 latency 不穩
- 真正穩定區間是 ~60GB 以下

Qwen2.5-72B Q4_K_M（47GB）才是舒適區：
- 裝完剩 ~68GB KV cache
- 無 reasoning 問題（不是 reasoning 模型）
- tools 成熟穩定

**測試步驟：**
```bash
# GB10 上
sudo systemctl stop llama-server
cat > ~/start_llama.sh << 'EOF'
#!/bin/bash
/home/zoe_gb/llama.cpp/build/bin/llama-server \
  --model /home/zoe_gb/Qwen2.5-72B/Qwen2.5-72B-Instruct-Q4_K_M.gguf \
  --alias minimax --host 0.0.0.0 --port 8001 \
  --ctx-size 32768 --parallel 2 \
  --flash-attn on --n-gpu-layers 99 --threads 20 \
  --cache-type-k q4_0 --cache-type-v q4_0 \
  --temp 0.7 --top-p 0.9 --top-k 40 --min-p 0.0 --jinja
EOF
chmod +x ~/start_llama.sh
sudo systemctl start llama-server

# 跑 8 題評測
bash ~/Downloads/qwen35_full_output.sh minimax 2>&1 | tee /tmp/qwen25_full.txt
# copy 給 GLM-5 Turbo 審查（督察 prompt 在文件第 6 節）
```

---

### 🟢 P2（P0修完後）

- **P6**：NemoClaw drop-in 驗證（等 P0 全修完）
- **P7**：OpenClaw Skill 相容性測試（A級10個優先）
- **analyze_burnin.py**：燒機數據自動分析腳本
- **tokens ?/131k 顯示修正**：context window 顯示不正確

---

## 6. 模型比較結果（GLM-5 Turbo 評審）

### 測試環境
- 硬體：NVIDIA DGX Spark (GB10)，128GB 統一記憶體
- llama.cpp build: 8400 (cf23ee244)
- 測試腳本：`model_compare.sh`（10題）+ `model_compare_hard.sh`（8題）

### 結論對比表

| 指標 | Qwen3.5-122B Q4_K_M | MiniMax IQ2_M |
|------|:-------------------:|:-------------:|
| 標準10題 | 9/10 ✅（1題 max_tokens 問題）| 8/10 |
| 8題GLM評審 | **8/8 ✅** | **1✅/5⚠️/2❌** |
| 速度 | 22 t/s | 28 t/s |
| 日文品質 | ✅ 母語級 | ❌ 俄/中/韓混入 |
| Q4質數證明 | ✅ 零瑕疵 | ❌ content=0，等2分鐘空白 |
| 多語言穩定 | ✅ | ❌ |
| 燒機 2000 輪 | ✅ 100% | 未完整測試 |

**GLM-5 Turbo 結論：Qwen3.5-122B 適合，且超出預期。MiniMax IQ2_M 不建議。**

### MiniMax IQ2_M 三個致命問題
1. Thinking token 吃光 → content=0（Q4質數：143秒，空白）
2. 日文崩潰：俄/中/韓文混入同一篇文章
3. content 深度只有 Qwen 的 55%

### Qwen3.5-122B 極小瑕疵（GLM指出）
- Hystrix 過時（應用 Resilience4j）
- Redis CP/AP 未細分
- Ribbon 過時（應用 Spring Cloud LoadBalancer）
- 繁體中文 Q5 有一個簡體字「执行力」

---

## 7. 關鍵技術知識（踩坑記錄）

**坑#1**: `/opt/ceclaw` 唯讀，需 cp 出來修改。

**坑#2**: `openclaw.extensions` 必須巢狀格式。

**坑#3**: sandbox 擋外網，npm install 會 E403。

**坑#4**: `openclaw.plugin.json` 必須有 `configSchema`。

**坑#5（無解）**: `registerCommand` openclaw 2026.3.11 不支援此 API。

**坑#6**: plugin name/id/目錄名三者必須一致。

**坑#7**: `ceclaw-start.sh` 轉義 bug，用 heredoc + os.environ 修正。

**坑#8**: openclaw gateway 必須前景執行，不能 systemd。

**坑#9**: MiniMax 冷啟動慢，timeout 已調高到 60000。

> ⚠️ **坑#10（關鍵）**: openclaw undici `EnvHttpProxyAgent` experimental，不要改 baseUrl 為 IP 或清 proxy 環境變數。保持 `baseUrl: http://host.openshell.internal:8000/v1`。

**坑#11（無解）**: TUI 底部 `local/minimax` 寫死。

**坑#12（無解）**: OpenShell auto-approve 無 CLI 指令，安全設計。

**坑#13**: openclaw TUI 預設用 `main` session，歷史累積後 replay 造成發瘋。
正式解法：`openclaw tui --history-limit 20`
根本解法：P0-3（預設化）

**坑#14（已解）**: MiniMax 228B reasoning 無限生成 → OOM。已換 Qwen3.5-122B。

**坑#15**: GB10 llama-server 載入大模型需要幾分鐘，記憶體使用量峰值後下降是正常的。

**坑#16**: qwen3-nothink 偶爾有 reasoning 殘留（約 11-12% 在 `tell me a joke`）。

**坑#17**: 燒機腳本 bash `$()` 變數有大小限制，用 tmpfile。

**坑#18（P0）**: openclcaw Role 相容性問題，`developer`/`toolResult` Qwen3.5 不認識。

**坑#19（P0）**: 身份洩漏 100%，`你是誰` → 通義千問/阿里巴巴，需白標化。

**坑#20（P0）**: session JSONL 膨脹到 470KB → 模型發瘋。

**坑#21（P0）**: `--history-limit 20` 沒有預設，用戶需要手動帶。

**坑#22（P0）**: web_search 過度觸發，所有 prompt 都嘗試搜尋。
- 中文 locale 送 `zh` 會 422，要送 `zh-hant`

---

## 8. Debug SOP

### Router 問題
```bash
# 1. 基本狀態
ceclaw status
curl http://localhost:8000/ceclaw/status | python3 -m json.tool

# 2. 詳細 log（journalctl，因為 router.log 可能為空）
sudo journalctl -u ceclaw-router -f

# 3. 重啟
sudo systemctl restart ceclaw-router
sudo systemctl status ceclaw-router
```

### GB10 問題
```bash
# 確認 GB10 活著
curl -s --max-time 10 http://192.168.1.91:8001/v1/models | python3 -m json.tool | grep n_vocab
# n_vocab: 248320 = Qwen3.5 ✅
# n_vocab: 200064 = MiniMax ❌（不應該出現）

# GB10 記憶體狀態（用 DGX Dashboard：localhost:11000）
# 或 ssh 後看
ssh zoe_gb@192.168.1.91 'free -h'

# GB10 llama-server 進程
ssh zoe_gb@192.168.1.91 'sudo systemctl status llama-server'

# GB10 崩潰處理
ssh zoe_gb@192.168.1.91 'sudo systemctl restart llama-server'
# 等幾分鐘載入（Qwen3.5 70GB 需要時間）
```

### TUI 問題
```bash
# session 發瘋 → 開新 session
openclaw tui --session fresh-$(date +%s) --history-limit 20

# 503 All backends unavailable
# 1. 先確認 Router 狀態
curl http://localhost:8000/ceclaw/status
# 2. 確認 GB10
curl -s http://192.168.1.91:8001/health
# 3. 通常是 session 歷史問題，開新 session
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

### Smart Routing 驗證
```bash
# sandbox 內
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

## 9. 燒機腳本說明

### burnin_routing.sh（主要燒機腳本）
位置：`~/ceclaw/burnin_routing.sh`（也在 sandbox `/tmp/burnin_routing.sh`）

用法：
```bash
# sandbox 內
bash /tmp/burnin_routing.sh 200   # 200輪
bash /tmp/burnin_routing.sh 1000  # 1000輪
```

特點：
- 70% fast（含 tools schema）/ 30% main
- 使用 tmpfile 避免 bash 變數截斷
- 燒機完成後提示執行 audit verify

### model_compare.sh（10題標準對比）
```bash
# GB10 本機跑
bash ~/Downloads/model_compare.sh minimax /tmp/result_model.csv
```

### model_compare_hard.sh（8題高難度）
```bash
bash ~/Downloads/model_compare_hard.sh minimax /tmp/result_hard.csv
```

### qwen35_full_output.sh（完整內容輸出，供 GLM-5 審查）
```bash
bash ~/Downloads/qwen35_full_output.sh minimax 2>&1 | tee /tmp/model_full.txt
# copy 給 GLM-5 Turbo
```

---

## 10. GLM-5 Turbo 督察使用指南

### 督察 Prompt
```
你是一位資深AI系統評審員，負責評估一個本地部署的LLM（運行在企業內網GPU伺服器上）的輸出品質。

這個模型將作為 OpenClaw（NVIDIA企業AI Agent框架）的主推論後端，直接面對工程師和企業用戶。

硬體環境：NVIDIA DGX Spark (GB10)，128GB 統一記憶體
模型：[填入模型名稱]，[填入量化等級]
POC 階段，量產走 vLLM + 滿級模型

評分：✅ 通過 / ⚠️ 勉強 / ❌ 不通過
```

### 費用參考
- GLM-5 Turbo 約 $0.12 / 次完整評審
- 透過 OpenRouter 使用

---

## 11. 路由架構說明

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
     ├── needs_reasoning(query)=True → gb10-llama（Qwen3.5-122B）
     │   觸發關鍵字：系統設計、架構設計、為什麼、分析、
     │              system design、calculate、why...
     │              実装、違い...（日文）
     │
     └── needs_reasoning=False → ollama-fast（qwen3-nothink）
          │
          └── ollama-fast 掛掉 → gb10-llama
               │
               └── gb10-llama 掛掉 → ollama-backup（qwen3:8b）
                    │
                    └── 全掛 → cloud fallback
```

---

## 12. 技術債

1. **Session replay**（坑#13）— P0 處理中
2. **GB10 systemd 描述名稱** — 已改為 Qwen3.5-122B ✅
3. **registerCommand**（坑#5）— openclaw 不支援，無解
4. **undici EnvHttpProxyAgent** — experimental，長期關注
5. **qwen3-nothink reasoning 殘留** — 11-12% 洩漏率
6. **difference between 冗餘** — 關鍵字重複，可清理
7. **身份洩漏**（坑#19）— P0 處理中
8. **Context 膨脹**（坑#20）— P0 處理中
9. **web_search 過度觸發**（坑#22）— P0 處理中
10. **tokens ?/131k 顯示** — context window 顯示不正確，待查
11. **MiniMax Q3_K_XL 95GB 未清理** — `~/MiniMax-M2.5-GGUF/UD-Q3_K_XL/`，可刪

---

## 13. 關鍵指令速查

```bash
# CECLAW CLI
ceclaw status
ceclaw connect
ceclaw logs --follow
ceclaw logs --lines 50
ceclaw start / stop / onboard

# Router 管理
sudo systemctl status/restart ceclaw-router
sudo journalctl -u ceclaw-router -f
curl http://localhost:8000/ceclaw/status
curl http://localhost:8000/ceclaw/reload  # 熱重載（POST）

# Ollama
ollama list
ollama run qwen3-nothink "你是誰"

# GB10 管理
ssh zoe_gb@192.168.1.91
sudo systemctl status llama-server
sudo systemctl restart llama-server
curl -s http://192.168.1.91:8001/v1/models | python3 -m json.tool | grep n_vocab

# 燒機（sandbox 內）
bash /tmp/burnin_routing.sh 200

# Audit verify（pop-os）
python3 -c "import sys; sys.path.insert(0,'/home/zoe_ai/ceclaw'); from router.audit import verify; ok,msg=verify(); print(msg)"

# OpenShell sandbox
openshell sandbox list
openshell sandbox connect ceclaw-agent
openclaw tui --session fresh-$(date +%s) --history-limit 20
openshell term

# CoreDNS restore
bash ~/nemoclaw-config/restore-coredns.sh

# 模型下載（HF，GB10 上）
HF_HUB_DISABLE_XET=1 hf download <repo> --include "<pattern>" --local-dir <dir>
```

---

## 14. 進度表

| Phase | 項目 | 狀態 | Commit/備注 |
|-------|------|------|------------|
| P1 | Inference Router | ✅ | |
| P1 | GB10 連線 | ✅ | |
| P1 | OpenShell Policy | ✅ | |
| P1 | 燒機 200 輪 | ✅ | |
| P2 | Plugin 整合 | ✅ | 6ebea02 |
| B方案 | image bug 修正 | ✅ | 2dfab79 |
| P3 | CoreDNS 持久化 | ✅ | 1bffd63 |
| P3 | ceclaw CLI v0.1.0 | ✅ | c412038 |
| P4 | Smart Routing | ✅ | |
| P4 | 多後端燒機 200 輪 | ✅ | 3bac2a5 |
| P5 | Chain Audit Log | ✅ | 40ac82a，2900條鏈完整 |
| P5 | E方案 qwen3-nothink | ✅ | 9d213b3 |
| P5 | Health Check 配置化 | ✅ | 65f5d89 |
| P5 | 燒機 2000 輪 | ✅ | 2000/2000 100% |
| **GB10** | **Qwen3.5-122B 切換** | ✅ | **POC 主力確認** |
| **GB10** | **開機自啟 systemd** | ✅ | |
| **GB10** | **GLM-5 Turbo 評審** | ✅ | **8/8 超出預期** |
| **GB10** | **Qwen2.5-72B 下載** | ✅ | **47GB，尚未測試** |
| **P0** | **身份洩漏白標化** | 🔴 | **坑#19，明天第一件事** |
| **P0** | **Context 膨脹修復** | 🔴 | **坑#20** |
| **P0** | **history-limit 預設化** | 🔴 | **坑#21** |
| **P0** | **Role 相容性** | 🔴 | **坑#18** |
| **P0** | **web_search 設定** | 🔴 | **坑#22，SearXNG 推薦** |
| P5 | 雲端降級測試 | ⏸️ | 待 API key |
| P6 | NemoClaw drop-in | ⬜ | P0 修完再議 |
| P7 | Skill 相容性測試 | ⬜ | |
| P8 | UX 升級 | ⬜ | |

---

## 15. 相關連結

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
*文件版本: v4.0 | 日期: 2026-03-22*  
*P1✅ P2✅ B方案✅ P3✅ P4✅ P5✅ GB10切換✅ | 下一步: P0修復→P6 | commit: d34d766*
