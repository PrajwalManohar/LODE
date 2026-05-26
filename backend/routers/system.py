from fastapi import APIRouter

from vein.agents.llm import has_llm
from vein.bootstrap import bootstrap
from vein.config import settings
from vein.db.database import get_instruments, get_rag_stats

router = APIRouter()


@router.get("/status")
def platform_status():
    instruments = get_instruments()
    rag = get_rag_stats()
    return {
        "version": "2.0.0",
        "demo_mode": not has_llm(),
        "llm_configured": has_llm(),
        "instruments_count": len(instruments),
        "rag_chunks": rag.get("total_chunks", 0),
        "rag_last_update": rag.get("last_update"),
        "fit_threshold": settings.fit_score_threshold,
    }


@router.post("/bootstrap")
def run_bootstrap(reindex: bool = False):
    return bootstrap(reindex=reindex)


@router.get("/notifications")
def notifications():
    """Campus & facility feed (CSM news, circulars, facts, research) + an
    AI-generated daily digest. Visible to all signed-in users."""
    from vein.services.notifications import get_feed

    return get_feed()
