import httpx
import uuid
from config import QDRANT_URL, QDRANT_COLLECTION, EMBEDDING_URL, EMBEDDING_MODEL, EMBEDDING_DIM


async def ensure_collection():
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}")
        if r.status_code == 404:
            await c.put(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}", json={
                "vectors": {"size": EMBEDDING_DIM, "distance": "Cosine"}
            })


async def embed(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(EMBEDDING_URL, json={"model": EMBEDDING_MODEL, "input": text})
        return r.json()["embeddings"][0]


async def store_document(filename: str, content: str, doc_type: str, metadata: dict = {}):
    await ensure_collection()
    chunks = [content[i:i+800] for i in range(0, len(content), 800)]
    points = []
    for i, chunk in enumerate(chunks):
        vector = await embed(chunk)
        points.append({
            "id": str(uuid.uuid4()),
            "vector": vector,
            "payload": {
                "filename": filename,
                "doc_type": doc_type,
                "chunk_index": i,
                "text": chunk,
                **metadata
            }
        })
    async with httpx.AsyncClient(timeout=30) as c:
        await c.put(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points",
                    json={"points": points})
    return len(points)


async def search_documents(query: str, limit: int = 5) -> list[dict]:
    vector = await embed(query)
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/search",
                         json={"vector": vector, "limit": limit, "with_payload": True})
        return r.json().get("result", [])
