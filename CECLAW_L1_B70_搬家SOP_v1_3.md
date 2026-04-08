# CECLAW L1 B70 搬家 SOP
**版本：v1.3 | 日期：2026-04-08**
**目標機器：iEPF-10000S + B70×2（辦公室 L1）**
**預計時間：6-8小時（含模型下載）**

---

## 架構總覽

```
iEPF-10000S（B70 機器）
├── 推理層（sandbox 外，共用）
│   ├── vLLM XPU Docker（Gemma 4，TP=2，port 8001）
│   ├── Qdrant（tw_laws + tw_knowledge，port 6333）
│   ├── ollama bge-m3（embedding，port 11434）
│   └── law_advisor_api（FastAPI，port 8010）
│
└── OpenShell Gateway（port 18234）
    ├── sandbox-companyA
    │   ├── OpenClaw gateway（port 18789）
    │   ├── CECLAW Router proxy.py（port 8000）
    │   ├── Chroma RAG（公司/部門/個人，三層）
    │   ├── Hermes-員工A（parquet-A）
    │   ├── Hermes-員工B（parquet-B）
    │   └── shared_bridge
    └── sandbox-companyB（完全隔離）

GB10（192.168.1.91）← 保留，繼續跑，不停機
```

---

## 前置確認

```bash
# 1. B70 硬體偵測
lspci | grep -i intel | grep -i arc
# 應看到：Intel Arc Pro B70（兩張）

# 2. OS 版本
lsb_release -a
# 需要：Ubuntu 24.04 LTS Server

# 3. 記憶體
free -h
# 建議：64GB RAM+（vLLM scheduler + KV cache 走 system RAM）

# 4. 磁碟空間
df -h /
# 需要：至少 300GB（模型60GB + Qdrant資料 + Docker images）

# 5. 網路
ping 192.168.1.91
# GB10 必須可達

# 6. 確認使用者名稱
whoami
# 記下 USER_NAME，後面用
```

---

## Phase 1：Intel 驅動環境

### 1.1 安裝 Intel compute-runtime（必須從 GitHub，APT 版本太舊不支援 B70）

```bash
# 到 https://github.com/intel/compute-runtime/releases 找最新版
# 下載全套（通常 3-4 個 deb）
mkdir -p ~/intel-drivers && cd ~/intel-drivers

# 範例（版本號以實際 release 為準）
BASE_URL="https://github.com/intel/compute-runtime/releases/download/26.09.32859.0"
wget $BASE_URL/intel-opencl-icd_26.09.32859.0_amd64.deb
wget $BASE_URL/intel-level-zero-gpu_1.6.32859.0_amd64.deb
wget $BASE_URL/libigc2_2.10.32859.0_amd64.deb
wget $BASE_URL/libigdfcl2-1_2.10.32859.0_amd64.deb
wget $BASE_URL/libigdgmm22_22.5.4_amd64.deb

sudo dpkg -i *.deb
sudo apt-get install -f -y

# 加入 render group
sudo usermod -aG render $USER
sudo usermod -aG video $USER
# 重新登入
```

### 1.2 安裝 Intel Graphics Compiler（IGC）

```bash
# https://github.com/intel/intel-graphics-compiler/releases
# 下載對應版本（與 compute-runtime 版本配對）
cd ~/intel-drivers
wget https://github.com/intel/intel-graphics-compiler/releases/download/v2.30.1/intel-igc-core_2.30.1_amd64.deb
wget https://github.com/intel/intel-graphics-compiler/releases/download/v2.30.1/intel-igc-opencl_2.30.1_amd64.deb
sudo dpkg -i intel-igc-*.deb
```

### 1.3 安裝 Level Zero

```bash
sudo apt-get install -y level-zero level-zero-dev
```

### 1.4 安裝 xpu-smi（GPU 監控）

```bash
# https://github.com/intel/xpumanager/releases
cd ~/intel-drivers
wget https://github.com/intel/xpumanager/releases/download/V1.2.40/xpu-smi_1.2.40_20250407.222418.108d4b44_u24.04_amd64.deb
sudo dpkg -i xpu-smi_*.deb

# 驗證兩張 B70
xpu-smi discovery
# 應看到兩個 device，各 32GB VRAM
```

### 1.5 驗證完整 XPU 環境

