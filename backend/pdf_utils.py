"""
Utility untuk extract teks dari file PDF.
Mengembalikan list of dict: [{"page": 1, "text": "..."}, ...]
"""
import pdfplumber


def extract_text_from_pdf(file_path: str):
    pages = []
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append({"page": i + 1, "text": text})
    return pages


def extract_text_from_plain(file_path: str):
    """Untuk file .txt biasa, dianggap 'page' 1 semua."""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    return [{"page": 1, "text": content}]