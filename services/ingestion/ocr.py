"""
Enhanced OCR with configurable Tesseract + layout preservation.

Usage:
    from services.ingestion.ocr import ocr_image, ocr_pdf_page

    text = ocr_image("scan.png", language="eng", config="--psm 6")
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

# ── Tesseract auto-detection ───────────────────────────────────────────


def _find_tesseract() -> Optional[str]:
    """Locate Tesseract binary on the system."""
    import shutil

    # 1. Check PATH
    path = shutil.which("tesseract")
    if path:
        return path

    # 2. Common Windows locations
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Tesseract-OCR\tesseract.exe",
    ]
    for c in candidates:
        if Path(c).is_file():
            return c

    return None


TESSERACT_PATH = _find_tesseract()


def _get_pytesseract():
    """Lazy-import and configure pytesseract."""
    try:
        import pytesseract

        if TESSERACT_PATH:
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
        return pytesseract
    except ImportError:
        return None


# ── OCR Functions ──────────────────────────────────────────────────────


def ocr_image(
    image_path: str | Path,
    language: str = "eng",
    config: str = "--psm 6",
    dpi: int = 300,
) -> str:
    """
    OCR a single image file.

    Args:
        image_path: Path to image (PNG, JPG, TIFF, BMP, etc.).
        language: Tesseract language code (e.g., 'eng', 'eng+spa').
        config: Tesseract config flags. Default --psm 6 (uniform block of text).
                --psm 3 = auto, --psm 4 = single column, --psm 6 = uniform block.
        dpi: DPI for rendering (only used for PDF pages, ignored for images).

    Returns:
        Extracted text string.
    """
    pt = _get_pytesseract()
    if pt is None:
        raise RuntimeError(
            "pytesseract not installed. Run: pip install pytesseract\n"
            "Also install Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki"
        )

    from PIL import Image

    img = Image.open(str(image_path))
    text = pt.image_to_string(img, lang=language, config=config)
    return text.strip()


def ocr_pdf_page(
    page_image,
    language: str = "eng",
    config: str = "--psm 6",
    dpi: int = 300,
) -> str:
    """
    OCR a pymupdf Page object by rendering it to an image first.

    Args:
        page_image: A pymupdf Page OR PIL Image.
        language: Tesseract language code.
        config: Tesseract config.
        dpi: DPI for page->image conversion.

    Returns:
        Extracted text.
    """
    pt = _get_pytesseract()
    if pt is None:
        return ""

    from PIL import Image

    # If it's a pymupdf page
    if hasattr(page_image, "get_pixmap"):
        import io

        pix = page_image.get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
    else:
        img = page_image

    text = pt.image_to_string(img, lang=language, config=config)
    return text.strip()


def ocr_pdf(
    pdf_path: str | Path,
    language: str = "eng",
    config: str = "--psm 6",
    dpi: int = 300,
    page_range: Optional[tuple[int, int]] = None,
) -> list[str]:
    """
    OCR every page of a PDF (force OCR even if text is selectable).

    Args:
        pdf_path: Path to PDF.
        language: Tesseract language.
        config: Tesseract config.
        dpi: Render DPI.
        page_range: (start, end) 0-indexed, inclusive. None = all pages.

    Returns:
        List of page texts.
    """
    import fitz

    doc = fitz.open(str(pdf_path))
    start, end = page_range or (0, len(doc) - 1)
    pages_text: list[str] = []

    for i in range(start, min(end + 1, len(doc))):
        page_text = ocr_pdf_page(doc[i], language=language, config=config, dpi=dpi)
        pages_text.append(page_text)

    doc.close()
    return pages_text


def is_ocr_available() -> bool:
    """Check if Tesseract OCR is installed and working."""
    return TESSERACT_PATH is not None and _get_pytesseract() is not None
