"""Unit tests for research features — search is pure logic, AI calls are mocked."""

from legal_doc_engine.research import search_documents, _find_snippet, KeyInfo


FAKE_DOCS = {
    "doc1": {
        "status": "completed",
        "original_filename": "contract.pdf",
        "client_name": "Acme",
        "classification": {"document_type": "Contract"},
        "markdown": "# Agreement\n\nThis force majeure clause applies when...\n\nThe indemnification cap is $500,000.",
        "markdown_length": 100,
    },
    "doc2": {
        "status": "completed",
        "original_filename": "motion.pdf",
        "client_name": "Globex",
        "classification": {"document_type": "Motion"},
        "markdown": "# Motion to Dismiss\n\nThe plaintiff alleges breach of contract.\n\nThere is no force majeure defense here.",
        "markdown_length": 120,
    },
    "doc3": {
        "status": "failed",
        "original_filename": "broken.pdf",
        "markdown": None,
        "markdown_length": 0,
    },
}


class TestSearchDocuments:
    """Tests for cross-document search."""

    def test_finds_matching_docs(self) -> None:
        results = search_documents(FAKE_DOCS, "force majeure")
        assert len(results) == 2
        filenames = {r["filename"] for r in results}
        assert "contract.pdf" in filenames
        assert "motion.pdf" in filenames

    def test_skips_failed_docs(self) -> None:
        results = search_documents(FAKE_DOCS, "anything")
        doc_ids = {r["doc_id"] for r in results}
        assert "doc3" not in doc_ids

    def test_returns_empty_for_no_match(self) -> None:
        results = search_documents(FAKE_DOCS, "xyznonexistent")
        assert results == []

    def test_respects_max_results(self) -> None:
        results = search_documents(FAKE_DOCS, "force", max_results=1)
        assert len(results) == 1

    def test_results_sorted_by_score(self) -> None:
        results = search_documents(FAKE_DOCS, "force majeure indemnification")
        # doc1 has "force majeure" AND "indemnification" -> higher score
        assert results[0]["doc_id"] == "doc1"

    def test_snippet_contains_query_context(self) -> None:
        results = search_documents(FAKE_DOCS, "indemnification")
        assert len(results) == 1
        assert "indemnification" in results[0]["snippet"].lower()


class TestFindSnippet:
    """Tests for the snippet extraction helper."""

    def test_returns_context_around_match(self) -> None:
        text = "A" * 200 + " KEYWORD " + "B" * 200
        snippet = _find_snippet(text, ["keyword"], context_chars=50)
        assert "KEYWORD" in snippet

    def test_handles_no_match(self) -> None:
        snippet = _find_snippet("some text", ["nonexistent"])
        # Should still return something (beginning of text)
        assert isinstance(snippet, str)


class TestKeyInfo:
    """Tests for the KeyInfo dataclass defaults."""

    def test_defaults(self) -> None:
        info = KeyInfo()
        assert info.summary == ""
        assert info.parties == []
        assert info.monetary_amounts == []
        assert info.obligations == []
