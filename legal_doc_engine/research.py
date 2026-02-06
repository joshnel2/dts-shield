"""Research tools — Q&A, key-info extraction, summaries, and search.

These are the features that make Document Intelligence useful *after*
extraction: lawyers can ask questions, get structured key information,
generate summaries, and search across all their documents.
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

logger = logging.getLogger("legal_doc_engine.research")


# ------------------------------------------------------------------ #
# Shared OpenAI helper
# ------------------------------------------------------------------ #

def _get_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=settings.openai_endpoint,
        api_key=settings.openai_api_key,
        api_version=settings.openai_api_version,
    )


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _chat(system: str, user: str, *, json_mode: bool = False, max_tokens: int = 2048) -> str:
    """Send a chat completion request with retries."""
    client = _get_client()
    kwargs: dict = {
        "model": settings.openai_deployment,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


# ------------------------------------------------------------------ #
# 1. Document Q&A — chat with a document
# ------------------------------------------------------------------ #

_QA_SYSTEM = """\
You are a legal research assistant. A lawyer has uploaded a document and is
asking questions about it. The full document text (in Markdown) is provided
below. Answer the question accurately, citing the specific section or
paragraph from the document when possible.

If the answer is not in the document, say so clearly — never make up legal
information.

Keep answers concise and professional. Use bullet points when listing
multiple items.

--- DOCUMENT START ---
{document}
--- DOCUMENT END ---
"""

_QA_MULTI_SYSTEM = """\
You are a legal research assistant. A lawyer has uploaded multiple documents
and is asking questions that may span across them. The documents are provided
below in Markdown. Answer the question accurately, citing which document and
section the information comes from.

If the answer is not in any document, say so clearly — never make up legal
information.

{documents}
"""


def ask_document(markdown: str, question: str) -> str:
    """Ask a question about a single document.

    Parameters
    ----------
    markdown : str
        The full extracted Markdown text of the document.
    question : str
        The lawyer's question.

    Returns
    -------
    str
        The AI's answer.
    """
    # Truncate to fit context window (~120k chars is safe for gpt-4o)
    doc_text = markdown[:120_000]
    system = _QA_SYSTEM.format(document=doc_text)
    logger.info("Document Q&A: %s", question[:80])
    return _chat(system, question)


def ask_documents(documents: list[dict], question: str) -> str:
    """Ask a question across multiple documents.

    Parameters
    ----------
    documents : list[dict]
        Each dict has ``name`` and ``markdown`` keys.
    question : str
        The lawyer's question.

    Returns
    -------
    str
        The AI's answer citing which document(s) the info comes from.
    """
    # Build combined context, truncating each doc proportionally
    max_per_doc = 80_000 // max(len(documents), 1)
    doc_sections = []
    for doc in documents:
        name = doc.get("name", "Untitled")
        text = doc.get("markdown", "")[:max_per_doc]
        doc_sections.append(f"--- DOCUMENT: {name} ---\n{text}\n--- END ---")
    combined = "\n\n".join(doc_sections)
    system = _QA_MULTI_SYSTEM.format(documents=combined)
    logger.info("Multi-doc Q&A (%d docs): %s", len(documents), question[:80])
    return _chat(system, question)


# ------------------------------------------------------------------ #
# 2. Key Information Extraction
# ------------------------------------------------------------------ #

_KEY_INFO_SYSTEM = """\
You are a legal document analyst. Extract the following structured information
from this legal document. Return a JSON object with these keys:

- "summary": A 2-3 sentence executive summary of what this document is.
- "document_date": The date on the document (ISO format, or null if unclear).
- "effective_date": When the agreement/order takes effect (ISO format, or null).
- "expiration_date": When it expires or terminates (ISO format, or null).
- "parties": Array of objects, each with "name" and "role" (e.g. "Plaintiff", "Seller", "Landlord").
- "key_dates": Array of objects with "date" and "description" for any deadlines or important dates.
- "monetary_amounts": Array of objects with "amount" and "description" for any dollar figures.
- "obligations": Array of strings describing key obligations or requirements.
- "governing_law": The jurisdiction or governing law (string, or null).
- "case_number": Court case number if applicable (string, or null).
- "key_clauses": Array of objects with "title" and "summary" for the most important clauses.

