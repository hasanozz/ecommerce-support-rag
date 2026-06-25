import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import psycopg2
from pgvector.psycopg2 import register_vector
from psycopg2.extras import Json

DEFAULT_CHUNKS_PATH = Path("rag_chunks/rag_chunks_clean.jsonl")
DEFAULT_MODEL_NAME = "BAAI/bge-m3"
EMBEDDING_DIMENSION = 1024
RAG_DOCS_DIR = Path("rag_documents_final")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read chunk records from a JSONL file without modifying it."""
    chunks: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            chunk = json.loads(line)
            if not chunk.get("content"):
                raise ValueError(f"Empty content at line {line_number}")
            chunks.append(chunk)
    return chunks


def find_raw_json_for_doc(doc_id: str, docs_dir: Path = RAG_DOCS_DIR) -> Optional[dict]:
    """Search `rag_documents_final/` for a JSON file that contains the full document for `doc_id`.

    The function performs heuristic matching: each JSON file is loaded and checked for
    a top-level `id` or `doc_id` field, or for an object keyed by the doc_id. If nothing
    matches, return None.
    """
    if not docs_dir.exists():
        return None

    for fp in docs_dir.glob("*.json"):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue

        # direct match
        if isinstance(data, dict):
            if data.get("id") == doc_id or data.get("doc_id") == doc_id:
                return data
            # some files may be top-level mapping of id -> doc
            if doc_id in data:
                return data[doc_id]

    return None


def build_documents_and_chunks(
    raw_chunks: List[Dict[str, Any]]
) -> Tuple[Dict[str, dict], List[dict]]:
    """Map JSONL chunks to documents and chunks prepared for DB insertion (in-memory).

    Returns a tuple of (documents_by_id, chunk_records).
    documents_by_id: {doc_id: {id, category, subcategory, title, raw_json}}
    chunk_records: list of chunk dicts matching backend `chunks` model columns
    """
    documents: Dict[str, dict] = {}
    chunks_by_doc: Dict[str, List[dict]] = {}

    for c in raw_chunks:
        doc_id = c["doc_id"]
        chunks_by_doc.setdefault(doc_id, []).append(c)

    for doc_id, chunks in chunks_by_doc.items():
        # pick representative values from first chunk
        first = chunks[0]
        raw_json = find_raw_json_for_doc(doc_id)
        if raw_json is None:
            # fallback: aggregate metadata from chunks
            aggregated_meta = {
                "doc_id": doc_id,
                "collected_from_chunks": True,
                "metadata_examples": [c.get("metadata") for c in chunks[:3]],
            }
            raw_json = aggregated_meta

        documents[doc_id] = {
            "id": doc_id,
            "category": first.get("category"),
            "subcategory": first.get("subcategory"),
            "title": first.get("title"),
            "raw_json": raw_json,
        }

    # build chunk records with placeholders for contextual_content and embedding
    chunk_records: List[dict] = []
    for doc_id, chunks in chunks_by_doc.items():
        # preserve order as in file
        for idx, c in enumerate(chunks):
            chunk_records.append(
                {
                    "chunk_id": c["chunk_id"],
                    "doc_id": doc_id,
                    "category": c.get("category"),
                    "subcategory": c.get("subcategory"),
                    "title": c.get("title"),
                    "section": c.get("section"),
                    "content": c.get("content"),
                    "metadata": c.get("metadata"),
                    # contextual_content and embedding will be filled later
                    "contextual_content": None,
                    "embedding": None,
                    "__order_idx": idx,
                }
            )

    return documents, chunk_records


def build_contextual_content_for_doc(chunks: List[dict], max_len: int = 2000) -> None:
    """Populate `contextual_content` for each chunk in-place using neighbors.

    Each chunk's contextual content will include title/category/subcategory/section,
    the chunk's own content and short snippets from previous and next chunks (same doc).
    The final string is trimmed to `max_len` characters.
    """
    for i, chunk in enumerate(chunks):
        parts: List[str] = []
        header = []
        if chunk.get("title"):
            header.append(chunk["title"])
        if chunk.get("category"):
            header.append(chunk["category"])
        if chunk.get("subcategory"):
            header.append(chunk["subcategory"])
        if chunk.get("section"):
            header.append(chunk["section"])

        if header:
            parts.append(" | ".join(header))

        # own content (truncate to keep room for neighbors)
        own = chunk.get("content") or ""
        own_snip = own[:1200]
        parts.append("CONTENT: " + own_snip)

        # neighbor snippets
        if i > 0:
            prev = chunks[i - 1].get("content", "")[:400]
            if prev:
                parts.append("PREV: " + prev)
        if i + 1 < len(chunks):
            nxt = chunks[i + 1].get("content", "")[:400]
            if nxt:
                parts.append("NEXT: " + nxt)

        ctx = "\n\n".join(parts)
        if len(ctx) > max_len:
            ctx = ctx[: max_len - 3] + "..."
        chunk["contextual_content"] = ctx


def get_database_connection(database_url: str | None = None):
    """Return a psycopg2 connection for EMBEDDING_DATABASE_URL or a sync DATABASE_URL."""
    url = database_url or os.environ.get("EMBEDDING_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "EMBEDDING_DATABASE_URL is required for real DB writes."
        )
    if url.startswith("postgresql+asyncpg://"):
        raise RuntimeError(
            "DATABASE_URL uses postgresql+asyncpg://, which is async-only and cannot be used with psycopg2. "
            "Set EMBEDDING_DATABASE_URL to a synchronous postgresql:// URL."
        )
    conn = psycopg2.connect(url)
    register_vector(conn)
    return conn


def generate_embeddings_placeholder(model_name: str, contents: List[str]) -> List[List[float]]:
    """Generate embeddings using SentenceTransformer and verify dimension."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    embs = model.encode(contents, batch_size=16, normalize_embeddings=True)
    if any(len(vec) != EMBEDDING_DIMENSION for vec in embs):
        raise ValueError(
            f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSION}, got {[len(vec) for vec in embs][:5]}..."
        )
    return embs.tolist()


