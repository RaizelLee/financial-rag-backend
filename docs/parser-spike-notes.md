# PDF Parser Spike Notes

- Date: 2026-09-04
- Project: Financial Report RAG Backend
- Status: Baseline passed
- Parser: PyMuPDF
- Source document:
  [TSMC 2025 Consolidated Financial Statements](../data/raw/TSMC_2025Q4_Consolidated_Financial_Statements_C.pdf)

## 1. Objective

The purpose of this parser spike is to verify whether a real financial
statement PDF can be converted into structured page-level data while
preserving:

- Source document identity
- PDF page number
- Extracted text
- Financial reporting period
- Currency and unit
- Extraction diagnostics
- Financial amounts

This spike does not attempt to solve OCR, table reconstruction or
chunking.

## 2. Document Information

| Field | Value |
|---|---|
| Company | 台灣積體電路製造股份有限公司 |
| Ticker | 2330 |
| Report type | Consolidated financial statements |
| Reporting period | 2025FY |
| Period end | 2025-12-31 |
| Currency | TWD |
| Default unit | New Taiwan dollars in thousands |
| Language | Traditional Chinese |
| Total PDF pages | 85 |

The document states that, unless otherwise specified, monetary amounts
are presented in thousands of New Taiwan dollars.

## 3. Extraction Result

| Result | Count |
|---|---:|
| Total pages | 85 |
| Pages with extractable text | 71 |
| Pages without extractable text | 14 |
| Pages requiring OCR or another parser | 1–14 |
| Pages containing financial amounts | 55 |

Pages 15–85 contain an extractable text layer.

Pages 1–14 do not contain a usable text layer and are represented mainly
as images or vector drawing objects.

## 4. Output Files

The parser produces the following files:

| File | Purpose |
|---|---|
| `artifacts/parsed_pages.json` | Complete page-level extraction result |
| `artifacts/parser_sample.json` | Representative pages for manual verification |
| `artifacts/parser_summary.json` | Extraction statistics and page classifications |

Each parsed page contains:

- `source_id`
- `pdf_page`
- `text`
- document metadata
- extraction status
- text and image diagnostics
- detected amount samples

## 5. Manual Verification

### 5.1 Page 15 — Document metadata and narrative text

Expected information:

- Company name
- Consolidated financial statement notes
- Reporting periods: ROC years 114 and 113
- Default unit: New Taiwan dollars in thousands
- Company history and accounting policy text

Observed result:

- Traditional Chinese text is readable.
- Company name is preserved.
- Reporting periods are preserved.
- Currency unit is preserved.
- PDF page number is correct.
- Narrative paragraphs are generally readable.

Result: Passed.

### 5.2 Page 18 — Complex table

Expected information:

- Subsidiary names
- Locations
- Main business activities
- Ownership percentages for two reporting periods

Observed result:

- Most text values are extracted.
- English and Chinese company names are present.
- Percentage values are present.
- Row and column relationships are not reliably preserved.
- Some values and company names are split across multiple lines.
- Plain-text extraction is insufficient for reliable table reconstruction.

Result: Text extraction passed, but table structure verification failed.

### 5.3 Page 31 — Cash and cash equivalents

Expected information:

- Cash and cash equivalents section
- Values for ROC years 114 and 113
- Multiple financial amounts

Observed result:

- Financial amounts are extracted.
- Section text is available.
- PDF page number is preserved.
- The relationship between each row, year and amount must still be
  checked against the original PDF.

Result: Passed with table-structure limitation.

### 5.4 Page 52 — Revenue

Expected financial amounts include:

- `3,809,054,272`
- `2,894,307,699`

Expected context:

- Revenue
- ROC years 114 and 113
- Amounts expressed in thousands of New Taiwan dollars

Observed result:

- Revenue-related text is extracted.
- Both financial amounts are present.
- The parser preserves the source page.
- The year-to-value relationship must be manually compared with the
  original table before using the data as a trusted answer.

Result: Passed with manual relationship verification required.

### 5.5 Page 58 — Earnings per share

Expected values include:

- Basic earnings per share for ROC year 114: `66.26`
- Basic earnings per share for ROC year 113: `45.25`

Observed result:

- Earnings-per-share text is extracted.
- Decimal values are present.
- PDF page number is preserved.
- The extracted text must still be checked for correct column order.

Result: Passed with table-structure limitation.

## 6. Successful Findings

The parser successfully demonstrates that:

1. A real financial statement PDF can be opened and processed page by
   page.
2. Pages with and without an extractable text layer can be classified.
3. Source document identity and PDF page numbers can be preserved.
4. Narrative financial-report text can be extracted.
5. Financial amounts can be detected in the extracted text.
6. Document-level metadata can be attached to every page.
7. Pages requiring OCR can be identified without interrupting the
   remaining extraction process.

## 7. Known Limitations

### 7.1 Missing text layer

Pages 1–14 do not contain extractable text.

This range includes important primary financial statement pages.
Therefore, the current parser does not provide complete coverage of the
financial statements.

### 7.2 Table structure loss

Plain-text extraction does not reliably preserve:

- Row and column boundaries
- Year-to-value relationships
- Table headers
- Multi-line company names
- Values spanning multiple columns

Extracting a number does not prove that the system understands what the
number represents.

### 7.3 Excessive whitespace

The extracted text contains:

- Repeated blank lines
- Irregular spacing between Chinese characters
- Unnatural line breaks
- Headers and footers mixed with document content

Text normalization will be required before chunking.

### 7.4 Unit interpretation

The document default unit is New Taiwan dollars in thousands, but some
tables may use a different unit.

The RAG system must not assume that every number has the same unit
without checking the page or table context.

## 8. Engineering Decision

For the initial RAG baseline:

- Index pages 15–85.
- Preserve the original PDF page number for every chunk.
- Keep pages 1–14 marked as requiring OCR or another parser.
- Do not implement full-document OCR during the baseline stage.
- Do not treat extracted table text as structured financial data.
- Require citations in every generated answer.
- Require manual verification for numeric evaluation questions.

After the text-based baseline works, investigate targeted OCR or table
extraction for pages 8–14.

Targeted processing is preferred over running OCR on the entire
85-page document.

## 9. Risk to the RAG System

The largest current risk is not failure to find a number.

The largest risk is finding the correct number but associating it with
the wrong:

- Financial year
- Company
- Statement
- Row
- Currency
- Unit
- Consolidation scope

Metadata, retrieval evaluation and numeric answer tests are therefore
required before the system can be considered reliable.

## 10. Baseline Acceptance Criteria

- [x] The PDF can be opened successfully.
- [x] All 85 pages are inspected.
- [x] Extractable and non-extractable pages are classified.
- [x] Source ID is preserved.
- [x] PDF page numbers are preserved.
- [x] Traditional Chinese narrative text is extracted.
- [x] Financial amounts are detected.
- [x] Representative pages are manually inspected.
- [x] Parsing limitations are documented.
- [ ] OCR is implemented for pages 1–14.
- [ ] Table rows and columns are reconstructed.
- [ ] Text is divided into chunks.
- [ ] Embeddings are generated.
- [ ] Data is stored in a vector database.

The unchecked items are not required for this parser spike.

## 11. Conclusion

The PDF parser baseline is successful.

The parser can extract usable text from pages 15–85 and preserve page
provenance. It can also detect pages without a usable text layer.

However, plain-text extraction alone is not sufficient for reliable
financial-table understanding. Pages 1–14 require a later extraction
strategy, and numeric values extracted from tables require validation of
their row, column, reporting period and unit.

The next step is to design and test a chunking strategy using the
successfully extracted text pages.