"""
CECLAW SearXNG → Firecrawl Adapter
讓 Hermes web_search 透過本機 SearXNG 搜尋

用法：
  python3 searxng_adapter.py
  # 或 systemd / pm2

設定：
  ~/.hermes/.env 加入：
  FIRECRAWL_API_URL=http://localhost:2337
"""
import os
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:8888")


def _searxng_to_firecrawl(results: list) -> dict:
    """把 SearXNG results 轉成 Firecrawl 標準格式"""
    web = []
    for i, r in enumerate(results):
        web.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "description": r.get("content", ""),
            "position": i + 1,
        })
    return {"success": True, "data": {"web": web}}


@app.post("/v1/search")
@app.post("/v2/search")
async def search(request: Request):
    body = await request.json()
    query = body.get("query", "")
    limit = body.get("limit", 5)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{SEARXNG_URL}/search",
                params={"q": query, "format": "json", "language": "zh-TW"},
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])[:limit]
            return JSONResponse(_searxng_to_firecrawl(results))
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/health")
def health():
    return {"status": "ok", "service": "searxng-adapter"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("ADAPTER_PORT", 2337))
    uvicorn.run(app, host="127.0.0.1", port=port)
