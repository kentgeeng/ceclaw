# CECLAW 專案交接文件
## 給下一個對話的軟工 + 總工角色說明

**總工（Kent）**：35年工程經驗，ZOE AI Digital Twin 作者，做決策、設計審核  
**軟工（下個對話）**：負責實作、測試、debug，遇困難問總工  
**原則**：SOP-002 — 每次動手前說意圖，等 Kent 確認；每步完成後 commit

---

## 0. 專案文件索引

| 文件 | 路徑 | 說明 |
|------|------|------|
| **本文件** | `~/ceclaw/CECLAW_交接文件.md` | 軟工交接、環境、指令速查 |
| **規格規劃說明書** | `~/ceclaw/CECLAW_規格規劃說明書.md` | 架構設計、NemoClaw 對比、路線圖 |
| **重灌 SOP** | `~/ceclaw/CECLAW_重灌SOP.md` | 從零開始到端到端通的完整步驟 |

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
- K3s in Docker container (ID: `64a2b20468a5`，重建後會變)
- 取得當前 ID: `docker ps --format "{{.ID}}" | head -1`
- Gateway endpoint: `https://127.0.0.1:8080`
- Sandbox image: `ghcr.io/kentgeeng/ceclaw-sandbox:latest`（已推上 ghcr.io）
- `host.openshell.internal` = NV 寫死解析到 `172.17.0.1`（Docker bridge，不可改）

---

## 2. CECLAW 專案位置

```
~/ceclaw/
├── .venv/                        # Python venv（已裝 fastapi/httpx/uvicorn/pyyaml/pydantic）
├── .gitignore
├── pyproject.toml
├── ceclaw-router.service         # systemd service（已 enable）
├── CECLAW_交接文件.md             # 本文件
├── CECLAW_規格規劃說明書.md       # 架構設計文件
├── CECLAW_重灌SOP.md             # 重灌步驟文件
├── router/
│   ├── __init__.py
│   ├── config.py                 # ✅ 完成
│   ├── backends.py               # ✅ 完成
│   ├── proxy.py                  # ✅ 完成
│   └── main.py                   # ✅ 完成
├── plugin/                       # TypeScript openclaw plugin
│   ├── src/index.ts              # ✅ 完成（未整合測試）
│   ├── dist/index.js             # ✅ 已編譯
│   ├── openclaw.plugin.json
│   ├── package.json
│   └── tsconfig.json
├── sandbox/
│   ├── Dockerfile                # ✅ 完成
│   └── ceclaw-start.sh           # ✅ 完成
└── config/
    └── ceclaw-policy.yaml        # ✅ 格式已修正，正常運作
```

### 設定檔
```
~/.ceclaw/ceclaw.yaml                    # Router 設定檔（master，不可修改）
~/.ceclaw/router.log                     # Router log
~/nemoclaw-config/restore-coredns.sh    # CoreDNS 修復腳本
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
- **功能**:
  - 零硬編碼：全部讀 `~/.ceclaw/ceclaw.yaml` + 環境變數
  - 後端健康檢查（啟動 + 每 30 秒）
  - 本地優先，自動降級雲端（Groq → Anthropic → OpenAI → NV）
  - SIGHUP 熱重載
- **Systemd**: `sudo systemctl status ceclaw-router`（已 enable，開機自啟）
- **測試結果**: ✅ 完整端到端驗證通過

### OpenShell Sandbox → Router → GB10（端到端）✅
- sandbox 內 `curl http://host.openshell.internal:8000/ceclaw/status` → 正常回應
- sandbox 內 `/v1/chat/completions` → MiniMax 推論正常回應
- 驗證時間: 2026-03-19

### CECLAW Plugin
- TypeScript，openclaw plugin v1 格式
- Banner 顯示 CECLAW registered / Router URL / Strategy
- 設定 local provider 指向 Router
- 已編譯到 `plugin/dist/index.js`
- **尚未做 Plugin 整合測試**（下個對話的第一件事）

