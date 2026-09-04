import json
import re
from pathlib import Path
from typing import Any

import pymupdf


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PDF_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "TSMC_2025Q4_Consolidated_Financial_Statements_C.pdf"
)

ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"

FULL_OUTPUT_PATH = ARTIFACTS_DIR / "parsed_pages.json"
SAMPLE_OUTPUT_PATH = ARTIFACTS_DIR / "parser_sample.json"
SUMMARY_OUTPUT_PATH = ARTIFACTS_DIR / "parser_summary.json"


# ============================================================
# Document metadata
# ============================================================

DOCUMENT_METADATA = {
    "company": "台灣積體電路製造股份有限公司",
    "ticker": "2330",
    "report_type": "consolidated_financial_statements",
    "reporting_period": "2025FY",
    "period_end": "2025-12-31",
    "currency": "TWD",
    "default_unit": "thousand",
    "language": "zh-TW",
    "is_consolidated": True,
}


# ============================================================
# Sample pages for manual verification
# ============================================================

# 這些頁面分別代表一般文字、複雜表格與財務金額。
SAMPLE_PAGE_NUMBERS = [
    15,  # 文件標題、年度、單位
    18,  # 複雜子公司表格
    31,  # 現金及約當現金
    38,  # 大量財務數值
    52,  # 營業收入
    54,  # 利息收入
    58,  # 每股盈餘
    62,  # 財務數值
    67,  # 金融工具表格
    71,  # 金融風險數值
]


# 找出帶有千分位或小數點的數字，例如：
# 3,809,054,272
# 86,642,964
# 66.26
AMOUNT_PATTERN = re.compile(
    r"(?<![\d,])"
    r"(?:\d{1,3}(?:,\d{3})+|\d+\.\d+)"
    r"(?![\d,])"
)


# ============================================================
# Helpers
# ============================================================

def write_json(path: Path, data: Any) -> None:
    """Write Python data to a UTF-8 JSON file."""

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def find_amounts(text: str) -> list[str]:
    """Find comma-formatted or decimal numeric values in text."""

    return AMOUNT_PATTERN.findall(text)


# ============================================================
# PDF extraction
# ============================================================

def extract_pages(pdf_path: Path) -> list[dict[str, Any]]:
    """
    Extract text and diagnostics from every PDF page.

    This function does not perform OCR. Pages without an extractable
    text layer are marked as needs_ocr_or_alternative_parser.
    """

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF file not found: {pdf_path}"
        )

    pages: list[dict[str, Any]] = []

    with pymupdf.open(pdf_path) as document:
        total_pages = document.page_count

        print(f"Opening PDF: {pdf_path}")
        print(f"Total pages: {total_pages}")
        print()

        for page_index, page in enumerate(document):
            pdf_page = page_index + 1

            text = page.get_text(
                "text",
                sort=True,
            ).strip()

            blocks = page.get_text(
                "blocks",
                sort=True,
            )

            images = page.get_images(full=True)
            amounts = find_amounts(text)

            if text:
                extraction_status = "text_extracted"
            else:
                extraction_status = (
                    "needs_ocr_or_alternative_parser"
                )

            page_data = {
                "source_id": pdf_path.stem,
                "pdf_page": pdf_page,
                "text": text,
                "metadata": {
                    **DOCUMENT_METADATA,
                },
                "extraction_status": extraction_status,
                "diagnostics": {
                    "text_chars": len(text),
                    "text_blocks": len(blocks),
                    "image_count": len(images),
                    "contains_amounts": bool(amounts),
                    "amount_count": len(amounts),
                    "amount_samples": amounts[:10],
                },
            }

            pages.append(page_data)

            print(
                f"page={pdf_page:>2}, "
                f"status={extraction_status}, "
                f"text_chars={len(text):>5}, "
                f"text_blocks={len(blocks):>3}, "
                f"images={len(images):>2}, "
                f"amounts={len(amounts):>3}"
            )

    return pages


# ============================================================
# Sample and summary generation
# ============================================================

def create_sample_pages(
    pages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Select representative pages for manual QA."""

    pages_by_number = {
        page["pdf_page"]: page
        for page in pages
    }

    sample_pages = []

    for page_number in SAMPLE_PAGE_NUMBERS:
        page = pages_by_number.get(page_number)

        if page is not None:
            sample_pages.append(page)

    return sample_pages


def create_summary(
    pages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create an extraction summary."""

    extractable_pages = [
        page
        for page in pages
        if page["text"]
    ]

    pages_needing_ocr = [
        page["pdf_page"]
        for page in pages
        if not page["text"]
    ]

    pages_with_amounts = [
        page["pdf_page"]
        for page in pages
        if page["diagnostics"]["contains_amounts"]
    ]

    return {
        "source_id": PDF_PATH.stem,
        "document_metadata": DOCUMENT_METADATA,
        "total_pages": len(pages),
        "text_extracted_page_count": len(
            extractable_pages
        ),
        "no_extractable_text_page_count": len(
            pages_needing_ocr
        ),
        "pages_needing_ocr_or_alternative_parser": (
            pages_needing_ocr
        ),
        "pages_with_amounts_count": len(
            pages_with_amounts
        ),
        "pages_with_amounts": pages_with_amounts,
        "sample_pages": SAMPLE_PAGE_NUMBERS,
    }


# ============================================================
# Main
# ============================================================

def main() -> None:
    ARTIFACTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    pages = extract_pages(PDF_PATH)

    sample_pages = create_sample_pages(pages)
    summary = create_summary(pages)

    # 完整解析結果：之後提供給 chunking pipeline。
    write_json(
        FULL_OUTPUT_PATH,
        pages,
    )

    # 代表性頁面：提供人工品質檢查。
    write_json(
        SAMPLE_OUTPUT_PATH,
        sample_pages,
    )

    # 解析摘要：記錄成功率與限制。
    write_json(
        SUMMARY_OUTPUT_PATH,
        summary,
    )

    print()
    print("=" * 60)
    print("Extraction completed")
    print("=" * 60)
    print(
        f"Total pages: "
        f"{summary['total_pages']}"
    )
    print(
        f"Pages with extractable text: "
        f"{summary['text_extracted_page_count']}"
    )
    print(
        f"Pages requiring OCR or another parser: "
        f"{summary['pages_needing_ocr_or_alternative_parser']}"
    )
    print(
        f"Pages containing amounts: "
        f"{summary['pages_with_amounts_count']}"
    )
    print()
    print(f"Full output:    {FULL_OUTPUT_PATH}")
    print(f"Sample output:  {SAMPLE_OUTPUT_PATH}")
    print(f"Summary output: {SUMMARY_OUTPUT_PATH}")


if __name__ == "__main__":
    main()