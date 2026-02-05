"""Unit tests for the semantic chunker — no Azure credentials required."""

from legal_doc_engine.chunker import chunk_markdown_by_headers, SemanticChunk


SAMPLE_MARKDOWN = """\
This is the preamble before any header.

# ARTICLE I — DEFINITIONS

"Agreement" means this contract between the parties.

## Section 1.1

First sub-section content here.

## Section 1.2

Second sub-section content here.

# ARTICLE II — OBLIGATIONS

The Seller shall deliver the goods.

### 2.1.a Minor Detail

Some minor detail nested three levels deep.

# ARTICLE III — TERMINATION

Either party may terminate upon 30 days' notice.
"""


class TestChunkMarkdownByHeaders:
    """Tests for ``chunk_markdown_by_headers``."""

    def test_returns_list_of_chunks(self) -> None:
        chunks = chunk_markdown_by_headers(SAMPLE_MARKDOWN)
        assert isinstance(chunks, list)
        assert all(isinstance(c, SemanticChunk) for c in chunks)

    def test_correct_number_of_chunks(self) -> None:
        chunks = chunk_markdown_by_headers(SAMPLE_MARKDOWN)
        # Preamble + ARTICLE I + Section 1.1 + Section 1.2 +
        # ARTICLE II + 2.1.a + ARTICLE III = 7
        assert len(chunks) == 7

    def test_preamble_has_level_zero(self) -> None:
        chunks = chunk_markdown_by_headers(SAMPLE_MARKDOWN)
        assert chunks[0].header_level == 0
        assert "preamble" in chunks[0].content.lower()

    def test_header_texts_are_preserved(self) -> None:
        chunks = chunk_markdown_by_headers(SAMPLE_MARKDOWN)
        headers = [c.header_text for c in chunks if c.header_level > 0]
        assert "ARTICLE I — DEFINITIONS" in headers
        assert "Section 1.1" in headers

    def test_max_header_depth_limits_splits(self) -> None:
        # Only split on # (level 1) — sub-headers stay merged
        chunks = chunk_markdown_by_headers(SAMPLE_MARKDOWN, max_header_depth=1)
        # Preamble + ARTICLE I + ARTICLE II + ARTICLE III = 4
        assert len(chunks) == 4

    def test_empty_input_returns_empty(self) -> None:
        assert chunk_markdown_by_headers("") == []
        assert chunk_markdown_by_headers("   \n\n  ") == []

    def test_no_headers_returns_single_chunk(self) -> None:
        text = "Just a plain paragraph with no headers at all."
        chunks = chunk_markdown_by_headers(text)
        assert len(chunks) == 1
        assert chunks[0].header_level == 0

    def test_chunk_indices_are_sequential(self) -> None:
        chunks = chunk_markdown_by_headers(SAMPLE_MARKDOWN)
        for i, chunk in enumerate(chunks):
            assert chunk.index == i
