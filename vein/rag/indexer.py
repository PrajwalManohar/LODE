"""RAG index backed by Supabase Postgres + pgvector.

Embeddings are computed locally with sentence-transformers (all-MiniLM-L6-v2,
384-dim) and stored in the `documents` table. Retrieval calls the
`match_documents()` SQL function (cosine distance). Vectors are passed as
string literals cast to `::vector`, so no special adapter registration is
needed. Public functions (`index_corpus`, `query_corpus`) keep the same
signatures and return shapes as the previous ChromaDB implementation.
"""

from typing import Optional

from vein.config import settings
from vein.db.database import get_conn, upsert_rag_metadata
from vein.rag.corpus import all_corpus_chunks

_model = None


def _embed_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.embedding_model)
    return _model


def _embed(texts: list[str]):
    """Return a 2D ndarray of embeddings for the given texts."""
    return _embed_model().encode(list(texts))


def _vec_literal(vec) -> str:
    values = vec.tolist() if hasattr(vec, "tolist") else list(vec)
    return "[" + ",".join(str(float(x)) for x in values) + "]"


def _count() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"]


def index_corpus(force: bool = False) -> dict:
    existing = _count()
    if existing > 0 and not force:
        return {"indexed": 0, "total": existing, "message": "Corpus already indexed"}

    chunks = all_corpus_chunks()
    embeddings = _embed([c["text"] for c in chunks])

    rows = [
        (
            c["id"],
            c["text"],
            _vec_literal(embeddings[i]),
            c["source"],
            c.get("section", ""),
            str(c.get("page", "")),
            c["corpus_type"],
            c.get("instrument_id", ""),
        )
        for i, c in enumerate(chunks)
    ]

    with get_conn() as conn:
        if force:
            conn.execute("DELETE FROM documents")
            conn.execute("DELETE FROM rag_metadata")
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO documents
                   (id, content, embedding, source, section, page, corpus_type, instrument_id)
                   VALUES (%s, %s, %s::vector, %s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET
                     content = EXCLUDED.content,
                     embedding = EXCLUDED.embedding,
                     source = EXCLUDED.source,
                     section = EXCLUDED.section,
                     page = EXCLUDED.page,
                     corpus_type = EXCLUDED.corpus_type,
                     instrument_id = EXCLUDED.instrument_id""",
                rows,
            )
        total = conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"]

    by_type: dict[str, int] = {}
    for c in chunks:
        by_type[c["corpus_type"]] = by_type.get(c["corpus_type"], 0) + 1
    for ctype, count in by_type.items():
        upsert_rag_metadata(ctype, f"{ctype}_corpus", count)

    return {"indexed": len(chunks), "total": total}


def _match(vec_literal: str, n_results: int, instrument_id: Optional[str], corpus_type: Optional[str]) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM match_documents(%s::vector, %s, %s, %s)",
            (vec_literal, n_results, instrument_id, corpus_type),
        ).fetchall()
    return rows


def query_corpus(
    query_text: str,
    n_results: int = 5,
    instrument_id: Optional[str] = None,
    corpus_type: Optional[str] = None,
) -> list[dict]:
    if _count() == 0:
        index_corpus()

    vec = _vec_literal(_embed([query_text])[0])
    rows = _match(vec, n_results, instrument_id, corpus_type)
    if not rows and (instrument_id or corpus_type):
        rows = _match(vec, n_results, None, None)

    items = []
    for r in rows:
        sim = r.get("similarity") or 0.0
        items.append({
            "text": r["content"],
            "source": r.get("source", "Unknown"),
            "section": r.get("section", "") or "",
            "page": r.get("page", "") or "",
            "corpus_type": r.get("corpus_type", "") or "",
            "instrument_id": r.get("instrument_id", "") or "",
            "distance": 1.0 - sim,
        })
    return items
