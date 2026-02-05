"""Configuration management for the Legal Document Processing Orchestrator.

Loads settings from environment variables (via .env file) and exposes
them as typed attributes on a Settings dataclass.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Immutable application settings sourced from environment variables."""

    # Azure Document Intelligence
    doc_intelligence_endpoint: str = field(
        default_factory=lambda: os.environ.get(
            "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", ""
        )
    )
    doc_intelligence_key: str = field(
        default_factory=lambda: os.environ.get(
            "AZURE_DOCUMENT_INTELLIGENCE_KEY", ""
        )
    )

    # Azure OpenAI
    openai_endpoint: str = field(
        default_factory=lambda: os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    )
    openai_api_key: str = field(
        default_factory=lambda: os.environ.get("AZURE_OPENAI_API_KEY", "")
    )
    openai_deployment: str = field(
        default_factory=lambda: os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    )
    openai_api_version: str = field(
        default_factory=lambda: os.environ.get(
            "AZURE_OPENAI_API_VERSION", "2024-06-01"
        )
    )

    # Folders
    inbox_folder: Path = field(
        default_factory=lambda: Path(
            os.environ.get("INBOX_FOLDER", "./inbox")
        )
    )
    organized_folder: Path = field(
        default_factory=lambda: Path(
            os.environ.get("ORGANIZED_FOLDER", "./organized")
        )
    )

    # Logging
    log_level: str = field(
        default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO")
    )

    def validate(self) -> None:
        """Raise ``ValueError`` if required credentials are missing."""
        missing: list[str] = []
        if not self.doc_intelligence_endpoint:
            missing.append("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        if not self.doc_intelligence_key:
            missing.append("AZURE_DOCUMENT_INTELLIGENCE_KEY")
        if not self.openai_endpoint:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not self.openai_api_key:
            missing.append("AZURE_OPENAI_API_KEY")
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )


# Singleton settings instance
settings = Settings()
