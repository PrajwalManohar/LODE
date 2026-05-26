import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from vein.bootstrap import bootstrap
from vein.config import LOCAL_TZ_NAME, OUTPUT_DIR, ensure_dirs

from backend.routers import admin, bookings, chat, instruments, me, postrun, system

logger = logging.getLogger("backend.main")
ensure_dirs()


def _scheduled_monthly_report() -> None:
    """Cron entry point — fires Email 4 on the 1st of every month at 07:00 local."""
    try:
        from backend.routers.admin import send_monthly_report

        out = send_monthly_report()
        logger.info("monthly report dispatched: %s", out)
    except Exception as exc:  # noqa: BLE001
        logger.exception("monthly report cron failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap(reindex=False)
    scheduler = None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BackgroundScheduler(timezone=LOCAL_TZ_NAME)
        scheduler.add_job(
            _scheduled_monthly_report,
            CronTrigger(day=1, hour=7, minute=0),
            id="monthly_report",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("APScheduler started — monthly_report cron registered (%s).", LOCAL_TZ_NAME)
    except Exception as exc:  # noqa: BLE001
        logger.warning("APScheduler not started (%s) — monthly cron disabled.", exc)
    try:
        yield
    finally:
        if scheduler is not None:
            try:
                scheduler.shutdown(wait=False)
            except Exception:  # noqa: BLE001
                pass


app = FastAPI(
    title="VEIN 2.0 API",
    description="Lab Intelligence Platform — Colorado School of Mines",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router, prefix="/api", tags=["system"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(instruments.router, prefix="/api/instruments", tags=["instruments"])
app.include_router(bookings.router, prefix="/api/bookings", tags=["bookings"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(postrun.router, prefix="/api/postrun", tags=["postrun"])
app.include_router(me.router, prefix="/api/me", tags=["me"])

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/api/files/sops", StaticFiles(directory=str(OUTPUT_DIR)), name="sops")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "vein-2.0"}
