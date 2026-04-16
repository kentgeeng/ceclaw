import httpx
import re
from config import LLM_URL, LLM_MODEL

async def llm_generate_design(prompt: str) -> str:
    system = """你是專業視覺設計師，專門輸出 SVG 和 HTML/CSS 設計稿。
規則：
- 收到設計需求，直接輸出完整可用的 SVG 或 HTML/CSS 程式碼
- 不說「我無法繪製」、不給文字描述、不詢問
- 預設使用藍白配色、無襯線字體、極簡風格
- 輸出格式：先給程式碼，再附一段簡短設計說明（50字內）
- 輸出語言：繁體中文"""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt}
    ]

    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(LLM_URL, json={
            "model": LLM_MODEL,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 3000
        })
        data = r.json()
        return data["choices"][0]["message"]["content"]

async def generate_design_html(prompt: str) -> str:
    content = await llm_generate_design(prompt)

    svg_match = re.search(r'(<svg[\s\S]*?</svg>)', content, re.IGNORECASE)
    html_match = re.search(r'```html\n([\s\S]*?)```', content)

    if svg_match:
        svg_code = svg_match.group(1)
        desc_part = content[content.rfind('</svg>')+6:].strip()[:200]
        return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CECLAW 設計稿</title>
<style>
  body {{ background: #f5f5f5; display: flex; flex-direction: column;
         align-items: center; justify-content: center; min-height: 100vh;
         font-family: sans-serif; padding: 20px; }}
  .design-container {{ background: white; padding: 40px; border-radius: 12px;
                       box-shadow: 0 4px 20px rgba(0,0,0,0.1); max-width: 800px; }}
  .description {{ margin-top: 20px; color: #666; font-size: 14px; }}
</style>
</head>
<body>
  <div class="design-container">
    {svg_code}
    <div class="description">{desc_part}</div>
  </div>
</body>
</html>"""
    elif html_match:
        return html_match.group(1)
    else:
        return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="UTF-8"><title>CECLAW 設計稿</title>
<style>body{{font-family:sans-serif;padding:40px;max-width:800px;margin:auto;}}</style>
</head>
<body><pre style="white-space:pre-wrap;">{content}</pre></body>
</html>"""
