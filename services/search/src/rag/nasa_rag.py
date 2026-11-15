#!/usr/bin/env python3
"""
NASA RAG System - Retrieval Augmented Generation over NASA PDF documents.

Pipeline:
1. Extract text from PDFs page by page (pdfplumber -> pypdf -> OCR fallback)
2. Split each page into overlapping chunks (page number kept in metadata)
3. Embed chunks with sentence-transformers and store them in a FAISS index
   using inner product over normalized vectors (== cosine similarity)
4. Retrieve the most relevant chunks for a query and aggregate them by PDF
5. Optionally generate a grounded answer with an LLM (Ollama or any
   OpenAI-compatible endpoint)

The retrieval half works with no LLM. To get a generated answer use `--ask`.
"""

import argparse
import hashlib
import json
import os
import shutil
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from tqdm import tqdm

# PDF processing
import pypdf
import pdfplumber
from pdf2image import convert_from_path
import pytesseract

# Embeddings and vector store
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = Path(os.getenv("NASA_RAG_DATA", BASE_DIR / "Data")).expanduser()
CACHE_DIR = Path(os.getenv("NASA_RAG_CACHE", BASE_DIR / ".cache")).expanduser()
INDEX_DIR = CACHE_DIR / "faiss_index"
INDEX_META = CACHE_DIR / "index_meta.json"

EMBEDDING_MODEL_NAME = os.getenv(
    "NASA_RAG_EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2"
)
# "cuda", "cpu", ... Leave empty to auto-detect (CUDA if available, else CPU).
EMBEDDING_DEVICE = os.getenv("NASA_RAG_DEVICE", "").strip()
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
TOP_K = int(os.getenv("NASA_RAG_TOP_K", "5"))

# A PDF is considered "text based" if at least this many characters come out
# of the normal extractors; otherwise we fall back to OCR.
MIN_TEXT_CHARS = 200
OCR_DPI = 200
MIN_CHUNK_CHARS = 30

