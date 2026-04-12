import pytesseract
from PIL import Image
import fitz  # pymupdf
import io


def ocr_image(image_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(image_bytes))
    return pytesseract.image_to_string(img, lang="chi_tra+chi_sim+eng")


def ocr_pdf(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    results = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            results.append(text)
        else:
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            results.append(pytesseract.image_to_string(img, lang="chi_tra+chi_sim+eng"))
    return "\n".join(results)
