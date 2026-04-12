import httpx
import json
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from config import LLM_URL, LLM_MODEL


async def llm_generate_report(topic: str) -> dict:
    prompt = f"""為主題「{topic}」生成報告內容，以 JSON 回覆：
{{"title": "報告標題", "summary": "摘要段落", "sections": [{{"heading": "章節標題", "content": "章節內容"}}]}}
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


async def generate_docx(topic: str, output_path: str) -> str:
    data = await llm_generate_report(topic)
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Arial"

    title = doc.add_heading(data["title"], 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.runs[0].font.color.rgb = RGBColor(0x1A, 0x1A, 0x2E)

    doc.add_paragraph()
    summary_para = doc.add_paragraph(data["summary"])
    summary_para.runs[0].font.size = Pt(11)

    doc.add_paragraph()
    for section in data.get("sections", []):
        doc.add_heading(section["heading"], level=1)
        p = doc.add_paragraph(section["content"])
        p.runs[0].font.size = Pt(11)

    doc.save(output_path)
    return output_path
