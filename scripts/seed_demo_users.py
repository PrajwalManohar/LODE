"""Seed 10 demo users + a spread of bookings into Supabase.

Idempotent: re-running it does not duplicate users or bookings. Use this to
populate a fresh Supabase project for a presentation or to repopulate after
clearing the tables.

    python scripts/seed_demo_users.py            # create users + bookings
    python scripts/seed_demo_users.py --wipe     # delete demo bookings first
    python scripts/seed_demo_users.py --print    # just print the credential table

Reads SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY + DATABASE_URL from .env.
Writes a CREDENTIALS_DEMO.md (gitignored) with the email/password table.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

# Make project root importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vein.config import settings  # noqa: E402
from vein.db.database import get_conn, init_db  # noqa: E402

# A shared simple password is fine for a demo — flagged as demo-only in the
# credentials file and in COMPLIANCE.md. Never use this pattern in production.
DEMO_PASSWORD = "LodeDemo2026!"

PERSONAS: list[dict[str, Any]] = [
    {
        "email": "lfischer@demo.mines.edu", "full_name": "Dr. Lena Fischer",
        "research_group": "Hydrogen Embrittlement Lab",
        "trained_instruments": ["SEM-Operator"],
        "primary_instrument": "sem-jeol",
    },
    {
        "email": "panand@demo.mines.edu", "full_name": "Dr. Priya Anand",
        "research_group": "Trace Geochemistry",
        "trained_instruments": ["ICP-MS-Cert"],
        "primary_instrument": "icp-ms",
    },
    {
        "email": "mrivera@demo.mines.edu", "full_name": "Marcus Rivera",
        "research_group": "Geology — Cu/Fe Sulfides",
        "trained_instruments": ["XRD-Safety-101"],
        "primary_instrument": "xrd-d8",
    },
    {
        "email": "achen@demo.mines.edu", "full_name": "Alice Chen",
        "research_group": "Steel Failure Analysis",
        "trained_instruments": ["SEM-Operator", "XRD-Safety-101"],
        "primary_instrument": "sem-jeol",
    },
    {
        "email": "jokonkwo@demo.mines.edu", "full_name": "Jane Okonkwo",
        "research_group": "Hydrogeology & Mine Drainage",
        "trained_instruments": ["ICP-MS-Cert"],
        "primary_instrument": "icp-ms",
    },
    {
        "email": "spatel@demo.mines.edu", "full_name": "Sanjay Patel",
        "research_group": "High-Strength Steels",
        "trained_instruments": ["XRD-Safety-101", "SEM-Operator"],
        "primary_instrument": "xrd-d8",
    },
    {
        "email": "mthompson@demo.mines.edu", "full_name": "Mark Thompson",
        "research_group": "Hydrogen Embrittlement Lab",
        "trained_instruments": ["SEM-Operator"],
        "primary_instrument": "sem-jeol",
    },
    {
        "email": "schen@demo.mines.edu", "full_name": "Dr. Sarah Chen",
        "research_group": "Surface Chemistry",
        "trained_instruments": ["XPS-Operator"],
        "primary_instrument": "xps-kratos",
    },
    {
        "email": "rmartinez@demo.mines.edu", "full_name": "Rita Martinez",
        "research_group": "Mining & Geochemistry",
        "trained_instruments": ["XRD-Safety-101", "ICP-MS-Cert"],
        "primary_instrument": "icp-ms",
    },
    {
        "email": "knakamura@demo.mines.edu", "full_name": "Kenji Nakamura",
        "research_group": "Mechanical Testing",
        "trained_instruments": ["RockMech-Basic", "Gleeble-Safety"],
        "primary_instrument": "rock-mech",
    },
]

# 3 bookings per user × 10 users = 30 bookings. Offsets are in days from "now".
# Past bookings exercise the analytics; today/near exercises the dashboard;
# future bookings exercise My Requests and the slot picker.
BOOKING_OFFSETS = [-9, +2, +14]  # days

# Optional secondary instruments to spread bookings across more locations.
# Maps a research_group keyword --> secondary instrument id. Picked when the
# user has multiple trained instruments or a generic match.
SECONDARY_INSTRUMENT = {
    "Hydrogen Embrittlement Lab": "xrd-d8",
    "Trace Geochemistry": "ms-orbitrap",
    "Geology — Cu/Fe Sulfides": "raman-witec",
    "Steel Failure Analysis": "tem-talos",
    "Hydrogeology & Mine Drainage": "icp-ms",
    "High-Strength Steels": "sem-jeol",
    "Surface Chemistry": "afm-asylum",
    "Mining & Geochemistry": "xrd-empyrean",
    "Mechanical Testing": "gleeble-3500",
}


def _admin_headers() -> dict[str, str]:
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


def _find_user_by_email(client: httpx.Client, email: str) -> dict | None:
    # Supabase admin list-users endpoint supports a `filter` query (best-effort
    # — it filters by email prefix). We fetch all and match to be safe.
    r = client.get(
        f"{settings.supabase_url}/auth/v1/admin/users",
        headers=_admin_headers(),
        params={"per_page": 200},
        timeout=30,
    )
    r.raise_for_status()
    for u in r.json().get("users", []):
        if (u.get("email") or "").lower() == email.lower():
            return u
    return None


def _create_user(client: httpx.Client, persona: dict[str, Any]) -> dict:
    body = {
        "email": persona["email"],
        "password": DEMO_PASSWORD,
        "email_confirm": True,
        "user_metadata": {
            "full_name": persona["full_name"],
            "research_group": persona["research_group"],
        },
    }
    r = client.post(
        f"{settings.supabase_url}/auth/v1/admin/users",
        headers=_admin_headers(),
        json=body,
        timeout=30,
    )
    if r.status_code in (200, 201):
        return r.json()
    # 422 / 409 --> already exists; fall back to lookup
    existing = _find_user_by_email(client, persona["email"])
    if existing:
        return existing
    raise RuntimeError(f"create_user failed for {persona['email']}: {r.status_code} {r.text[:200]}")


def _experiment_context(persona: dict[str, Any], instr_id: str) -> dict[str, Any]:
    # Lightweight context tuned to the instrument so the fit-score story stays
    # consistent. Keep it minimal — the real chat-driven context is richer.
    base = {
        "researcher_name": persona["full_name"],
        "researcher_email": persona["email"],
        "research_group": persona["research_group"],
        "trained_instruments": persona["trained_instruments"],
        "urgency": "medium",
        "is_complete": True,
        "clarifying_questions": [],
        "hazardous_materials": [],
        "hazmat_review_required": False,
    }
    by_instr = {
        "sem-jeol":    {"material_type": "martensitic steel",       "analysis_goal": "fracture surface morphology"},
        "xrd-d8":      {"material_type": "chalcopyrite ore powder", "analysis_goal": "phase identification"},
        "icp-ms":      {"material_type": "mine drainage water",     "analysis_goal": "trace metal quantification"},
        "rock-mech":   {"material_type": "sandstone core",          "analysis_goal": "compressive strength"},
        "tube-furnace":{"material_type": "ceramic powder",          "analysis_goal": "sintering schedule"},
        "tem-talos":   {"material_type": "thin foil steel",         "analysis_goal": "dislocation microstructure"},
        "fib-helios":  {"material_type": "steel coupon",             "analysis_goal": "cross-section preparation"},
        "xrd-empyrean":{"material_type": "polycrystalline ceramic", "analysis_goal": "phase analysis"},
        "raman-witec": {"material_type": "carbon film",              "analysis_goal": "graphitic Raman signature"},
        "afm-asylum":  {"material_type": "polymer thin film",        "analysis_goal": "surface roughness mapping"},
        "xps-kratos":  {"material_type": "oxidized alloy",           "analysis_goal": "oxidation state / binding energy"},
        "xct-versa":   {"material_type": "rock core",                "analysis_goal": "3D porosity mapping"},
        "apt-leap":    {"material_type": "steel needle",             "analysis_goal": "atomic-scale composition"},
        "ms-orbitrap": {"material_type": "water sample",             "analysis_goal": "high-resolution mass spectrometry"},
        "gleeble-3500":{"material_type": "steel rod",                "analysis_goal": "thermomechanical simulation"},
    }
    base.update(by_instr.get(instr_id, {"material_type": "sample", "analysis_goal": "characterization"}))
    return base


def upsert_users(client: httpx.Client) -> list[dict[str, Any]]:
    out = []
    for persona in PERSONAS:
        user = _create_user(client, persona)
        out.append({**persona, "id": user["id"]})
        print(f"  [ok]{persona['email']:<32} {persona['full_name']}")
    return out


def update_profile_trainings(users: list[dict[str, Any]]) -> None:
    with get_conn() as conn:
        for u in users:
            conn.execute(
                "UPDATE profiles SET trained_instruments = %s, full_name = %s, research_group = %s "
                "WHERE id = %s",
                (u["trained_instruments"], u["full_name"], u["research_group"], u["id"]),
            )


def wipe_demo_bookings() -> int:
    with get_conn() as conn:
        n = conn.execute(
            "DELETE FROM bookings WHERE researcher_email LIKE %s RETURNING id",
            ("%@demo.mines.edu",),
        ).fetchall()
        return len(n)


def insert_bookings(users: list[dict[str, Any]]) -> int:
    import json as _json
    inserted = 0
    now = datetime.now()
    with get_conn() as conn:
        # Pre-check to keep idempotent: if this user already has >=3 demo
        # bookings, skip them.
        for u in users:
            existing = conn.execute(
                "SELECT COUNT(*) AS n FROM bookings WHERE researcher_email = %s",
                (u["email"],),
            ).fetchone()["n"]
            if existing and existing >= len(BOOKING_OFFSETS):
                continue

            instrs = [u["primary_instrument"]]
            secondary = SECONDARY_INSTRUMENT.get(u["research_group"])
            if secondary and secondary != u["primary_instrument"]:
                instrs.append(secondary)

            for i, day_offset in enumerate(BOOKING_OFFSETS):
                instr = instrs[i % len(instrs)]
                start = (now + timedelta(days=day_offset)).replace(
                    hour=9 + (i * 2) % 8, minute=0, second=0, microsecond=0
                )
                end = start + timedelta(hours=2)
                ctx = _experiment_context(u, instr)
                conn.execute(
                    """INSERT INTO bookings
                       (instrument_id, user_id, researcher_name, researcher_email,
                        start_time, end_time, status, experiment_context)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)""",
                    (instr, u["id"], u["full_name"], u["email"], start, end,
                     "confirmed", _json.dumps(ctx)),
                )
                inserted += 1
    return inserted


def write_credentials_md(users: list[dict[str, Any]]) -> Path:
    path = Path(__file__).resolve().parent.parent / "CREDENTIALS_DEMO.md"
    rows = [
        "| # | Name | Email | Password | Research group | Trained on |",
        "|---|------|-------|----------|----------------|------------|",
    ]
    for i, u in enumerate(users, 1):
        rows.append(
            f"| {i} | {u['full_name']} | `{u['email']}` | `{DEMO_PASSWORD}` | "
            f"{u['research_group']} | {', '.join(u['trained_instruments'])} |"
        )
    body = (
        "# LODE — Demo User Credentials\n\n"
        "Generated by `scripts/seed_demo_users.py`. **Demo-only — never reuse this "
        "pattern in production.** All ten users share a single password.\n\n"
        f"Shared password: `{DEMO_PASSWORD}`\n\n"
        + "\n".join(rows)
        + "\n\nFirst user created via this script will land as `user` role. The "
          "`profiles.handle_new_user` trigger promotes only the very first auth "
          "row in the project to `admin`. To make one of these users admin, run:\n\n"
          "```sql\nupdate public.profiles set role = 'admin' "
          "where email = 'lfischer@demo.mines.edu';\n```\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wipe", action="store_true", help="Delete existing @demo.mines.edu bookings first")
    ap.add_argument("--print", dest="print_only", action="store_true", help="Just print the credentials")
    args = ap.parse_args()

    if not settings.supabase_url or not settings.supabase_service_role_key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env", file=sys.stderr)
        return 2

    if args.print_only:
        for p in PERSONAS:
            print(f"{p['email']:<32} {DEMO_PASSWORD}  {p['full_name']}")
        return 0

    init_db()
    if args.wipe:
        n = wipe_demo_bookings()
        print(f"  [ok]wiped {n} demo booking(s)")

    print("--> Creating / fetching auth users …")
    with httpx.Client() as client:
        users = upsert_users(client)

    print("--> Updating profile rows with trainings …")
    update_profile_trainings(users)

    print("--> Inserting bookings …")
    n = insert_bookings(users)
    print(f"  [ok]inserted {n} new booking(s)")

    path = write_credentials_md(users)
    print(f"\n[done] Credentials written to {path}")
    print(f"   Shared password for ALL demo users: {DEMO_PASSWORD}\n")
    for u in users:
        print(f"   {u['email']:<32} {u['full_name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
