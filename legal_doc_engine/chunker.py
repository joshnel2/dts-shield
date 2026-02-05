"""Semantic Chunking — split Markdown by header boundaries.

Legal documents use headers to delineate sections (e.g., "RECITALS",
"ARTICLE I", "WHEREAS"). This module splits extracted Markdown so that
each chunk begins with its nearest header, keeping legal headers
together with their paragraphs.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("legal_doc_engine.chunker")

# Matches Markdown ATX-style headers: #, ##, ### etc.
_HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)", re.MULTILINE)


@dataclass
class SemanticChunk:
    """A single semantic chunk extracted from a Markdown document.

    Attributes
    ----------
    header_level : int
        The header level (1–6). ``0`` means the chunk is a preamble
        with no preceding header.
    header_text : str
        The raw header text (without ``#`` symbols).
    content : str
        The full text of the chunk, *including* the header line.
    index : int
        Zero-based position of this chunk in the document.
    """

    header_level: int = 0
    header_text: str = ""
    content: str = ""
    index: int = 0
    metadata: dict = field(default_factory=dict)


def chunk_markdown_by_headers(
    markdown: str,
    *,
    max_header_depth: int = 6,
) -> list[SemanticChunk]:
    """Split *markdown* into semantic chunks at header boundaries.

    Parameters
    ----------
    markdown : str
        The full Markdown text to split.
    max_header_depth : int, optional
        Maximum header depth to split on (default ``6`` = all headers).
        For example, ``2`` means only split on ``#`` and ``##``.

    Returns
    -------
    list[SemanticChunk]
        Ordered list of semantic chunks.
    """
    if not markdown or not markdown.strip():
        logger.warning("Empty markdown received; returning empty chunk list.")
        return []

    lines = markdown.split("\n")
    chunks: list[SemanticChunk] = []

    current_header_level = 0
    current_header_text = ""
    current_lines: list[str] = []
    chunk_index = 0

    for line in lines:
        match = _HEADER_RE.match(line)
        if match:
            level = len(match.group(1))
            header_text = match.group(2).strip()

            # Only split if this header is within the requested depth
            if level <= max_header_depth:
                # Save the accumulated chunk (if any content exists)
                if current_lines:
                    content = "\n".join(current_lines).strip()
                    if content:
                        chunks.append(
                            SemanticChunk(
                                header_level=current_header_level,
                                header_text=current_header_text,
                                content=content,
                                index=chunk_index,
                            )
                        )
                        chunk_index += 1

                # Start a new chunk
                current_header_level = level
                current_header_text = header_text
                current_lines = [line]
                continue

        current_lines.append(line)

    # Flush the last chunk
    if current_lines:
        content = "\n".join(current_lines).strip()
        if content:
            chunks.append(
                SemanticChunk(
                    header_level=current_header_level,
                    header_text=current_header_text,
                    content=content,
                    index=chunk_index,
                )
            )

    logger.info("Produced %d semantic chunks from markdown.", len(chunks))
    return chunks
