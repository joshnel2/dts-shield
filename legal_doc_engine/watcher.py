"""Inbox Watcher — monitor a folder for new legal documents.

Uses the ``watchdog`` library to detect new files in ``./inbox`` and
feed them through the processing pipeline automatically.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

from legal_doc_engine.config import settings
from legal_doc_engine.pipeline import process_document

logger = logging.getLogger("legal_doc_engine.watcher")

# File extensions accepted for processing
SUPPORTED_EXTENSIONS = {
    ".pdf", ".tiff", ".tif", ".jpeg", ".jpg", ".png", ".bmp", ".docx",
}


class _InboxHandler(FileSystemEventHandler):
    """React to new files created in the inbox folder."""

    def __init__(self, client_name: str = "General") -> None:
        super().__init__()
        self.client_name = client_name

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            logger.debug("Ignoring unsupported file: %s", file_path.name)
            return

        # Brief pause to let the OS finish writing the file
        time.sleep(1)

        logger.info("New file detected: %s", file_path.name)
        try:
            result = process_document(
                file_path,
                client_name=self.client_name,
            )
            logger.info(
                "Successfully processed %s -> %s (type=%s)",
                file_path.name,
                result["destination"],
                result["classification"].document_type,
            )
        except Exception:
            logger.exception("Failed to process %s", file_path.name)


class InboxWatcher:
    """High-level API to start/stop the inbox watcher.

    Parameters
    ----------
    inbox_folder : Path | str, optional
        Folder to monitor. Falls back to ``settings.inbox_folder``.
    client_name : str
        Default client/matter name for organized files.
    """

    def __init__(
        self,
        inbox_folder: Path | str | None = None,
        client_name: str = "General",
    ) -> None:
        self.inbox_folder = Path(inbox_folder or settings.inbox_folder)
        self.client_name = client_name
        self._observer: Observer | None = None

    def start(self) -> None:
        """Start watching the inbox folder (blocking)."""
        self.inbox_folder.mkdir(parents=True, exist_ok=True)
        handler = _InboxHandler(client_name=self.client_name)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.inbox_folder), recursive=False)
        self._observer.start()

        logger.info(
            "Watching '%s' for new documents (client=%s) ...",
            self.inbox_folder,
            self.client_name,
        )

        try:
            while self._observer.is_alive():
                self._observer.join(timeout=1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """Gracefully stop the observer."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            logger.info("Inbox watcher stopped.")
