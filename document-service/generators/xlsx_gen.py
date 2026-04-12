import httpx
import json
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from config import LLM_URL, LLM_MODEL


HEADER_FILL = PatternFill("solid", fgColor="1A1A2E")
HEADER_FONT = Font(color="FFFFFF", bold=True)
ALT_FILL = PatternFill("solid", fgColor="F0F0F8")


async def llm_generate_table(topic: str) -> dict:
    prompt = f"""為「{topic}」生成試算表資料，以 JSON 回覆：
{{"title": "表格標題", "headers": ["欄位1", "欄位2"], "rows": [["資料1", "資料2"]]}}
只輸出 JSON。"""
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(LLM_URL, json={
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0
        })
    text = r.json()["choices"][0]["message"]["content"].strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    return json.loads(text[start:end])


async def generate_xlsx(topic: str, output_path: str) -> str:
    data = await llm_generate_table(topic)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = data.get("title", "資料")[:31]

    headers = data.get("headers", [])
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
        ws.column_dimensions[cell.column_letter].width = max(15, len(h) * 2)

    for row_idx, row in enumerate(data.get("rows", []), 2):
        fill = ALT_FILL if row_idx % 2 == 0 else None
        for col_idx, val in enumerate(row, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            if fill:
                cell.fill = fill

    wb.save(output_path)
    return output_path
