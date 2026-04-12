import re
import httpx
import json
from weasyprint import HTML, CSS
from config import LLM_URL, LLM_MODEL

SEARXNG_URL = "http://127.0.0.1:2337/v1/search"

THEMES = {
    "dark": {
        "bg": "#0D0D1A", "accent": "#E8405A", "accent2": "#6C63FF",
        "title": "#FFFFFF", "body": "#CCCCDD", "sub": "#888899",
        "bar": "#1A1A30", "card": "#14142A",
    },
    "light": {
        "bg": "#F4F6FF", "accent": "#1A56DB", "accent2": "#7C3AED",
        "title": "#0D0D2A", "body": "#222244", "sub": "#555577",
        "bar": "#E0E4F8", "card": "#FFFFFF",
    },
    "tech": {
        "bg": "#030A1A", "accent": "#00D4FF", "accent2": "#00FFA3",
        "title": "#E8F4FF", "body": "#A0C8E8", "sub": "#508090",
        "bar": "#051428", "card": "#081828",
    },
}


async def search_web(query: str, num: int = 6) -> list:
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(SEARXNG_URL, json={"query": query})
            results = r.json().get("data", {}).get("web", [])[:num]
            return [{"title": x["title"], "description": x.get("description", "")} for x in results]
    except Exception:
        return []


async def llm_generate_slides(topic: str, pages: int, search_results: list) -> list:
    context = "\n".join([f"- {r['title']}: {r['description'][:200]}" for r in search_results])
    prompt = f"""你是一位資深商業顧問，專長製作高品質繁體中文簡報。

主題：{topic}
頁數：{pages} 頁（含封面）

網路最新參考資料：
{context}

生成有深度、有數據、有觀點的簡報。規則：
- 標題簡潔有力（10字以內）
- 每頁 3-4 要點，每點 20-40 字，含具體數據或案例
- 第一頁封面只要 title 和 subtitle
- 台灣本地化視角，禁止空話

只輸出 JSON 陣列：
[
  {{"type":"cover","title":"主標題","subtitle":"副標題"}},
  {{"type":"content","title":"頁面標題","points":["要點1","要點2","要點3"]}}
]"""

    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.post(LLM_URL, json={
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": 3000,
        })
    text = r.json()["choices"][0]["message"]["content"].strip()
    text = re.sub(r'<\|channel\|>.*?<channel\|>', '', text, flags=re.DOTALL)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return json.loads(text[text.find("["):text.rfind("]")+1])


def render_cover(slide: dict, t: dict, total: int) -> str:
    return f"""
<div class="slide cover">
  <div class="cover-left">
    <div class="cover-logo">CECLAW</div>
    <div class="cover-num">01</div>
    <div class="cover-tag">Enterprise AI</div>
  </div>
  <div class="cover-right">
    <div class="cover-deco-line"></div>
    <h1 class="cover-title">{slide.get('title','')}</h1>
    <div class="cover-divider"></div>
    <p class="cover-sub">{slide.get('subtitle','')}</p>
    <div class="cover-total">共 {total} 頁</div>
  </div>
  <div class="cover-dots">
    <span></span><span></span><span></span>
  </div>
</div>"""


def render_content(slide: dict, t: dict, num: int, total: int) -> str:
    points_html = ""
    colors = [t["accent"], t["accent2"], t["accent"], t["accent2"]]
    for i, pt in enumerate(slide.get("points", [])[:4]):
        c = colors[i % 2]
        points_html += f"""
    <div class="point">
      <div class="point-num" style="background:{c}">{i+1}</div>
      <div class="point-text">{pt}</div>
    </div>"""

    return f"""
<div class="slide content">
  <div class="top-bar"></div>
  <div class="slide-inner">
    <div class="title-row">
      <div class="title-accent"></div>
      <h2 class="slide-title">{slide.get('title','')}</h2>
    </div>
    <div class="title-rule"></div>
    <div class="points">{points_html}</div>
  </div>
  <div class="slide-footer">
    <span class="footer-brand">CECLAW</span>
    <span class="footer-page">{num:02d} / {total:02d}</span>
  </div>
  <div class="corner-dot d1"></div>
  <div class="corner-dot d2"></div>
</div>"""


def build_html(slides_data: list, t: dict, topic: str) -> str:
    total = len(slides_data)
    slides_html = ""
    for i, slide in enumerate(slides_data):
        if slide.get("type") == "cover" or i == 0:
            slides_html += render_cover(slide, t, total)
        else:
            slides_html += render_content(slide, t, i + 1, total)

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700&display=swap');

* {{ margin:0; padding:0; box-sizing:border-box; }}

body {{
  font-family: 'Noto Sans TC', 'Noto Serif CJK TC', sans-serif;
  background: {t['bg']};
}}

.slide {{
  width: 297mm;
  height: 210mm;
  position: relative;
  overflow: hidden;
  page-break-after: always;
  background: {t['bg']};
}}

/* ── 封面 ── */
.cover {{
  display: flex;
}}

