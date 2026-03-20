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
- 模型: MiniMax-M2.5-UD-Q3_K_XL (GGUF)
- alias: `minimax`
- 啟動: `~/start_llama.sh`（`--parallel 2`）

### OpenShell（沙盒系統）
- K3s in Docker container (ID 每次重建會變)
- 取得當前 ID: `docker ps --format "{{.ID}}" | head -1`
- Gateway endpoint: `https://127.0.0.1:8080`
- Sandbox image: `ghcr.io/kentgeeng/ceclaw-sandbox:latest`（已推上 ghcr.io）
- `host.openshell.internal` = NV 寫死解析到 `172.17.0.1`（Docker bridge，不可改）

---

## 2. CECLAW 專案位置

```
~/ceclaw/
├── .venv/                    # Python venv（已裝 fastapi/httpx/uvicorn/pyyaml/pydantic）
├── .gitignore
├── pyproject.toml
├── ceclaw-router.service     # systemd service（已 enable）
├── router/
│   ├── __init__.py
│   ├── config.py             # ✅ 完成
│   ├── backends.py           # ✅ 完成
│   ├── proxy.py              # ✅ 完成
│   └── main.py               # ✅ 完成
├── plugin/                   # TypeScript openclaw plugin
│   ├── src/index.ts          # ✅ 完成（registerCommand 暫時 disabled，見坑#5）
│   ├── dist/index.js         # ✅ 已編譯
│   ├── openclaw.plugin.json  # ✅ 已加 configSchema
│   ├── package.json          # ✅ 已修正（name/巢狀/dependencies）
│   └── tsconfig.json
├── sandbox/
│   ├── Dockerfile            # ✅ 完成
│   └── ceclaw-start.sh       # ✅ 已修轉義 bug（heredoc + os.environ）
└── config/
    └── ceclaw-policy.yaml    # ✅ 格式正確，正常運作
```

### 設定檔
```
~/.ceclaw/ceclaw.yaml         # Router 設定檔（master，不在 repo，不可直接修改）
~/.ceclaw/router.log          # Router log
~/nemoclaw-config/restore-coredns.sh  # CoreDNS 修復腳本
```

---

## 3. 已完成的功能 ✅

### CECLAW Inference Router（核心）
- **監聽**: `0.0.0.0:8000`
- **端點**:
  - `GET  /v1/models` — 列出本地後端模型
  - `POST /v1/chat/completions` — 推論（proxy 到本地或雲端）
  - `POST /v1/completions` — 推論
  - `GET  /ceclaw/status` — 狀態查詢
  - `POST /ceclaw/reload` — 熱重載設定
- **功能**: 零硬編碼、後端健康檢查（30s）、本地優先、雲端降級、SIGHUP 熱重載
- **Systemd**: 已 enable，開機自啟
- **燒機**: 200 輪 sandbox → Router → GB10，200/200 HTTP 200 ✅

### P2 Plugin 整合測試 ✅（2026-03-20，commit: 6ebea02）
- openclaw TUI 顯示 `local/minimax` ✅
- MiniMax 回應正常 ✅
- Router log 確認流量 `gb10-llama → 200` ✅

### B方案 rebuild image ✅（2026-03-20，commit: 2dfab79）
- 5 個 image bug 全部修正 ✅
- npm run build → docker build → docker push ✅
- 重建 sandbox 驗證通過 ✅（不需要手動 Step 12）
- timeout_local_ms 調高到 60000 ✅

### P3 CoreDNS 持久化 ✅（commit: 1bffd63）
- `ceclaw-coredns.service` 開機自動 patch

### Sandbox Image
- `ghcr.io/kentgeeng/ceclaw-sandbox:latest`（已推上 ghcr.io，public）
- 重建 sandbox 後自動執行 `ceclaw-start`，無需手動設定

---

## 4. 啟動方式（B方案完成後）

重建 sandbox 後只需兩步：

**Terminal 1（gateway）：**
```bash
openshell sandbox connect ceclaw-agent
# 自動執行 ceclaw-start
# 看到 [gateway] agent model: local/minimax = 成功
```

**Terminal 2（TUI）：**
```bash
openshell sandbox connect ceclaw-agent
openclaw tui
# 底部看到 local/minimax，發訊息確認回應
```