def upsert_documents(cursor, documents: Dict[str, dict]) -> int:
    sql = """
        INSERT INTO documents (id, category, subcategory, title, raw_json)
        VALUES (%(id)s, %(category)s, %(subcategory)s, %(title)s, %(raw_json)s)
        ON CONFLICT (id) DO UPDATE SET
            category = EXCLUDED.category,
            subcategory = EXCLUDED.subcategory,
            title = EXCLUDED.title,
            raw_json = EXCLUDED.raw_json;
    """
    rows = [
        {
            "id": doc["id"],
            "category": doc["category"],
            "subcategory": doc["subcategory"],
            "title": doc["title"],
            "raw_json": Json(doc["raw_json"]),
        }
        for doc in documents.values()
    ]
    cursor.executemany(sql, rows)
    return len(rows)


def upsert_chunks(cursor, chunks: List[dict]) -> int:
    sql = """
        INSERT INTO chunks (
            chunk_id,
            doc_id,
            category,
            subcategory,
            title,
            section,
            content,
            contextual_content,
            embedding
        )
        VALUES (
            %(chunk_id)s,
            %(doc_id)s,
            %(category)s,
            %(subcategory)s,
            %(title)s,
            %(section)s,
            %(content)s,
            %(contextual_content)s,
            %(embedding)s
        )
        ON CONFLICT (chunk_id) DO UPDATE SET
            doc_id = EXCLUDED.doc_id,
            category = EXCLUDED.category,
            subcategory = EXCLUDED.subcategory,
            title = EXCLUDED.title,
            section = EXCLUDED.section,
            content = EXCLUDED.content,
            contextual_content = EXCLUDED.contextual_content,
            embedding = EXCLUDED.embedding;
    """
    rows = []
    for chunk in chunks:
        if chunk.get("embedding") is None:
            raise ValueError(f"Chunk {chunk['chunk_id']} missing embedding")
        if len(chunk["embedding"]) != EMBEDDING_DIMENSION:
            raise ValueError(
                f"Embedding dimension mismatch for {chunk['chunk_id']}: "
                f"expected {EMBEDDING_DIMENSION}, got {len(chunk['embedding'])}"
            )
        rows.append(
            {
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "category": chunk["category"],
                "subcategory": chunk["subcategory"],
                "title": chunk["title"],
                "section": chunk["section"],
                "content": chunk["content"],
                "contextual_content": chunk["contextual_content"],
                "embedding": chunk["embedding"],
            }
        )
    cursor.executemany(sql, rows)
    return len(rows)


def validate_db_counts(cursor) -> Dict[str, Any]:
    counts = {}
    cursor.execute("SELECT COUNT(*) FROM documents;")
    counts["final_documents_count"] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM chunks;")
    counts["final_chunks_count"] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NULL;")
    counts["null_embedding_count"] = cursor.fetchone()[0]
    cursor.execute("SELECT vector_dims(embedding), COUNT(*) FROM chunks GROUP BY vector_dims(embedding);")
    counts["vector_dims_counts"] = cursor.fetchall()
    return counts


