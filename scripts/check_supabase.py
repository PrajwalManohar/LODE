"""Supabase connectivity check for LODE.

Verifies, from the values in .env:
  1. PostgREST (URL + service_role key) and that core tables exist.
  2. Direct Postgres connection via DATABASE_URL (session pooler).
  3. pgvector extension + match_documents() function are installed.

Run:  .\.venv\Scripts\python.exe scripts\check_supabase.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from vein.config import settings

TABLES = ["instruments", "profiles", "documents", "bookings", "work_orders", "agent_decisions"]


def check_rest() -> bool:
    print("== PostgREST (URL + service_role) ==")
    if not settings.supabase_url or not settings.supabase_service_role_key:
        print("  SKIP: SUPABASE_URL / SERVICE_ROLE_KEY not set")
        return False
    h = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }
    ok = True
    for t in TABLES:
        try:
            r = httpx.get(
                f"{settings.supabase_url}/rest/v1/{t}",
                params={"select": "*", "limit": 1},
                headers=h,
                timeout=20,
            )
            flag = "OK " if r.status_code == 200 else "ERR"
            if r.status_code != 200:
                ok = False
            print(f"  {flag} {t:16} {r.status_code} {r.text[:60]}")
        except Exception as exc:  # noqa: BLE001
            ok = False
            print(f"  ERR {t:16} {exc}")
    return ok


def check_postgres() -> bool:
    print("== Direct Postgres (DATABASE_URL) ==")
    if not settings.database_url:
        print("  SKIP: DATABASE_URL not set")
        return False
    try:
        import psycopg
    except ImportError:
        print("  ERR: psycopg not installed")
        return False
    try:
        with psycopg.connect(settings.database_url, connect_timeout=20) as conn:
            cur = conn.cursor()
            cur.execute("select 1")
            print("  OK  connect ->", cur.fetchone()[0])
            cur.execute("select count(*) from instruments")
            print("  OK  instruments rows:", cur.fetchone()[0])
            cur.execute("select extname from pg_extension where extname = 'vector'")
            print("  OK  pgvector ext:", cur.fetchone())
            cur.execute("select proname from pg_proc where proname = 'match_documents'")
            print("  OK  match_documents fn:", cur.fetchone())
        return True
    except Exception as exc:  # noqa: BLE001
        print("  ERR:", exc)
        return False


if __name__ == "__main__":
    rest_ok = check_rest()
    pg_ok = check_postgres()
    print()
    print(f"REST: {'PASS' if rest_ok else 'FAIL'}   Postgres: {'PASS' if pg_ok else 'FAIL'}")
    sys.exit(0 if (rest_ok and pg_ok) else 1)
