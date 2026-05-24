"""One-shot platform initialization: directories, DB seed, RAG index."""

from vein.config import ensure_dirs
from vein.db.seed import seed_database
from vein.rag.indexer import index_corpus


def bootstrap(reindex: bool = False) -> dict:
    ensure_dirs()
    seed_database()
    rag_result = {"status": "ok", "indexed": 0, "total": 0}
    try:
        rag_result = index_corpus(force=reindex)
        rag_result["status"] = "ok"
    except Exception as exc:
        rag_result = {"status": "deferred", "error": str(exc), "message": "RAG will index on first query"}
    return {"database": "seeded", "rag": rag_result}
