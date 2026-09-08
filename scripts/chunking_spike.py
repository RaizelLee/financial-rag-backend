import json
import re
import statistics
from pathlib import Path
from typing import Any
import os

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

import numpy as np
import plotly.graph_objects as go

from sklearn.manifold import TSNE

# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_PATH = PROJECT_ROOT / "artifacts" / "parsed_pages.json"

FULL_OUTPUT_PATH = PROJECT_ROOT / "artifacts" / "chunks.json"
SAMPLE_OUTPUT_PATH = PROJECT_ROOT / "artifacts" / "chunk_sample.json"
SUMMARY_OUTPUT_PATH = PROJECT_ROOT / "artifacts" / "chunk_summary.json"

CHROMA_PATH = PROJECT_ROOT / "chroma_db"
CHROMA_COLLECTION_NAME = "financial_report_chunks"

VISUALIZATION_2D_PATH = (
    PROJECT_ROOT
    / "artifacts"
    / "chunk_embeddings_2d.html"
)

VISUALIZATION_3D_PATH = (
    PROJECT_ROOT
    / "artifacts"
    / "chunk_embeddings_3d.html"
)


# ============================================================
# Baseline configuration
# ============================================================

MAX_CHARS = 1200
OVERLAP_CHARS = 150

# 人工檢查用的代表頁面
SAMPLE_PAGE_NUMBERS = [
    15,  # 文件資訊、期間、單位
    18,  # 複雜表格
    52,  # 營業收入
    58,  # 每股盈餘
]


# ============================================================
# JSON helpers
# ============================================================

