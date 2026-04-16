#!/usr/bin/env python3
"""
ingest_bible.py
繁體中文和合本聖經 → ceclaw_faith_knowledge
按章節 ingest（一章一筆），共約 1,189 筆
用法：~/ceclaw/.venv/bin/python3 ingest_bible.py
"""

import asyncio
import aiohttp
import json
import uuid
import sys

BIBLE_URL = "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/ChiUn.json"
QDRANT_URL = "http://192.168.1.91:6333"
COLLECTION = "ceclaw_faith_knowledge"
EMBEDDING_URL = "http://192.168.1.91:11434/api/embed"
EMBEDDING_MODEL = "bge-m3:latest"
EMBEDDING_DIM = 1024

# 書卷中文名對照（Genesis → 創世記）
BOOK_NAMES_ZH = {
    "Genesis": "創世記", "Exodus": "出埃及記", "Leviticus": "利未記",
    "Numbers": "民數記", "Deuteronomy": "申命記", "Joshua": "約書亞記",
    "Judges": "士師記", "Ruth": "路得記", "1 Samuel": "撒母耳記上",
    "2 Samuel": "撒母耳記下", "1 Kings": "列王紀上", "2 Kings": "列王紀下",
    "1 Chronicles": "歷代志上", "2 Chronicles": "歷代志下", "Ezra": "以斯拉記",
    "Nehemiah": "尼希米記", "Esther": "以斯帖記", "Job": "約伯記",
    "Psalms": "詩篇", "Proverbs": "箴言", "Ecclesiastes": "傳道書",
    "Song of Solomon": "雅歌", "Isaiah": "以賽亞書", "Jeremiah": "耶利米書",
    "Lamentations": "耶利米哀歌", "Ezekiel": "以西結書", "Daniel": "但以理書",
    "Hosea": "何西阿書", "Joel": "約珥書", "Amos": "阿摩司書",
    "Obadiah": "俄巴底亞書", "Jonah": "約拿書", "Micah": "彌迦書",
    "Nahum": "那鴻書", "Habakkuk": "哈巴谷書", "Zephaniah": "西番雅書",
    "Haggai": "哈該書", "Zechariah": "撒迦利亞書", "Malachi": "瑪拉基書",
    "Matthew": "馬太福音", "Mark": "馬可福音", "Luke": "路加福音",
    "John": "約翰福音", "Acts": "使徒行傳", "Romans": "羅馬書",
    "1 Corinthians": "哥林多前書", "2 Corinthians": "哥林多後書",
    "Galatians": "加拉太書", "Ephesians": "以弗所書", "Philippians": "腓立比書",
    "Colossians": "歌羅西書", "1 Thessalonians": "帖撒羅尼迦前書",
    "2 Thessalonians": "帖撒羅尼迦後書", "1 Timothy": "提摩太前書",
    "2 Timothy": "提摩太後書", "Titus": "提多書", "Philemon": "腓利門書",
    "Hebrews": "希伯來書", "James": "雅各書", "1 Peter": "彼得前書",
    "2 Peter": "彼得後書", "1 John": "約翰一書", "2 John": "約翰二書",
    "3 John": "約翰三書", "Jude": "猶大書", "Revelation": "啟示錄",
}

# 舊約/新約分類
OT_BOOKS = {
    "創世記", "出埃及記", "利未記", "民數記", "申命記", "約書亞記",
    "士師記", "路得記", "撒母耳記上", "撒母耳記下", "列王紀上", "列王紀下",
    "歷代志上", "歷代志下", "以斯拉記", "尼希米記", "以斯帖記", "約伯記",
    "詩篇", "箴言", "傳道書", "雅歌", "以賽亞書", "耶利米書", "耶利米哀歌",
    "以西結書", "但以理書", "何西阿書", "約珥書", "阿摩司書", "俄巴底亞書",
    "約拿書", "彌迦書", "那鴻書", "哈巴谷書", "西番雅書", "哈該書",
    "撒迦利亞書", "瑪拉基書",
}


async def ensure_collection(session: aiohttp.ClientSession):
    async with session.put(
        f"{QDRANT_URL}/collections/{COLLECTION}",
        json={"vectors": {"size": EMBEDDING_DIM, "distance": "Cosine"}},
    ) as r:
        result = await r.json()
        status = result.get("result", {})
        if status is True or result.get("status") == "ok":
            print(f"✅ Collection {COLLECTION} 建立完成")
        else:
            print(f"ℹ️  Collection: {result}")


async def embed(text: str, session: aiohttp.ClientSession) -> list:
    async with session.post(
        EMBEDDING_URL,
        json={"model": EMBEDDING_MODEL, "input": text[:2000]},
        timeout=aiohttp.ClientTimeout(total=30),
    ) as r:
        d = await r.json()
        return d["embeddings"][0]


async def upsert_point(point: dict, session: aiohttp.ClientSession) -> bool:
    async with session.put(
        f"{QDRANT_URL}/collections/{COLLECTION}/points",
        json={"points": [point]},
        timeout=aiohttp.ClientTimeout(total=30),
    ) as r:
        d = await r.json()
        return d.get("status") == "ok"


async def process_chapter(book_zh: str, chapter_num: int, verses: list,
                           session: aiohttp.ClientSession,
                           sem: asyncio.Semaphore) -> str:
    async with sem:
        category = "舊約聖經" if book_zh in OT_BOOKS else "新約聖經"
        title = f"{book_zh} 第{chapter_num}章"
        content_lines = [f"【{title}】（繁體中文和合本）"]
        for v in verses:
            content_lines.append(f"{v['verse']}. {v['text'].strip()}")
        content = "\n".join(content_lines)

        try:
            vector = await embed(content, session)
            point = {
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"bible_cuv_{book_zh}_{chapter_num}")),
                "vector": vector,
                "payload": {
                    "title": title,
                    "category": category,
                    "content": content,
                    "book": book_zh,
                    "chapter": chapter_num,
                    "verse_count": len(verses),
                    "source": "bible_cuv",
                },
            }
            ok = await upsert_point(point, session)
            return "ok" if ok else "fail"
        except Exception as e:
            return f"fail:{e}"


async def main():
    print("=== ceclaw_faith_knowledge 聖經 ingest ===")
    print("下載和合本 JSON...")

    async with aiohttp.ClientSession() as session:
        async with session.get(BIBLE_URL, timeout=aiohttp.ClientTimeout(total=60)) as r:
            data = await r.json(content_type=None)

        books = data["books"]
        print(f"書卷數: {len(books)}")

        # 建 collection
        await ensure_collection(session)

        # 展開所有章節
        tasks = []
        for book in books:
            book_en = book["name"]
            book_zh = BOOK_NAMES_ZH.get(book_en, book_en)
            for chapter in book["chapters"]:
                tasks.append((book_zh, chapter["chapter"], chapter["verses"]))

        print(f"總章節數: {len(tasks)}")

        sem = asyncio.Semaphore(5)
        ok = fail = 0
        coros = [process_chapter(b, c, v, session, sem) for b, c, v in tasks]

        for i, coro in enumerate(asyncio.as_completed(coros)):
            result = await coro
            if result == "ok":
                ok += 1
            else:
                fail += 1
            if (i + 1) % 100 == 0:
                print(f"  進度: {i+1}/{len(tasks)} | ok:{ok} fail:{fail}", end="\r")

        print(f"\n=== 完成 ===")
        print(f"成功: {ok} / 失敗: {fail}")
        print(f"ceclaw_faith_knowledge 新增約 {ok} 筆")


if __name__ == "__main__":
    asyncio.run(main())
