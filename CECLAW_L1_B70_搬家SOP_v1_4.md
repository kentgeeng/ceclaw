# CECLAW L1 B70 搬家 SOP
**版本：v1.4 | 日期：2026-04-10**
**目標機器：iEPF-10000S + B70×2（辦公室 L1）**
**預計時間：6-8小時（含模型下載）**

---

## 重要更新（v1.3 → v1.4）

1. **L3 知識庫從 Chroma 改為 Qdrant**（v1.3 寫 Chroma 已過時）
2. **Hermes 版本升級到 v0.8.0 + P3 hook 移植**
3. **vault 記憶層加入搬家清單**
4. **所有架構圖 SVG 搬家步驟**
5. **Qdrant 搬家從 4 個 collection 改為 6 個**

---

## 架構總覽

```
iEPF-10000S（B70 機器）
├── 推理層（共用）
│   ├── vLLM XPU（Gemma 4，TP=2，port 8001）
│   ├── Qdrant（六個 collections，port 6333）
│   ├── ollama bge-m3（embedding，port 11434）
│   └── law_advisor_api（FastAPI，port 8010）
│
└── OpenShell Gateway（port 18234）
    ├── sandbox-companyA
    │   ├── OpenClaw gateway（port 18789）
    │   ├── CECLAW Router proxy.py（port 8000）
    │   ├── Hermes webapi（port 8642）+ workspace（port 3000）
    │   ├── SearXNG adapter（port 2337）
    │   ├── vault（~/ceclaw/vault/）
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
# 需要：64GB RAM+

# 4. 磁碟空間
df -h /
# 需要：至少 300GB

# 5. 網路
ping 192.168.1.91
# GB10 必須可達

# 6. 確認使用者名稱
whoami
```

---

## Phase 1：Intel 驅動環境

### 1.1 安裝 Intel compute-runtime（必須從 GitHub）

```bash
mkdir -p ~/intel-drivers && cd ~/intel-drivers

BASE_URL="https://github.com/intel/compute-runtime/releases/download/26.09.32859.0"
wget $BASE_URL/intel-opencl-icd_26.09.32859.0_amd64.deb
wget $BASE_URL/intel-level-zero-gpu_1.6.32859.0_amd64.deb
wget $BASE_URL/libigc2_2.10.32859.0_amd64.deb
wget $BASE_URL/libigdfcl2-1_2.10.32859.0_amd64.deb
wget $BASE_URL/libigdgmm22_22.5.4_amd64.deb

sudo dpkg -i *.deb
sudo apt-get install -f -y

sudo usermod -aG render $USER
sudo usermod -aG video $USER
# 重新登入
```

### 1.2 安裝 Intel Graphics Compiler（IGC）

```bash
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
cd ~/intel-drivers
wget https://github.com/intel/xpumanager/releases/download/V1.2.40/xpu-smi_1.2.40_20250407.222418.108d4b44_u24.04_amd64.deb
sudo dpkg -i xpu-smi_*.deb

# 驗證兩張 B70
xpu-smi discovery
# 應看到兩個 device，各 32GB VRAM
```

### 1.5 驗證 XPU 環境

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/xpu

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
sudo apt-get install -y docker.io docker-buildx
sudo usermod -aG docker $USER

sudo apt-get install -y intel-container-toolkit
sudo systemctl restart docker

# 驗證
docker run --rm --device /dev/dri intel/oneapi-basekit:latest clinfo | grep "Device Name"
```

---

## Phase 3：vLLM XPU Build（from source）

**⚠️ 必須 from source，llama.cpp multi-GPU bug #16767，不能用 llama-server**

```bash
mkdir -p ~/vllm-build && cd ~/vllm-build

git clone https://github.com/vllm-project/vllm.git
cd vllm

# Build（30-60 分鐘）
docker build \
  -f Dockerfile.xpu \
  -t vllm-xpu:local \
  --build-arg http_proxy=$http_proxy \
  --build-arg https_proxy=$https_proxy \
  .

docker run --rm --device /dev/dri vllm-xpu:local python3 -c "import vllm; print('vLLM version:', vllm.__version__)"
```

---

## Phase 4：Gemma 4 模型下載（HuggingFace safetensors 格式）

**⚠️ B70 用 vLLM XPU，需要 safetensors 格式，不是 GGUF**

```bash
pip install huggingface_hub --break-system-packages

mkdir -p ~/models

huggingface-cli login
# 輸入 HF token，需接受 Gemma 4 條款