```bash
# 安裝 PyTorch XPU
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/xpu

# 驗證
python3 -c "
import torch
print('XPU available:', torch.xpu.is_available())
print('Device count:', torch.xpu.device_count())
for i in range(torch.xpu.device_count()):
    print(f'  Device {i}:', torch.xpu.get_device_name(i))
"
# 應輸出：XPU available: True / Device count: 2
```

---

## Phase 2：Docker 環境

```bash
# 安裝 Docker
sudo apt-get install -y docker.io docker-buildx
sudo usermod -aG docker $USER

# 安裝 Intel Container Toolkit（讓 Docker 能存取 XPU）
# https://github.com/intel/container-toolkit
sudo apt-get install -y intel-container-toolkit
sudo systemctl restart docker

# 驗證
docker run --rm --device /dev/dri intel/oneapi-basekit:latest clinfo | grep "Device Name"
```

---

## Phase 3：vLLM XPU Build（from source）

**⚠️ 必須 from source，預建 image 不支援 Gemma 4（2026-04-02 後才發布）**

```bash
# 建立工作目錄
mkdir -p ~/vllm-build && cd ~/vllm-build

# Clone vLLM（main branch，含 Gemma 4 支援）
git clone https://github.com/vllm-project/vllm.git
cd vllm
git log --oneline -3  # 確認是最新 commit

# Build XPU Docker image（30-60 分鐘）
docker build \
  -f Dockerfile.xpu \
  -t vllm-xpu:local \
  --build-arg http_proxy=$http_proxy \
  --build-arg https_proxy=$https_proxy \
  .

# 驗證 build 成功
docker images | grep vllm-xpu
docker run --rm --device /dev/dri vllm-xpu:local python3 -c "import vllm; print('vLLM version:', vllm.__version__)"
```

---

## Phase 4：Gemma 4 模型下載（HuggingFace 格式）

**⚠️ B70 用 vLLM XPU，需要 HuggingFace safetensors 格式，不是 GGUF**

```bash
# 安裝 huggingface-cli
pip install huggingface_hub --break-system-packages

# 建立模型目錄
mkdir -p ~/models

# 登入 HuggingFace（需要帳號，Gemma 4 需要接受條款）
huggingface-cli login
# 輸入 HF token

# 下載 Gemma 4 26B Instruct（約 52GB safetensors）
huggingface-cli download google/gemma-4-26b-it \
  --local-dir ~/models/gemma-4-26b-it \
  --local-dir-use-symlinks False

# 驗證
ls ~/models/gemma-4-26b-it/
# 應看到：config.json, tokenizer.json, model-*.safetensors

# 確認 chat template 存在（transformers 5.x 需要）
python3 -c "
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained('$HOME/models/gemma-4-26b-it')
print('Chat template:', 'OK' if tok.chat_template else 'MISSING')
"
```

---

## Phase 5：推理服務啟動

### 5.1 啟動 vLLM XPU（TP=2，兩張 B70）

```bash
# 建立啟動腳本
cat > ~/start-vllm.sh << 'EOF'
#!/bin/bash
docker run -d \
  --name vllm-xpu \
  --restart unless-stopped \
  --device /dev/dri \
  -v ~/models:/models \
  -p 8001:8000 \
  -e ZE_AFFINITY_MASK=0,1 \
  -e CCL_WORKER_AFFINITY=0,1 \
  -e SYCL_CACHE_PERSISTENT=1 \
  vllm-xpu:local \
  python3 -m vllm.entrypoints.openai.api_server \
    --model /models/gemma-4-26b-it \
    --tensor-parallel-size 2 \
    --max-model-len 131072 \
    --gpu-memory-utilization 0.90 \
    --dtype bfloat16 \
    --host 0.0.0.0 \
    --port 8000 \
    --served-model-name gemma4
EOF
chmod +x ~/start-vllm.sh
bash ~/start-vllm.sh

# 等待啟動（2-3 分鐘）
sleep 120

# 驗證
curl -s http://localhost:8001/health
curl -s http://localhost:8001/v1/models | python3 -c "import json,sys; [print(m['id']) for m in json.load(sys.stdin)['data']]"
```

### 5.2 設定 systemd watchdog（vLLM 熱保護）

