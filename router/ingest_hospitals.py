#!/usr/bin/env python3
"""
ingest_hospitals.py
衛福部醫療機構基本資料 24,138筆 → tw_knowledge
用法：~/ceclaw/.venv/bin/python3 ingest_hospitals.py
前提：/tmp/hospital.ods 已下載
"""

import asyncio
import sys
import os
import json
import uuid
import pandas as pd

# Qdrant + embedding 設定（對齊 config.py）
QDRANT_URL = "http://192.168.1.91:6333"
COLLECTION = "tw_knowledge"
EMBEDDING_URL = "http://192.168.1.91:11434/api/embed"
EMBEDDING_MODEL = "bge-m3:latest"
EMBEDDING_DIM = 1024
BATCH = 50
ODS_PATH = "/tmp/hospital.ods"

# 醫事人員欄位 → 顯示名稱（只顯示 >0 的）
STAFF_COLS = {
    "A醫師": "醫師", "B中醫師": "中醫師", "C牙醫師": "牙醫師",
    "D藥師": "藥師", "F護理師": "護理師", "G護士": "護士",
    "Q物理治療師": "物理治療師", "R職能治療師": "職能治療師",
    "S醫事放射師": "放射師", "J醫事檢驗師": "檢驗師",
    "X諮商心理師": "諮商心理師", "Y臨床心理師": "臨床心理師",
    "Z營養師": "營養師", "V呼吸治療師": "呼吸治療師",
    "1語言治療師": "語言治療師",
}


def build_content(row: dict) -> str:
    parts = []
    name = str(row.get("機構名稱", "")).strip()
    addr = str(row.get("地址", "")).strip()
    county = str(row.get("縣市區名", "")).strip()
    tel = str(row.get("電話", "")).strip()
    dept = str(row.get("科別", "")).strip().rstrip(",")
    code = str(row.get("機構代碼", "")).strip()

    parts.append(f"台灣醫療機構，機構代碼{code}，位於{county}。")
    if addr:
        parts.append(f"地址：{addr}。")
    if tel and tel != "nan":
        parts.append(f"電話：{tel}。")
    if dept and dept != "nan":
        parts.append(f"科別：{dept}。")

    # 醫事人員統計（只列有人的）
    staff_parts = []
    for col, label in STAFF_COLS.items():
        n = int(row.get(col, 0) or 0)
        if n > 0:
            staff_parts.append(f"{label}{n}人")
    if staff_parts:
        parts.append(f"人員：{'、'.join(staff_parts)}。")

    return "".join(parts)


async def embed(text: str, session) -> list:
    import aiohttp
    async with session.post(
        EMBEDDING_URL,
        json={"model": EMBEDDING_MODEL, "input": text},
        timeout=aiohttp.ClientTimeout(total=30)
    ) as r:
        d = await r.json()
        return d["embeddings"][0]


async def upsert_batch(points: list, session) -> int:
    import aiohttp
    async with session.put(
        f"{QDRANT_URL}/collections/{COLLECTION}/points",
        json={"points": points},
        timeout=aiohttp.ClientTimeout(total=60)
    ) as r:
        d = await r.json()
        return 1 if d.get("status") == "ok" else 0


async def check_exists(title: str, session) -> bool:
    """title 去重"""
    import aiohttp
    async with session.post(
        f"{QDRANT_URL}/collections/{COLLECTION}/points/scroll",
        json={
            "filter": {"must": [{"key": "title", "match": {"value": title}}]},
            "limit": 1,
            "with_payload": False,
            "with_vector": False,
        },
        timeout=aiohttp.ClientTimeout(total=10)
    ) as r:
        d = await r.json()
        return len(d.get("result", {}).get("points", [])) > 0


async def process_row(row: dict, session, sem: asyncio.Semaphore) -> str:
    """回傳 'ok' / 'skip' / 'fail'"""
    async with sem:
        name = str(row.get("機構名稱", "")).strip()
        code = str(row.get("機構代碼", "")).strip()
        if not name:
            return "skip"
        try:
            if await check_exists(name, session):
                return "skip"
            content = build_content(row)
            vector = await embed(content, session)
            point = {
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"hospital_{code}")),
                "vector": vector,
                "payload": {
                    "title": name,
                    "category": "台灣醫療機構",
                    "content": content,
                    "code": code,
                    "source": "mohw.gov.tw",
                }
            }
            ok = await upsert_batch([point], session)
            return "ok" if ok else "fail"
        except Exception as e:
            return f"fail:{e}"


async def main():
    import aiohttp
    print("=== 衛福部醫療機構 ingest ===")
    print(f"讀取 {ODS_PATH} ...")
    df = pd.read_excel(ODS_PATH, engine="odf")
    print(f"總筆數: {len(df)}")

    records = df.to_dict("records")
    sem = asyncio.Semaphore(5)  # 同時最多5個 embed 請求

    ok = skip = fail = 0
    fail_log = []

    async with aiohttp.ClientSession() as session:
        tasks = [process_row(r, session, sem) for r in records]
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            result = await coro
            if result == "ok":
                ok += 1
            elif result == "skip":
                skip += 1
            else:
                fail += 1
                fail_log.append(result)
            if (i + 1) % 200 == 0:
                print(f"  進度: {i+1}/{len(records)} | ok:{ok} skip:{skip} fail:{fail}", end="\r")

    print(f"\n=== 完成 ===")
    print(f"成功: {ok} / 跳過(重複): {skip} / 失敗: {fail}")
    print(f"tw_knowledge 預計新增: {ok} 筆")
    if fail_log:
        with open("/tmp/hospital_fail.log", "w") as f:
            f.write("\n".join(fail_log[:100]))
        print(f"失敗記錄: /tmp/hospital_fail.log")


if __name__ == "__main__":
    asyncio.run(main())