def read_json(path: Path) -> Any:
    """Read a UTF-8 JSON file."""

    if not path.exists():
        raise FileNotFoundError(
            f"Input file not found: {path}\n"
            "Run scripts/parser_spike.py first."
        )

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def write_json(path: Path, data: Any) -> None:
    """Write data to a UTF-8 JSON file."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# ============================================================
# Text normalization
# ============================================================

def normalize_text(text: str) -> str:
    """
    Perform conservative whitespace normalization.

    Financial punctuation, numbers, decimal points, negative signs,
    parentheses and percentage symbols are preserved.
    """

    # Windows newline → Unix newline
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # 清除每一行前後空白，保留換行
    cleaned_lines = [
        re.sub(r"[ \t]+", " ", line).strip()
        for line in text.splitlines()
    ]

    text = "\n".join(cleaned_lines)

    # 三個以上連續換行縮減為兩個
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ============================================================
# Chunk boundary selection
# ============================================================

def choose_split_end(
    text: str,
    start: int,
    hard_end: int,
    max_chars: int,
) -> int:
    """
    Find a readable split boundary before hard_end.

    Preferred boundaries:
    1. Paragraph boundary
    2. Chinese full stop
    3. Semicolon
    4. Line break

    If no suitable boundary is found, use hard_end.
    """

    if hard_end >= len(text):
        return len(text)

    # 不要為了找漂亮的邊界，讓 chunk 小得太誇張
    minimum_end = start + int(max_chars * 0.6)

    if minimum_end >= hard_end:
        return hard_end

    candidates: list[int] = []

    separators = [
        "\n\n",
        "。",
        "；",
        "\n",
    ]

    for separator in separators:
        position = text.rfind(
            separator,
            minimum_end,
            hard_end,
        )

        if position != -1:
            candidates.append(
                position + len(separator)
            )

    if not candidates:
        return hard_end

    # 選擇最接近 hard_end 的合理邊界
    return max(candidates)


# ============================================================
# Text splitting
# ============================================================

def split_text(
    text: str,
    max_chars: int = MAX_CHARS,
    overlap_chars: int = OVERLAP_CHARS,
) -> list[str]:
    """
    Split one page of text into overlapping chunks.

    This function never receives text from multiple PDF pages,
    so a chunk cannot cross page boundaries.
    """

    if max_chars <= 0:
        raise ValueError(
            "max_chars must be greater than zero."
        )

    if overlap_chars < 0:
        raise ValueError(
            "overlap_chars cannot be negative."
        )

    if overlap_chars >= max_chars:
        raise ValueError(
            "overlap_chars must be smaller than max_chars."
        )

    text = normalize_text(text)

    if not text:
        return []

    chunks: list[str] = []
    start = 0

    while start < len(text):
        hard_end = min(
            start + max_chars,
            len(text),
        )

        end = choose_split_end(
            text=text,
            start=start,
            hard_end=hard_end,
            max_chars=max_chars,
        )

        chunk_text = text[start:end].strip()

        if chunk_text:
            chunks.append(chunk_text)

        if end >= len(text):
            break

        next_start = end - overlap_chars

        # 防止因參數或邊界錯誤造成無限迴圈
        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


# ============================================================
# Chunk ID
# ============================================================

def create_source_prefix(source_id: str) -> str:
    """
    Convert source_id into a safe lowercase chunk ID prefix.
    """

    prefix = re.sub(
        r"[^a-zA-Z0-9]+",
        "_",
        source_id,
    )

    return prefix.strip("_").lower()


def create_chunk_id(
    source_id: str,
    pdf_page: int,
    chunk_index: int,
) -> str:
    """Create a deterministic and readable chunk ID."""

    source_prefix = create_source_prefix(source_id)

    return (
        f"{source_prefix}"
        f"_p{pdf_page:03d}"
        f"_c{chunk_index:02d}"
    )


# ============================================================
# Chunk generation
# ============================================================

def create_chunks(
    pages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Convert page-level parsed data into chunk-level data.
    """

    chunks: list[dict[str, Any]] = []

    for page in pages:
        extraction_status = page.get(
            "extraction_status"
        )

        original_text = page.get("text", "")

        # 跳過無法解析或沒有文字的頁面
        SUPPORTED_EXTRACTION_STATUSES = {
            "text_extracted",
            "ocr_extracted",
        }

        if extraction_status not in (
            SUPPORTED_EXTRACTION_STATUSES
        ):
            continue

        if not original_text.strip():
            continue

        source_id = page["source_id"]
        pdf_page = page["pdf_page"]

        page_chunks = split_text(original_text)

        for chunk_index, chunk_text in enumerate(
            page_chunks,
            start=1,
        ):
            chunk = {
                "chunk_id": create_chunk_id(
                    source_id=source_id,
                    pdf_page=pdf_page,
                    chunk_index=chunk_index,
                ),
                "source_id": source_id,
                "pdf_page": pdf_page,
                "chunk_index": chunk_index,
                "text": chunk_text,
                "metadata": {
                    **page.get("metadata", {}),
                },
                "diagnostics": {
                    "char_count": len(chunk_text),
                    "max_chars": MAX_CHARS,
                    "overlap_chars": OVERLAP_CHARS,
                },
                "extraction_status": extraction_status,
            }

            chunks.append(chunk)

    return chunks


# ============================================================
# Validation
# ============================================================

def validate_chunks(
    chunks: list[dict[str, Any]],
) -> None:
    """
    Fail immediately if baseline chunk invariants are violated.
    """

    if not chunks:
        raise ValueError(
            "No chunks were generated."
        )

    chunk_ids = [
        chunk["chunk_id"]
        for chunk in chunks
    ]

    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError(
            "Duplicate chunk IDs were detected."
        )

    for chunk in chunks:
        if not chunk["text"].strip():
            raise ValueError(
                f"Empty chunk detected: "
                f"{chunk['chunk_id']}"
            )

        if not chunk.get("source_id"):
            raise ValueError(
                f"Missing source_id: "
                f"{chunk['chunk_id']}"
            )

        if not chunk.get("pdf_page"):
            raise ValueError(
                f"Missing pdf_page: "
                f"{chunk['chunk_id']}"
            )

        if len(chunk["text"]) > MAX_CHARS:
            raise ValueError(
                f"Chunk exceeds MAX_CHARS: "
                f"{chunk['chunk_id']} "
                f"({len(chunk['text'])} characters)"
            )


