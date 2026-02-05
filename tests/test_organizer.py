"""Unit tests for the file organizer — uses temp directories."""

import tempfile
from pathlib import Path

from legal_doc_engine.classifier import DocumentClassification
from legal_doc_engine.organizer import organize_file, _sanitize


class TestSanitize:
    """Tests for ``_sanitize``."""

    def test_removes_unsafe_characters(self) -> None:
        assert _sanitize('file<>:"/\\|?*name') == "file_________name"

    def test_strips_dots_and_spaces(self) -> None:
        assert _sanitize("  hello...") == "hello"


class TestOrganizeFile:
    """Tests for ``organize_file``."""

    def test_moves_file_to_correct_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "test.pdf"
            source.write_bytes(b"fake pdf")

            organized_root = root / "organized"
            classification = DocumentClassification(
                document_type="Contract",
                parties=["Alice"],
                suggested_filename="2026-01-01 - Contract - Alice.pdf",
            )

            dest = organize_file(
                source,
                classification,
                client_name="TestClient",
                organized_root=organized_root,
            )

            assert dest.exists()
            assert "TestClient" in str(dest)
            assert "Contract" in str(dest)
            assert not source.exists()

    def test_avoids_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            organized_root = root / "organized"

            classification = DocumentClassification(
                document_type="Motion",
                suggested_filename="file.pdf",
            )

            # Create two source files
            src1 = root / "a.pdf"
            src1.write_bytes(b"one")
            src2 = root / "b.pdf"
            src2.write_bytes(b"two")

            dest1 = organize_file(
                src1, classification, organized_root=organized_root
            )
            dest2 = organize_file(
                src2, classification, organized_root=organized_root
            )

            assert dest1 != dest2
            assert dest1.exists()
            assert dest2.exists()
