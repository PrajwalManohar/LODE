"""Demo helper: run a free-text question through the RAG retriever and print the
top-k chunks with their cosine similarity — exactly what the agents receive.

    .\.venv\Scripts\python.exe scripts\rag_query.py "how do I image a fracture surface on steel?"
    .\.venv\Scripts\python.exe scripts\rag_query.py "trace metals in mine water" --k 3
    .\.venv\Scripts\python.exe scripts\rag_query.py "phase identification" --instrument xrd-d8

This embeds the query with the same model the index uses (all-MiniLM-L6-v2,
384-dim) and calls the match_documents() cosine search in Supabase/pgvector.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vein.rag.indexer import query_corpus  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="The question / text to retrieve against")
    ap.add_argument("--k", type=int, default=5, help="How many chunks to return")
    ap.add_argument("--instrument", default=None, help="Filter to an instrument_id (e.g. xrd-d8)")
    ap.add_argument("--corpus", default=None, help="Filter to a corpus_type (manual/sop/...)")
    args = ap.parse_args()

    rows = query_corpus(args.query, n_results=args.k,
                        instrument_id=args.instrument, corpus_type=args.corpus)

    print(f'\nQuery: "{args.query}"')
    print(f"Top {len(rows)} chunks by cosine similarity:\n")
    for i, r in enumerate(rows, 1):
        sim = 1.0 - r["distance"]
        bar = "#" * int(round(sim * 30))
        print(f"{i}. similarity={sim:.4f}  {bar}")
        print(f"   source : {r['source']}  ({r['corpus_type']} / {r['instrument_id'] or 'general'})")
        print(f"   section: {r['section']}")
        txt = r["text"].replace("\n", " ")
        print(f"   text   : {txt[:240]}{'...' if len(txt) > 240 else ''}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