# ============================================================
# Sample generation
# ============================================================

def create_chunk_sample(
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Select all chunks from representative PDF pages.
    """

    return [
        chunk
        for chunk in chunks
        if chunk["pdf_page"] in SAMPLE_PAGE_NUMBERS
    ]


# ============================================================
# Summary generation
# ============================================================

def create_chunk_summary(
    pages: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create statistics for the chunking baseline."""

    chunk_sizes = [
        len(chunk["text"])
        for chunk in chunks
    ]

    processed_pages = sorted({
        chunk["pdf_page"]
        for chunk in chunks
    })

    skipped_pages = [
        page["pdf_page"]
        for page in pages
        if page.get("extraction_status")
        != "text_extracted"
    ]

    chunks_per_page: dict[str, int] = {}

    for chunk in chunks:
        page_key = str(chunk["pdf_page"])

        chunks_per_page[page_key] = (
            chunks_per_page.get(page_key, 0) + 1
        )

    return {
        "configuration": {
            "max_chars": MAX_CHARS,
            "overlap_chars": OVERLAP_CHARS,
            "cross_page_chunks_allowed": False,
        },
        "input_page_count": len(pages),
        "processed_page_count": len(
            processed_pages
        ),
        "skipped_page_count": len(
            skipped_pages
        ),
        "skipped_pages": skipped_pages,
        "total_chunk_count": len(chunks),
        "minimum_chunk_chars": min(
            chunk_sizes
        ),
        "maximum_chunk_chars": max(
            chunk_sizes
        ),
        "average_chunk_chars": round(
            statistics.mean(chunk_sizes),
            2,
        ),
        "median_chunk_chars": round(
            statistics.median(chunk_sizes),
            2,
        ),
        "sample_pages": SAMPLE_PAGE_NUMBERS,
        "chunks_per_page": chunks_per_page,
    }


# ============================================================
# Main
# ============================================================

def main() -> None:
    pages = read_json(INPUT_PATH)

    if not isinstance(pages, list):
        raise TypeError(
            "parsed_pages.json must contain a JSON list."
        )

    chunks = create_chunks(pages)

    validate_chunks(chunks)

    documents = create_documents(chunks)

    vectorstore = create_vector_store(documents)

    vectors, stored_documents, stored_metadatas = (
        get_embedding_data(vectorstore)
    )

    print(
        f"Loaded {len(vectors)} embeddings "
        f"with {vectors.shape[1]} dimensions."
    )

    create_2d_visualization(
        vectors=vectors,
        documents=stored_documents,
        metadatas=stored_metadatas,
    )

    create_3d_visualization(
        vectors=vectors,
        documents=stored_documents,
        metadatas=stored_metadatas,
    )

    vector_count = vectorstore._collection.count()

    chunk_sample = create_chunk_sample(chunks)

    chunk_summary = create_chunk_summary(
        pages=pages,
        chunks=chunks,
    )

    write_json(
        FULL_OUTPUT_PATH,
        chunks,
    )

    write_json(
        SAMPLE_OUTPUT_PATH,
        chunk_sample,
    )

    write_json(
        SUMMARY_OUTPUT_PATH,
        chunk_summary,
    )

    print()
    print("=" * 60)
    print("Chunking baseline completed")
    print("=" * 60)
    print(
        f"Input pages: "
        f"{chunk_summary['input_page_count']}"
    )
    print(
        f"Processed pages: "
        f"{chunk_summary['processed_page_count']}"
    )
    print(
        f"Skipped pages: "
        f"{chunk_summary['skipped_page_count']}"
    )
    print(
        f"Total chunks: "
        f"{chunk_summary['total_chunk_count']}"
    )
    print(
        f"Minimum chunk size: "
        f"{chunk_summary['minimum_chunk_chars']}"
    )
    print(
        f"Maximum chunk size: "
        f"{chunk_summary['maximum_chunk_chars']}"
    )
    print(
        f"Average chunk size: "
        f"{chunk_summary['average_chunk_chars']}"
    )
    print()
    print(f"Full output:   {FULL_OUTPUT_PATH}")
    print(f"Sample output: {SAMPLE_OUTPUT_PATH}")
    print(f"Summary:       {SUMMARY_OUTPUT_PATH}")
    print(
    f"Embedding model: "
    f"{os.getenv('EMBEDDING_MODEL', 'text-embedding-3-large')}"
    )
    print(f"Chroma vectors: {vector_count}")
    print(f"Chroma path:    {CHROMA_PATH}")
    results = vectorstore.similarity_search(
        "公司的營業收入是多少？",
        k=3,
    )

    for index, document in enumerate(results, start=1):
        print()
        print(f"Result {index}")
        print(f"Metadata: {document.metadata}")
        print(document.page_content[:300])

def create_documents(
    chunks: list[dict[str, Any]],
) -> list[Document]:
    """
    Convert chunk dictionaries into LangChain Documents.
    """

    documents: list[Document] = []

    for chunk in chunks:
        metadata = {
            "chunk_id": chunk["chunk_id"],
            "source_id": chunk["source_id"],
            "pdf_page": chunk["pdf_page"],
            "chunk_index": chunk["chunk_index"],
            "extraction_status": chunk.get(
                "extraction_status",
                "unknown",
            ),
        }

        # Chroma metadata 適合存字串、整數、浮點數、布林值，
        # 不要直接放巢狀 dict 或 list。
        for key, value in chunk.get("metadata", {}).items():
            if isinstance(value, (str, int, float, bool)):
                metadata[key] = value

        documents.append(
            Document(
                page_content=chunk["text"],
                metadata=metadata,
            )
        )

    return documents

def create_vector_store(
    documents: list[Document],
) -> Chroma:
    load_dotenv(PROJECT_ROOT / ".env")

    embedding_model = os.getenv(
        "EMBEDDING_MODEL",
        "text-embedding-3-large",
    )

    embeddings = OpenAIEmbeddings(
        model=embedding_model,
    )

    existing_store = Chroma(
        collection_name=CHROMA_COLLECTION_NAME,
        persist_directory=str(CHROMA_PATH),
        embedding_function=embeddings,
    )

    if existing_store._collection.count() > 0:
        existing_store.delete_collection()

    return Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        ids=[
            document.metadata["chunk_id"]
            for document in documents
        ],
        collection_name=CHROMA_COLLECTION_NAME,
        persist_directory=str(CHROMA_PATH),
    )

