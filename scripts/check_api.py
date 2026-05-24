"""In-process API smoke against the real ASGI app (Postgres-backed).

Uses FastAPI TestClient so it runs the app lifespan (bootstrap) and routers
without binding a port or touching a separately running server.

Run:  .\.venv\Scripts\python.exe scripts\check_api.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from backend.main import app


def main() -> int:
    with TestClient(app) as client:
        checks = [
            ("GET /api/health", "/api/health"),
            ("GET /api/status", "/api/status"),
            ("GET /api/instruments", "/api/instruments"),
            ("GET /api/bookings", "/api/bookings"),
            ("GET /api/admin/rag", "/api/admin/rag"),
            ("GET /api/admin/audit", "/api/admin/audit?limit=3"),
            ("GET /api/admin/work-orders", "/api/admin/work-orders"),
            ("GET /api/admin/equity", "/api/admin/equity?weeks=8"),
            ("GET /api/bookings/utilization", "/api/bookings/utilization"),
        ]
        ok = True
        for label, url in checks:
            r = client.get(url)
            body = r.json()
            n = len(body) if isinstance(body, list) else "obj"
            print(f"  {r.status_code}  {label:30} -> {n}")
            if r.status_code != 200:
                ok = False
                print("     ", str(body)[:200])

        print("\n  status payload:")
        print("   ", client.get("/api/status").json())

    print("\nAPI SMOKE", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
