import json
import httpx
from config import LLM_URL, LLM_MODEL

KNOWN_TYPES = ["合約", "財報", "HR文件", "發票", "會議紀錄", "技術文件", "其他"]

SCHEMAS = {
    "合約": ["合約名稱", "甲方", "乙方", "簽約日期", "合約期限", "金額", "主要條款", "違約條款"],
    "財報": ["公司名稱", "報告期間", "營收", "淨利", "EPS", "資產總額", "負債總額"],
    "HR文件": ["員工姓名", "職稱", "部門", "到職日期", "薪資", "主要內容"],
    "發票": ["發票號碼", "開票日期", "買方", "賣方", "品項", "金額", "稅額"],
    "會議紀錄": ["會議日期", "出席人員", "主席", "議題", "決議事項", "待辦事項"],
    "技術文件": ["文件名稱", "版本", "作者", "摘要", "主要章節"],
    "其他": ["標題", "日期", "主要內容", "重點摘要"],
}

async def classify(text: str) -> str:
    prompt = (
        f"請判斷以下文件屬於哪個類型，只回傳類型名稱，不要其他文字。\n"
        f"可選類型：{'、'.join(KNOWN_TYPES)}\n\n"
        f"文件內容（前500字）：\n{text[:500]}"
    )
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(LLM_URL, json={
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 20,
            })
        result = r.json()["choices"][0]["message"]["content"].strip()
        for t in KNOWN_TYPES:
            if t in result:
                return t
        return "其他"
    except Exception:
        return "其他"

async def extract(text: str, doc_type: str) -> dict:
    fields = SCHEMAS.get(doc_type, SCHEMAS["其他"])
    fields_str = "、".join(fields)
    prompt = (
        f"請從以下{doc_type}中萃取結構化資料，以 JSON 格式回傳，"
        f"欄位包含：{fields_str}。\n"
        f"找不到的欄位填 null，不要加任何說明文字，只回傳 JSON。\n\n"
        f"文件內容（前2000字）：\n{text[:2000]}"
    )
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(LLM_URL, json={
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 800,
            })
        raw = r.json()["choices"][0]["message"]["content"].strip()
        # 找 JSON 邊界
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
        return {f: None for f in fields}
    except Exception:
        return {f: None for f in fields}
