"""
File Processor — handles text extraction from uploaded files.
Supports: TXT, PDF, EPUB
"""

import io
from pathlib import Path

import aiofiles


async def extract_text_from_file(filepath: str, filename: str) -> str:
    """Extract plain text from an uploaded file."""
    ext = Path(filename).suffix.lower()

    if ext == ".txt":
        return await _read_txt(filepath)
    elif ext == ".pdf":
        return await _read_pdf(filepath)
    elif ext in (".epub",):
        return await _read_epub(filepath)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


async def _read_txt(filepath: str) -> str:
    async with aiofiles.open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return await f.read()


async def _read_pdf(filepath: str) -> str:
    import PyPDF2

    text_parts = []
    with open(filepath, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n\n".join(text_parts)


async def _read_epub(filepath: str) -> str:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup

    book = epub.read_epub(filepath)
    text_parts = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), "html.parser")
            text_parts.append(soup.get_text())
    return "\n\n".join(text_parts)
