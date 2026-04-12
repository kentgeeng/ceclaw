import httpx
import json
import re
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

from config import LLM_URL, LLM_MODEL

SEARXNG_URL = "http://127.0.0.1:2337/v1/search"

THEMES = {
    "dark": {
        "bg":      RGBColor(0x0D, 0x0D, 0x1A),
        "accent":  RGBColor(0xE8, 0x40, 0x5A),
        "accent2": RGBColor(0x6C, 0x63, 0xFF),
        "title":   RGBColor(0xFF, 0xFF, 0xFF),
        "body":    RGBColor(0xCC, 0xCC, 0xDD),
        "sub":     RGBColor(0x88, 0x88, 0xAA),
        "bar":     RGBColor(0x1A, 0x1A, 0x30),
    },
    "light": {
        "bg":      RGBColor(0xF8, 0xF8, 0xFF),
        "accent":  RGBColor(0x1A, 0x56, 0xDB),
        "accent2": RGBColor(0x7C, 0x3A, 0xED),
        "title":   RGBColor(0x0D, 0x0D, 0x1A),
        "body":    RGBColor(0x22, 0x22, 0x44),
        "sub":     RGBColor(0x55, 0x55, 0x77),
        "bar":     RGBColor(0xE8, 0xE8, 0xF5),
    },
    "tech": {
        "bg":      RGBColor(0x03, 0x0A, 0x1A),
        "accent":  RGBColor(0x00, 0xD4, 0xFF),
        "accent2": RGBColor(0x00, 0xFF, 0xA3),
        "title":   RGBColor(0xE8, 0xF4, 0xFF),
        "body":    RGBColor(0xA0, 0xC8, 0xE8),
        "sub":     RGBColor(0x50, 0x80, 0xA0),
        "bar":     RGBColor(0x05, 0x14, 0x28),
    },
}


async def search_web(query: str, num: int = 6) -> list:
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(SEARXNG_URL, json={"query": query})
            data = r.json()
            results = data.get("data", {}).get("web", [])[:num]
            return [{"title": x["title"], "description": x.get("description", "")} for x in results]
    except Exception:
        return []


async def llm_generate_slides(topic: str, pages: int, search_results: list) -> list:
    context = "\n".join([f"- {r['title']}: {r['description'][:200]}" for r in search_results])

    prompt = f"""你是一位資深商業顧問，專長是製作高品質的繁體中文簡報。

主題：{topic}
頁數：{pages} 頁（含封面）

以下是來自網路的最新參考資料：
{context}

請根據參考資料，生成一份有深度、有數據、有觀點的簡報內容。

規則：
- 每頁標題簡潔有力（10字以內）
- 每頁 3-4 個要點，每點 20-40 字，要有具體數據或案例
- 第一頁是封面，只要 title 和 subtitle
- 內容要台灣本地化，符合台灣企業視角
- 禁止空話，每個要點都要有實質資訊

只輸出 JSON 陣列，不要其他任何文字：
[
  {{"type": "cover", "title": "主標題", "subtitle": "副標題或日期"}},
  {{"type": "content", "title": "頁面標題", "points": ["要點1含數據", "要點2含案例", "要點3含觀點"]}},
  ...
]"""

    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.post(LLM_URL, json={
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 3000,
        })

    text = r.json()["choices"][0]["message"]["content"].strip()
    text = re.sub(r'<\|channel\|>.*?<channel\|>', '', text, flags=re.DOTALL)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    start = text.find("[")
    end = text.rfind("]") + 1
    return json.loads(text[start:end])


def set_bg(slide, color):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color

