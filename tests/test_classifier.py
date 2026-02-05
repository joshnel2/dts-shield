"""Unit tests for the classifier — tests the JSON parsing logic only.

No Azure OpenAI calls are made; we mock the API call.
"""

from unittest.mock import patch, MagicMock

from legal_doc_engine.classifier import (
    _parse_classification,
    classify_document,
    DocumentClassification,
)


class TestParseClassification:
    """Tests for ``_parse_classification``."""

    def test_valid_json(self) -> None:
        raw = (
            '{"document_type": "Motion", '
            '"parties": ["Alice", "Bob"], '
            '"suggested_filename": "2026-01-15 - Motion - Alice.pdf"}'
        )
        result = _parse_classification(raw)
        assert result.document_type == "Motion"
        assert result.parties == ["Alice", "Bob"]
        assert result.suggested_filename == "2026-01-15 - Motion - Alice.pdf"

    def test_missing_keys_use_defaults(self) -> None:
        result = _parse_classification("{}")
        assert result.document_type == "Unknown"
        assert result.parties == []
        assert result.suggested_filename == "Unknown.pdf"

    def test_invalid_json_returns_default(self) -> None:
        result = _parse_classification("NOT JSON")
        assert result.document_type == "Unknown"
        assert result.raw_response == "NOT JSON"


class TestClassifyDocument:
    """Tests for ``classify_document`` with mocked OpenAI."""

    @patch("legal_doc_engine.classifier._call_openai")
    def test_returns_classification(self, mock_call: MagicMock) -> None:
        mock_call.return_value = (
            '{"document_type": "Affidavit", '
            '"parties": ["Jane Doe"], '
            '"suggested_filename": "2026-02-05 - Affidavit - Jane Doe.pdf"}'
        )
        result = classify_document("Some legal text here...")
        assert isinstance(result, DocumentClassification)
        assert result.document_type == "Affidavit"
        mock_call.assert_called_once()

    def test_empty_text_returns_default(self) -> None:
        result = classify_document("")
        assert result.document_type == "Unknown"
