#!/usr/bin/env python3
"""Legal Document Processing Orchestrator — entry point.

Usage
-----
Start the web UI (recommended for lawyers)::

    python main.py serve [--host 0.0.0.0] [--port 8000]

Process an entire folder of documents::

    python main.py batch ./case-files --client "Smith v. Jones" [--no-recursive]

Start the inbox watcher (headless background mode)::

    python main.py watch [--inbox ./inbox] [--client "Acme Corp"]

Process a single file::

    python main.py process <file> [--client "Acme Corp"]
"""

from __future__ import annotations

import argparse
import sys

from legal_doc_engine.logging_config import setup_logging
from legal_doc_engine.config import settings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Legal Document Processing Orchestrator",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ---- serve (web UI) ----
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start the web UI for lawyers to upload and manage documents.",
    )
    serve_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: %(default)s).",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (default: %(default)s).",
    )

    # ---- batch (folder processing) ----
    batch_parser = subparsers.add_parser(
        "batch",
        help="Process all documents in a folder (and sub-folders).",
    )
    batch_parser.add_argument(
        "folder",
        help="Path to the folder containing documents.",
    )
    batch_parser.add_argument(
        "--client",
        default="General",
        help="Client/matter name (default: %(default)s).",
    )
    batch_parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Do not search sub-folders.",
    )

    # ---- watch ----
    watch_parser = subparsers.add_parser(
        "watch",
        help="Monitor the inbox folder for new documents (headless).",
    )
    watch_parser.add_argument(
        "--inbox",
        default=str(settings.inbox_folder),
        help="Path to the inbox folder (default: %(default)s).",
    )
    watch_parser.add_argument(
        "--client",
        default="General",
        help="Default client/matter name (default: %(default)s).",
    )

    # ---- process ----
    process_parser = subparsers.add_parser(
        "process",
        help="Process a single document file.",
    )
    process_parser.add_argument(
        "file",
        help="Path to the document to process.",
    )
    process_parser.add_argument(
        "--client",
        default="General",
        help="Client/matter name (default: %(default)s).",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    logger = setup_logging()
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        print("\n  Tip: run 'python main.py serve' to start the web UI.\n")
        sys.exit(0)

    if args.command == "serve":
        import uvicorn

        logger.info(
            "Starting Legal Doc Orchestrator web UI on %s:%d",
            args.host,
            args.port,
        )
        uvicorn.run(
            "legal_doc_engine.web:app",
            host=args.host,
            port=args.port,
            reload=False,
            log_level="info",
        )

    elif args.command == "batch":
        # Validate credentials
        try:
            settings.validate()
        except ValueError as exc:
            logger.error(str(exc))
            sys.exit(1)

        from legal_doc_engine.pipeline import process_folder

        def _progress(current: int, total: int, name: str, status: str) -> None:
            icon = "OK" if status == "completed" else "FAIL"
            logger.info("[%d/%d] %s — %s", current, total, name, icon)

        summary = process_folder(
            args.folder,
            client_name=args.client,
            recursive=not args.no_recursive,
            on_progress=_progress,
        )
        logger.info(
            "Batch complete: %d succeeded, %d failed out of %d files.",
            summary["succeeded"],
            summary["failed"],
            summary["total_files"],
        )
        if summary["errors"]:
            logger.warning("Failed files:")
            for err in summary["errors"]:
                logger.warning("  %s — %s", err["source"], err["error"])

    elif args.command == "watch":
        # Validate credentials for headless mode
        try:
            settings.validate()
        except ValueError as exc:
            logger.error(str(exc))
            sys.exit(1)

        from legal_doc_engine.watcher import InboxWatcher

        watcher = InboxWatcher(
            inbox_folder=args.inbox,
            client_name=args.client,
        )
        watcher.start()

    elif args.command == "process":
        # Validate credentials for direct processing
        try:
            settings.validate()
        except ValueError as exc:
            logger.error(str(exc))
            sys.exit(1)

        from legal_doc_engine.pipeline import process_document

        result = process_document(args.file, client_name=args.client)
        logger.info("Done. Destination: %s", result["destination"])


if __name__ == "__main__":
    main()
