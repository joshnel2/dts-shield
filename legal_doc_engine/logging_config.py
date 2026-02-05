"""Centralized logging configuration.

Call ``setup_logging()`` once at application startup to configure the
root logger with a consistent format and the level specified in settings.
"""

from __future__ import annotations

import logging
import sys

from legal_doc_engine.config import settings


def setup_logging() -> logging.Logger:
    """Configure and return the application root logger.

    Returns
    -------
    logging.Logger
        The configured ``legal_doc_engine`` logger.
    """
    logger = logging.getLogger("legal_doc_engine")
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    file_handler = logging.FileHandler("legal_doc_engine.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