### Sandbox Image
- `ghcr.io/kentgeeng/ceclaw-sandbox:latest`（已推上 ghcr.io，public）
- 基於 `ghcr.io/nvidia/openshell-community/sandboxes/openclaw:latest`
- 包含 CECLAW plugin 和 ceclaw-start.sh

---

## 4. 關鍵技術知識（踩坑記錄）

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

**重要**：
- `network_policies` 是 map，不是 list（不要用 `-`）
- 必須指定 `binaries`，否則 proxy 不知道哪個 process 可用
- 必須指定 `allowed_ips`，否則 proxy 擋內部 IP
- `host.openshell.internal` 被 NV proxy **寫死**解析到 `172.17.0.1`，CoreDNS 改不了它
- Policy 套用後需要在 TUI (`openshell term`) 按 `r` → `A` Approve All

### iptables 網路穿透（已持久化到 /etc/iptables/rules.v4）
```bash
sudo iptables -I FORWARD -s 172.20.0.0/16 -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -I FORWARD -s 10.42.0.0/16 -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -I FORWARD -s 10.200.0.0/16 -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -t nat -A POSTROUTING -s 172.20.0.0/16 -d 172.17.0.1 -j MASQUERADE
sudo iptables -t nat -A POSTROUTING -s 10.42.0.0/16 -d 172.17.0.1 -j MASQUERADE
sudo ufw allow from 172.20.0.0/16 to any port 8000
```

### CoreDNS（重開機後消失，需手動 restore）
```bash
bash ~/nemoclaw-config/restore-coredns.sh
```

---

## 5. TODO List（優先順序）

### 立刻做（下個對話第一件事）
- [ ] **Plugin 整合測試**
  ```bash
  openshell sandbox connect ceclaw-agent
  openclaw plugins install /opt/ceclaw
  # 確認 banner 顯示 CECLAW registered
  openclaw tui
  # 對話測試，確認推論走 CECLAW Router → GB10
  ```

### 之後做
- [ ] CoreDNS patch 持久化（加到 systemd 開機腳本）
- [ ] `ceclaw` CLI（`onboard`/`connect`/`status`）
- [ ] 多後端支援（vLLM / Ollama / SGLang）
- [ ] 雲端降級完整測試（加 GROQ_API_KEY 測試）
- [ ] Streaming 回應支援完整測試

### 已完成
- [x] ~~NVIDIA API key revoke~~ ✅ 2026-03-19
- [x] ~~GitHub token revoke~~ ✅ 2026-03-19（舊 token 已刪，新 `ceclaw-ghcr` token 保留）

---

## 6. 關鍵指令速查

```bash
# Router 管理
sudo systemctl status ceclaw-router
sudo systemctl restart ceclaw-router
tail -f ~/.ceclaw/router.log

# 手動啟動 Router（開發用）
cd ~/ceclaw && source .venv/bin/activate && python3 -m router.main

# Router 測試
curl -s http://localhost:8000/ceclaw/status | python3 -m json.tool
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"minimax","messages":[{"role":"user","content":"hi"}],"max_tokens":50}'

# GB10 測試
curl -s http://192.168.1.91:8001/v1/models | python3 -m json.tool

# OpenShell sandbox
CONTAINER=$(docker ps --format "{{.ID}}" | head -1)
openshell sandbox list
openshell sandbox create --name ceclaw-agent \
  --from ghcr.io/kentgeeng/ceclaw-sandbox:latest \
  --policy ~/ceclaw/config/ceclaw-policy.yaml --keep
openshell sandbox connect ceclaw-agent
openshell sandbox delete ceclaw-agent
openshell policy set ceclaw-agent --policy ~/ceclaw/config/ceclaw-policy.yaml --wait
openshell term   # TUI，按 r 看 pending rules，A approve all

# CoreDNS restore（重開機後執行）
bash ~/nemoclaw-config/restore-coredns.sh

# K3s 診斷
docker exec $CONTAINER kubectl get pod -n openshell
docker exec $CONTAINER kubectl logs -n openshell openshell-0 --tail=30

# Plugin 重新編譯
cd ~/ceclaw/plugin && npm run build
```