Be thorough but concise. If information is not present, use null or empty arrays.
Respond ONLY with valid JSON.
"""


@dataclass
class KeyInfo:
    """Structured key information extracted from a legal document."""
    summary: str = ""
    document_date: str | None = None
    effective_date: str | None = None
    expiration_date: str | None = None
    parties: list[dict] = field(default_factory=list)
    key_dates: list[dict] = field(default_factory=list)
    monetary_amounts: list[dict] = field(default_factory=list)
    obligations: list[str] = field(default_factory=list)
    governing_law: str | None = None
    case_number: str | None = None
    key_clauses: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


def extract_key_info(markdown: str) -> KeyInfo:
    """Extract structured key information from a document.

    Parameters
    ----------
    markdown : str
        The full extracted Markdown text.

    Returns
    -------
    KeyInfo
        Structured extraction result.
    """
    doc_text = markdown[:60_000]
    logger.info("Extracting key info (%d chars)", len(doc_text))
    raw_json = _chat(_KEY_INFO_SYSTEM, doc_text, json_mode=True, max_tokens=4096)

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        logger.error("Failed to parse key info JSON")
        return KeyInfo()

    return KeyInfo(
        summary=data.get("summary", ""),
        document_date=data.get("document_date"),
        effective_date=data.get("effective_date"),
        expiration_date=data.get("expiration_date"),
        parties=data.get("parties", []),
        key_dates=data.get("key_dates", []),
        monetary_amounts=data.get("monetary_amounts", []),
        obligations=data.get("obligations", []),
        governing_law=data.get("governing_law"),
        case_number=data.get("case_number"),
        key_clauses=data.get("key_clauses", []),
        raw=data,
    )


# ------------------------------------------------------------------ #
# 3. Document Summary
# ------------------------------------------------------------------ #

_SUMMARY_SYSTEM = """\
You are a legal document summarizer working for a busy law firm.
Generate a clear, professional summary of this legal document.

Structure your summary with:
1. **Overview** — What type of document is this and what is its purpose? (2-3 sentences)
2. **Key Points** — Bullet list of the most important provisions, terms, or findings
3. **Parties & Roles** — Who is involved and in what capacity
4. **Critical Dates & Deadlines** — Any dates the lawyers need to know
5. **Action Items** — What needs to happen next, if anything

Be concise but don't miss anything a lawyer would need to know.
Write in plain professional English, not legalese.
"""


def summarize_document(markdown: str) -> str:
    """Generate an executive summary of a legal document.

    Parameters
    ----------
    markdown : str
        The full extracted Markdown text.

    Returns
    -------
    str
        Formatted summary text.
    """
    doc_text = markdown[:100_000]
    logger.info("Generating summary (%d chars)", len(doc_text))
    return _chat(_SUMMARY_SYSTEM, doc_text, max_tokens=2048)


# ------------------------------------------------------------------ #
# 4. Cross-Document Search
# ------------------------------------------------------------------ #

def search_documents(
    documents: dict[str, dict],
    query: str,
    *,
    max_results: int = 20,
) -> list[dict]:
    """Search across all processed documents by content.

    This performs a simple but effective keyword + fuzzy search across
    the extracted markdown of all documents. For a 70-person firm's
    volume this is sufficient; for larger scale, swap in a vector DB.

    Parameters
    ----------
    documents : dict
        The in-memory document store (doc_id -> doc dict).
    query : str
        Search query string.
    max_results : int
        Maximum number of results to return.

    Returns
    -------
    list[dict]
        Matching documents with relevant snippets.
    """
    query_lower = query.lower()
    query_terms = query_lower.split()
    results: list[dict] = []

    for doc_id, doc in documents.items():
        markdown = doc.get("markdown")
        if not markdown or doc.get("status") != "completed":
            continue

        markdown_lower = markdown.lower()

        # Score: how many query terms appear, weighted by frequency
        score = 0
        for term in query_terms:
            count = markdown_lower.count(term)
            if count > 0:
                score += 1 + min(count, 10) * 0.1  # cap frequency bonus

        if score == 0:
            continue

        # Find the best matching snippet
        snippet = _find_snippet(markdown, query_terms)

        results.append({
            "doc_id": doc_id,
            "filename": doc.get("original_filename", ""),
            "client_name": doc.get("client_name", ""),
            "document_type": (doc.get("classification") or {}).get("document_type", ""),
            "score": round(score, 2),
            "snippet": snippet,
            "markdown_length": doc.get("markdown_length", 0),
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:max_results]


def _find_snippet(text: str, terms: list[str], context_chars: int = 200) -> str:
    """Find the best snippet containing the most query terms."""
    text_lower = text.lower()
    best_pos = 0
    best_count = 0

    # Slide a window and find the region with the most term hits
    for term in terms:
        pos = text_lower.find(term)
        if pos == -1:
            continue
        # Count how many terms appear near this position
        window_start = max(0, pos - context_chars)
        window_end = min(len(text), pos + context_chars)
        window = text_lower[window_start:window_end]
        count = sum(1 for t in terms if t in window)
        if count > best_count:
            best_count = count
            best_pos = pos

    start = max(0, best_pos - context_chars // 2)
    end = min(len(text), best_pos + context_chars)
    snippet = text[start:end].strip()

    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."

    return snippet
