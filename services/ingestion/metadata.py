"""
Document metadata extraction.

Extracts structured metadata from parsed documents:
  - Word count, character count
  - Detected language (using langdetect or fasttext)
  - Key entities (simple regex-based: dates, emails, phone numbers, dollar amounts)
  - Document structure info (sections, headings count)
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Patterns ───────────────────────────────────────────────────────────

DATE_PATTERNS = [
    re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),  # 01/15/2025
    re.compile(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b",
        re.I,
    ),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),  # 2025-01-15
]

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
DOLLAR_PATTERN = re.compile(r"\$\s?[\d,]+(?:\.\d{2})?")
CASE_NUMBER_PATTERN = re.compile(
    r"(?:Case|Civil Action|Docket)\s*(?:No\.|Number:?)?\s*[\d:A-Z-]+", re.I
)
HEADING_PATTERN = re.compile(
    r"^(?:#{1,6}\s|(?:ARTICLE|SECTION|PART)\s+(?:[IVX]+|\d+))", re.M | re.I
)


# ── Main ───────────────────────────────────────────────────────────────


def extract_metadata(
    text: str,
    parsed_meta: dict[str, Any] | None = None,
    file_path: str = "",
) -> dict[str, Any]:
    """
    Extract metadata from document text.

    Args:
        text: Full document text.
        parsed_meta: Metadata from the parser (title, author, etc.).
        file_path: Path to the original file.

    Returns:
        Dict of metadata fields.
    """
    meta: dict[str, Any] = {}

    # Merge parser metadata if provided
    if parsed_meta:
        meta.update(parsed_meta)

    # Basic stats
    meta["char_count"] = len(text)
    meta["word_count"] = len(text.split())
    meta["line_count"] = len(text.splitlines())

    # File info
    if file_path:
        p = Path(file_path)
        meta["filename"] = p.name
        meta["file_extension"] = p.suffix.lower()
        meta["file_size_bytes"] = p.stat().st_size if p.exists() else 0

    # Dates found
    dates_found: list[str] = []
    for pat in DATE_PATTERNS:
        dates_found.extend(pat.findall(text))
    meta["dates_found"] = dates_found[:10]  # limit

    # Contact info
    meta["emails_found"] = EMAIL_PATTERN.findall(text)[:5]
    meta["phones_found"] = PHONE_PATTERN.findall(text)[:5]

    # Financial
    meta["dollar_amounts"] = DOLLAR_PATTERN.findall(text)[:10]

    # Legal-specific
    meta["case_numbers"] = CASE_NUMBER_PATTERN.findall(text)[:5]

    # Structure
    meta["heading_count"] = len(HEADING_PATTERN.findall(text))

    # Timestamp
    meta["extracted_at"] = datetime.utcnow().isoformat()

    return meta


def detect_language(text: str) -> str:
    """
    Detect document language.

    Returns ISO 639-1 code (e.g., 'en', 'es') or 'unknown'.
    """
    try:
        from langdetect import detect

        return detect(text[:2000])  # sample first 2000 chars for speed
    except ImportError:
        pass
    except Exception:
        pass
    return "unknown"
