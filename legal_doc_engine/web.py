"""FastAPI web application for the Legal Document Processing Orchestrator.

Provides a REST API and serves the frontend for lawyers to:
- Upload documents
- View processing status and history
- Browse organized files
- Preview extracted markdown and classification results
- Download organized documents
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from legal_doc_engine.config import settings
from legal_doc_engine.logging_config import setup_logging

logger = setup_logging()

app = FastAPI(
    title="Legal Doc Orchestrator",
    description="AI-powered legal document processing and organization",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------ #
# In-memory document store (persists for the lifetime of the server)
# ------------------------------------------------------------------ #

_documents: dict[str, dict[str, Any]] = {}

# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

SUPPORTED_EXTENSIONS = {
    ".pdf", ".tiff", ".tif", ".jpeg", ".jpg", ".png", ".bmp", ".docx",
}

UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def _walk_organized(root: Path) -> list[dict]:
    """Recursively walk the organized folder and return a tree structure."""
    items: list[dict] = []
    if not root.exists():
        return items
    for entry in sorted(root.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            items.append({
                "name": entry.name,
                "type": "folder",
                "path": str(entry.relative_to(settings.organized_folder)),
                "children": _walk_organized(entry),
            })
        else:
            items.append({
                "name": entry.name,
                "type": "file",
                "path": str(entry.relative_to(settings.organized_folder)),
                "size": entry.stat().st_size,
                "modified": datetime.fromtimestamp(
                    entry.stat().st_mtime
                ).isoformat(),
            })
    return items


async def _process_in_background(doc_id: str, file_path: Path, client_name: str) -> None:
    """Run the processing pipeline in a background thread."""
    try:
        _documents[doc_id]["status"] = "extracting"

        # Import here to avoid circular imports and allow lazy loading
        from legal_doc_engine.engine import LegalDocEngine
        from legal_doc_engine.chunker import chunk_markdown_by_headers
        from legal_doc_engine.classifier import classify_document
        from legal_doc_engine.organizer import organize_file

        # Step 1: Extract Markdown
        engine = LegalDocEngine()
        markdown = await asyncio.to_thread(engine.extract_markdown, file_path)
        _documents[doc_id]["markdown"] = markdown
        _documents[doc_id]["markdown_length"] = len(markdown)
        _documents[doc_id]["status"] = "chunking"

        # Step 2: Chunk
        chunks = chunk_markdown_by_headers(markdown)
        _documents[doc_id]["num_chunks"] = len(chunks)
        _documents[doc_id]["chunks"] = [
            {
                "index": c.index,
                "header_level": c.header_level,
                "header_text": c.header_text,
                "content": c.content[:500] + ("..." if len(c.content) > 500 else ""),
            }
            for c in chunks
        ]
        _documents[doc_id]["status"] = "classifying"

        # Step 3: Classify
        classification = await asyncio.to_thread(classify_document, markdown)
        _documents[doc_id]["classification"] = {
            "document_type": classification.document_type,
            "parties": classification.parties,
            "suggested_filename": classification.suggested_filename,
        }
        _documents[doc_id]["status"] = "organizing"

        # Step 4: Organize
        destination = organize_file(
            file_path, classification, client_name=client_name
        )
        _documents[doc_id]["destination"] = str(destination)
        _documents[doc_id]["status"] = "completed"
        _documents[doc_id]["completed_at"] = datetime.now().isoformat()

        logger.info("Document %s processed successfully -> %s", doc_id, destination)

    except Exception as exc:
        logger.exception("Failed to process document %s", doc_id)
        _documents[doc_id]["status"] = "failed"
        _documents[doc_id]["error"] = str(exc)


# ------------------------------------------------------------------ #
# API Routes
# ------------------------------------------------------------------ #

@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...),
    client_name: str = Form("General"),
):
    """Upload a document for processing."""
    if not file.filename:
        raise HTTPException(400, "No filename provided.")

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    doc_id = str(uuid.uuid4())[:8]
    save_path = UPLOAD_DIR / f"{doc_id}_{file.filename}"

    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)

    _documents[doc_id] = {
        "id": doc_id,
        "original_filename": file.filename,
        "client_name": client_name,
        "file_size": len(content),
        "uploaded_at": datetime.now().isoformat(),
        "status": "queued",
        "markdown": None,
        "markdown_length": 0,
        "num_chunks": 0,
        "chunks": [],
        "classification": None,
        "destination": None,
        "error": None,
        "completed_at": None,
    }

    # Start background processing
    asyncio.create_task(_process_in_background(doc_id, save_path, client_name))

    return {"id": doc_id, "message": "Upload successful. Processing started."}


@app.get("/api/documents")
async def list_documents():
    """List all processed and in-progress documents."""
    docs = sorted(
        _documents.values(),
        key=lambda d: d.get("uploaded_at", ""),
        reverse=True,
    )
    # Return summary without full markdown
    return [
        {k: v for k, v in doc.items() if k not in ("markdown", "chunks")}
        for doc in docs
    ]


@app.get("/api/documents/{doc_id}")
async def get_document(doc_id: str):
    """Get full details for a specific document."""
    if doc_id not in _documents:
        raise HTTPException(404, "Document not found.")
    return _documents[doc_id]


@app.get("/api/browse")
async def browse_organized():
    """Browse the organized folder hierarchy."""
    root = settings.organized_folder
    root.mkdir(parents=True, exist_ok=True)
    return _walk_organized(root)


@app.get("/api/download")
async def download_file(path: str):
    """Download a file from the organized folder."""
    full_path = settings.organized_folder / path
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(404, "File not found.")
    # Security check — ensure path doesn't escape the organized folder
    try:
        full_path.resolve().relative_to(settings.organized_folder.resolve())
    except ValueError:
        raise HTTPException(403, "Access denied.")
    return FileResponse(full_path, filename=full_path.name)


@app.get("/api/stats")
async def get_stats():
    """Return summary statistics for the dashboard."""
    total = len(_documents)
    completed = sum(1 for d in _documents.values() if d["status"] == "completed")
    failed = sum(1 for d in _documents.values() if d["status"] == "failed")
    processing = total - completed - failed

    # Count organized files by type
    type_counts: dict[str, int] = {}
    for doc in _documents.values():
        if doc.get("classification"):
            dt = doc["classification"].get("document_type", "Unknown")
            type_counts[dt] = type_counts.get(dt, 0) + 1

    # Count by client
    client_counts: dict[str, int] = {}
    for doc in _documents.values():
        cn = doc.get("client_name", "General")
        client_counts[cn] = client_counts.get(cn, 0) + 1

    return {
        "total_documents": total,
        "completed": completed,
        "failed": failed,
        "processing": processing,
        "by_type": type_counts,
        "by_client": client_counts,
    }


# ------------------------------------------------------------------ #
# Serve Frontend
# ------------------------------------------------------------------ #

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main frontend page."""
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(500, "Frontend not found.")
    return index_path.read_text(encoding="utf-8")


# Mount static assets (CSS, JS, images) if the folder exists
if (FRONTEND_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")
