# Chunking Baseline

## Input

`artifacts/parsed_pages.json`

Only pages with `text_extracted` status are processed.

## Baseline Rules

- Never combine two different PDF pages.
- Preserve source ID and PDF page number.
- Preserve company, reporting period, currency and unit.
- Split text primarily on paragraph boundaries.
- Maximum target size: 1,200 characters.
- Overlap target: 150 characters.
- Do not remove financial numbers.
- Do not reconstruct tables yet.
- Ignore pages without extractable text.

## Expected Outputs

- `artifacts/chunks.json`
- `artifacts/chunk_sample.json`
- `artifacts/chunk_summary.json`

## Current Hypothesis

The selected chunk size is only a baseline. It will be compared with
other strategies during evaluation.

## Manual Verification Results

### Page 52 — Revenue

The chunk contains:

- Revenue section title
- ROC years 114 and 113
- Total revenue values `3,809,054,272` and `2,894,307,699`
- Product, geographic, technology-platform and process breakdowns
- Correct PDF page metadata

Result: Retrieval context preserved.

### Page 58 — Earnings Per Share

The chunk contains:

- Basic earnings per share
- Diluted earnings per share
- ROC years 114 and 113
- EPS values `66.26`, `45.25`, `66.25` and `45.25`
- Correct PDF page metadata

Result: Retrieval context preserved.

## Observed Data Quality Problems

Some financial values are split by line breaks during PDF text
extraction.

Examples:

```text
32\n7,502,739
70,40\n1,621
459,530,\n166
4,304\n,867
1,173,267,7\n03