# 下載 Gemma 4 26B Instruct（約 52GB）
huggingface-cli download google/gemma-4-26b-it \
  --local-dir ~/models/gemma-4-26b-it \
  --local-dir-use-symlinks False

# 驗證 chat template
python3 -c "
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained('/root/models/gemma-4-26b-it')
print('Chat template:', 'OK' if tok.chat_template else 'MISSING')
"
```

---

## Phase 5：推理服務啟動

### 5.1 啟動 vLLM XPU（TP=2）

```bash
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
    --max-model-len 262144 \
    --gpu-memory-utilization 0.90 \
    --dtype bfloat16 \
    --host 0.0.0.0 \
    --port 8000 \
    --served-model-name gemma4
EOF
chmod +x ~/start-vllm.sh
bash ~/start-vllm.sh

sleep 120
curl -s http://localhost:8001/health
```

**預期速度：**
- L1 B70×2：~140 tok/s（vLLM continuous batching，可服務多人並發）

### 5.2 GPU 熱保護 watchdog

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

sudo tee /etc/systemd/system/gpu-thermal-watchdog.service << EOF
[Unit]
Description=GPU Thermal Watchdog
After=network.target

[Service]
ExecStart=/home/$USER/gpu-thermal-watchdog.sh
Restart=always
User=$USER

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable gpu-thermal-watchdog
sudo systemctl start gpu-thermal-watchdog
```

---

## Phase 6：Qdrant 搬家（六個 collections）

**⚠️ v1.4 更新：L3 從 Chroma 改為 Qdrant，需搬六個 collections**

### 6.1 在 GB10 建立全部 snapshots

```bash
ssh zoe_gb@192.168.1.91 << 'REMOTE'
cd ~
for col in tw_laws tw_knowledge ceclaw_company_poc ceclaw_dept_engineering ceclaw_dept_legal ceclaw_personal_kent; do
  echo "建立 $col snapshot..."
  SNAP=$(curl -s -X POST http://localhost:6333/collections/$col/snapshots | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['name'])")
  curl -o ~/${col}_latest.snapshot "http://localhost:6333/collections/$col/snapshots/$SNAP"
  echo "$col: $(ls -lh ~/${col}_latest.snapshot | awk '{print $5}')"
done
ls -lh ~/*.snapshot
REMOTE
```

### 6.2 rsync 到 B70

```bash
# 在 B70 上執行
rsync -avP zoe_gb@192.168.1.91:~/*.snapshot ~/qdrant_snapshots/
ls -lh ~/qdrant_snapshots/
```

### 6.3 啟動 B70 Qdrant 並 restore

```bash
mkdir -p ~/qdrant_data

docker run -d \
  --name qdrant \
  --restart unless-stopped \
  -p 6333:6333 \
  -v ~/qdrant_data:/qdrant/storage \
  qdrant/qdrant:latest

sleep 10

# Restore 全部 collections
for col in tw_laws tw_knowledge ceclaw_company_poc ceclaw_dept_engineering ceclaw_dept_legal ceclaw_personal_kent; do
  echo "Restoring $col..."
  curl -s -X POST "http://localhost:6333/collections/$col/snapshots/upload" \
    -H "Content-Type: multipart/form-data" \
    -F "snapshot=@~/qdrant_snapshots/${col}_latest.snapshot"
  sleep 5
done

# 驗證全部
for col in tw_laws tw_knowledge ceclaw_company_poc ceclaw_dept_engineering ceclaw_dept_legal ceclaw_personal_kent; do
  COUNT=$(curl -s http://localhost:6333/collections/$col | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['points_count'])")
  echo "$col: $COUNT"
done
```

---

## Phase 7：embedding + law_advisor

### 7.1 ollama bge-m3

```bash
curl -fsSL https://ollama.com/install.sh | sh

sudo tee /etc/systemd/system/ollama.service << EOF
[Unit]
Description=Ollama Service
After=network.target

[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
ExecStart=/usr/local/bin/ollama serve
Restart=always
User=$USER

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable ollama
sudo systemctl start ollama
sleep 10
ollama pull bge-m3

# 驗證
curl -s http://localhost:11434/api/tags | python3 -c "import json,sys; [print(m['name']) for m in json.load(sys.stdin)['models']]"
```

### 7.2 law_advisor_api

```bash
# rsync 從 GB10 搬
rsync -avP zoe_gb@192.168.1.91:~/law_advisor/ ~/law_advisor/

# 修改 IP（若有 hardcode）
sed -i 's/192.168.1.91/localhost/g' ~/law_advisor/api.py

# 建立 systemd service
sudo tee /etc/systemd/system/law-advisor.service << EOF
[Unit]
Description=Law Advisor API
After=network.target

[Service]
WorkingDirectory=/home/$USER/law_advisor
ExecStart=python3 api.py
Restart=always
User=$USER

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable law-advisor
sudo systemctl start law-advisor
sleep 5
curl -s http://localhost:8010/health
```