---

## 7. 設定檔內容

### `~/.ceclaw/ceclaw.yaml`
```yaml
version: 1
router:
  listen_host: "0.0.0.0"
  listen_port: 8000
  tls: false
  reload_on_sighup: true
inference:
  strategy: local-first
  timeout_local_ms: 30000
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

## 8. 架構說明

```
[openclaw sandbox (K3s pod, 10.42.0.x)]
    ↓ http://host.openshell.internal:8000/v1
    ↓ (OpenShell proxy 10.200.0.1:3128 放行)
    ↓ (iptables FORWARD: 172.20.x → 172.17.0.1)
[CECLAW Inference Router :8000 (systemd on pop-os, 172.17.0.1)]
    ↓ local-first: http://192.168.1.91:8001/v1
[GB10 llama-server (MiniMax-M2.5)]
    fallback ↓ (若 GB10 掛掉或超時)
[Groq / Anthropic / OpenAI / NV Cloud]
```

**關鍵事實**：
- `host.openshell.internal` 被 NV proxy 寫死解析 → 172.17.0.1，無法用 CoreDNS 覆蓋
- policy 需要 `allowed_ips: [172.17.0.1]` + `binaries` 才能放行
- TUI 需要人工 Approve pending rules（或重建 sandbox 時 policy 已 active 則自動）

---

## 9. Debug SOP

### 推論失敗時
1. `curl http://localhost:8000/ceclaw/status` — Router 活著？
2. `curl http://192.168.1.91:8001/v1/models` — GB10 活著？
3. `openshell policy get ceclaw-agent` — policy active version？
4. sandbox 內：`curl -v http://host.openshell.internal:8000/ceclaw/status`
5. TUI：`openshell term` → 選 ceclaw-agent → `r` 看 pending rules → `A` approve
6. `tail -f ~/.ceclaw/router.log`
7. `docker exec $CONTAINER kubectl logs -n openshell openshell-0 --tail=30`

### 重開機後恢復步驟
```bash
# 1. CoreDNS（iptables 已持久化，不需要手動）
bash ~/nemoclaw-config/restore-coredns.sh

# 2. Router 應該已自啟，確認
sudo systemctl status ceclaw-router

# 3. GB10（若未自啟）
ssh zoe_gb@192.168.1.91 "nohup ~/start_llama.sh > ~/llama.log 2>&1 &"

# 4. 重建 sandbox
openshell sandbox create --name ceclaw-agent \
  --from ghcr.io/kentgeeng/ceclaw-sandbox:latest \
  --policy ~/ceclaw/config/ceclaw-policy.yaml --keep
```

---

## 10. 注意事項

1. **零硬編碼原則**：任何 IP/port/model name/key 不得寫死在程式碼，全部讀設定檔
2. **每步 commit**：`git add -A && git commit -m "..."`
3. **不改 master files**：`~/.ceclaw/ceclaw.yaml` 是 master，不能在程式碼裡改它
4. **SOP-002**：每次動手前先說意圖，等 Kent 確認
5. ✅ GitHub token 舊值已 revoke，新 `ceclaw-ghcr` token 保留
6. ✅ NVIDIA API key 已 revoke

---

## 11. 相關連結

- OpenShell docs: https://docs.nvidia.com/openshell/latest/
- NemoClaw GitHub: https://github.com/NVIDIA/NemoClaw
- OpenShell Community: https://github.com/NVIDIA/OpenShell-Community
- CECLAW sandbox image: ghcr.io/kentgeeng/ceclaw-sandbox:latest
- Kent GitHub: kentgeeng

---

*CECLAW — Secure local AI agents, your inference, your rules.*  
*總工: Kent | 軟工: 下個對話 Claude | 日期: 2026-03-19*  
*端到端驗證: ✅ sandbox → Router → GB10 全通*
