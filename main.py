#!/usr/bin/env python3
"""Legal Document Processing Orchestrator — entry point.

Usage
-----
Start the inbox watcher (default)::

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

    # ---- watch ----
    watch_parser = subparsers.add_parser(
        "watch",
        help="Monitor the inbox folder for new documents.",
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
        sys.exit(0)

    # Validate credentials upfront
    try:
        settings.validate()
    except ValueError as exc:
        logger.error(str(exc))
        sys.exit(1)

    if args.command == "watch":
        from legal_doc_engine.watcher import InboxWatcher

        watcher = InboxWatcher(
            inbox_folder=args.inbox,
            client_name=args.client,
        )
        watcher.start()

    elif args.command == "process":
        from legal_doc_engine.pipeline import process_document

        result = process_document(args.file, client_name=args.client)
        logger.info("Done. Destination: %s", result["destination"])


if __name__ == "__main__":
    main()