def dry_run_report(
    documents: Dict[str, dict], chunks: List[dict]
) -> Dict[str, Any]:
    """Return a report dict describing planned changes without writing to DB."""
    report: Dict[str, Any] = {}
    report["documents_to_create"] = len(documents)
    report["chunks_to_create"] = len(chunks)

    # missing raw_json
    missing_raw = [d for d in documents.values() if not d.get("raw_json")]
    report["missing_raw_json_count"] = len(missing_raw)

    # duplicate ids
    doc_ids = [d["id"] for d in documents.values()]
    dup_docs = {x for x in doc_ids if doc_ids.count(x) > 1}
    report["duplicate_doc_ids"] = list(dup_docs)

    chunk_ids = [c["chunk_id"] for c in chunks]
    dup_chunks = {x for x in chunk_ids if chunk_ids.count(x) > 1}
    report["duplicate_chunk_ids"] = list(dup_chunks)

    # subcategory uniqueness risk: multiple documents sharing same subcategory
    subcat_map = {}
    for d in documents.values():
        sub = d.get("subcategory")
        if not sub:
            continue
        subcat_map.setdefault(sub, []).append(d["id"]) 
    risky = {k: v for k, v in subcat_map.items() if len(v) > 1}
    report["subcategory_conflicts"] = risky

    # DB env validation: report presence and async/sync form
    emb_db = os.environ.get("EMBEDDING_DATABASE_URL")
    db_url = os.environ.get("DATABASE_URL")
    db_info = {
        "EMBEDDING_DATABASE_URL": bool(emb_db),
        "DATABASE_URL_present": bool(db_url),
        "DATABASE_URL_async_format": bool(db_url and db_url.startswith("postgresql+asyncpg://")),
    }
    report["db_env"] = db_info

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare upsert of cleaned RAG chunks into backend `documents` and `chunks` models. "
            "By default the script runs in dry-run mode and will NOT connect to the database."
        )
    )
    parser.add_argument("--chunks-path", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--dry-run", action="store_true", default=True, help="Do not write to DB; print report.")
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false", help="Enable real DB write mode.")
    parser.add_argument("--confirm-write", action="store_true", help="Confirm that database writes are intended.")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of chunks processed (0 = all).")
    parser.add_argument("--generate-embeddings", action="store_true", help="Compute embeddings for chunks when writing to DB.")
    parser.add_argument("--embedding-model", default=DEFAULT_MODEL_NAME)
    args = parser.parse_args()

    raw_chunks = read_jsonl(args.chunks_path)
    if args.limit and args.limit > 0:
        raw_chunks = raw_chunks[: args.limit]

    documents, chunk_records = build_documents_and_chunks(raw_chunks)

    # attach contextual_content per doc
    # group chunk_records by doc_id preserving original order
    from collections import defaultdict

    grouped = defaultdict(list)
    for c in chunk_records:
        grouped[c["doc_id"]].append(c)

    for doc_id, chunks in grouped.items():
        # ensure sorted by order index
        chunks.sort(key=lambda x: x.get("__order_idx", 0))
        build_contextual_content_for_doc(chunks)

    # flatten back to list
    chunk_records = [c for doc in grouped.values() for c in doc]

    # prepare dry-run report
    report = dry_run_report(documents, chunk_records)

    # print a concise report
    print("Dry-run report:" )
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.dry_run:
        print("Dry-run report:")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    if not args.confirm_write:
        raise RuntimeError("Refusing to write to database without --confirm-write")
    if not args.generate_embeddings:
        raise RuntimeError("Real write mode requires --generate-embeddings")

    contents = [c["contextual_content"] for c in chunk_records]
    print("Generating embeddings for chunks using contextual_content...")
    embeddings = generate_embeddings_placeholder(args.embedding_model, contents)
    for chunk, emb in zip(chunk_records, embeddings):
        chunk["embedding"] = emb

    connection = get_database_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                docs_upserted = upsert_documents(cursor, documents)
                chunks_upserted = upsert_chunks(cursor, chunk_records)

                counts = validate_db_counts(cursor)

        print("Load summary:")
        print(json.dumps(
            {
                "documents_upserted": docs_upserted,
                "chunks_upserted": chunks_upserted,
                "embedding_dim": EMBEDDING_DIMENSION,
                "model_name": args.embedding_model,
                "db_url_used": os.environ.get("EMBEDDING_DATABASE_URL") or os.environ.get("DATABASE_URL"),
                **counts,
            },
            indent=2,
            ensure_ascii=False,
        ))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
