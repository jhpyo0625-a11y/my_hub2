from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).resolve().parent
CHROMA_DIR = BASE_DIR / "rag_store" / "chroma"

# 실습용 multilingual embedding model
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class RAGRetriever:
    """Embedding + ChromaDB 기반 RAG 검색기."""

    def __init__(
        self,
        chroma_dir: Path = CHROMA_DIR,
        collection_name: str = "nutrition_rag",
        model_name: str = EMBEDDING_MODEL_NAME,
    ):
        self.chroma_dir = Path(chroma_dir)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)

        print(f"[RAG] Embedding model loading: {model_name}")
        self.embedding_model = SentenceTransformer(model_name)

        self.client = chromadb.PersistentClient(path=str(self.chroma_dir))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def search(self, query: str, top_k: int = 8) -> List[Dict[str, Any]]:
        if not query.strip():
            return []

        query_embedding = self.embedding_model.encode(
            query,
            normalize_embeddings=True,
        ).tolist()

        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        ids = result.get("ids", [[]])[0]

        return [
            {
                "id": doc_id,
                "content": document,
                "metadata": metadata or {},
                "distance": distance,
                "score": 1.0 - distance if distance is not None else None,
            }
            for doc_id, document, metadata, distance in zip(
                ids, documents, metadatas, distances
            )
        ]

    def count(self) -> int:
        return self.collection.count()


rag_retriever = RAGRetriever()