```bash
cat > ~/gpu-thermal-watchdog.sh << 'EOF'
#!/bin/bash
while true; do
  TEMP=$(xpu-smi dump -d 0 -m 2 2>/dev/null | grep temperature | awk '{print $NF}' | head -1)
  if [ ! -z "$TEMP" ] && [ "$TEMP" -gt 90 ]; then
    echo "$(date): GPU temperature $TEMP°C > 90°C, stopping vLLM"
    docker stop vllm-xpu
  fi
  sleep 30
done
EOF
chmod +x ~/gpu-thermal-watchdog.sh

sudo tee /etc/systemd/system/gpu-thermal-watchdog.service << 'EOF'
[Unit]
Description=GPU Thermal Watchdog
After=network.target

[Service]
ExecStart=/home/USER_NAME/gpu-thermal-watchdog.sh
Restart=always
User=USER_NAME

[Install]
WantedBy=multi-user.target
EOF

# 替換 USER_NAME
sudo sed -i "s/USER_NAME/$USER/g" /etc/systemd/system/gpu-thermal-watchdog.service
sudo systemctl enable gpu-thermal-watchdog
sudo systemctl start gpu-thermal-watchdog
```

---

## Phase 6：三層知識庫部署

### 架構說明

```
Layer 1：tw_laws（法律骨架）← 從 GB10 snapshot 搬移
  → 221,599條法規，18大類
  → Qdrant collection: tw_laws
  → 唯讀，定期更新

Layer 2：tw_knowledge（在地百科）← 從 GB10 snapshot 搬移
  → 51,969筆，12類分類
  → Qdrant collection: tw_knowledge
  → 定期更新（上市公司/Wiki）

Layer 3：Chroma RAG（公司知識）← 各 sandbox 獨立，不搬
  → personal/dept/company 三層
  → 每個 sandbox 自己的 Chroma
  → 員工貢獻，shared_bridge 審核
```

### 6.1 啟動 Qdrant

```bash
mkdir -p ~/qdrant_data

docker run -d \
  --name qdrant \
  --restart unless-stopped \
  -p 6333:6333 \
  -v ~/qdrant_data:/qdrant/storage \
  qdrant/qdrant:latest

sleep 5
curl -s http://localhost:6333/collections
```

### 6.2 從 GB10 建立 Snapshot

```bash
# 在 GB10 上執行
ssh zoe_gb@192.168.1.91 << 'REMOTE'

# tw_laws snapshot
echo "建立 tw_laws snapshot..."
SNAP_LAWS=$(curl -s -X POST http://localhost:6333/collections/tw_laws/snapshots | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['name'])")
echo "tw_laws snapshot: $SNAP_LAWS"

# tw_knowledge snapshot
echo "建立 tw_knowledge snapshot..."
SNAP_KNW=$(curl -s -X POST http://localhost:6333/collections/tw_knowledge/snapshots | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['name'])")
echo "tw_knowledge snapshot: $SNAP_KNW"

# 下載到 GB10 home
curl -o ~/tw_laws_latest.snapshot "http://localhost:6333/collections/tw_laws/snapshots/$SNAP_LAWS"
curl -o ~/tw_knowledge_latest.snapshot "http://localhost:6333/collections/tw_knowledge/snapshots/$SNAP_KNW"

ls -lh ~/*.snapshot
REMOTE
```

### 6.3 傳輸 Snapshot 到 B70

```bash
# 從 B70 拉（在 B70 上執行）
rsync -av --progress \
  zoe_gb@192.168.1.91:~/tw_laws_latest.snapshot ~/
rsync -av --progress \
  zoe_gb@192.168.1.91:~/tw_knowledge_latest.snapshot ~/

ls -lh ~/*.snapshot
# tw_laws 約 500MB，tw_knowledge 約 200MB
```

### 6.4 Restore 到 B70 Qdrant

```bash
# Restore tw_laws
echo "Restoring tw_laws..."
curl -X POST "http://localhost:6333/collections/tw_laws/snapshots/upload?priority=snapshot" \
  -H "Content-Type: multipart/form-data" \
  -F "snapshot=@${HOME}/tw_laws_latest.snapshot"

# 等待 restore 完成
sleep 30

# Restore tw_knowledge
echo "Restoring tw_knowledge..."
curl -X POST "http://localhost:6333/collections/tw_knowledge/snapshots/upload?priority=snapshot" \
  -H "Content-Type: multipart/form-data" \
  -F "snapshot=@${HOME}/tw_knowledge_latest.snapshot"

sleep 30

# 驗證
curl -s http://localhost:6333/collections/tw_laws | python3 -c "import json,sys; d=json.load(sys.stdin); print('tw_laws:', d['result']['points_count'])"
curl -s http://localhost:6333/collections/tw_knowledge | python3 -c "import json,sys; d=json.load(sys.stdin); print('tw_knowledge:', d['result']['points_count'])"
# tw_laws: 221599
# tw_knowledge: 51969
```