---

## Phase 8：OpenShell + CECLAW 部署

### 8.1 安裝 OpenShell

```bash
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh
openshell gateway start --name b70-gateway --port 18234
```

### 8.2 Clone CECLAW repo

```bash
git clone https://github.com/kentgeeng/ceclaw.git ~/ceclaw

# 更新所有 IP 指向 localhost
sed -i 's/192.168.1.91/localhost/g' ~/ceclaw/router/proxy.py
sed -i 's/192.168.1.91/localhost/g' ~/ceclaw/router/knowledge_service_v2.py

# 驗證
grep -n "192.168.1.91" ~/ceclaw/router/proxy.py ~/ceclaw/router/knowledge_service_v2.py
# 應該沒有輸出
```

### 8.3 Hermes v0.8.0 部署（含 P3 hook 移植）

```bash
# Clone Hermes v0.8.0
git clone https://github.com/NousResearch/hermes-agent.git ~/hermes-v0.8.0
cd ~/hermes-v0.8.0
git checkout v2026.4.8

# 安裝依賴
pip install -e ".[all]" --break-system-packages

# 移植 P3 hook 到新位置
# 新位置：gateway/platforms/api_server.py
# 在 _handle_chat_completions 函數內
# result, usage = await _compute_completion() 之後插入：

python3 - << 'PYEOF'
import re

hook_code = '''
            # P3: auto-submit to shared_bridge if task completed with tools
            try:
                if result.get("api_calls", 0) > 1:
                    import importlib as _il
                    _sb = _il.import_module("shared_bridge")
                    if hasattr(_sb, "submit"):
                        _sb.submit(
                            content=result.get("final_response", ""),
                            metadata={"api_calls": result.get("api_calls"), "model": result.get("model")}
                        )
            except Exception as _e:
                pass  # P3 hook failure should not break response
'''

with open("gateway/platforms/api_server.py", "r") as f:
    content = f.read()

# 在 _compute_completion() 之後插入
old = "        result, usage = await _compute_completion()\n"
new = old + hook_code

content = content.replace(old, new, 1)

with open("gateway/platforms/api_server.py", "w") as f:
    f.write(content)

print("P3 hook 移植完成")
PYEOF

# 驗證
grep -n "P3\|shared_bridge" gateway/platforms/api_server.py
```

### 8.4 設定 Hermes config

```bash
mkdir -p ~/.hermes
cat > ~/.hermes/config.yaml << 'EOF'
model:
  provider: custom
  default: ceclaw
  base_url: http://localhost:8000/v1
  api_key: 97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759
web:
  backend: firecrawl
platform_toolsets:
  webchat:
    - web
    - terminal
    - file
    - memory
    - session_search
EOF

echo 'FIRECRAWL_API_URL=http://localhost:2337' > ~/.hermes/.env
```

### 8.5 vault 搬家

```bash
# vault 在 ~/ceclaw/vault/（已在 repo），git clone 就帶過來了
# 建立 symlink
ln -sf ~/ceclaw/vault ~/.ceclaw/vault
ls -la ~/.ceclaw/vault
```

### 8.6 啟動全部服務

```bash
cat > ~/start-hermes.sh << 'EOF'
#!/bin/bash
# SearXNG adapter
cd ~/ceclaw/router && source ../.venv/bin/activate
python3 searxng_adapter.py &
sleep 2

# Hermes webapi
cd ~/hermes-v0.8.0
python3 -m gateway.platforms.api_server &
sleep 3

# Hermes workspace
cd ~/hermes-v0.8.0
npm run start:workspace &

echo "Hermes 啟動完成"
curl -s http://localhost:8642/health
curl -s http://localhost:2337/health
EOF
chmod +x ~/start-hermes.sh

# 啟動
bash ~/start-hermes.sh
```

---

## Phase 9：IP 更新確認

```bash
# 確認沒有殘留的 GB10 IP
grep -rn "192.168.1.91" ~/ceclaw/router/ ~/hermes-v0.8.0/ 2>/dev/null
# 應該沒有輸出

# 確認 proxy.py 的推理後端指向 vLLM
grep -n "8001\|localhost" ~/ceclaw/router/proxy.py | head -10
```

---

## Phase 10：開機自啟設定

