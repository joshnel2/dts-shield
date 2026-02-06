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
from pydantic import BaseModel

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
# In-memory stores (persist for the lifetime of the server)
# ------------------------------------------------------------------ #

_documents: dict[str, dict[str, Any]] = {}
_batch_jobs: dict[str, dict[str, Any]] = {}

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
# Research Features — Q&A, Key Info, Summary, Search
# ------------------------------------------------------------------ #


class ChatRequest(BaseModel):
    """Request body for document Q&A."""
    doc_id: str | None = None
    doc_ids: list[str] | None = None
    question: str


class SearchRequest(BaseModel):
    """Request body for cross-document search."""
    query: str
    max_results: int = 20


@app.post("/api/chat")
async def chat_with_document(req: ChatRequest):
    """Ask a question about one or more documents."""
    from legal_doc_engine.research import ask_document, ask_documents

    if not req.question.strip():
        raise HTTPException(400, "Question cannot be empty.")

    # Single document Q&A
    if req.doc_id:
        if req.doc_id not in _documents:
            raise HTTPException(404, "Document not found.")
        doc = _documents[req.doc_id]
        if not doc.get("markdown"):
            raise HTTPException(400, "Document has not been processed yet.")
        answer = await asyncio.to_thread(ask_document, doc["markdown"], req.question)
        return {"answer": answer, "doc_id": req.doc_id}

    # Multi-document Q&A
    if req.doc_ids:
        docs = []
        for did in req.doc_ids:
            if did not in _documents:
                continue
            doc = _documents[did]
            if doc.get("markdown"):
                docs.append({"name": doc.get("original_filename", did), "markdown": doc["markdown"]})
        if not docs:
            raise HTTPException(400, "No processed documents found for the given IDs.")
        answer = await asyncio.to_thread(ask_documents, docs, req.question)
        return {"answer": answer, "doc_ids": req.doc_ids}

    # Search all documents if no specific doc given
    raise HTTPException(400, "Provide doc_id or doc_ids.")


@app.post("/api/key-info/{doc_id}")
async def get_key_info(doc_id: str):
    """Extract structured key information from a document."""
    from legal_doc_engine.research import extract_key_info

    if doc_id not in _documents:
        raise HTTPException(404, "Document not found.")
    doc = _documents[doc_id]
    if not doc.get("markdown"):
        raise HTTPException(400, "Document has not been processed yet.")

    # Cache: don't re-extract if already done
    if doc.get("key_info"):
        return doc["key_info"]

    info = await asyncio.to_thread(extract_key_info, doc["markdown"])
    doc["key_info"] = info.raw
    return info.raw


@app.post("/api/summary/{doc_id}")
async def get_summary(doc_id: str):
    """Generate an executive summary of a document."""
    from legal_doc_engine.research import summarize_document

    if doc_id not in _documents:
        raise HTTPException(404, "Document not found.")
    doc = _documents[doc_id]
    if not doc.get("markdown"):
        raise HTTPException(400, "Document has not been processed yet.")

    # Cache
    if doc.get("summary"):
        return {"summary": doc["summary"]}

    summary = await asyncio.to_thread(summarize_document, doc["markdown"])
    doc["summary"] = summary
    return {"summary": summary}


@app.post("/api/search")
async def search_docs(req: SearchRequest):
    """Search across all processed documents."""
    from legal_doc_engine.research import search_documents

    if not req.query.strip():
        raise HTTPException(400, "Query cannot be empty.")

    results = search_documents(_documents, req.query, max_results=req.max_results)
    return {"query": req.query, "total_results": len(results), "results": results}


# ------------------------------------------------------------------ #
# Batch / Folder Processing
# ------------------------------------------------------------------ #


class BatchRequest(BaseModel):
    """Request body for starting a batch folder job."""
    folder_path: str
    client_name: str = "General"
    recursive: bool = True


def _scan_folder(folder: Path, recursive: bool) -> list[Path]:
    """Find all supported files in a directory."""
    pattern = "**/*" if recursive else "*"
    return sorted(
        p for p in folder.glob(pattern)
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )


