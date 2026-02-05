# Legal Document Processing Orchestrator

A Python-based engine for extracting, classifying, and organizing legal documents using **Azure AI Document Intelligence** and **Azure OpenAI (GPT-4o)**.

## Architecture

```
inbox/                          # Drop documents here
  └── incoming.pdf

  ┌──────────────────────────────────────────────────┐
  │  1. Extract Markdown    (Azure Doc Intelligence)  │
  │  2. Semantic Chunking   (Header-based splitting)  │
  │  3. AI Classification   (Azure OpenAI GPT-4o)     │
  │  4. Organize & Rename   (Rule-based file mover)   │
  └──────────────────────────────────────────────────┘

organized/                      # Auto-organized output
  └── {client_name}/
        └── {document_type}/
              └── YYYY-MM-DD - Type - Party.pdf
```

## Features

- **Markdown Extraction** — Uses `prebuilt-layout` with `ocrHighResolution` for maximum fidelity on scanned legal documents, stamps, and fine print.
- **Semantic Chunking** — Splits Markdown at header boundaries (`#`, `##`, `###`) so legal sections stay intact.
- **AI Classification** — GPT-4o reads the first 2,000 characters and returns structured JSON: `document_type`, `parties`, and `suggested_filename`.
- **Watchdog Automation** — Monitors `./inbox` and processes new files automatically.
- **Resilient Retries** — All Azure API calls use `tenacity` with exponential backoff for rate-limit handling.

## Requirements

- Python 3.10+
- Azure AI Document Intelligence resource
- Azure OpenAI resource with a `gpt-4o` deployment

## Quick Start

### 1. Clone & Install

```bash
git clone <this-repo>
cd legal-doc-orchestrator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

Copy the example environment file and fill in your Azure credentials:

```bash
cp .env.example .env
# Edit .env with your values
```

| Variable | Description |
|---|---|
| `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` | Doc Intelligence endpoint URL |
| `AZURE_DOCUMENT_INTELLIGENCE_KEY` | Doc Intelligence API key |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | Deployment name (default: `gpt-4o`) |
| `AZURE_OPENAI_API_VERSION` | API version (default: `2024-06-01`) |
| `INBOX_FOLDER` | Watch folder (default: `./inbox`) |
| `ORGANIZED_FOLDER` | Output folder (default: `./organized`) |

### 3. Run

**Watch mode** (monitors `./inbox` continuously):

```bash
python main.py watch --client "Acme Corp"
```

**Single file** processing:

```bash
python main.py process path/to/document.pdf --client "Acme Corp"
```

## Project Structure

```
.
├── main.py                          # CLI entry point
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment variable template
├── legal_doc_engine/
│   ├── __init__.py                  # Package exports
│   ├── config.py                    # Settings from environment
│   ├── logging_config.py            # Centralized logging setup
│   ├── engine.py                    # LegalDocEngine (Markdown extraction)
│   ├── chunker.py                   # Semantic chunking by headers
│   ├── classifier.py                # AI classification via GPT-4o
│   ├── organizer.py                 # File move/rename logic
│   ├── pipeline.py                  # End-to-end orchestration
│   └── watcher.py                   # Watchdog inbox monitor
├── tests/
│   ├── test_chunker.py              # Chunker unit tests
│   ├── test_classifier.py           # Classifier unit tests (mocked)
│   └── test_organizer.py            # Organizer unit tests
├── inbox/                           # Drop files here
└── organized/                       # Auto-organized output
```

## Testing

```bash
pip install pytest
pytest tests/ -v
```

The test suite runs entirely offline — Azure API calls are mocked.

## How It Works

1. **Markdown is King** — By forcing Markdown output, the AI accurately distinguishes footnotes, tables, headings, and body text. Standard PDF extraction often scrambles these, which is catastrophic for legal research.

2. **Agentic Organization** — Instead of static folder rules, GPT-4o reads the document content and decides where it belongs based on the actual legal substance.

3. **High Resolution OCR** — The `ocrHighResolution` flag ensures small-print clauses, court stamps, and case numbers are captured accurately — no confusing `0` for `8`.

## License

MIT
