# CECLAW Sandbox 網路設定 SOP
**日期：2026-03-26**
**版本：v1.1**

---

## 背景

三天的根本問題：舊 sandbox image (`ghcr.io/kentgeeng/ceclaw-sandbox:latest`) 內建了奇怪的 network rules，導致 OpenShell TUI 不出現 `[A] Approve All`，所有外網連線被擋死。

**解法：用乾淨的 community base image 建新 sandbox。**

---

## 正確建立 Sandbox 流程

### Step 1：建立新 sandbox

```bash
openshell sandbox create --name <sandbox-name> \
  --from ghcr.io/nvidia/openshell-community/sandboxes/base:latest \
  --policy ~/ceclaw/config/ceclaw-policy.yaml \
  --keep
```

### Step 2：觸發 network rules

sandbox 建好後，在 sandbox 內執行外網連線：

```bash
# ollama (pop-os)
curl -s --max-time 5 http://172.17.0.1:11434/v1/models | head -c 100

# GB10
curl -s --max-time 5 http://192.168.1.91:8001/v1/models | head -c 100

# 外網
curl -s --max-time 5 https://httpbin.org/ip
```

### Step 3：在 OpenShell TUI 按 `[A] Approve All`

MobaXterm → openshell TUI 畫面會出現 pending rules，按 `[A]` 一次全部 approve。

> ⚠️ 私有 IP（172.17.0.1、192.168.1.91）不會出現在 pending，必須在 policy yaml 明確指定（見下方）。

### Step 4：驗證

```bash
# 三個全通才算成功
curl -s --max-time 5 http://172.17.0.1:11434/v1/models | head -c 50
curl -s --max-time 5 http://192.168.1.91:8001/v1/models | head -c 50
curl -s --max-time 5 https://httpbin.org/ip
node -e "require('https').get('https://finance.yahoo.com',r=>console.log('node:',r.statusCode)).on('error',e=>console.error(e.message))"
```

---

## ceclaw-policy.yaml 標準內容

```yaml
version: 1
network_policies:
  ceclaw_router:
    endpoints:
      - host: host.openshell.internal
        port: 8000
        allowed_ips:
          - 172.17.0.1
    binaries:
      - path: /usr/bin/curl
      - path: /usr/bin/node
      - path: /usr/local/bin/openclaw
  ollama_local:
    endpoints:
      - host: "172.17.0.1"
        port: 11434
        allowed_ips:
          - 172.17.0.1
    binaries:
      - path: /usr/bin/curl
      - path: /usr/bin/node
  gb10_llama:
    endpoints:
      - host: "192.168.1.91"
        port: 8001
        allowed_ips:
          - 192.168.1.91
    binaries:
      - path: /usr/bin/curl
      - path: /usr/bin/node
  external_web:
    endpoints:
      - host: "*.yahoo.com"
        port: 443
      - host: "*.google.com"
        port: 443
      - host: "*.twse.com.tw"
        port: 443
      - host: "*.tpex.org.tw"
        port: 443
      - host: "technews.tw"
        port: 443
      - host: "*.github.com"
        port: 443
      - host: "openweathermap.org"
        port: 443
      - host: "*.com"
        port: 443
      - host: "*.tw"
        port: 443
      - host: "*.net"
        port: 443
      - host: "*.org"
        port: 443
      - host: "*.io"
        port: 443
      - host: "*.in"
        port: 443
    binaries:
      - path: /usr/bin/node
      - path: /usr/local/bin/openclaw
      - path: /usr/bin/curl
  npm_registry:
    endpoints:
      - host: "registry.npmjs.org"
        port: 443
      - host: "*.npmjs.org"
        port: 443
    binaries:
      - path: /usr/bin/node
      - path: /usr/local/bin/npm
      - path: /usr/bin/npm
```

> ⚠️ `*` wildcard 全開會被 OpenShell 拒絕，必須指定 TLD pattern。
> ⚠️ 私有 IP 必須在 policy 明確指定，`[A] Approve All` 不會處理私有 IP。

---

## openclaw 安裝

base image 沒有 openclaw，需要手動安裝：

```bash
# sandbox 內
npm install -g openclaw@2026.3.13 --prefix ~/.npm-global
echo 'export PATH=$HOME/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
openclaw --version
```

安裝後複製 openclaw.json：

```bash
# pop-os 上，從 ceclaw-agent 複製
TOKEN_SRC=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep "2e04e3db" | grep -o "token [a-z0-9-]*" | head -1 | awk '{print $2}')
scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o "ProxyCommand=/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id 2e04e3db-259d-4820-ae39-af385c5d0ce1 --token $TOKEN_SRC --gateway-name openshell" \
  sandbox@ceclaw-agent:/sandbox/.openclaw/openclaw.json /tmp/openclaw.json
```

---

## 已知限制

| 限制 | 說明 |
|------|------|
| `*` wildcard 不能用 | OpenShell policy 不允許，用 `*.com` 等 TLD pattern 替代 |
| 私有 IP 需要 policy 明確指定 | 不能靠 `[A] Approve All`，必須在 yaml 裡加 `allowed_ips` |
| 新 domain 第一次需要 approve | 觸發連線後在 TUI `[A] Approve All` |
| filesystem/process policy 建立後鎖定 | 不能用 `openshell policy set` 修改，需要重建 sandbox |

---

## 燒機驗證

建好後跑燒機腳本確認穩定：

```bash
bash ~/burnin_net.sh 100
```

通過標準：三個項目 100/100 成功。

---

## 坑記錄

| 坑# | 說明 |
|-----|------|
| #83 | 舊 sandbox image 預設 network rules 不對，沒有 `[A] Approve All`，導致三天無法上網 |
| #84 | `*` wildcard host 被 OpenShell policy validation 拒絕 |
| #85 | `access: full` 不是 policy endpoint 的合法欄位 |
| #86 | filesystem policy 建立後無法用 `openshell policy set` 修改，必須重建 |
| #87 | 私有 IP（172.17.0.1、192.168.1.91）不會出現在 pending，必須在 policy yaml 明確指定 `allowed_ips` |

---

## 教訓

1. **用乾淨的 base image**，不要在 image 裡預設 network rules
2. **新 sandbox 第一次就做 `[A] Approve All`**，不要等
3. **遇到 sandbox 網路問題，先建新 sandbox 測試**，不要在舊的上面修
4. **私有 IP 必須在 policy yaml 明確指定**，不能靠 TUI approve

---

*生成日期：2026-03-26*
*版本：v1.1（新增私有 IP policy 坑#87）*
*作者：Claude AI 軟工*