.cover-left {{
  width: 38%;
  background: {t['accent2']};
  display: flex;
  flex-direction: column;
  padding: 14mm 10mm;
  position: relative;
}}

.cover-logo {{
  font-size: 11pt;
  font-weight: 700;
  letter-spacing: 0.2em;
  color: rgba(255,255,255,0.9);
}}

.cover-num {{
  font-size: 56pt;
  font-weight: 700;
  color: rgba(255,255,255,0.15);
  position: absolute;
  bottom: 14mm;
  left: 10mm;
  line-height: 1;
}}

.cover-tag {{
  font-size: 8pt;
  letter-spacing: 0.15em;
  color: rgba(255,255,255,0.5);
  position: absolute;
  bottom: 30mm;
  left: 10mm;
  text-transform: uppercase;
}}

.cover-right {{
  flex: 1;
  padding: 22mm 14mm 14mm 18mm;
  display: flex;
  flex-direction: column;
  justify-content: center;
  position: relative;
}}

.cover-deco-line {{
  position: absolute;
  right: 5mm;
  top: 20mm;
  width: 2.5pt;
  height: 80mm;
  background: {t['accent']};
}}

.cover-title {{
  font-size: 30pt;
  font-weight: 700;
  color: {t['title']};
  line-height: 1.3;
  margin-bottom: 8mm;
}}

.cover-divider {{
  width: 30mm;
  height: 2pt;
  background: {t['accent']};
  margin-bottom: 6mm;
}}

.cover-sub {{
  font-size: 11pt;
  color: {t['sub']};
  line-height: 1.6;
  font-weight: 300;
}}

.cover-total {{
  position: absolute;
  bottom: 10mm;
  right: 14mm;
  font-size: 8pt;
  color: {t['sub']};
}}

.cover-dots {{
  position: absolute;
  bottom: 10mm;
  left: 42%;
  display: flex;
  gap: 3mm;
}}
.cover-dots span {{
  width: 6pt;
  height: 6pt;
  border-radius: 50%;
  background: {t['accent']};
  display: inline-block;
}}
.cover-dots span:nth-child(2) {{
  background: {t['accent2']};
  width: 4pt;
  height: 4pt;
  margin-top: 1pt;
}}
.cover-dots span:nth-child(3) {{
  background: {t['sub']};
  width: 3pt;
  height: 3pt;
  margin-top: 1.5pt;
}}

/* ── 內容頁 ── */
.top-bar {{
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2.5pt;
  background: {t['accent']};
}}

.slide-inner {{
  padding: 12mm 14mm 8mm 14mm;
}}

.title-row {{
  display: flex;
  align-items: center;
  gap: 4mm;
  margin-bottom: 3mm;
}}

.title-accent {{
  width: 2pt;
  height: 16mm;
  background: {t['accent']};
  flex-shrink: 0;
}}

.slide-title {{
  font-size: 22pt;
  font-weight: 700;
  color: {t['title']};
  line-height: 1.2;
}}

.title-rule {{
  height: 0.5pt;
  background: {t['bar']};
  margin: 3mm 0 6mm 0;
}}

.points {{
  display: flex;
  flex-direction: column;
  gap: 5mm;
}}

.point {{
  display: flex;
  align-items: flex-start;
  gap: 5mm;
  padding: 4mm 5mm;
  background: {t['card']};
  border-radius: 3mm;
  border-left: 2pt solid {t['bar']};
}}

.point-num {{
  width: 8mm;
  height: 8mm;
  border-radius: 2mm;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10pt;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
  margin-top: 0.5mm;
}}

.point-text {{
  font-size: 11pt;
  color: {t['body']};
  line-height: 1.65;
  font-weight: 400;
}}

.slide-footer {{
  position: absolute;
  bottom: 8mm;
  left: 14mm;
  right: 14mm;
  display: flex;
  justify-content: space-between;
  align-items: center;
}}

.footer-brand {{
  font-size: 8pt;
  font-weight: 700;
  letter-spacing: 0.15em;
  color: {t['sub']};
}}

.footer-page {{
  font-size: 9pt;
  color: {t['sub']};
  font-weight: 500;
}}

.corner-dot {{
  position: absolute;
  border-radius: 50%;
}}
.d1 {{
  width: 5pt; height: 5pt;
  background: {t['accent']};
  bottom: 8mm; right: 14mm;
}}
.d2 {{
  width: 3pt; height: 3pt;
  background: {t['accent2']};
  bottom: 9.5mm; right: 20mm;
}}
</style>
</head>
<body>
{slides_html}
</body>
</html>"""


async def generate_pdf(topic: str, pages: int, output_path: str, theme: str = "dark") -> str:
    t = THEMES.get(theme, THEMES["dark"])
    search_results = await search_web(topic)
    slides_data = await llm_generate_slides(topic, pages, search_results)

    html_content = build_html(slides_data, t, topic)

    HTML(string=html_content).write_pdf(
        output_path,
        stylesheets=[CSS(string="@page { size: A4 landscape; margin: 0; }")]
    )
    return output_path
