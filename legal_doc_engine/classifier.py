"""AI Classification — categorise legal documents with Azure OpenAI.

Sends the first 2,000 characters of a document to a GPT-4o deployment
and receives back a structured JSON classification:

    {
        "document_type": "Motion",
        "parties": ["Alice Smith", "Bob Jones"],
        "suggested_filename": "2026-02-05 - Motion - Alice Smith.pdf"
    }
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from openai import AzureOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from legal_doc_engine.config import settings

logger = logging.getLogger("legal_doc_engine.classifier")

# ------------------------------------------------------------------ #
# Data model
# ------------------------------------------------------------------ #


@dataclass
class DocumentClassification:
    """Result of AI classification on a legal document."""

    document_type: str = "Unknown"
    parties: list[str] = field(default_factory=list)
    suggested_filename: str = "Unknown.pdf"
    raw_response: str = ""


# ------------------------------------------------------------------ #
# System prompt
# ------------------------------------------------------------------ #

_SYSTEM_PROMPT = """\
You are a legal-document classification assistant working for a law firm.

Given the beginning of a legal document, return a JSON object with exactly
these three keys:

  - "document_type": a short label such as "Motion", "Affidavit",
    "Contract", "Brief", "Memorandum", "Complaint", "Subpoena",
    "Deposition", "Settlement Agreement", "Court Order", "Pleading",
    or another appropriate legal category.
  - "parties": a JSON array of the names of the people or entities
    involved (e.g., ["Alice Smith", "ACME Corp."]).
  - "suggested_filename": a string in the format
    "YYYY-MM-DD - Type - PrimaryParty.pdf"
    (use today's date if the document date is unclear).

Respond ONLY with valid JSON. No markdown fences, no explanation.
"""


# ------------------------------------------------------------------ #
# Public API
# ------------------------------------------------------------------ #


def classify_document(
    text: str,
    *,
    endpoint: str | None = None,
    api_key: str | None = None,
    deployment: str | None = None,
    api_version: str | None = None,
    char_limit: int = 2000,
) -> DocumentClassification:
    """Classify a legal document using Azure OpenAI GPT-4o.

    Parameters
    ----------
    text : str
        The full (or partial) Markdown text of the document.
    endpoint, api_key, deployment, api_version : str, optional
        Azure OpenAI connection details. Fall back to ``settings``.
    char_limit : int
        Number of leading characters to send (default 2 000).

    Returns
    -------
    DocumentClassification
        Structured classification result.
    """
    snippet = text[:char_limit].strip()
    if not snippet:
        logger.warning("Empty text supplied for classification.")
        return DocumentClassification()

    logger.info(
        "Classifying document (snippet length=%d chars, limit=%d)",
        len(snippet),
        char_limit,
    )

    raw = _call_openai(
        snippet,
        endpoint=endpoint or settings.openai_endpoint,
        api_key=api_key or settings.openai_api_key,
        deployment=deployment or settings.openai_deployment,
        api_version=api_version or settings.openai_api_version,
    )

    return _parse_classification(raw)


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
def _call_openai(
    snippet: str,
    *,
    endpoint: str,
    api_key: str,
    deployment: str,
    api_version: str,
) -> str:
    """Send the classification request to Azure OpenAI with retries."""
    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
    )

    logger.debug("Calling Azure OpenAI deployment=%s", deployment)

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Classify the following legal document excerpt:\n\n"
                    f"{snippet}"
                ),
            },
        ],
        temperature=0.0,
        max_tokens=512,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content or "{}"
    logger.debug("OpenAI raw response: %s", content)
    return content


def _parse_classification(raw_json: str) -> DocumentClassification:
    """Parse the JSON response into a ``DocumentClassification``."""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        logger.error("Failed to parse classification JSON: %s", raw_json)
        return DocumentClassification(raw_response=raw_json)

    return DocumentClassification(
        document_type=data.get("document_type", "Unknown"),
        parties=data.get("parties", []),
        suggested_filename=data.get("suggested_filename", "Unknown.pdf"),
        raw_response=raw_json,
    )
