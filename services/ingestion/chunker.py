"""
Smart text chunker with multiple strategies.

Strategies:
  - sliding_window: Fixed-size chunks with overlap, respects paragraph boundaries
  - semantic: Splits on section headers, paragraph breaks, and sentences
  - recursive: RecursiveCharacterTextSplitter-style (character-agnostic)
  - fixed: Simple character split, no overlap (fastest)

All strategies return Chunk objects with:
  - text, index, start_char, end_char, metadata
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Chunk:
    """A single text chunk."""

    text: str
    index: int  # position in the chunk list
    start_char: int  # offset in original text
    end_char: int
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Separators ─────────────────────────────────────────────────────────

PARAGRAPH_SEP = re.compile(r"\n\s*\n")
SECTION_SEP = re.compile(r"\n(?:#{1,6}\s|(?:\d+\.)+\s|[A-Z][A-Z\s]{2,}\n)")
SENTENCE_SEP = re.compile(r"(?<=[.!?])\s+")


def _merge_small(chunks: list[str], min_size: int) -> list[str]:
    """Merge chunks smaller than min_size with their neighbour."""
    if not chunks:
        return chunks
    merged: list[str] = [chunks[0]]
    for chunk in chunks[1:]:
        if len(merged[-1]) < min_size or len(chunk) < min_size:
            merged[-1] += "\n\n" + chunk
        else:
            merged.append(chunk)
    return merged


# ── Sliding Window ─────────────────────────────────────────────────────


def sliding_window(
    text: str,
    chunk_size: int = 1024,
    chunk_overlap: int = 128,
    min_chunk_size: int = 100,
    separators: list[str] | None = None,
) -> list[Chunk]:
    """
    Split text into overlapping chunks, breaking at natural boundaries.

    Attempts to split on paragraph breaks first, then sentences, then words.

    Args:
        text: Input text.
        chunk_size: Target characters per chunk.
        chunk_overlap: Overlap between consecutive chunks.
        min_chunk_size: Merge chunks smaller than this.
        separators: Custom separators (tried in order).
    """
    if separators is None:
        separators = ["\n\n", "\n", ". ", " ", ""]

    chunks: list[Chunk] = []
    start = 0
    idx = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        # If we're not at the end, try to break at a natural boundary
        if end < len(text):
            # Walk backwards from end to find best split point
            best = end
            for sep in separators:
                if not sep:
                    best = end
                    break
                # Find separator closest to but before end
                search_start = max(start + chunk_size // 2, end - chunk_overlap * 2)
                pos = text.rfind(sep, search_start, end + chunk_overlap)
                if pos != -1 and pos > start:
                    best = pos + len(sep)
                    break

            end = min(best, len(text))

        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(
                Chunk(
                    text=chunk_text,
                    index=idx,
                    start_char=start,
                    end_char=end,
                    metadata={"strategy": "sliding_window"},
                )
            )
            idx += 1

        start = end - chunk_overlap if end < len(text) else end

    return chunks


# ── Semantic ───────────────────────────────────────────────────────────


def semantic(
    text: str,
    max_chunk_size: int = 2048,
    min_chunk_size: int = 200,
) -> list[Chunk]:
    """
    Split text by section headers, then paragraphs, then sentences.

    Best for structured documents (legal briefs, reports, articles).
    """
    # First pass: split by section headers
    sections = SECTION_SEP.split(text)

    all_chunks: list[str] = []

    for section in sections:
        # Split section into paragraphs
        paragraphs = PARAGRAPH_SEP.split(section.strip())
        current = ""

        for para in paragraphs:
            if len(current) + len(para) > max_chunk_size:
                if current.strip():
                    all_chunks.append(current.strip())
                current = para
            else:
                current += "\n\n" + para if current else para

        if current.strip():
            # If the last piece is too large, split by sentences
            if len(current) > max_chunk_size:
                sentences = SENTENCE_SEP.split(current)
                sent_chunk = ""
                for sent in sentences:
                    if len(sent_chunk) + len(sent) > max_chunk_size:
                        if sent_chunk.strip():
                            all_chunks.append(sent_chunk.strip())
                        sent_chunk = sent
                    else:
                        sent_chunk += " " + sent if sent_chunk else sent
                if sent_chunk.strip():
                    all_chunks.append(sent_chunk.strip())
            else:
                all_chunks.append(current.strip())

    # Merge small chunks
    all_chunks = _merge_small(all_chunks, min_chunk_size)

    # Build Chunk objects
    chunks: list[Chunk] = []
    pos = 0
    for i, chunk_text in enumerate(all_chunks):
        start_pos = text.find(chunk_text, pos)
        if start_pos == -1:
            start_pos = pos
        end_pos = start_pos + len(chunk_text)
        chunks.append(
            Chunk(
                text=chunk_text,
                index=i,
                start_char=start_pos,
                end_char=end_pos,
                metadata={"strategy": "semantic"},
            )
        )
        pos = end_pos

    return chunks


# ── Recursive ──────────────────────────────────────────────────────────


def recursive(
    text: str,
    chunk_size: int = 1024,
    chunk_overlap: int = 128,
    separators: list[str] | None = None,
) -> list[Chunk]:
    """
    Recursive character splitter — tries separators in order,
    recursing into smaller units when a chunk is too large.

    Style: LangChain's RecursiveCharacterTextSplitter.
    """
    if separators is None:
        separators = ["\n\n", "\n", ". ", " ", ""]

    def _split(_text: str, _seps: list[str]) -> list[str]:
        if not _seps:
            return [_text]
        sep = _seps[0]
        if sep == "":
            # Character-level split
            pieces = [
                _text[i : i + chunk_size]
                for i in range(0, len(_text), chunk_size - chunk_overlap)
            ]
        else:
            pieces = _text.split(sep)
        # Recurse on pieces that are too large
        result: list[str] = []
        for piece in pieces:
            if len(piece) > chunk_size:
                result.extend(_split(piece, _seps[1:]))
            else:
                result.append(piece)
        return result

    pieces = _split(text, list(separators))

    chunks: list[Chunk] = []
    pos = 0
    for i, piece in enumerate(pieces):
        piece = piece.strip()
        if not piece:
            continue
        start_pos = text.find(piece, pos)
        if start_pos == -1:
            start_pos = pos
        chunks.append(
            Chunk(
                text=piece,
                index=i,
                start_char=start_pos,
                end_char=start_pos + len(piece),
                metadata={"strategy": "recursive"},
            )
        )
        pos = start_pos + len(piece)

    return chunks


# ── Fixed ──────────────────────────────────────────────────────────────


def fixed(
    text: str,
    chunk_size: int = 1024,
) -> list[Chunk]:
    """Simple character split, no overlap. Fastest option."""
    chunks: list[Chunk] = []
    for i in range(0, len(text), chunk_size):
        chunk_text = text[i : i + chunk_size].strip()
        if chunk_text:
            chunks.append(
                Chunk(
                    text=chunk_text,
                    index=len(chunks),
                    start_char=i,
                    end_char=min(i + chunk_size, len(text)),
                    metadata={"strategy": "fixed"},
                )
            )
    return chunks


# ── Dispatcher ─────────────────────────────────────────────────────────

STRATEGIES: dict[str, Callable[..., list[Chunk]]] = {
    "sliding_window": sliding_window,
    "semantic": semantic,
    "recursive": recursive,
    "fixed": fixed,
}


def chunk(
    text: str,
    strategy: str = "sliding_window",
    **kwargs,
) -> list[Chunk]:
    """
    Split text into chunks using the chosen strategy.

    Args:
        text: Input text.
        strategy: One of 'sliding_window', 'semantic', 'recursive', 'fixed'.
        **kwargs: Passed to the strategy function.

    Returns:
        List of Chunk objects.
    """
    if strategy not in STRATEGIES:
        raise ValueError(
            f"Unknown strategy '{strategy}'. Choose from: {list(STRATEGIES)}"
        )

    return STRATEGIES[strategy](text, **kwargs)
