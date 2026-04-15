#!/usr/bin/env python3
"""
ingest_tw_companies.py
爬取 TWSE 上市（1081筆）+ TPEX 上櫃（879筆），ingest 進 tw_knowledge
用法：cd ~/ceclaw/router && python3 ingest_tw_companies.py
"""

import asyncio
import httpx
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from knowledge_service_v2 import add_document

# TWSE 產業別代碼對照
TWSE_INDUSTRY = {
    "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維",
    "05": "電機機械", "06": "電器電纜", "07": "化學生技醫療", "08": "玻璃陶瓷",
    "09": "造紙工業", "10": "鋼鐵工業", "11": "橡膠工業", "12": "汽車工業",
    "13": "電子工業", "14": "建材營造", "15": "航運業", "16": "觀光餐旅",
    "17": "金融保險", "18": "貿易百貨", "19": "綜合", "20": "其他",
    "21": "化學工業", "22": "生技醫療業", "23": "油電燃氣業", "24": "半導體業",
    "25": "電腦及週邊設備業", "26": "光電業", "27": "通信網路業",
    "28": "電子零組件業", "29": "電子通路業", "30": "資訊服務業", "31": "其他電子業",
}

TWSE_API = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_API = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis"

BATCH = 50  # 每批筆數，避免 GB10 壓力


async def fetch_json(url: str) -> list:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()


def build_twse_doc(c: dict) -> dict:
    code = c.get("公司代號", "").strip()
    name = c.get("公司名稱", "").strip()
    abbr = c.get("公司簡稱", "").strip()
    ind_code = c.get("產業別", "").strip()
    industry = TWSE_INDUSTRY.get(ind_code, f"產業別{ind_code}")
    chairman = c.get("董事長", "").strip()
    founded = c.get("成立日期", "").strip()
    addr = c.get("住址", "").strip()
    website = c.get("網址", "").strip()

    # 成立日期轉西元
    founded_str = ""
    if founded and len(founded) == 8:
        try:
            dt = datetime.strptime(founded, "%Y%m%d")
            founded_str = f"成立於{dt.year}年，"
        except Exception:
            pass

    content_parts = [
        f"台灣上市公司，股票代號{code}，{industry}類。",
        f"{founded_str}董事長{chairman}。" if chairman else "",
        f"總部：{addr}。" if addr else "",
        f"官網：{website}" if website else "",
    ]
    content = "".join(p for p in content_parts if p)

    return {
        "title": f"{abbr or name}（{name}）" if abbr and abbr != name else name,
        "category": "台灣上市公司",
        "content": content,
        "code": code,
        "source": "TWSE",
    }


def build_tpex_doc(c: dict) -> dict:
    code = c.get("SecuritiesCompanyCode", "").strip()
    name = c.get("CompanyName", "").strip()

    content = f"台灣上櫃公司，股票代號{code}。"

    return {
        "title": name,
        "category": "台灣上櫃公司",
        "content": content,
        "code": code,
        "source": "TPEX",
    }


async def ingest_batch(docs: list, label: str) -> tuple:
    ok = 0
    fail = 0
    fail_log = []

    for i in range(0, len(docs), BATCH):
        batch = docs[i:i + BATCH]
        tasks = [
            add_document(
                title=d["title"],
                category=d["category"],
                content=d["content"],
                code=d["code"],
                source=d["source"],
            )
            for d in batch
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for d, r in zip(batch, results):
            if isinstance(r, Exception):
                fail += 1
                fail_log.append({"code": d["code"], "error": str(r)})
            else:
                ok += 1

        done = min(i + BATCH, len(docs))
        print(f"  [{label}] {done}/{len(docs)} ...", end="\r")

    print()
    return ok, fail, fail_log


async def main():
    print("=== CECLAW tw_knowledge 上市櫃公司 ingest ===")

    # 抓 TWSE
    print("[1/4] 抓取 TWSE 上市公司...")
    twse_raw = await fetch_json(TWSE_API)
    twse_docs = [build_twse_doc(c) for c in twse_raw]
    print(f"  TWSE: {len(twse_docs)} 筆")

    # 抓 TPEX
    print("[2/4] 抓取 TPEX 上櫃公司...")
    tpex_raw = await fetch_json(TPEX_API)
    tpex_docs = [build_tpex_doc(c) for c in tpex_raw]
    print(f"  TPEX: {len(tpex_docs)} 筆")

    # Ingest TWSE
    print("[3/4] Ingest TWSE...")
    twse_ok, twse_fail, twse_err = await ingest_batch(twse_docs, "TWSE")

    # Ingest TPEX
    print("[4/4] Ingest TPEX...")
    tpex_ok, tpex_fail, tpex_err = await ingest_batch(tpex_docs, "TPEX")

    # 結果
    print("\n=== 完成 ===")
    print(f"TWSE: {twse_ok} 成功 / {twse_fail} 失敗")
    print(f"TPEX: {tpex_ok} 成功 / {tpex_fail} 失敗")
    print(f"總計新增: {twse_ok + tpex_ok} 筆")

    if twse_err or tpex_err:
        with open("/tmp/ingest_fail.jsonl", "w") as f:
            for e in twse_err + tpex_err:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        print(f"失敗記錄: /tmp/ingest_fail.jsonl")


if __name__ == "__main__":
    asyncio.run(main())