def get_embedding_data(
    vectorstore: Chroma,
) -> tuple[
    np.ndarray,
    list[str],
    list[dict[str, Any]],
]:
    """
    Read embeddings, documents and metadata from Chroma.
    """

    collection = vectorstore._collection

    result = collection.get(
        include=[
            "embeddings",
            "documents",
            "metadatas",
        ]
    )

    embeddings = result.get("embeddings")
    documents = result.get("documents")
    metadatas = result.get("metadatas")

    if embeddings is None:
        raise ValueError(
            "No embeddings were returned from Chroma."
        )

    if documents is None or metadatas is None:
        raise ValueError(
            "Documents or metadata are missing from Chroma."
        )

    vectors = np.asarray(
        embeddings,
        dtype=np.float32,
    )

    if len(vectors) < 4:
        raise ValueError(
            "At least 4 vectors are required "
            "for this t-SNE visualization."
        )

    return vectors, documents, metadatas

def create_hover_texts(
    documents: list[str],
    metadatas: list[dict[str, Any]],
) -> list[str]:
    """
    Create text displayed when hovering over a point.
    """

    hover_texts: list[str] = []

    for document, metadata in zip(
        documents,
        metadatas,
    ):
        preview = document[:200].replace(
            "\n",
            "<br>",
        )

        hover_texts.append(
            f"Chunk: {metadata.get('chunk_id')}<br>"
            f"Source: {metadata.get('source_id')}<br>"
            f"PDF page: {metadata.get('pdf_page')}<br>"
            f"Text: {preview}..."
        )

    return hover_texts