def add_rect(slide, x, y, w, h, color):
    shape = slide.shapes.add_shape(1, x, y, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape

def add_text(slide, text, x, y, w, h, size, color, bold=False, align=PP_ALIGN.LEFT):
    txb = slide.shapes.add_textbox(x, y, w, h)
    tf = txb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.name = "Noto Serif CJK TC"
    return txb


def build_cover(prs, slide_data, t):
    layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(layout)
    set_bg(slide, t["bg"])
    W, H = prs.slide_width, prs.slide_height

    # 左側大色塊
    add_rect(slide, 0, 0, Inches(3.8), H, t["accent2"])
    # 右側裝飾線條
    add_rect(slide, W - Inches(0.08), Inches(1), Inches(0.08), Inches(4), t["accent"])
    add_rect(slide, W - Inches(0.22), Inches(2), Inches(0.06), Inches(2), t["accent2"])
    # CECLAW 標籤
    add_text(slide, "CECLAW", Inches(0.3), Inches(0.3), Inches(3.2), Inches(0.6),
             11, RGBColor(0xFF,0xFF,0xFF), bold=True)
    # 主標題
    add_text(slide, slide_data.get("title",""), Inches(4.1), Inches(1.2), Inches(5.5), Inches(2.5),
             32, t["title"], bold=True)
    # 副標題裝飾線
    add_rect(slide, Inches(4.1), Inches(3.9), Inches(1.5), Inches(0.06), t["accent"])
    add_text(slide, slide_data.get("subtitle",""), Inches(4.1), Inches(4.1), Inches(5.5), Inches(0.8),
             14, t["sub"])
    # 頁碼
    add_text(slide, "01", Inches(0.5), H - Inches(1), Inches(2), Inches(0.6),
             28, RGBColor(0xFF,0xFF,0xFF), bold=True)


def build_content_slide(prs, slide_data, t, page_num, total):
    layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(layout)
    set_bg(slide, t["bg"])
    W, H = prs.slide_width, prs.slide_height

    # 頂部色條
    add_rect(slide, 0, 0, W, Inches(0.06), t["accent"])
    # 左側細線
    add_rect(slide, Inches(0.4), Inches(0.8), Inches(0.04), Inches(0.7), t["accent"])
    # 標題
    add_text(slide, slide_data.get("title",""), Inches(0.55), Inches(0.75), Inches(8.5), Inches(0.85),
             26, t["title"], bold=True)
    # 標題底線
    add_rect(slide, Inches(0.55), Inches(1.55), Inches(8.5), Inches(0.02), t["bar"])

    # 要點
    points = slide_data.get("points", [])
    y_start = Inches(1.75)
    point_h = Inches(1.1)

    for i, point in enumerate(points[:4]):
        y = y_start + i * point_h
        # 數字標號
        add_rect(slide, Inches(0.4), y + Inches(0.05), Inches(0.38), Inches(0.38),
                 t["accent"] if i % 2 == 0 else t["accent2"])
        add_text(slide, str(i+1), Inches(0.4), y + Inches(0.05), Inches(0.38), Inches(0.38),
                 12, RGBColor(0xFF,0xFF,0xFF), bold=True, align=PP_ALIGN.CENTER)
        # 要點文字
        add_text(slide, point, Inches(0.9), y, Inches(8.6), Inches(0.95),
                 13, t["body"])

    # 頁碼
    add_text(slide, f"{page_num:02d} / {total:02d}", W - Inches(1.5), H - Inches(0.45),
             Inches(1.3), Inches(0.35), 10, t["sub"], align=PP_ALIGN.RIGHT)
    # 裝飾點
    add_rect(slide, W - Inches(0.25), H - Inches(0.25), Inches(0.12), Inches(0.12), t["accent"])
    add_rect(slide, W - Inches(0.45), H - Inches(0.25), Inches(0.08), Inches(0.08), t["accent2"])


async def generate_pptx(topic: str, pages: int, output_path: str, theme: str = "dark") -> str:
    t = THEMES.get(theme, THEMES["dark"])
    search_results = await search_web(topic)
    slides_data = await llm_generate_slides(topic, pages, search_results)

    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7)
    total = len(slides_data)

    for i, slide in enumerate(slides_data):
        if slide.get("type") == "cover" or i == 0:
            build_cover(prs, slide, t)
        else:
            build_content_slide(prs, slide, t, i+1, total)

    prs.save(output_path)
    return output_path
