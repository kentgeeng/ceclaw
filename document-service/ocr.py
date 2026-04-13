import os
import tempfile

from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.datamodel.base_models import InputFormat

_converter = None

def get_converter():
    global _converter
    if _converter is None:
        import torch
        torch.device("cpu")
        import os
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        _converter = DocumentConverter()
    return _converter

def _convert_bytes(content: bytes, suffix: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(content)
        tmp_path = f.name
    try:
        result = get_converter().convert(tmp_path)
        return result.document.export_to_markdown()
    finally:
        os.unlink(tmp_path)

def ocr_image(image_bytes: bytes) -> str:
    return _convert_bytes(image_bytes, ".png")

def ocr_pdf(pdf_bytes: bytes) -> str:
    return _convert_bytes(pdf_bytes, ".pdf")

def read_docx(content: bytes) -> str:
    return _convert_bytes(content, ".docx")

def read_xlsx(content: bytes) -> str:
    return _convert_bytes(content, ".xlsx")

def read_pptx(content: bytes) -> str:
    return _convert_bytes(content, ".pptx")

def read_document(content: bytes, ext: str) -> str:
    ext = ext.lower().strip(".")
    map_ = {
        "pdf":".pdf","png":".png","jpg":".jpg","jpeg":".jpeg",
        "tiff":".tiff","bmp":".bmp","docx":".docx",
        "xlsx":".xlsx","pptx":".pptx",
    }
    suffix = map_.get(ext)
    if suffix is None:
        return content.decode("utf-8", errors="ignore")
    return _convert_bytes(content, suffix)

async def read_document_async(content: bytes, ext: str) -> str:
    import asyncio
    return await asyncio.to_thread(read_document, content, ext)
