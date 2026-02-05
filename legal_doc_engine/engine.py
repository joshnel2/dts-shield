"""LegalDocEngine — Markdown extraction from legal documents.

Uses Azure AI Document Intelligence with the ``prebuilt-layout`` model,
``markdown`` output format, and ``ocrHighResolution`` analysis feature
to produce high-fidelity Markdown from scanned or digital PDFs.
"""

from __future__ import annotations

import logging
from pathlib import Path

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import (
    AnalyzeDocumentRequest,
    DocumentAnalysisFeature,
    DocumentContentFormat,
)
from azure.core.credentials import AzureKeyCredential
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from legal_doc_engine.config import settings

logger = logging.getLogger("legal_doc_engine.engine")


class LegalDocEngine:
    """Extract Markdown from legal documents via Azure Document Intelligence.

    Parameters
    ----------
    endpoint : str, optional
        Azure Document Intelligence endpoint. Falls back to settings.
    key : str, optional
        Azure Document Intelligence API key. Falls back to settings.
    """

    MODEL_ID = "prebuilt-layout"

    def __init__(
        self,
        endpoint: str | None = None,
        key: str | None = None,
    ) -> None:
        self._endpoint = endpoint or settings.doc_intelligence_endpoint
        self._key = key or settings.doc_intelligence_key
        if not self._endpoint or not self._key:
            raise ValueError(
                "Azure Document Intelligence endpoint and key are required. "
                "Set AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and "
                "AZURE_DOCUMENT_INTELLIGENCE_KEY."
            )
        self._client = DocumentIntelligenceClient(
            endpoint=self._endpoint,
            credential=AzureKeyCredential(self._key),
        )
        logger.info(
            "LegalDocEngine initialized (endpoint=%s)", self._endpoint
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def extract_markdown(self, file_path: str | Path) -> str:
        """Extract Markdown content from a document file.

        Parameters
        ----------
        file_path : str | Path
            Path to the document (PDF, TIFF, JPEG, PNG, BMP, DOCX).

        Returns
        -------
        str
            The extracted Markdown text.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")

        logger.info("Starting extraction for %s", file_path.name)

        with open(file_path, "rb") as f:
            document_bytes = f.read()

        content = self._analyze_document(document_bytes)
        logger.info(
            "Extraction complete for %s (%d characters)",
            file_path.name,
            len(content),
        )
        return content

    def extract_markdown_from_bytes(self, data: bytes) -> str:
        """Extract Markdown content from raw document bytes.

        Parameters
        ----------
        data : bytes
            Raw file bytes.

        Returns
        -------
        str
            The extracted Markdown text.
        """
        logger.info("Starting extraction from byte stream (%d bytes)", len(data))
        content = self._analyze_document(data)
        logger.info("Extraction complete (%d characters)", len(content))
        return content

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _analyze_document(self, document_bytes: bytes) -> str:
        """Call Azure Document Intelligence with retry logic.

        Uses ``prebuilt-layout``, ``markdown`` content format, and
        ``ocrHighResolution`` for maximum fidelity on legal documents.
        """
        logger.debug("Sending %d bytes to Document Intelligence", len(document_bytes))

        poller = self._client.begin_analyze_document(
            model_id=self.MODEL_ID,
            body=AnalyzeDocumentRequest(bytes_source=document_bytes),
            output_content_format=DocumentContentFormat.MARKDOWN,
            features=[DocumentAnalysisFeature.OCR_HIGH_RESOLUTION],
        )

        result = poller.result()
        return result.content or ""
