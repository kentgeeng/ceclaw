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
│   ├── openclaw.plugin.json  # ⚠️ 需加 configSchema（B方案#1）
│   ├── package.json          # ⚠️ 需修3處（B方案#2/#3/#5）
│   └── tsconfig.json
├── sandbox/
│   ├── Dockerfile            # ✅ 完成
│   └── ceclaw-start.sh       # ⚠️ 有 ${VAR} 轉義 bug（B方案#4）
└── config/
    └── ceclaw-policy.yaml    # ✅ 格式正確，正常運作
```

### 設定檔
```
~/.ceclaw/ceclaw.yaml         # Router 設定檔（master，不可修改）
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

### P2 Plugin 整合測試 ✅（2026-03-20 完成，commit: 6ebea02）
- openclaw TUI 顯示 `local/minimax` ✅
- MiniMax 回應正常 ✅
- Router log 確認流量 `gb10-llama → 200` ✅
- ⚠️ **目前是 A 方案（sandbox 內手動修正）。B 方案 rebuild image 尚未完成。**
- ⚠️ 重建 sandbox 後需要重走手動修正步驟，直到 B 方案完成為止。

### Sandbox Image
- `ghcr.io/kentgeeng/ceclaw-sandbox:latest`（已推上 ghcr.io，public）
- ⚠️ image 有 5 個已知問題待 B 方案 rebuild 修正

---

## 4. ⚠️ B 方案待做清單（下個對話第一件事）

**這 5 個修正必須先完成，才能 rebuild image，否則重建 sandbox 每次都要手動 debug。**

| # | 檔案 | 問題 | 修法 |
|---|------|------|------|
| 1 | `plugin/openclaw.plugin.json` | 缺 `configSchema` 欄位，gateway 報 config invalid | 加 `"configSchema": {}` |
| 2 | `plugin/package.json` | `openclaw.extensions` 是 flat key，openclaw 讀不到 | 改成巢狀 `"openclaw": {"extensions": ["./dist/index.js"]}` |
| 3 | `plugin/package.json` | dependencies 非空，sandbox 擋外網 npm 失敗 | 清空 `dependencies` 和 `devDependencies` |
| 4 | `sandbox/ceclaw-start.sh` | `\${VAR}` 轉義 bug，python3 NameError | 用 heredoc 或單引號修正 |
| 5 | `plugin/package.json` | `name` 是 `ceclaw-plugin`，與 manifest id `ceclaw` 不一致 | 改成 `"name": "ceclaw"` |

B 方案完成後執行順序：
```bash
cd ~/ceclaw/plugin && npm run build
docker build -t ghcr.io/kentgeeng/ceclaw-sandbox:latest ./sandbox
docker push ghcr.io/kentgeeng/ceclaw-sandbox:latest
# 重建 sandbox 驗證
openshell sandbox delete ceclaw-agent
openshell sandbox create --name ceclaw-agent \
  --from ghcr.io/kentgeeng/ceclaw-sandbox:latest \
  --policy ~/ceclaw/config/ceclaw-policy.yaml --keep
# 確認 plugin 自動載入，不需要手動修正
```

---

## 5. 關鍵技術知識（踩坑記錄）

### Plugin 安裝踩坑（2026-03-20）

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

**坑#7**: `ceclaw-start.sh` 裡 python3 -c 字串中 `\${ROUTER_HOST}` 在 image build 時反斜線被吃掉，執行時炸 `NameError`。

**坑#8**: openclaw gateway 在 container 內不能用 systemd，必須前景執行 `openclaw gateway`。不能用 `openclaw gateway restart`。

**坑#9**: MiniMax 冷啟動慢，第一個 request 可能超時（30s）。`timeout_local_ms` 可考慮調高到 60000。

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

### CoreDNS（重開機後消失）
```bash
bash ~/nemoclaw-config/restore-coredns.sh
```

---

## 6. TODO List

### 立刻做（下個對話第一件事）
- [ ] **B 方案：修 5 個問題 → rebuild image → 重建 sandbox 驗證**（見第 4 節）

### P3（B方案完成後）
- [ ] CoreDNS patch 持久化（systemd 開機腳本）
- [ ] `ceclaw` CLI（`onboard`/`connect`/`status`）
- [ ] 自動 Approve policy（不需要 TUI）

### P4/P5
- [ ] 多後端支援（vLLM / Ollama / SGLang）
- [ ] 雲端降級完整測試
- [ ] Streaming 完整測試
- [ ] `registerCommand` bug 修正（坑#5）
- [ ] `timeout_local_ms` 調高到 60000

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

# sandbox 內（plugin 操作）
openclaw config set gateway.mode local
openclaw gateway          # 前景執行，不能用 restart
openclaw tui              # 另開 terminal 執行

# CoreDNS restore
bash ~/nemoclaw-config/restore-coredns.sh

# Plugin 重新編譯
cd ~/ceclaw/plugin && npm run build
```

---

## 8. 設定檔內容

### `~/.ceclaw/ceclaw.yaml`（master，不可直接修改）
```yaml
version: 1
router:
  listen_host: "0.0.0.0"
  listen_port: 8000
  tls: false
  reload_on_sighup: true
inference:
  strategy: local-first
  timeout_local_ms: 30000   # 待調高到 60000
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
# 1. CoreDNS
bash ~/nemoclaw-config/restore-coredns.sh

# 2. Router 確認
sudo systemctl status ceclaw-router

# 3. 重建 sandbox
openshell sandbox create --name ceclaw-agent \
  --from ghcr.io/kentgeeng/ceclaw-sandbox:latest \
  --policy ~/ceclaw/config/ceclaw-policy.yaml --keep

# 4. ⚠️ B方案未完成前：進 sandbox 手動設定 openclaw.json（見第4節）
```

---

## 10. 注意事項

1. **零硬編碼原則**：任何 IP/port/model name/key 不得寫死在程式碼，全部讀設定檔
2. **每步 commit**：`git add -A && git commit -m "..."`
3. **不改 master files**：`~/.ceclaw/ceclaw.yaml` 是 master
4. **SOP-002**：每次動手前先說意圖，等 Kent 確認
5. **不停 Router 傳檔**：用 http server 傳檔後記得 `sudo systemctl start ceclaw-router`
6. ⚠️ **GitHub token 已曝光**：確認已 revoke → https://github.com/settings/tokens
7. ⚠️ **NVIDIA API key 已曝光**：確認已 revoke → https://build.nvidia.com/settings/api-keys

---

## 11. 相關連結

- OpenShell docs: https://docs.nvidia.com/openshell/latest/
- NemoClaw GitHub: https://github.com/NVIDIA/NemoClaw
- CECLAW sandbox image: ghcr.io/kentgeeng/ceclaw-sandbox:latest
- Kent GitHub: kentgeeng

---

*CECLAW — Secure local AI agents, your inference, your rules.*  
*總工: Kent | 軟工: 下個對話 Claude | 文件版本: v2 | 日期: 2026-03-20*  
*P1 ✅ P2 ✅ | 下一步: B方案 rebuild image → P3 | commit: 6ebea02*
