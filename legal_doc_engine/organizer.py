"""File Organizer — move classified documents into the target hierarchy.

Target structure::

    organized/
      └── {client_name}/
            └── {document_type}/
                  └── YYYY-MM-DD - Type - Party.pdf
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from legal_doc_engine.classifier import DocumentClassification
from legal_doc_engine.config import settings

logger = logging.getLogger("legal_doc_engine.organizer")


def _sanitize(name: str) -> str:
    """Remove characters that are unsafe for file/directory names."""
    unsafe = '<>:"/\\|?*'
    for ch in unsafe:
        name = name.replace(ch, "_")
    return name.strip().strip(".")


def organize_file(
    source: Path,
    classification: DocumentClassification,
    *,
    client_name: str = "General",
    organized_root: Path | None = None,
) -> Path:
    """Move *source* into the organized folder hierarchy.

    Parameters
    ----------
    source : Path
        The original file on disk.
    classification : DocumentClassification
        Classification result from the AI classifier.
    client_name : str
        Name of the client/matter folder (default ``"General"``).
    organized_root : Path, optional
        Root of the organized tree. Falls back to settings.

    Returns
    -------
    Path
        The final destination path of the moved file.
    """
    root = organized_root or settings.organized_folder
    doc_type = _sanitize(classification.document_type) or "Uncategorized"
    client_dir = _sanitize(client_name) or "General"

    target_dir = root / client_dir / doc_type
    target_dir.mkdir(parents=True, exist_ok=True)

    # Use the AI-suggested filename; fall back to the original name.
    suggested = classification.suggested_filename
    if not suggested or suggested == "Unknown.pdf":
        suggested = source.name

    # Preserve the original extension if the suggestion lacks one
    suggested_path = Path(_sanitize(suggested))
    if not suggested_path.suffix:
        suggested_path = suggested_path.with_suffix(source.suffix)

    destination = target_dir / suggested_path.name

    # Avoid overwriting: append a counter if needed
    counter = 1
    while destination.exists():
        stem = suggested_path.stem
        destination = target_dir / f"{stem}_{counter}{suggested_path.suffix}"
        counter += 1

    shutil.move(str(source), str(destination))
    logger.info("Organized: %s -> %s", source.name, destination)
    return destination