### 6.5 安裝 ollama + bge-m3（embedding 服務）

```bash
# 安裝 ollama
curl -fsSL https://ollama.com/install.sh | sh

# 設定對外監聽
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf << 'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF
sudo systemctl daemon-reload
sudo systemctl enable ollama
sudo systemctl restart ollama

sleep 5

# 拉 bge-m3
ollama pull bge-m3
curl -s http://localhost:11434/api/tags | python3 -c "import json,sys; [print(m['name']) for m in json.load(sys.stdin)['models']]"

# 驗證 embedding 功能
curl -s -X POST http://localhost:11434/api/embeddings \
  -d '{"model":"bge-m3","prompt":"測試"}' | python3 -c "import json,sys; d=json.load(sys.stdin); print('embedding dim:', len(d['embedding']))"
# 應輸出：embedding dim: 1024
```

### 6.6 部署 law_advisor_api

```bash
# Clone repo（包含 law_advisor 腳本）
git clone https://github.com/kentgeeng/ceclaw.git ~/ceclaw

# 安裝依賴
pip install httpx qdrant-client pyyaml fastapi uvicorn --break-system-packages

# 複製腳本（GB10 版本）
rsync -av zoe_gb@192.168.1.91:~/law_advisor.py ~/
rsync -av zoe_gb@192.168.1.91:~/law_advisor_api.py ~/

# 建立 systemd service
sudo tee /etc/systemd/system/law-advisor.service << EOF
[Unit]
Description=CECLAW Law Advisor API
After=network.target docker.service

[Service]
User=$USER
WorkingDirectory=/home/$USER
ExecStart=/usr/bin/python3 -m uvicorn law_advisor_api:app --host 0.0.0.0 --port 8010
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable law-advisor
sudo systemctl start law-advisor
sleep 5
curl -s http://localhost:8010/health

# 功能驗證
curl -s -X POST http://localhost:8010/search \
  -H "Content-Type: application/json" \
  -d '{"query":"勞工加班費","advisor":"hr","top_k":3}' \
  | python3 -c "import json,sys; [print(f\"{r['score']:.3f} {r['law']}\") for r in json.load(sys.stdin)['results']]"
```

---

## Phase 7：OpenShell Sandbox 部署

### 7.1 安裝 OpenShell

```bash
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh

# 確認版本
openshell --version
# 應為 0.0.24 或更新
```

### 7.2 啟動 Gateway

```bash
openshell gateway start --name b70-gateway --port 18234

# 驗證
openshell sandbox list --gateway b70-gateway
```

### 7.3 建立 CECLAW Sandbox Template

```bash
mkdir -p ~/ceclaw-sandbox-template

cat > ~/ceclaw-sandbox-template/Dockerfile << 'DOCKERFILE'
FROM ubuntu:24.04

# 基礎工具
RUN apt-get update && apt-get install -y \
    python3 python3-pip \
    iproute2 \
    git curl wget \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Node.js 工具
RUN npm install -g pnpm openclaw@2026.4.8

# Python 工具
RUN pip3 install httpx qdrant-client pyyaml requests --break-system-packages

# sandbox 用戶（OpenShell 必要）
RUN groupadd -r sandbox && \
    useradd -r -g sandbox -d /sandbox -s /bin/bash sandbox && \
    mkdir -p /sandbox && \
    chown sandbox:sandbox /sandbox

USER sandbox
WORKDIR /sandbox
DOCKERFILE

cat > ~/ceclaw-sandbox-template/policy.yaml << 'POLICY'
version: 1
filesystem_policy:
  read_only: [/usr, /lib, /etc]
  read_write: [/sandbox, /tmp]
landlock:
  compatibility: best_effort
process:
  run_as_user: sandbox
  run_as_group: sandbox
network_policies:
  ceclaw_gateway:
    name: ceclaw-internal
    endpoints:
      - host: 172.25.0.1
        port: 8000
        protocol: rest
      - host: 172.25.0.1
        port: 18789
        protocol: rest
    binaries:
      - path: /usr/bin/curl
      - path: /usr/local/bin/openclaw
POLICY
```

### 7.4 建立各公司 Sandbox

```bash
# POC 第一個公司
openshell sandbox create \
  --name sandbox-poc \
  --from ~/ceclaw-sandbox-template \
  --gateway b70-gateway

# 驗證
openshell sandbox list --gateway b70-gateway
# 應看到 sandbox-poc Ready

# 連入測試
openshell sandbox connect sandbox-poc --gateway b70-gateway
# 在 sandbox 內
python3 -c "print('CECLAW sandbox OK')"
openclaw --version
exit
```

---

## Phase 8：CECLAW 應用部署（每個 Sandbox）

**⚠️ 啟動順序：8.3（Chroma）→ 8.2（proxy.py）→ 8.1（OpenClaw），不可顛倒**

### 8.3 在 sandbox 內部署 Chroma（Layer 3）

```bash
openshell sandbox connect sandbox-poc --gateway b70-gateway

# Chroma 在每個 sandbox 內獨立運行
pip3 install chromadb --break-system-packages

# 建立公司知識庫目錄
mkdir -p /sandbox/chroma_data/{personal,dept,company}

# 啟動 Chroma server
python3 -m chromadb.cli.cli run \
  --path /sandbox/chroma_data \
  --host 0.0.0.0 \
  --port 8100 &

sleep 3
curl -s http://localhost:8100/api/v1/heartbeat

exit
```

### 8.2 在 sandbox 內部署 proxy.py

```bash
openshell sandbox connect sandbox-poc --gateway b70-gateway

# Clone repo
git clone https://github.com/kentgeeng/ceclaw.git ~/ceclaw

# 更新 proxy.py IP 設定（指向 B70 本機服務）
# GB10 IP (192.168.1.91) → B70 本機 (localhost 或 172.25.0.1)
sed -i 's/192.168.1.91/localhost/g' ~/ceclaw/router/proxy.py

# 安裝依賴
pip3 install httpx qdrant-client pyyaml chromadb --break-system-packages

# 啟動 CECLAW router
cd ~/ceclaw/router
python3 proxy.py &

# 測試
sleep 3
curl -s http://localhost:8000/health

exit
```

### 8.1 在 sandbox 內設定 OpenClaw

```bash
# 連入 sandbox
openshell sandbox connect sandbox-poc --gateway b70-gateway

# 在 sandbox 內執行
openclaw onboard
# 選擇 Custom Provider
# Base URL: http://172.25.0.1:8000/v1（⚠️ 指向 proxy.py，不是 vLLM 8001）
# API Key: <ROUTER_TOKEN>

# 設定完成後測試
openclaw "你是誰？"
exit
```

---

## Phase 9：proxy.py IP 更新

```bash
# 確認需要改的 IP
grep -n "192.168.1.91" ~/ceclaw/router/proxy.py

# B70 本機服務走 localhost，不需要改太多
# 主要改：
# - vLLM endpoint: localhost:8001
# - Qdrant: localhost:6333
# - ollama: localhost:11434
# - law_advisor_api: localhost:8010

# 用 str_replace 逐一修改（不要一次全 sed，避免誤改）
```

---

## Phase 10：開機自啟設定

```bash
# Docker containers（已設 --restart unless-stopped）
docker update --restart unless-stopped vllm-xpu qdrant

# systemd services
sudo systemctl enable ollama law-advisor gpu-thermal-watchdog

# OpenShell gateway 開機自啟
# 建立 systemd service
sudo tee /etc/systemd/system/openshell-gateway.service << EOF
[Unit]
Description=OpenShell Gateway
After=docker.service network.target

[Service]
User=$USER
ExecStart=/home/$USER/.local/bin/openshell gateway start --name b70-gateway --port 18234
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable openshell-gateway
sudo systemctl start openshell-gateway

# 驗證全部 service
sudo systemctl status ollama law-advisor gpu-thermal-watchdog openshell-gateway | grep -E "Active|●"
```

---

## Phase 11：全系統體檢