def create_2d_visualization(
    vectors: np.ndarray,
    documents: list[str],
    metadatas: list[dict[str, Any]],
) -> None:
    """
    Reduce embeddings to 2D with t-SNE
    and save an interactive Plotly chart.
    """

    vector_count = len(vectors)

    # perplexity 必須小於資料筆數
    perplexity = min(
        30,
        vector_count - 1,
    )

    tsne = TSNE(
        n_components=2,
        perplexity=perplexity,
        random_state=42,
        init="pca",
        learning_rate="auto",
    )

    reduced_vectors = tsne.fit_transform(
        vectors
    )

    page_numbers = [
        metadata.get("pdf_page", 0)
        for metadata in metadatas
    ]

    hover_texts = create_hover_texts(
        documents,
        metadatas,
    )

    figure = go.Figure(
        data=[
            go.Scatter(
                x=reduced_vectors[:, 0],
                y=reduced_vectors[:, 1],
                mode="markers",
                marker={
                    "size": 8,
                    "color": page_numbers,
                    "colorscale": "Viridis",
                    "showscale": True,
                    "colorbar": {
                        "title": "PDF page",
                    },
                    "opacity": 0.8,
                },
                text=hover_texts,
                hoverinfo="text",
            )
        ]
    )

    figure.update_layout(
        title="Financial Report Chunk Embeddings — 2D",
        xaxis_title="t-SNE dimension 1",
        yaxis_title="t-SNE dimension 2",
        width=1000,
        height=700,
    )

    figure.write_html(
        str(VISUALIZATION_2D_PATH),
        include_plotlyjs=True,
    )

    print(
        f"2D visualization: "
        f"{VISUALIZATION_2D_PATH}"
    )

def create_3d_visualization(
    vectors: np.ndarray,
    documents: list[str],
    metadatas: list[dict[str, Any]],
) -> None:
    """
    Reduce embeddings to 3D with t-SNE
    and save an interactive Plotly chart.
    """

    vector_count = len(vectors)

    perplexity = min(
        30,
        vector_count - 1,
    )

    tsne = TSNE(
        n_components=3,
        perplexity=perplexity,
        random_state=42,
        init="pca",
        learning_rate="auto",
    )

    reduced_vectors = tsne.fit_transform(
        vectors
    )

    page_numbers = [
        metadata.get("pdf_page", 0)
        for metadata in metadatas
    ]

    hover_texts = create_hover_texts(
        documents,
        metadatas,
    )

    figure = go.Figure(
        data=[
            go.Scatter3d(
                x=reduced_vectors[:, 0],
                y=reduced_vectors[:, 1],
                z=reduced_vectors[:, 2],
                mode="markers",
                marker={
                    "size": 5,
                    "color": page_numbers,
                    "colorscale": "Viridis",
                    "showscale": True,
                    "colorbar": {
                        "title": "PDF page",
                    },
                    "opacity": 0.8,
                },
                text=hover_texts,
                hoverinfo="text",
            )
        ]
    )

    figure.update_layout(
        title="Financial Report Chunk Embeddings — 3D",
        scene={
            "xaxis_title": "t-SNE dimension 1",
            "yaxis_title": "t-SNE dimension 2",
            "zaxis_title": "t-SNE dimension 3",
        },
        width=1100,
        height=800,
    )

    figure.write_html(
        str(VISUALIZATION_3D_PATH),
        include_plotlyjs=True,
    )

    print(
        f"3D visualization: "
        f"{VISUALIZATION_3D_PATH}"
    )


if __name__ == "__main__":
    main()