```bash
# Docker containers（已設 --restart unless-stopped）
docker update --restart unless-stopped vllm-xpu qdrant

# systemd services
sudo systemctl enable ollama law-advisor gpu-thermal-watchdog

# OpenShell gateway
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
```

---

## Phase 11：全系統體檢

```bash
echo "=== B70 全系統體檢 ==="

echo "--- vLLM XPU ---"
curl -s http://localhost:8001/health
curl -s http://localhost:8001/v1/models | python3 -c "import json,sys; [print(m['id']) for m in json.load(sys.stdin)['data']]"

echo "--- GPU ---"
xpu-smi dump -d 0 -m 0,2,5 2>/dev/null | head -5
xpu-smi dump -d 1 -m 0,2,5 2>/dev/null | head -5

echo "--- Qdrant 六個 collections ---"
for col in tw_laws tw_knowledge ceclaw_company_poc ceclaw_dept_engineering ceclaw_dept_legal ceclaw_personal_kent; do
  COUNT=$(curl -s http://localhost:6333/collections/$col | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['points_count'])")
  echo "$col: $COUNT"
done

echo "--- bge-m3 ---"
curl -s http://localhost:11434/api/tags | python3 -c "import json,sys; [print(m['name']) for m in json.load(sys.stdin)['models']]"

echo "--- law_advisor_api ---"
curl -s http://localhost:8010/health

echo "--- Hermes ---"
curl -s http://localhost:8642/health
curl -s http://localhost:2337/health

echo "--- vault ---"
cat ~/.ceclaw/vault/working-context.md

echo "--- P3 hook ---"
grep -n "P3\|shared_bridge" ~/hermes-v0.8.0/gateway/platforms/api_server.py | head -5

echo "--- CECLAW 端對端 ---"
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759" \
  -d '{"model":"ceclaw","messages":[{"role":"user","content":"加班費怎麼算？"}]}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['choices'][0]['message']['content'][:200])"

echo "=== 體檢完成 ==="
```

---

## 完成標準 Checklist

- [ ] 兩張 B70 xpu-smi 正常偵測
- [ ] vLLM XPU health OK，gemma4 可見，~140 tok/s
- [ ] tw_laws 221,599 筆確認
- [ ] tw_knowledge 51,970 筆確認
- [ ] ceclaw_company_poc 395 筆確認
- [ ] ceclaw_dept_* + ceclaw_personal_kent 確認
- [ ] bge-m3 embedding 1024 dim 正常
- [ ] law_advisor_api :8010 健康
- [ ] Hermes v0.8.0 webapi :8642 健康
- [ ] SearXNG adapter :2337 健康
- [ ] vault symlink 正常，working-context.md 可讀
- [ ] P3 hook 在 gateway/platforms/api_server.py 確認
- [ ] OpenShell gateway b70-gateway Ready
- [ ] CECLAW 端對端問答正確（含法規引用）
- [ ] 開機自啟全部 service 正常
- [ ] 熱保護 watchdog 運行中

---

## 注意事項

| 項目 | 說明 |
|------|------|
| vLLM build 時間 | 30-60分鐘，正常 |
| Gemma 4 下載 | 約 52GB safetensors（非 GGUF）|
| Qdrant restore 時間 | tw_laws 約10分鐘，其餘各約2分鐘 |
| B70 驅動 | 必須 compute-runtime v26.09+，APT 太舊 |
| llama.cpp 禁用 | multi-GPU bug #16767，必須用 vLLM |
| TP=2 環境變數 | ZE_AFFINITY_MASK + CCL_WORKER_AFFINITY 必設 |
| vault symlink | ~/.ceclaw/vault → ~/ceclaw/vault（在 repo 裡）|
| GB10 不停機 | 搬家期間 GB10 繼續服務，確認 B70 正常後再切換 |

---

## 回滾方案

```bash
# 若 B70 出問題，proxy.py 改回 GB10
sed -i 's/localhost/192.168.1.91/g' ~/ceclaw/router/proxy.py
sed -i 's/localhost/192.168.1.91/g' ~/ceclaw/router/knowledge_service_v2.py
sudo systemctl restart ceclaw-router
# GB10 繼續服務，B70 可慢慢排查
```

---

## 版本歷史

| 版本 | 日期 | 主要變更 |
|------|------|---------|
| v1.4 | 2026-04-10 | L3 Qdrant（非 Chroma）、Hermes v0.8.0 P3 hook 移植、vault 搬家、六個 collections |
| v1.3 | 2026-04-08 | Phase8 順序修正、token 佔位符 |