```bash
echo "=== Phase 11：全系統體檢 ==="

# 1. 推理服務
echo "--- vLLM XPU ---"
curl -s http://localhost:8001/health
curl -s http://localhost:8001/v1/models | python3 -c "import json,sys; [print(m['id']) for m in json.load(sys.stdin)['data']]"

# 2. GPU 狀態
echo "--- GPU ---"
xpu-smi dump -d 0 -m 0,2,5 2>/dev/null | head -5
xpu-smi dump -d 1 -m 0,2,5 2>/dev/null | head -5

# 3. Qdrant 三層知識庫
echo "--- Qdrant ---"
curl -s http://localhost:6333/collections/tw_laws | python3 -c "import json,sys; print('tw_laws:', json.load(sys.stdin)['result']['points_count'])"
curl -s http://localhost:6333/collections/tw_knowledge | python3 -c "import json,sys; print('tw_knowledge:', json.load(sys.stdin)['result']['points_count'])"

# 4. bge-m3 embedding
echo "--- bge-m3 ---"
curl -s http://localhost:11434/api/tags | python3 -c "import json,sys; [print(m['name']) for m in json.load(sys.stdin)['models']]"

# 5. law_advisor_api
echo "--- law_advisor_api ---"
curl -s http://localhost:8010/health
curl -s -X POST http://localhost:8010/search \
  -H "Content-Type: application/json" \
  -d '{"query":"勞工加班費","advisor":"hr","top_k":2}' \
  | python3 -c "import json,sys; [print(f\"{r['score']:.3f} {r['law']}\") for r in json.load(sys.stdin)['results']]"

# 6. OpenShell
echo "--- OpenShell ---"
openshell sandbox list --gateway b70-gateway

# 7. 端對端 CECLAW 測試（在 sandbox 內）
echo "--- End-to-End ---"
openshell sandbox exec sandbox-poc --gateway b70-gateway -- \
  curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ROUTER_TOKEN>" \
  -d '{"model":"ceclaw","messages":[{"role":"user","content":"加班費怎麼算？"}]}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['choices'][0]['message']['content'][:200])"

echo "=== 體檢完成 ==="
```

---

## 三層知識庫維護 SOP

### Layer 1（tw_laws）更新（每月）

```bash
# GB10 更新完後，重新 snapshot 搬到 B70
ssh zoe_gb@192.168.1.91 "curl -s -X POST http://localhost:6333/collections/tw_laws/snapshots"
# rsync + restore（同 Phase 6）
```

### Layer 2（tw_knowledge）更新（每月）

```bash
# 上市公司更新
python3 ~/ceclaw/scripts/update_twse.py  # 重新抓 TWSE

# Snapshot + 搬到 B70
ssh zoe_gb@192.168.1.91 "curl -s -X POST http://localhost:6333/collections/tw_knowledge/snapshots"
# rsync + restore
```

### Layer 3（Chroma）備份（每週）

```bash
# 每個 sandbox 各自備份
openshell sandbox connect sandbox-poc --gateway b70-gateway
tar -czf /tmp/chroma_backup_$(date +%Y%m%d).tar.gz /sandbox/chroma_data
exit

# 下載到主機
openshell sandbox download sandbox-poc /tmp/chroma_backup_*.tar.gz ~/backups/ --gateway b70-gateway
```

---

## 注意事項

| 項目 | 說明 |
|------|------|
| vLLM build 時間 | 30-60分鐘，正常 |
| Gemma 4 下載 | 約 52GB，4G網速約 30分鐘 |
| Qdrant restore 時間 | tw_laws 約10分鐘，tw_knowledge 約5分鐘 |
| B70 驅動 | 必須 compute-runtime v26.09+，APT 太舊 |
| HF 格式 | vLLM 吃 safetensors，不是 GGUF |
| TP=2 環境變數 | ZE_AFFINITY_MASK + CCL_WORKER_AFFINITY 必設 |
| sandbox 隔離 | 每公司一個 sandbox，Chroma 各自獨立 |
| GB10 不停機 | 搬家期間 GB10 繼續服務，搬完再切換 |

---

## 回滾方案

```bash
# 若 B70 出問題，proxy.py 改回 GB10
grep -n "localhost" ~/ceclaw/router/proxy.py
# 把 localhost 改回 192.168.1.91
sudo systemctl restart ceclaw-router
# GB10 繼續服務，B70 可慢慢排查
```

---

## 完成標準 Checklist

- [ ] 兩張 B70 xpu-smi 正常偵測
- [ ] vLLM XPU health OK，模型 gemma4 可見
- [ ] tw_laws 221,599 筆確認
- [ ] tw_knowledge 51,969 筆確認
- [ ] bge-m3 embedding 1024 dim 正常
- [ ] law_advisor_api 查詢加班費正常
- [ ] OpenShell sandbox-poc Ready
- [ ] Chroma Layer 3 啟動正常
- [ ] CECLAW 端對端問答正確（含法規引用）
- [ ] 開機自啟全部 service 正常
- [ ] 熱保護 watchdog 運行中