async def _process_batch_in_background(batch_id: str, files: list[Path], client_name: str) -> None:
    """Process every file in the batch sequentially in the background."""
    from legal_doc_engine.engine import LegalDocEngine
    from legal_doc_engine.chunker import chunk_markdown_by_headers
    from legal_doc_engine.classifier import classify_document
    from legal_doc_engine.organizer import organize_file

    job = _batch_jobs[batch_id]
    job["status"] = "processing"

    for idx, file_path in enumerate(files):
        file_entry: dict[str, Any] = {
            "filename": file_path.name,
            "relative_path": str(file_path),
            "status": "processing",
            "classification": None,
            "destination": None,
            "error": None,
        }
        job["files"][str(file_path)] = file_entry
        job["current_index"] = idx + 1
        job["current_file"] = file_path.name

        # Also register in the main documents store so it shows on dashboard
        doc_id = f"b-{batch_id}-{idx}"

        _documents[doc_id] = {
            "id": doc_id,
            "original_filename": file_path.name,
            "client_name": client_name,
            "file_size": file_path.stat().st_size if file_path.exists() else 0,
            "uploaded_at": datetime.now().isoformat(),
            "status": "extracting",
            "markdown": None,
            "markdown_length": 0,
            "num_chunks": 0,
            "chunks": [],
            "classification": None,
            "destination": None,
            "error": None,
            "completed_at": None,
            "batch_id": batch_id,
        }

        try:
            # 1. Extract
            _documents[doc_id]["status"] = "extracting"
            engine = LegalDocEngine()
            markdown = await asyncio.to_thread(engine.extract_markdown, file_path)
            _documents[doc_id]["markdown"] = markdown
            _documents[doc_id]["markdown_length"] = len(markdown)

            # 2. Chunk
            _documents[doc_id]["status"] = "chunking"
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

            # 3. Classify
            _documents[doc_id]["status"] = "classifying"
            classification = await asyncio.to_thread(classify_document, markdown)
            cls_dict = {
                "document_type": classification.document_type,
                "parties": classification.parties,
                "suggested_filename": classification.suggested_filename,
            }
            _documents[doc_id]["classification"] = cls_dict

            # 4. Organize
            _documents[doc_id]["status"] = "organizing"
            destination = organize_file(
                file_path, classification, client_name=client_name
            )
            _documents[doc_id]["destination"] = str(destination)
            _documents[doc_id]["status"] = "completed"
            _documents[doc_id]["completed_at"] = datetime.now().isoformat()

            file_entry["status"] = "completed"
            file_entry["classification"] = cls_dict
            file_entry["destination"] = str(destination)
            job["succeeded"] += 1

            logger.info("Batch %s: [%d/%d] %s -> %s", batch_id, idx + 1, len(files), file_path.name, destination)

        except Exception as exc:
            logger.exception("Batch %s: Failed on %s", batch_id, file_path.name)
            file_entry["status"] = "failed"
            file_entry["error"] = str(exc)
            job["failed_count"] += 1

            _documents[doc_id]["status"] = "failed"
            _documents[doc_id]["error"] = str(exc)

    job["status"] = "completed"
    job["completed_at"] = datetime.now().isoformat()
    logger.info(
        "Batch %s complete: %d succeeded, %d failed",
        batch_id,
        job["succeeded"],
        job["failed_count"],
    )


@app.post("/api/batch")
async def start_batch(req: BatchRequest):
    """Start processing all documents in a server-side folder."""
    folder = Path(req.folder_path)
    if not folder.is_dir():
        raise HTTPException(400, f"'{req.folder_path}' is not a valid directory on the server.")

    files = _scan_folder(folder, req.recursive)
    if not files:
        raise HTTPException(
            400,
            f"No supported documents found in '{req.folder_path}'. "
            f"Supported types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    batch_id = str(uuid.uuid4())[:8]
    _batch_jobs[batch_id] = {
        "id": batch_id,
        "folder": str(folder),
        "client_name": req.client_name,
        "recursive": req.recursive,
        "total_files": len(files),
        "succeeded": 0,
        "failed_count": 0,
        "current_index": 0,
        "current_file": None,
        "status": "queued",
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "files": {},
    }

    asyncio.create_task(_process_batch_in_background(batch_id, files, req.client_name))

    return {
        "batch_id": batch_id,
        "total_files": len(files),
        "message": f"Batch started. Processing {len(files)} documents.",
    }


@app.get("/api/batch")
async def list_batches():
    """List all batch jobs."""
    return sorted(
        [
            {k: v for k, v in job.items() if k != "files"}
            for job in _batch_jobs.values()
        ],
        key=lambda j: j.get("started_at", ""),
        reverse=True,
    )


@app.get("/api/batch/{batch_id}")
async def get_batch(batch_id: str):
    """Get full details for a batch job, including per-file results."""
    if batch_id not in _batch_jobs:
        raise HTTPException(404, "Batch job not found.")
    return _batch_jobs[batch_id]


@app.post("/api/scan-folder")
async def scan_folder(req: BatchRequest):
    """Preview what files would be processed in a folder (dry run)."""
    folder = Path(req.folder_path)
    if not folder.is_dir():
        raise HTTPException(400, f"'{req.folder_path}' is not a valid directory on the server.")

    files = _scan_folder(folder, req.recursive)
    return {
        "folder": str(folder),
        "recursive": req.recursive,
        "total_files": len(files),
        "files": [
            {
                "name": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "extension": f.suffix.lower(),
            }
            for f in files
        ],
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
