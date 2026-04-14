#!/usr/bin/env python3
import sys, uuid, asyncio, logging, httpx
sys.path.insert(0, "/home/zoe_ai/ceclaw/router")
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from knowledge_service_v2 import _get_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

COLLECTION = "ceclaw_it_knowledge"
VECTOR_DIM = 1024
OLLAMA_URL = "http://192.168.1.91:11434/api/embeddings"
EMBED_MODEL = "bge-m3"
BATCH_SIZE = 100
MAX_RECORDS = 10000  # 先跑 1 萬筆，夠用

KEEP_KEYWORDS = [
    "MDM","mobile device","endpoint","ISO 27001","ISMS","NIST CSF",
    "CIS control","access control","IAM","identity","VPN","zero trust",
    "backup","disaster recovery","BCP","incident response","patch",
    "antivirus","EDR","SIEM","audit","governance","compliance",
    "cloud security","firewall","network security","asset management",
    "password policy","MFA","multi-factor","encryption","DLP",
    "security policy","security awareness","phishing","IT governance",
]
EXCLUDE_KEYWORDS = [
    "shellcode","reverse shell","privilege escalation","metasploit",
    "meterpreter","buffer overflow","rootkit","malware sample",
]

def is_relevant(text: str) -> bool:
    t = text.lower()
    if any(k.lower() in t for k in EXCLUDE_KEYWORDS):
        return False
    return any(k.lower() in t for k in KEEP_KEYWORDS)

async def embed_batch(texts: list[str]) -> list[list[float]]:
    async with httpx.AsyncClient(timeout=60) as client:
        tasks = [client.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": t}) for t in texts]
        results = await asyncio.gather(*tasks)
    return [r.json()["embedding"] for r in results]

async def main():
    from datasets import load_dataset
    logger.info("載入資料集...")
    ds = load_dataset("AlicanKiraz0/Cybersecurity-Dataset-Fenrir-v2.0", split="train")
    logger.info(f"原始筆數: {len(ds)}")

    filtered = []
    for row in ds:
        user = row.get("user","") or row.get("instruction","") or ""
        assistant = row.get("assistant","") or row.get("output","") or ""
        if is_relevant(user + " " + assistant):
            filtered.append({"title": user[:200], "content": assistant, "source": "Fenrir-v2.0"})
        if len(filtered) >= MAX_RECORDS:
            break

    logger.info(f"過濾後筆數: {len(filtered)}（上限 {MAX_RECORDS}）")

    client = _get_client()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        logger.info(f"建立 collection: {COLLECTION}")

    total = 0
    for i in range(0, len(filtered), BATCH_SIZE):
        batch_items = filtered[i:i+BATCH_SIZE]
        texts = [f"{item['title']}\n{item['content'][:500]}" for item in batch_items]
        vectors = await embed_batch(texts)
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vectors[j],
                payload={
                    "title": batch_items[j]["title"],
                    "content": batch_items[j]["content"],
                    "source": "Fenrir-v2.0",
                    "category": "IT知識庫",
                }
            )
            for j in range(len(batch_items))
        ]
        client.upsert(collection_name=COLLECTION, points=points)
        total += len(points)
        logger.info(f"已 ingest {total}/{len(filtered)}")

    logger.info(f"完成！共 ingest {total} 筆 → {COLLECTION}")

if __name__ == "__main__":
    asyncio.run(main())
