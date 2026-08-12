from pathlib import Path
from typing import Dict, List
import csv
import hashlib
import re

import chromadb
from sentence_transformers import SentenceTransformer

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = BASE_DIR / "rag_store" / "chroma"

RAG_EXTENSIONS = {".pdf", ".csv", ".txt", ".md"}

EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION_NAME = "nutrition_rag"

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[str]:
    text = normalize_text(text)

    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = max(end - overlap, start + 1)

    return chunks


def make_id(source_file: str, location: str, chunk_index: int) -> str:
    raw = f"{source_file}:{location}:{chunk_index}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def load_pdf(path: Path) -> List[Dict]:
    if fitz is None:
        raise RuntimeError(
            "PDF ingestion에는 PyMuPDF가 필요합니다. "
            "`pip install pymupdf`를 실행하세요."
        )

    documents = []

    with fitz.open(path) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text("text")

            for chunk_index, chunk in enumerate(chunk_text(text)):
                documents.append(
                    {
                        "content": chunk,
                        "metadata": {
                            "source_file": path.name,
                            "source_path": str(path),
                            "source_type": "pdf",
                            "page_number": page_number,
                            "chunk_index": chunk_index,
                        },
                        "id": make_id(path.name, str(page_number), chunk_index),
                    }
                )

    return documents


def read_csv_rows(path: Path) -> List[Dict]:
    last_error = None

    for encoding in ("utf-8-sig", "cp949", "utf-8"):
        try:
            with path.open("r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)

                documents = []

                for row_number, row in enumerate(reader, start=2):
                    fields = [
                        f"{key}: {value}"
                        for key, value in row.items()
                        if value not in (None, "")
                    ]

                    content = " | ".join(fields)

                    if not content.strip():
                        continue

                    documents.append(
                        {
                            "content": content,
                            "metadata": {
                                "source_file": path.name,
                                "source_path": str(path),
                                "source_type": "csv",
                                "row_number": row_number,
                                "chunk_index": 0,
                            },
                            "id": make_id(path.name, str(row_number), 0),
                        }
                    )

                return documents

        except UnicodeDecodeError as exc:
            last_error = exc

    raise last_error


def load_text(path: Path) -> List[Dict]:
    last_error = None

    for encoding in ("utf-8-sig", "cp949", "utf-8"):
        try:
            text = path.read_text(encoding=encoding)

            return [
                {
                    "content": chunk,
                    "metadata": {
                        "source_file": path.name,
                        "source_path": str(path),
                        "source_type": path.suffix.lower().lstrip("."),
                        "chunk_index": chunk_index,
                    },
                    "id": make_id(path.name, "text", chunk_index),
                }
                for chunk_index, chunk in enumerate(chunk_text(text))
            ]

        except UnicodeDecodeError as exc:
            last_error = exc

    raise last_error


def load_file(path: Path) -> List[Dict]:
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return load_pdf(path)

    if suffix == ".csv":
        return read_csv_rows(path)

    return load_text(path)


def main():
    if not DATA_DIR.exists():
        raise FileNotFoundError(
            f"RAG data directory not found: {DATA_DIR}"
        )

    files = sorted(
        path
        for path in DATA_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in RAG_EXTENSIONS
    )

    if not files:
        print(f"[RAG] No supported files found in {DATA_DIR}")
        return

    print(f"[RAG] Found {len(files)} source files")

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # 실습 단계에서는 전체 collection을 재생성하여
    # data/ 변경 사항이 확실히 반영되도록 합니다.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    all_documents = []

    for path in files:
        print(f"[RAG] Loading: {path.name}")

        try:
            docs = load_file(path)
            all_documents.extend(docs)
            print(f"      -> {len(docs)} chunks/documents")
        except Exception as exc:
            print(f"      -> ERROR: {exc}")

    if not all_documents:
        print("[RAG] Nothing to index.")
        return

    texts = [doc["content"] for doc in all_documents]

    print(f"[RAG] Creating embeddings for {len(texts)} documents...")

    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,
    ).tolist()

    collection.add(
        ids=[doc["id"] for doc in all_documents],
        documents=texts,
        metadatas=[doc["metadata"] for doc in all_documents],
        embeddings=embeddings,
    )

    print()
    print("[RAG] ====================================")
    print("[RAG] Ingestion complete")
    print(f"[RAG] Collection : {COLLECTION_NAME}")
    print(f"[RAG] Documents  : {collection.count()}")
    print(f"[RAG] DB path    : {CHROMA_DIR}")
    print("[RAG] ====================================")


if __name__ == "__main__":
    main()
