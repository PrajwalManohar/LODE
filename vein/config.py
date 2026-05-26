from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CHROMA_DIR = DATA_DIR / "chroma"
MANUALS_DIR = DATA_DIR / "corpus" / "manuals"
SOPS_DIR = DATA_DIR / "corpus" / "sops"
OUTPUT_DIR = DATA_DIR / "output" / "sops"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    google_api_key: str = ""
    google_model: str = "gemini-3.5-flash"
    # "google" | "anthropic" | "auto" (prefer google, fall back to anthropic).
    llm_provider: str = "auto"
    embedding_model: str = "all-MiniLM-L6-v2"
    fit_score_threshold: int = 40
    demo_mode: bool = False  # Use rule-based fallbacks when no API key

    airtable_api_key: str = ""
    airtable_base_id: str = ""
    sendgrid_api_key: str = ""
    resend_api_key: str = ""
    resend_from: str = "LODE <onboarding@resend.dev>"  # verified domain in prod; test sender works out of the box
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    lab_email_from: str = "lode@mines.edu"
    lab_email_tech: str = "labtech@mines.edu"      # lab manager / tech
    lab_email_facilities: str = "facilities@mines.edu"
    lab_email_chair: str = "chair@mines.edu"        # department chair (monthly report)
    # Demo: force every outgoing email to this address (Resend test mode only
    # delivers to the account owner). Leave blank in production once a domain is
    # verified. The originally-intended recipients are shown in the email body.
    email_override: str = ""

    # --- Supabase (Phase 1 onward) -----------------------------------------
    # Frontend uses the anon key; the backend uses the service-role key for
    # trusted server writes (bypasses RLS by design). database_url is the
    # Postgres connection string used by Phase 2's data-layer port.
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""  # Settings → API → JWT Secret; verifies request tokens
    database_url: str = ""         # postgresql://...:6543/postgres (pooled)

    # IANA timezone name (e.g. "America/Denver"). Empty = detect from the
    # system. Used to:
    #   • SET the Postgres session timezone so naive datetimes round-trip
    #     correctly (no more bookings stored as UTC then displayed as UTC).
    #   • Generate "Mon, May 29 · 9:00 AM MDT" strings in emails / SOP.
    lode_timezone: str = ""

    @property
    def supabase_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)


settings = Settings()


def _detect_local_tz() -> str:
    """Return an IANA timezone name. Honors LODE_TZ → tzlocal lookup → UTC."""
    if settings.lode_timezone:
        return settings.lode_timezone
    try:
        from tzlocal import get_localzone_name

        return get_localzone_name() or "UTC"
    except Exception:
        # Fall back to ZoneInfo-friendly default if tzlocal isn't available.
        try:
            from datetime import datetime as _dt

            tz = _dt.now().astimezone().tzinfo
            return getattr(tz, "key", None) or str(tz) or "UTC"
        except Exception:
            return "UTC"


LOCAL_TZ_NAME: str = _detect_local_tz()


def local_now():
    """Naive ``datetime.now()`` in the configured local timezone.

    Returns a *naive* datetime (no tzinfo) so it remains compatible with the
    rest of the codebase, which compares naive datetimes from Postgres
    ``timestamptz`` columns (stripped of tzinfo in ``row_to_dict``).
    """
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(tz=ZoneInfo(LOCAL_TZ_NAME)).replace(tzinfo=None)
    except Exception:
        from datetime import datetime as _dt

        return _dt.now()


def local_tz_label() -> str:
    """Short timezone abbreviation (e.g. "MDT") for display in emails."""
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime

        return datetime.now(tz=ZoneInfo(LOCAL_TZ_NAME)).strftime("%Z") or LOCAL_TZ_NAME
    except Exception:
        import time

        return time.tzname[time.daylight] if time.daylight else time.tzname[0]


def ensure_dirs() -> None:
    for d in (DATA_DIR, CHROMA_DIR, MANUALS_DIR, SOPS_DIR, OUTPUT_DIR):
        d.mkdir(parents=True, exist_ok=True)
