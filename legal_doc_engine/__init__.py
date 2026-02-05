"""Legal Document Processing Orchestrator.

A Python-based engine for extracting, classifying, and organizing
legal documents using Azure AI Document Intelligence and Azure OpenAI.
"""

__version__ = "1.0.0"

from legal_doc_engine.engine import LegalDocEngine
from legal_doc_engine.chunker import chunk_markdown_by_headers
from legal_doc_engine.classifier import classify_document
from legal_doc_engine.watcher import InboxWatcher

__all__ = [
    "LegalDocEngine",
    "chunk_markdown_by_headers",
    "classify_document",
    "InboxWatcher",
]
