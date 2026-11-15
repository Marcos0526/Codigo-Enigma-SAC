"""FAISS retrieval-augmented generation over the local NASA PSI catalog."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from services.search.src.rag.local_catalog import LocalPSICatalog


class PSIDataRAG:
    """Reuse the existing NASA RAG embeddings/FAISS pipeline with PSI metadata."""

    def __init__(
        self,
        catalog: LocalPSICatalog,
        cache_dir: str | Path,
        embedding_model: str,
    ):
        self.catalog = catalog
        self.cache_dir = Path(cache_dir)
        self.embedding_model = embedding_model
        self._vectorstore = None
        self._lock = threading.Lock()

    def _corpus_signature(self) -> str:
        digest = hashlib.sha256()
        for path in sorted(self.catalog.data_dir.glob("PSI-*/*")):
            if not path.is_file():
                continue
            stat = path.stat()
            relative_path = path.relative_to(self.catalog.data_dir).as_posix()
            digest.update(f"{relative_path}|{stat.st_size}|{stat.st_mtime_ns}".encode())
        digest.update(self.embedding_model.encode())
        return digest.hexdigest()

    def _get_vectorstore(self):
        if self._vectorstore is not None:
            return self._vectorstore
        with self._lock:
            if self._vectorstore is not None:
                return self._vectorstore

            # Imported lazily so data-only operations do not load an embedding model.
            from langchain_core.documents import Document

            from services.search.src.rag import nasa_rag

            signature = self._corpus_signature()
            index_dir = self.cache_dir / "faiss_index"
            meta_path = self.cache_dir / "index_meta.json"
            metadata = {}
            if meta_path.is_file():
                try:
                    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    metadata = {}

            if (
                index_dir.is_dir()
                and metadata.get("corpus_signature") == signature
                and metadata.get("embedding_model") == self.embedding_model
            ):
                self._vectorstore = nasa_rag.load_vectorstore(
                    self.cache_dir, model_name=self.embedding_model
                )
                return self._vectorstore

            documents = [
                Document(page_content=text, metadata=metadata)
                for text, metadata in self.catalog.retrieval_documents()
            ]
            if not documents:
                raise ValueError("No local NASA PSI metadata was found to index")
            self._vectorstore = nasa_rag.create_embeddings(
                documents, model_name=self.embedding_model
            )
            nasa_rag.save_vectorstore(
                self._vectorstore,
                self.cache_dir,
                meta={
                    "embedding_model": self.embedding_model,
                    "corpus_signature": signature,
                    "document_count": len(documents),
                    "source": "data/psi_databases",
                },
            )
            return self._vectorstore

    def retrieve(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Return ranked metadata chunks and cosine similarities."""
        from services.search.src.rag import nasa_rag

        pairs = nasa_rag.cosine_similarity_search(
            self._get_vectorstore(), query, k=max(1, min(k, 100))
        )
        return [
            {
                "content": document.page_content,
                "metadata": dict(document.metadata),
                "score": score,
            }
            for document, score in pairs
        ]

    def search(
        self,
        query: str,
        max_results: int = 100,
        min_score: float = 0.0,
        psi_ids: Optional[List[str]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Retrieve every distinct eligible local dataset, ordered by relevance."""
        allowed_psi_ids = set(psi_ids or [])
        retrieved = self.retrieve(query, k=max(100, max_results))
        datasets = []
        seen = set()
        for match in retrieved:
            metadata = match["metadata"]
            dataset_id = metadata.get("dataset_id")
            if not dataset_id or dataset_id in seen or match["score"] < min_score:
                continue
            if allowed_psi_ids and metadata.get("psi_id") not in allowed_psi_ids:
                continue
            try:
                dataset = self.catalog.public_dataset(dataset_id)
            except (OSError, ValueError):
                continue
            if not dataset["numericColumns"]:
                continue
            dataset["score"] = round(float(match["score"]), 4)
            datasets.append(dataset)
            seen.add(dataset_id)
            if len(datasets) >= max_results:
                break
        return datasets, retrieved

    @property
    def index_ready(self) -> bool:
        return self._vectorstore is not None