不需要手動設定 openclaw.json。

---

## 5. 關鍵技術知識（踩坑記錄）

**坑#1**: `/opt/ceclaw` 是唯讀的，不能在 sandbox 內直接修改。需要 `cp -r /opt/ceclaw ~/ceclaw-plugin` 後修改再安裝。

**坑#2**: `openclaw plugins install` 讀 `package.json` 的 `openclaw.extensions`，必須是巢狀格式：
```json
"openclaw": {
  "extensions": ["./dist/index.js"]
}
```
不是 flat key `"openclaw.extensions": [...]`

**坑#3**: sandbox 擋外網，`npm install` 會失敗（E403 npmjs.org）。需清空 `dependencies`/`devDependencies`，dist 已編譯不需要重裝。

**坑#4**: `openclaw.plugin.json` 必須有 `configSchema` 欄位，否則 gateway 報 `config is invalid`。

**坑#5**: `registerCommand` 在 openclaw 內部觸發 `TypeError: Cannot read properties of undefined (reading 'trim')`。已暫時 disable。Banner 和 provider 設定正常，只有 `openclaw ceclaw <command>` 子指令不可用。

**坑#6**: plugin `name`（package.json）、manifest `id`（openclaw.plugin.json）、安裝目錄名 三者必須一致，都是 `ceclaw`。

**坑#7**: `ceclaw-start.sh` 裡 python3 -c 字串中 `\${ROUTER_HOST}` 在 image build 時反斜線被吃掉，執行時炸 `NameError`。修法：改用 heredoc（`python3 << 'PYEOF' ... PYEOF`）+ `os.environ.get()` 讀變數。

**坑#8**: openclaw gateway 在 container 內不能用 systemd，必須前景執行 `openclaw gateway`。不能用 `openclaw gateway restart`。

**坑#9**: MiniMax 冷啟動慢，Router `timeout_local_ms: 30000` 太短會先 503。已調高到 60000，解決冷啟動超時問題。

**坑#10**: openclaw 使用 undici `EnvHttpProxyAgent`（experimental），即使設定 `no_proxy` 或清掉 `HTTP_PROXY`，HTTP 請求仍可能走 OpenShell proxy（10.200.0.1:3128）或直接 Connection error。**正確做法**：保持 `baseUrl: http://host.openshell.internal:8000/v1` + `api: openai-completions`，讓請求走 proxy → iptables FORWARD → Router。不要試圖改 baseUrl 為 IP 或清 proxy 環境變數來繞過。

### 傳檔案進 sandbox 的方法
sandbox 只開放 port 8000，傳法：
```bash
# pop-os：停 Router，用 port 8000 開 HTTP server
sudo systemctl stop ceclaw-router
cd /要傳的目錄 && python3 -m http.server 8000

# sandbox：curl 下載
curl -s http://host.openshell.internal:8000/檔名 -o /目標路徑

# pop-os：傳完後重啟 Router（不要忘！）
sudo systemctl start ceclaw-router
```

### OpenShell Policy 正確格式
```yaml
version: 1
network_policies:
  ceclaw_router:
    endpoints:
      - host: host.openshell.internal
        port: 8000
        access: full
        allowed_ips:
          - 172.17.0.1      # NV 寫死，不可改
    binaries:
      - path: /usr/bin/curl
      - path: /usr/bin/node
      - path: /usr/local/bin/openclaw
```

- `network_policies` 是 map，不是 list（不要用 `-`）
- 必須指定 `binaries` + `allowed_ips`，缺一不可

### iptables 網路穿透（已持久化）
```bash
sudo iptables -I FORWARD -s 172.20.0.0/16 -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -I FORWARD -s 10.42.0.0/16 -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -I FORWARD -s 10.200.0.0/16 -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -t nat -A POSTROUTING -s 172.20.0.0/16 -d 172.17.0.1 -j MASQUERADE
sudo iptables -t nat -A POSTROUTING -s 10.42.0.0/16 -d 172.17.0.1 -j MASQUERADE
sudo ufw allow from 172.20.0.0/16 to any port 8000
```
已 `iptables-persistent` 持久化，重開機自動恢復。

