"""Tests for the FastAPI web application routes (no Azure credentials needed)."""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal_doc_engine.web import app


@pytest.fixture
def client():
    return TestClient(app)


class TestWebRoutes:
    """Smoke tests for the web API."""

    def test_homepage_returns_html(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Legal Doc Orchestrator" in resp.text

    def test_list_documents_empty(self, client: TestClient) -> None:
        resp = client.get("/api/documents")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_stats_endpoint(self, client: TestClient) -> None:
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_documents" in data
        assert "completed" in data

    def test_browse_returns_list(self, client: TestClient) -> None:
        resp = client.get("/api/browse")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_unknown_document_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/documents/nonexistent")
        assert resp.status_code == 404

    def test_upload_rejects_unsupported_file(self, client: TestClient) -> None:
        resp = client.post(
            "/api/upload",
            files={"file": ("test.txt", b"hello", "text/plain")},
            data={"client_name": "Test"},
        )
        assert resp.status_code == 400
        assert "Unsupported" in resp.json()["detail"]

    def test_download_nonexistent_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/download?path=nope.pdf")
        assert resp.status_code == 404


class TestBatchRoutes:
    """Tests for batch/folder processing API endpoints."""

    def test_scan_folder_finds_files(self, client: TestClient) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "doc.pdf").write_bytes(b"fake")
            Path(tmpdir, "img.png").write_bytes(b"fake")
            Path(tmpdir, "readme.txt").write_bytes(b"skip")

            resp = client.post(
                "/api/scan-folder",
                json={"folder_path": tmpdir, "recursive": True},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_files"] == 2
            names = {f["name"] for f in data["files"]}
            assert "doc.pdf" in names
            assert "img.png" in names
            assert "readme.txt" not in names

    def test_scan_folder_rejects_bad_path(self, client: TestClient) -> None:
        resp = client.post(
            "/api/scan-folder",
            json={"folder_path": "/nonexistent/xyz"},
        )
        assert resp.status_code == 400

    def test_batch_rejects_bad_path(self, client: TestClient) -> None:
        resp = client.post(
            "/api/batch",
            json={"folder_path": "/nonexistent/xyz", "client_name": "Test"},
        )
        assert resp.status_code == 400

    def test_batch_rejects_empty_folder(self, client: TestClient) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            resp = client.post(
                "/api/batch",
                json={"folder_path": tmpdir, "client_name": "Test"},
            )
            assert resp.status_code == 400
            assert "No supported" in resp.json()["detail"]

    def test_list_batches(self, client: TestClient) -> None:
        resp = client.get("/api/batch")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_unknown_batch_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/batch/nonexistent")
        assert resp.status_code == 404