# LLM configuration (only needed for `--ask`)
LLM_PROVIDER = os.getenv("NASA_RAG_LLM_PROVIDER", "auto")  # auto|ollama|openai|none
LLM_MODEL = os.getenv("NASA_RAG_LLM_MODEL", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")


# --------------------------------------------------------------------------
# Text extraction
# --------------------------------------------------------------------------
def _extract_with_pdfplumber(pdf_path: Path) -> List[str]:
    pages: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pages.append("")
    return pages


def _extract_with_pypdf(pdf_path: Path) -> List[str]:
    pages: List[str] = []
    reader = pypdf.PdfReader(pdf_path)
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return pages


def _ocr_pdf(pdf_path: Path) -> List[str]:
    pages: List[str] = []
    images = convert_from_path(pdf_path, dpi=OCR_DPI)
    for image in images:
        pages.append(pytesseract.image_to_string(image, lang="eng"))
    return pages


def ocr_is_available() -> bool:
    """OCR needs the tesseract binary *and* the English traineddata file."""
    if shutil.which("tesseract") is None:
        return False
    try:
        return "eng" in pytesseract.get_languages(config="")
    except Exception:
        return False


def extract_pages_from_pdf(pdf_path: Path, enable_ocr: bool = True) -> List[str]:
    """
    Extract one string per page. Tries pdfplumber, then pypdf, then OCR.
    Returns an empty list if nothing could be extracted.
    """
    pages: List[str] = []

    try:
        pages = _extract_with_pdfplumber(pdf_path)
    except Exception as exc:
        print(f"  pdfplumber failed for {pdf_path.name}: {exc}")

    if sum(len(p.strip()) for p in pages) < MIN_TEXT_CHARS:
        try:
            alt = _extract_with_pypdf(pdf_path)
            if sum(len(p.strip()) for p in alt) > sum(len(p.strip()) for p in pages):
                pages = alt
        except Exception as exc:
            print(f"  pypdf failed for {pdf_path.name}: {exc}")

    if sum(len(p.strip()) for p in pages) < MIN_TEXT_CHARS and enable_ocr:
        print(f"  OCR: {pdf_path.name} (this can take a few minutes)")
        try:
            ocr_pages = _ocr_pdf(pdf_path)
            # Keep OCR output when it adds real content.
            if sum(len(p.strip()) for p in ocr_pages) > sum(len(p.strip()) for p in pages):
                pages = ocr_pages
        except Exception as exc:
            print(f"  OCR failed for {pdf_path.name}: {exc}")

    return pages


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Backwards-compatible helper: full text of a PDF as a single string."""
    return "\n".join(extract_pages_from_pdf(pdf_path)).strip()


def process_pdfs(data_dir: Path, enable_ocr: bool = True) -> List[Document]:
    """
    Process every PDF under `data_dir` and return one Document per page.

    Keeping one document per page preserves the page number in the metadata,
    which is what makes citations meaningful later on.
    """
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    if enable_ocr and not ocr_is_available():
        print(
            "WARNING: OCR is not available (tesseract or eng.traineddata missing).\n"
            "         Scanned PDFs will be skipped. On Arch:\n"
            "           sudo pacman -S tesseract tesseract-data-eng\n"
            "         or point TESSDATA_PREFIX at a directory containing eng.traineddata."
        )
        enable_ocr = False

    pdf_files = sorted(data_dir.rglob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files in {data_dir}")

    documents: List[Document] = []
    skipped: List[str] = []

    for pdf_path in tqdm(pdf_files, desc="Extracting text"):
        rel_path = pdf_path.relative_to(data_dir)
        try:
            pages = extract_pages_from_pdf(pdf_path, enable_ocr=enable_ocr)
        except Exception as exc:
            print(f"  FAILED {rel_path}: {exc}")
            skipped.append(str(rel_path))
            continue

        chars = 0
        for page_number, page_text in enumerate(pages, start=1):
            page_text = (page_text or "").strip()
            if not page_text:
                continue
            chars += len(page_text)
            documents.append(
                Document(
                    page_content=page_text,
                    metadata={
                        "source": rel_path.as_posix(),
                        "filename": pdf_path.name,
                        "page": page_number,
                    },
                )
            )

        if chars:
            print(f"  OK   {rel_path} ({len(pages)} pages, {chars} chars)")
        else:
            print(f"  SKIP {rel_path} (no text extracted)")
            skipped.append(str(rel_path))

    if skipped:
        print(f"\n{len(skipped)} PDF(s) without extractable text:")
        for name in skipped:
            print(f"  - {name}")

    return documents


# --------------------------------------------------------------------------
# Embeddings / index
# --------------------------------------------------------------------------
def _resolve_device() -> str:
    """Pick the embedding device: explicit NASA_RAG_DEVICE or auto-detect."""
    if EMBEDDING_DEVICE:
        return EMBEDDING_DEVICE
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def _make_embeddings(model_name: str = EMBEDDING_MODEL_NAME) -> HuggingFaceEmbeddings:
    device = _resolve_device()
    if device.startswith("cuda"):
        try:
            import torch

            print(f"Embedding device: CUDA ({torch.cuda.get_device_name(0)})")
        except Exception:
            print("Embedding device: CUDA")
    else:
        print(f"Embedding device: {device}")
    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},  # so inner product == cosine
    )


def _signature(data_dir: Path) -> str:
    """Cheap fingerprint of the corpus, used to detect stale indexes."""
    digest = hashlib.sha256()
    for path in sorted(data_dir.rglob("*.pdf")):
        stat = path.stat()
        digest.update(f"{path.as_posix()}|{stat.st_size}|{stat.st_mtime_ns}".encode())
    return digest.hexdigest()


def save_vectorstore(vectorstore: FAISS, cache_dir: Path, meta: Optional[Dict] = None):
    index_dir = cache_dir / "faiss_index"
    index_dir.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(index_dir))
    meta_path = cache_dir / "index_meta.json"
    if meta is not None:
        meta_path.write_text(json.dumps(meta, indent=2))
    print(f"Vector store saved to {index_dir}")


def load_vectorstore(
    cache_dir: Path,
    model_name: str = EMBEDDING_MODEL_NAME,
    data_dir: Optional[Path] = None,
) -> FAISS:
    index_dir = cache_dir / "faiss_index"
    embeddings = _make_embeddings(model_name)
    vectorstore = FAISS.load_local(
        str(index_dir), embeddings, allow_dangerous_deserialization=True
    )

    meta_path = cache_dir / "index_meta.json"
    if data_dir is not None and meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if meta.get("embedding_model") != model_name:
            print(
                "WARNING: index was built with a different embedding model "
                f"({meta.get('embedding_model')}). Run with --rebuild."
            )
        elif meta.get("corpus_signature") != _signature(data_dir):
            print("WARNING: Data/ changed since the index was built. Run with --rebuild.")
        print(f"Index: {meta.get('chunk_count', '?')} chunks from "
              f"{meta.get('document_count', '?')} pages "
              f"(built {meta.get('created_at', 'unknown')})")
    else:
        print(f"Vector store loaded from {index_dir}")
    return vectorstore


def create_embeddings(
    documents: List[Document], model_name: str = EMBEDDING_MODEL_NAME
) -> FAISS:
    """Split page documents into chunks and index them with cosine similarity."""
    print(f"Loading embedding model: {model_name}")
    embeddings = _make_embeddings(model_name)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)

    # Drop tiny fragments and exact duplicates (repeated headers, page numbers...)
    seen = set()
    clean_chunks: List[Document] = []
    for chunk in chunks:
        text = chunk.page_content.strip()
        if len(text) < MIN_CHUNK_CHARS:
            continue
        key = (chunk.metadata.get("source"), text)
        if key in seen:
            continue
        seen.add(key)
        chunk.page_content = text
        clean_chunks.append(chunk)

    if not clean_chunks:
        raise ValueError("No chunks to index: the PDFs produced no usable text.")

    print(
        f"Created {len(clean_chunks)} chunks from {len(documents)} pages "
        f"({len(chunks) - len(clean_chunks)} empty/duplicate chunks dropped)"
    )

    print("Creating FAISS vector store (inner product / cosine similarity)...")
    vectorstore = FAISS.from_documents(
        clean_chunks,
        embeddings,
        distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT,
    )
    return vectorstore


def cosine_similarity_search(
    vectorstore: FAISS, query: str, k: int = TOP_K
) -> List[Tuple[Document, float]]:
    """
    Return (chunk, cosine similarity) pairs, best first.

    Documents are normalized before indexing and the index uses inner product,
    so the score is already a cosine similarity in [-1, 1] (higher is better).
    No distance->similarity conversion is needed.
    """
    pairs = vectorstore.similarity_search_with_score(query, k=k)
    results = []
    for doc, score in pairs:
        # Guard against tiny floating point overshoot.
        similarity = float(max(-1.0, min(1.0, score)))
        results.append((doc, similarity))
    results.sort(key=lambda item: item[1], reverse=True)
    return results


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------
def _pages_for(chunks: List[Document]) -> List[int]:
    return sorted({d.metadata.get("page") for d in chunks if d.metadata.get("page")})


def get_pdf_summary(
    results: List[Tuple[Document, float]], query: str
) -> Dict:
    """
    Aggregate chunks by source PDF.

    PDFs are ranked by their *best* chunk (max similarity), with the mean as a
    tie-breaker. Using the max avoids penalizing large documents that happen to
    contribute many mediocre chunks.
    """
    grouped: Dict[str, List[Tuple[Document, float]]] = {}
    for doc, score in results:
        source = doc.metadata.get("source", "unknown")
        grouped.setdefault(source, []).append((doc, score))

    if not grouped:
        return {"query": query, "error": "No results found"}

    ranking = []
    for source, items in grouped.items():
        items.sort(key=lambda item: item[1], reverse=True)
        scores = [score for _, score in items]
        ranking.append(
            {
                "pdf": source,
                "best_similarity": float(max(scores)),
                "avg_similarity": float(np.mean(scores)),
                "pages": _pages_for([doc for doc, _ in items]),
                "chunks": items,
            }
        )
    ranking.sort(key=lambda row: (row["best_similarity"], row["avg_similarity"]), reverse=True)

    top = ranking[0]
    summary_chunks = [doc.page_content for doc, _ in top["chunks"][:3]]
    combined = " ".join(summary_chunks).strip()
    summary = combined[:1500] + "..." if len(combined) > 1500 else combined

    return {
        "query": query,
        "top_pdf": top["pdf"],
        "similarity_score": top["best_similarity"],
        "pages": top["pages"],
        "summary": summary,
        "all_matches": [
            {
                "pdf": row["pdf"],
                "best_similarity": row["best_similarity"],
                "avg_similarity": row["avg_similarity"],
                "pages": row["pages"],
            }
            for row in ranking
        ],
        "_chunks": results,
    }


# --------------------------------------------------------------------------
# Optional LLM generation (turns retrieval into a real RAG answer)
# --------------------------------------------------------------------------
def _post_json(url: str, payload: Dict, headers: Optional[Dict] = None, timeout: int = 120) -> Dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _ollama_available() -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def resolve_llm() -> Optional[str]:
    """Decide which LLM backend to use. Returns None when none is configured."""
    if LLM_PROVIDER == "none":
        return None
    if LLM_PROVIDER in ("ollama", "openai"):
        return LLM_PROVIDER
    # auto
    if OPENAI_API_KEY or os.getenv("OPENAI_BASE_URL"):
        return "openai"
    if _ollama_available():
        return "ollama"
    return None


def generate_answer(question: str, context: str) -> str:
    """Send a grounded prompt to the configured LLM and return its answer."""
    system = (
        "You are a NASA mission-documentation assistant. Answer ONLY with facts "
        "found in the provided context. Cite sources using their bracketed numbers, "
        "for example [1]. If the context does not contain the answer, say so plainly "
        "instead of guessing."
    )
    user = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"

    provider = resolve_llm()
    if provider is None:
        raise RuntimeError(
            "No LLM configured. Retrieval works, but generation needs one of:\n"
            "  - Ollama running locally (https://ollama.com) and a model pulled, e.g.\n"
            "      ollama pull llama3.1\n"
            "  - an OpenAI-compatible endpoint: export OPENAI_API_KEY=... "
            "[OPENAI_BASE_URL=...] [NASA_RAG_LLM_MODEL=...]\n"
            "Re-run without --ask to get retrieval only."
        )

    if provider == "ollama":
        model = LLM_MODEL or "llama3.1"
        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            data = _post_json(f"{OLLAMA_HOST}/api/chat", payload)
        except Exception as exc:
            raise RuntimeError(
                f"Ollama at {OLLAMA_HOST} with model '{model}' failed: {exc}. "
                "Is `ollama serve` running and the model pulled?"
            ) from exc
        return data["message"]["content"].strip()

    # OpenAI-compatible
    model = LLM_MODEL or os.getenv("NASA_RAG_LLM_MODEL") or "gpt-4o-mini"
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {}
    if OPENAI_API_KEY:
        headers["Authorization"] = f"Bearer {OPENAI_API_KEY}"
    try:
        data = _post_json(f"{OPENAI_BASE_URL}/chat/completions", payload, headers)
    except Exception as exc:
        raise RuntimeError(f"LLM request failed: {exc}") from exc
    return data["choices"][0]["message"]["content"].strip()


def _build_context(results: List[Tuple[Document, float]]) -> str:
    blocks = []
    for index, (doc, _score) in enumerate(results, start=1):
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page")
        label = f"{source} (page {page})" if page else source
        blocks.append(f"[{index}] {label}\n{doc.page_content}")
    return "\n\n".join(blocks)


def query_rag(vectorstore: FAISS, query: str, k: int = TOP_K) -> Dict:
    """Retrieve relevant chunks and return the aggregated retrieval result."""
    print(f"\nQuery: {query}")
    results = cosine_similarity_search(vectorstore, query, k=k)

    if not results:
        return {"query": query, "error": "No results found"}

    print(f"Found {len(results)} relevant chunks")
    for i, (doc, score) in enumerate(results[:3], start=1):
        page = doc.metadata.get("page")
        location = f"{doc.metadata.get('source')} p.{page}" if page else doc.metadata.get("source")
        print(f"  {i}. {location} (cosine: {score:.4f})")

    return get_pdf_summary(results, query)


def ask(vectorstore: FAISS, question: str, k: int = TOP_K) -> Dict:
    """Full RAG: retrieve, build a grounded prompt, generate an answer."""
    result = query_rag(vectorstore, question, k=k)
    if "error" in result:
        return result

    chunks = result["_chunks"]
    try:
        answer = generate_answer(question, _build_context(chunks))
    except RuntimeError as exc:
        print(f"\n{exc}")
        return result

    return {
        **result,
        "answer": answer,
        "sources": [
            {
                "pdf": row["pdf"],
                "pages": row["pages"],
                "best_similarity": row["best_similarity"],
            }
            for row in result["all_matches"]
        ],
    }


def print_result(result: Dict, k: int = 3):
    print("\n" + "=" * 70)
    if result.get("answer"):
        print("ANSWER")
        print("=" * 70)
        print(result["answer"])
        print("\nSOURCES")
        for row in result.get("sources", []):
            pages = ", ".join(str(p) for p in row["pages"]) or "-"
            print(f"  - {row['pdf']} (pages {pages}, cosine {row['best_similarity']:.4f})")
        return

    print("RETRIEVAL RESULT (no LLM answer)")
    print("=" * 70)
    if "error" in result:
        print(result["error"])
        return
    print(f"Top PDF: {result['top_pdf']}")
    print(f"Best cosine similarity: {result['similarity_score']:.4f}")
    print(f"Pages: {', '.join(str(p) for p in result['pages'])}")
    print(f"\nMost relevant excerpt:\n{result['summary']}")
    print("\nAll matching PDFs:")
    for match in result["all_matches"][:10]:
        pages = ", ".join(str(p) for p in match["pages"])
        print(
            f"  - {match['pdf']}  best={match['best_similarity']:.4f} "
            f"avg={match['avg_similarity']:.4f} pages=[{pages}]"
        )


# --------------------------------------------------------------------------
# Index lifecycle / CLI
# --------------------------------------------------------------------------
def build_index(
    data_dir: Path,
    cache_dir: Path,
    force_rebuild: bool = False,
    enable_ocr: bool = True,
    model_name: str = EMBEDDING_MODEL_NAME,
) -> FAISS:
    index_path = cache_dir / "faiss_index"

    if index_path.exists() and not force_rebuild:
        print("Index already exists. Use --rebuild to rebuild.")
        return load_vectorstore(cache_dir, model_name=model_name, data_dir=data_dir)

    if shutil.which("tesseract") is None and enable_ocr:
        print("WARNING: tesseract not found; scanned PDFs will be skipped.")
        enable_ocr = False

    print("Building new index...")
    documents = process_pdfs(data_dir, enable_ocr=enable_ocr)
    if not documents:
        raise ValueError(
            "No text could be extracted from Data/. Check the PDFs or install "
            "tesseract/poppler for OCR."
        )

    vectorstore = create_embeddings(documents, model_name=model_name)

    from datetime import datetime, timezone

    meta = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "embedding_model": model_name,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "document_count": len(documents),
        "chunk_count": len(vectorstore.index_to_docstore_id),
        "corpus_signature": _signature(data_dir),
    }
    save_vectorstore(vectorstore, cache_dir, meta=meta)
    return vectorstore


def main():
    parser = argparse.ArgumentParser(
        description="NASA RAG System (retrieval + optional LLM answer)"
    )
    parser.add_argument("query", nargs="*", help="Query to search")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild index")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    parser.add_argument(
        "--ask",
        action="store_true",
        help="Generate an LLM answer from the retrieved chunks (needs Ollama or an "
        "OpenAI-compatible endpoint)",
    )
    parser.add_argument(
        "--no-ocr", action="store_true", help="Skip OCR for scanned PDFs (much faster)"
    )
    parser.add_argument(
        "-k", "--top-k", type=int, default=TOP_K, help=f"Chunks to retrieve (default {TOP_K})"
    )
    args = parser.parse_args()

    if not args.query and not args.interactive and not args.rebuild:
        parser.print_help()
        return

    vectorstore = build_index(
        DATA_DIR, CACHE_DIR, force_rebuild=args.rebuild, enable_ocr=not args.no_ocr
    )

    if args.query:
        query = " ".join(args.query)
        result = ask(vectorstore, query, k=args.top_k) if args.ask else query_rag(
            vectorstore, query, k=args.top_k
        )
        print_result(result)

    elif args.interactive:
        mode = "ask (LLM)" if args.ask else "retrieval"
        print(f"\nInteractive mode [{mode}]. Type 'quit' to exit.")
        while True:
            try:
                query = input("\nQuery> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if query.lower() in ["quit", "exit", "q"]:
                break
            if not query:
                continue
            result = ask(vectorstore, query, k=args.top_k) if args.ask else query_rag(
                vectorstore, query, k=args.top_k
            )
            print_result(result)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
