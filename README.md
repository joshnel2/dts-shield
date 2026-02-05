# Legal Document Processing Orchestrator

A Python-based engine with a **web UI for lawyers** to upload, classify, and auto-organize legal documents using **Azure AI Document Intelligence** and **Azure OpenAI (GPT-4o)**.

## What It Does

A lawyer uploads a PDF (or DOCX, image) through the web interface. Behind the scenes:

1. **Azure Document Intelligence** extracts high-fidelity Markdown from the document — preserving tables, headers, footnotes, and fine print via high-resolution OCR.
2. **Semantic Chunking** splits the Markdown at legal header boundaries (`ARTICLE I`, `Section 2.3`, etc.) so each section stays intact.
3. **GPT-4o Classification** reads the first 2,000 characters and returns:
   - **Document Type** (Motion, Affidavit, Contract, Brief, Court Order...)
   - **Parties** involved (people and entities)
   - **Suggested Filename** in `YYYY-MM-DD - Type - Party.pdf` format
4. **Auto-Organization** renames and moves the file into `organized/{client}/{document_type}/`.

The lawyer sees real-time processing status, classification results, extracted text, and semantic sections — all from the web dashboard.

## Architecture

```
                    ┌─────────────────────────┐
   Lawyer uploads   │   Web UI (FastAPI)      │
   via browser ────>│   /api/upload           │
                    └──────────┬──────────────┘
                               │
                    ┌──────────▼──────────────┐
                    │  1. Extract Markdown     │  Azure Document Intelligence
                    │     prebuilt-layout      │  ocrHighResolution + markdown
                    ├─────────────────────────┤
                    │  2. Semantic Chunking    │  Split at # / ## / ### headers
                    ├─────────────────────────┤
                    │  3. AI Classification    │  Azure OpenAI GPT-4o
                    │     type, parties, name  │  JSON structured output
                    ├─────────────────────────┤
                    │  4. Organize & Rename    │  Move to client/type/ folder
                    └──────────┬──────────────┘
                               │
                    organized/{client}/{type}/YYYY-MM-DD - Type - Party.pdf
```

## Web UI Features

| Page | What lawyers see |
|---|---|
| **Dashboard** | Stats cards (total, completed, processing, failed), recent activity feed, document-type breakdown chart |
| **Upload** | Drag-and-drop zone, client/matter name field, upload queue with real-time progress |
| **Documents** | Full list of processed documents with classification badges, click to view extracted markdown, semantic sections, and AI results |
| **File Browser** | Tree view of the `organized/` folder hierarchy with download links |

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

```bash
cp .env.example .env
# Edit .env with your Azure credentials
```

| Variable | Description |
|---|---|
| `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` | Doc Intelligence endpoint URL |
| `AZURE_DOCUMENT_INTELLIGENCE_KEY` | Doc Intelligence API key |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | Deployment name (default: `gpt-4o`) |
| `AZURE_OPENAI_API_VERSION` | API version (default: `2024-06-01`) |

### 3. Run the Web UI

```bash
python main.py serve
```

Open **http://localhost:8000** in your browser. That's it.

### Other Modes

**Headless folder watcher** (monitors `./inbox` automatically):

```bash
python main.py watch --client "Acme Corp"
```

**Single file** processing from the command line:

```bash
python main.py process path/to/document.pdf --client "Acme Corp"
```

## Project Structure

```
.
├── main.py                          # CLI: serve / watch / process
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment variable template
├── frontend/
│   └── index.html                   # Lawyer-facing web UI
├── legal_doc_engine/
│   ├── __init__.py                  # Package exports
│   ├── config.py                    # Settings from environment
│   ├── logging_config.py            # Centralized logging
│   ├── engine.py                    # LegalDocEngine (Markdown extraction)
│   ├── chunker.py                   # Semantic chunking by headers
│   ├── classifier.py                # AI classification via GPT-4o
│   ├── organizer.py                 # File move/rename logic
│   ├── pipeline.py                  # End-to-end orchestration
│   ├── watcher.py                   # Watchdog inbox monitor
│   └── web.py                       # FastAPI web server + API
├── tests/
│   ├── test_chunker.py              # Chunker unit tests
│   ├── test_classifier.py           # Classifier unit tests (mocked)
│   ├── test_organizer.py            # Organizer unit tests
│   └── test_web.py                  # Web API endpoint tests
├── inbox/                           # Drop files here (watcher mode)
└── organized/                       # Auto-organized output
```

## Testing

```bash
pip install pytest
pytest tests/ -v
```

All 24 tests run offline — no Azure credentials required.

## Why This Design Works for a 70-Person Firm

1. **Markdown is King** — By forcing Markdown output, the AI accurately distinguishes footnotes, tables, headings, and body text. Standard PDF extraction scrambles these, which is a disaster for legal research.

2. **Agentic Organization** — Instead of static folder rules, GPT-4o reads the document content and decides where it belongs based on the actual legal substance.

3. **High Resolution OCR** — The `ocrHighResolution` flag ensures small-print clauses, court stamps, and case numbers are captured accurately.

4. **Lawyer-Friendly UI** — No command line needed. Lawyers drag-and-drop files in a browser and see results in real time.

## License

MIT
