"""Apply a SQL migration file to the Supabase Postgres (via DATABASE_URL).

Usage:  .\.venv\Scripts\python.exe scripts\apply_migration.py supabase\migrations\0005_automation_events.sql
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg

from vein.config import settings


def main(path: str) -> int:
    sql = Path(path).read_text(encoding="utf-8")
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute(sql)
    print(f"applied: {path}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: apply_migration.py <path-to.sql>")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