### CoreDNS（P3 已持久化）
```bash
# 手動修復（若需要）
bash ~/nemoclaw-config/restore-coredns.sh
# 開機由 ceclaw-coredns.service 自動處理
```

---

## 6. TODO List

### P3 剩餘
- [ ] `ceclaw` CLI（`onboard`/`connect`/`status`）
- [ ] 自動 Approve policy（不需要 TUI）

### P4
- [ ] 多後端支援（vLLM / Ollama / SGLang）

### P5
- [ ] 雲端降級完整測試
- [ ] Streaming 完整測試
- [ ] `registerCommand` bug 修正（坑#5）

---

## 7. 關鍵指令速查

```bash
# Router 管理
sudo systemctl status ceclaw-router
sudo systemctl restart ceclaw-router
tail -f ~/.ceclaw/router.log

# Router 測試
curl -s http://localhost:8000/ceclaw/status | python3 -m json.tool

# GB10 測試
curl -s http://192.168.1.91:8001/v1/models | python3 -m json.tool

# OpenShell sandbox
openshell sandbox list
openshell sandbox create --name ceclaw-agent \
  --from ghcr.io/kentgeeng/ceclaw-sandbox:latest \
  --policy ~/ceclaw/config/ceclaw-policy.yaml --keep
openshell sandbox connect ceclaw-agent
openshell sandbox delete ceclaw-agent
openshell term   # TUI，按 r 看 pending rules，A approve all

# sandbox 內
openclaw tui              # 另開 terminal 執行

# CoreDNS restore（手動）
bash ~/nemoclaw-config/restore-coredns.sh

# Plugin 重新編譯
cd ~/ceclaw/plugin && npm run build
```

---

## 8. 設定檔內容

### `~/.ceclaw/ceclaw.yaml`（master，不在 repo，不可直接修改）
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

## 9. Debug SOP

### 推論失敗時
1. `curl http://localhost:8000/ceclaw/status` — Router 活著？
2. `curl http://192.168.1.91:8001/v1/models` — GB10 活著？
3. sandbox 內：`curl -v http://host.openshell.internal:8000/ceclaw/status`
4. TUI：`openshell term` → 選 ceclaw-agent → `r` 看 pending rules → `A` approve
5. `tail -f ~/.ceclaw/router.log`

### 重開機後恢復步驟
```bash
# 1. CoreDNS（若 ceclaw-coredns.service 未自啟）
bash ~/nemoclaw-config/restore-coredns.sh

# 2. Router 確認（systemd 自啟）
sudo systemctl status ceclaw-router

# 3. 重建 sandbox
openshell sandbox create --name ceclaw-agent \
  --from ghcr.io/kentgeeng/ceclaw-sandbox:latest \
  --policy ~/ceclaw/config/ceclaw-policy.yaml --keep

# 4. 進 sandbox，自動跑 ceclaw-start
# 看到 [gateway] agent model: local/minimax = 完成
```

---

## 10. 注意事項

1. **零硬編碼原則**：任何 IP/port/model name/key 不得寫死在程式碼，全部讀設定檔
2. **每步 commit**：`git add -A && git commit -m "..."`
3. **不改 master files**：`~/.ceclaw/ceclaw.yaml` 是 master，不在 repo
4. **SOP-002**：每次動手前先說意圖，等 Kent 確認
5. **不停 Router 傳檔**：用 http server 傳檔後記得 `sudo systemctl start ceclaw-router`
6. **坑#10**：不要試圖改 baseUrl 為 IP 或清 proxy 環境變數，會讓問題更複雜

---

## 11. 相關連結

- OpenShell docs: https://docs.nvidia.com/openshell/latest/
- NemoClaw GitHub: https://github.com/NVIDIA/NemoClaw
- CECLAW sandbox image: ghcr.io/kentgeeng/ceclaw-sandbox:latest
- Kent GitHub: kentgeeng

---

*CECLAW — Secure local AI agents, your inference, your rules.*  
*總工: Kent | 軟工: 下個對話 Claude | 文件版本: v3 | 日期: 2026-03-20*  
*P1 ✅ P2 ✅ B方案 ✅ P3 CoreDNS ✅ | 下一步: P3 CLI → 自動 Approve | commit: 2dfab79*
