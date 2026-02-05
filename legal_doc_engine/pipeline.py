"""End-to-end processing pipeline.

Orchestrates: Extract Markdown -> Chunk -> Classify -> Organize.
"""

from __future__ import annotations

import logging
from pathlib import Path

from legal_doc_engine.engine import LegalDocEngine
from legal_doc_engine.chunker import chunk_markdown_by_headers, SemanticChunk
from legal_doc_engine.classifier import classify_document, DocumentClassification
from legal_doc_engine.organizer import organize_file

logger = logging.getLogger("legal_doc_engine.pipeline")


def process_document(
    file_path: str | Path,
    *,
    client_name: str = "General",
) -> dict:
    """Run the full pipeline on a single document.

    Steps
    -----
    1. Extract Markdown via Azure Document Intelligence.
    2. Split into semantic chunks by headers.
    3. Classify the document via Azure OpenAI GPT-4o.
    4. Move/rename the file into the organized folder tree.

    Parameters
    ----------
    file_path : str | Path
        Path to the incoming document.
    client_name : str
        Name of the client/matter (used as top-level folder).

    Returns
    -------
    dict
        Summary of the processing result::

            {
                "source": Path,
                "markdown_length": int,
                "num_chunks": int,
                "classification": DocumentClassification,
                "destination": Path,
            }
    """
    file_path = Path(file_path)
    logger.info("========== Pipeline start: %s ==========", file_path.name)

    # 1. Extract Markdown ------------------------------------------------
    engine = LegalDocEngine()
    markdown = engine.extract_markdown(file_path)
    logger.info("Markdown extracted (%d chars).", len(markdown))

    # 2. Semantic Chunking -----------------------------------------------
    chunks: list[SemanticChunk] = chunk_markdown_by_headers(markdown)
    logger.info("Document chunked into %d semantic sections.", len(chunks))

    # 3. AI Classification -----------------------------------------------
    classification: DocumentClassification = classify_document(markdown)
    logger.info(
        "Classified as '%s' | parties=%s | suggested_filename='%s'",
        classification.document_type,
        classification.parties,
        classification.suggested_filename,
    )

    # 4. Organize / move -------------------------------------------------
    destination = organize_file(
        file_path,
        classification,
        client_name=client_name,
    )
    logger.info("File moved to %s", destination)
    logger.info("========== Pipeline complete: %s ==========", file_path.name)

    return {
        "source": file_path,
        "markdown_length": len(markdown),
        "num_chunks": len(chunks),
        "classification": classification,
        "destination": destination,
    }
