"""End-to-end processing pipeline.

Orchestrates: Extract Markdown -> Chunk -> Classify -> Organize.

Supports both single-file and batch-folder processing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from legal_doc_engine.engine import LegalDocEngine
from legal_doc_engine.chunker import chunk_markdown_by_headers, SemanticChunk
from legal_doc_engine.classifier import classify_document, DocumentClassification
from legal_doc_engine.organizer import organize_file

logger = logging.getLogger("legal_doc_engine.pipeline")

# File extensions the pipeline can handle
SUPPORTED_EXTENSIONS = {
    ".pdf", ".tiff", ".tif", ".jpeg", ".jpg", ".png", ".bmp", ".docx",
}


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


# ------------------------------------------------------------------ #
# Batch / Folder processing
# ------------------------------------------------------------------ #


def discover_files(
    folder: str | Path,
    *,
    recursive: bool = True,
) -> list[Path]:
    """Find all supported document files in *folder*.

    Parameters
    ----------
    folder : str | Path
        Directory to scan.
    recursive : bool
        If ``True``, search sub-folders as well.

    Returns
    -------
    list[Path]
        Sorted list of discovered file paths.
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder}")

    pattern = "**/*" if recursive else "*"
    files = [
        p for p in folder.glob(pattern)
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    files.sort()
    logger.info(
        "Discovered %d supported files in '%s' (recursive=%s)",
        len(files),
        folder,
        recursive,
    )
    return files


def process_folder(
    folder: str | Path,
    *,
    client_name: str = "General",
    recursive: bool = True,
    on_progress: Callable[[int, int, str, str], None] | None = None,
) -> dict:
    """Process every supported document in *folder*.

    Parameters
    ----------
    folder : str | Path
        Directory containing legal documents.
    client_name : str
        Client/matter name for organization.
    recursive : bool
        Search sub-folders as well.
    on_progress : callable, optional
        ``(current_index, total, filename, status)`` callback fired
        after each file is attempted.

    Returns
    -------
    dict
        Summary::

            {
                "folder": Path,
                "total_files": int,
                "succeeded": int,
                "failed": int,
                "results": [dict, ...],  # per-file results
                "errors": [dict, ...],   # per-file errors
            }
    """
    folder = Path(folder)
    files = discover_files(folder, recursive=recursive)

    results: list[dict] = []
    errors: list[dict] = []

    logger.info(
        "========== Batch start: %d files in '%s' ==========",
        len(files),
        folder,
    )

    for idx, file_path in enumerate(files):
        try:
            result = process_document(file_path, client_name=client_name)
            results.append({
                "source": str(result["source"]),
                "destination": str(result["destination"]),
                "document_type": result["classification"].document_type,
                "parties": result["classification"].parties,
                "suggested_filename": result["classification"].suggested_filename,
                "markdown_length": result["markdown_length"],
                "num_chunks": result["num_chunks"],
            })
            if on_progress:
                on_progress(idx + 1, len(files), file_path.name, "completed")
        except Exception as exc:
            logger.exception("Failed to process %s", file_path.name)
            errors.append({
                "source": str(file_path),
                "error": str(exc),
            })
            if on_progress:
                on_progress(idx + 1, len(files), file_path.name, "failed")

    logger.info(
        "========== Batch complete: %d succeeded, %d failed ==========",
        len(results),
        len(errors),
    )

    return {
        "folder": folder,
        "total_files": len(files),
        "succeeded": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }
