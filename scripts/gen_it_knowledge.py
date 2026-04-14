#!/usr/bin/env python3
"""
gen_it_knowledge.py
用 Gemma 4 生成 2,000 條繁中 IT 管理知識庫，ingest 進 ceclaw_it_knowledge
預計執行時間：3-4 小時（夜間跑）
"""
import sys, uuid, asyncio, logging, json, httpx
sys.path.insert(0, "/home/zoe_ai/ceclaw/router")
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from knowledge_service_v2 import _get_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[
        logging.FileHandler("/home/zoe_ai/ceclaw/scripts/gen_it_knowledge.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

COLLECTION = "ceclaw_it_knowledge"
VECTOR_DIM = 1024
OLLAMA_URL = "http://192.168.1.91:11434/api/embeddings"
GEMMA_URL = "http://192.168.1.91:8001/v1/chat/completions"
EMBED_MODEL = "bge-m3"
BATCH_SIZE = 50

TOPICS = [
    ("MDM行動裝置管理", [
        "BYOD 政策制定", "MDM 廠商比較（Jamf/Intune/MobileIron）",
        "遠端抹除策略", "裝置合規性檢查", "Zero-touch 部署",
        "MDM 與 VPN 整合", "iOS vs Android MDM 差異",
        "員工隱私與公司管控平衡", "MDM 授權成本評估", "MDM 導入失敗常見原因",
        "MDM 與 Zero Trust 架構", "裝置生命週期管理",
        "應用程式白名單管理", "MDM 事件告警設定", "MDM 定期稽核流程",
        "MDM 與 AD/LDAP 整合", "離職員工裝置回收", "MDM 資料加密設定",
        "MDM KPI 指標定義", "MDM 政策範本"
    ]),
    ("ISO27001_ISMS導入", [
        "ISO 27001:2022 新版條文重點", "ISMS 範疇界定", "風險評鑑方法",
        "適用性聲明書（SoA）撰寫", "ISO 27001 導入時程規劃",
        "內部稽核執行流程", "管理審查會議", "矯正預防措施",
        "ISO 27001 中小企業導入挑戰", "ISO 27001 vs ISO 27002 差異",
        "ISMS 文件化要求", "台灣取得 ISO 27001 認證流程",
        "ISMS 與個資法整合", "ISO 27001 Annex A 控制措施解說",
        "持續改善 PDCA 循環", "ISO 27001 常見不符合項",
        "資安政策撰寫要點", "ISO 27001 供應商管理條款",
        "資安目標設定與量測", "ISO 27001 導入 ROI 計算"
    ]),
    ("資安事件應變SOP", [
        "資安事件分級定義", "事件應變小組組建", "資安事件通報流程",
        "勒索病毒應變 SOP", "個資外洩應變流程", "DDoS 攻擊應變",
        "內部人員資料竊取處理", "資安事件證據保全", "事後檢討報告撰寫",
        "資安事件演練設計", "台灣資安法通報義務", "事件應變工具清單",
        "BCP 與資安事件的關係", "雲端服務中斷應變", "供應商資安事件處理",
        "APT 攻擊應變流程", "社交工程事件處理", "勒索金支付決策",
        "資安事件公關處理", "事件應變委外評估"
    ]),
    ("端點安全", [
        "EDR vs 傳統防毒比較", "EDR 廠商評選標準", "端點加密策略",
        "USB 裝置管控政策", "防毒軟體集中管理", "端點安全基準設定",
        "Windows 更新管理策略", "Mac 端點安全設定", "Linux 伺服器強化",
        "端點 DLP 部署", "VPN 選型評估", "零信任端點存取",
        "端點安全稽核", "BYOD 端點安全風險", "端點安全效能影響",
        "端點威脅獵捕", "端點安全事件調查", "端點安全 KPI",
        "遠端工作端點安全", "端點安全成本優化"
    ]),
    ("備份與災難復原", [
        "3-2-1 備份原則實作", "RTO/RPO 定義與設定", "備份媒體選擇",
        "雲端備份策略", "備份加密要求", "備份驗證測試",
        "DR 站台規劃", "BCP 文件撰寫", "備份監控告警",
        "勒索病毒備份保護", "不可變備份（Immutable Backup）",
        "備份保留期限政策", "跨地備份架構", "備份成本優化",
        "資料庫備份策略", "虛擬機備份方案", "備份頻率設定",
        "DR 演練規劃", "備份軟體比較", "備份委外服務評估"
    ]),
    ("IT採購與廠商評選", [
        "伺服器採購規格制定", "廠商評比矩陣設計", "IT 採購 RFP 撰寫",
        "硬體驗收流程", "軟體授權管理", "雲端服務採購評估",
        "IT 預算規劃", "TCO 總擁有成本計算", "廠商合約條款重點",
        "政府標案 IT 採購規範", "資訊安全廠商評選", "IT 採購舞弊防範",
        "二手設備採購注意事項", "採購週期管理", "廠商 SLA 談判",
        "IT 委外廠商管理", "硬體折舊計算", "採購驗收測試",
        "供應商風險評估", "綠色採購標準"
    ]),
    ("存取控制與MFA", [
        "最小權限原則實作", "RBAC 角色設計", "AD 群組策略設定",
        "MFA 導入策略", "特權帳號管理（PAM）", "單一登入（SSO）架構",
        "帳號生命週期管理", "密碼政策設定", "存取稽核日誌",
        "零信任存取模型", "API 存取控制", "資料庫存取控制",
        "遠端存取安全", "共用帳號管理", "存取審查流程",
        "MFA 廠商比較", "生物辨識存取", "條件式存取政策",
        "離職人員存取撤銷", "存取控制稽核"
    ]),
    ("雲端安全評估", [
        "雲端資安責任共擔模型", "AWS 安全最佳實務", "Azure 安全設定",
        "GCP 安全評估", "多雲安全策略", "雲端 CASB 部署",
        "雲端資料分類與保護", "雲端身份管理（IAM）", "雲端網路安全設計",
        "雲端合規評估", "雲端成本與安全平衡", "容器安全（Docker/K8s）",
        "無伺服器安全", "雲端監控與日誌", "雲端 DR 架構",
        "私有雲 vs 公有雲安全比較", "雲端資料主權", "雲端供應商評估",
        "雲端安全事件應變", "雲端安全成熟度評估"
    ]),
    ("員工資安意識訓練", [
        "資安訓練課程設計", "釣魚郵件演練規劃", "社交工程防範教育",
        "資安意識測驗設計", "資安文化建立", "新進員工資安訓練",
        "主管資安責任意識", "資安海報與宣導", "資安事件通報管道",
        "個資保護教育訓練", "行動裝置安全意識", "密碼安全訓練",
        "公共場所資安意識", "遠端工作資安訓練", "資安意識成效評估",
        "訓練頻率與方式", "第三方資安訓練平台", "遊戲化資安訓練",
        "資安訓練預算規劃", "資安訓練紀錄管理"
    ]),
    ("台灣資安法規實務", [
        "資通安全管理法適用範圍", "關鍵基礎設施資安要求", "資安長（CISO）設置規定",
        "資安事件通報時限", "資安稽核頻率要求", "個資法與資安法整合",
        "金融業資安規範", "醫療業資安規範", "政府機關資安等級",
        "資安管理措施訂定", "台灣資安成熟度模型", "資安演練法規要求",
        "供應鏈資安法規", "個資保護影響評估", "台灣資安主管機關",
        "資安違規罰則", "跨境資料傳輸規範", "資安委外法規要求",
        "資安保險法規", "台灣資安最新修法動態"
    ]),
]

SYSTEM_PROMPT = """你是台灣企業IT管理顧問，擁有豐富的資安、IT治理和系統管理實務經驗。
請用繁體中文回答，針對台灣中小企業環境提供具體可執行的建議。
回答長度約300-500字，條列式呈現，實用為主。
不要使用markdown標題（#），不要用星號粗體（**），不要用bullet point（*）。
用數字條列或純文字段落。"""

async def generate_qa(topic: str, subtopic: str) -> dict | None:
    prompt = f"針對台灣企業IT管理，請詳細說明：{topic} - {subtopic}\n\n提供具體實作步驟、注意事項和台灣適用的法規或標準建議。"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(GEMMA_URL, json={
                "model": "gemma-4-27b",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 800,
                "temperature": 0.7,
            })
        content = resp.json()["choices"][0]["message"]["content"]
        return {"title": f"{topic}：{subtopic}", "content": content,
                "category": "IT知識庫", "source": "Gemma4-generated", "topic": topic}
    except Exception as e:
        logger.warning(f"生成失敗 {subtopic}: {e}")
        return None

async def embed_text(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    return r.json()["embedding"]

async def main():
    client = _get_client()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        logger.info(f"建立 collection: {COLLECTION}")

    total = 0
    for topic, subtopics in TOPICS:
        for subtopic in subtopics:
            item = await generate_qa(topic, subtopic)
            if not item:
                continue
            text = f"{item['title']}\n{item['content']}"
            vector = await embed_text(text)
            client.upsert(collection_name=COLLECTION, points=[
                PointStruct(id=str(uuid.uuid4()), vector=vector, payload=item)
            ])
            total += 1
            logger.info(f"[{total}/200] {topic} - {subtopic}")
            await asyncio.sleep(1)

    logger.info(f"完成！共生成 {total} 筆")

if __name__ == "__main__":
    asyncio.run(main())
