# Financial Report RAG Backend

A production-oriented financial-report RAG backend that retrieves
evidence from public financial statements and returns answers with
source-page citations.

## Current Status

Completed:

- [x] Project scope and non-goals
- [x] Financial-report data card
- [x] Page-level PDF parser spike
- [x] Source and page metadata preservation
- [x] Extractable-page classification
- [x] Financial amount detection
- [x] Manual parsing-quality assessment

Next:

- [ ] Text normalization
- [ ] Chunking baseline
- [ ] Embedding generation
- [ ] Vector database ingestion
- [ ] Retrieval evaluation
- [ ] Citation-grounded answer API

## Current Parser Result

| Metric | Result |
|---|---:|
| Total PDF pages | 85 |
| Pages with extractable text | 71 |
| Pages requiring another parser or OCR | 14 |
| Pages containing detected amounts | 55 |

## Run Locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/parser_spike.py