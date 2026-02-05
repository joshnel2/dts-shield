"""Unit tests for batch/folder processing — no Azure credentials required."""

import tempfile
from pathlib import Path

from legal_doc_engine.pipeline import discover_files, SUPPORTED_EXTENSIONS


class TestDiscoverFiles:
    """Tests for ``discover_files``."""

    def test_finds_supported_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "contract.pdf").write_bytes(b"fake")
            (root / "photo.jpg").write_bytes(b"fake")
            (root / "readme.txt").write_bytes(b"ignore me")
            (root / "notes.md").write_bytes(b"ignore me")

            files = discover_files(root)
            names = {f.name for f in files}
            assert "contract.pdf" in names
            assert "photo.jpg" in names
            assert "readme.txt" not in names
            assert "notes.md" not in names

    def test_recursive_finds_nested_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sub = root / "subdir" / "deep"
            sub.mkdir(parents=True)
            (root / "top.pdf").write_bytes(b"fake")
            (sub / "nested.docx").write_bytes(b"fake")

            files = discover_files(root, recursive=True)
            assert len(files) == 2

    def test_non_recursive_ignores_nested(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sub = root / "subdir"
            sub.mkdir()
            (root / "top.pdf").write_bytes(b"fake")
            (sub / "nested.docx").write_bytes(b"fake")

            files = discover_files(root, recursive=False)
            assert len(files) == 1
            assert files[0].name == "top.pdf"

    def test_empty_folder_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            files = discover_files(tmpdir)
            assert files == []

    def test_raises_on_nonexistent_folder(self) -> None:
        import pytest

        with pytest.raises(NotADirectoryError):
            discover_files("/nonexistent/path/xyz")

    def test_returns_sorted_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "z_last.pdf").write_bytes(b"fake")
            (root / "a_first.pdf").write_bytes(b"fake")
            (root / "m_middle.pdf").write_bytes(b"fake")

            files = discover_files(root)
            names = [f.name for f in files]
            assert names == sorted(names)
