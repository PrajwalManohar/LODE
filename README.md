# LODE — Lab Operations & Data Engine

Agentic lab scheduling and research co-pilot for the **Colorado School of Mines**
Shared Instrumentation Facility. Conversational intake, RAG-grounded instrument
fit scoring, safety gate, custom SOP generation, post-run analysis, and a full
HITL automation surface — all with manual citations on every agent decision.

## Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 18, TypeScript, Vite, Tailwind, TanStack Query, Recharts, lucide-react |
| **Backend** | FastAPI, Pydantic v2, APScheduler (monthly cron) |
| **Agents** | 5-agent LangGraph pipeline (Context → Fit → Schedule → SOP → Post-run) + Safety Gate |
| **RAG** | ChromaDB + sentence-transformers (`all-MiniLM-L6-v2`) |
| **Data** | Supabase Postgres (`timestamptz`, RLS) + pgvector; psycopg connection pool |
| **Auth / Realtime** | Supabase Auth + Postgres change feed (`supabase-js`) |
| **Email** | Resend → SendGrid → SMTP → local outbox (auto-failover) |
| **LLM (optional)** | Anthropic Claude via `ANTHROPIC_API_KEY`; rule-based fallback otherwise |

## Quick start

```powershell
# Backend (Window 1)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env       # then fill in DATABASE_URL + SUPABASE_* keys
uvicorn backend.main:app --port 8000

# Frontend (Window 2)
cd frontend
copy .env.example .env       # set VITE_SUPABASE_URL + VITE_SUPABASE_ANON_KEY
npm install
npm run dev
```

Open **http://127.0.0.1:5173** and sign in.

## Features

- **Conversational intake** — Agent 1 parses the experiment; asks clarifying
  questions when fields are missing.
- **Instrument fit scoring** — Agent 2 ranks the 5 lab instruments with grades,
  rationale, and lavender RAG citation pills.
- **Smart scheduler** — Agent 3 proposes 3 conflict-free slots with warm-up and
  prep time baked in.
- **Safety gate** — Hard refusal rules (training cert, hazmat keywords,
  calibration overdue, fit confidence < 80%) enforced architecturally.
- **Custom SOPs** — Agent 4 generates a cited `.docx` per booking via
  `python-docx`.
- **Post-run analyzer** — Agent 5 logs the run, re-indexes ChromaDB, and opens
  a critical work order when anomalies are detected.
- **Four automation emails** (all fire from real triggers, no demo script
  required):

  | # | Color | Trigger | Recipients |
  |---|---|---|---|
  | 1 | Navy | Successful booking confirm | Researcher + lab tech |
  | 2 | Brown | Safety gate refusal (training / hazmat / calibration / confidence) | Lab manager |
  | 3 | Purple | Post-run anomaly or calibration overdue | Lab manager + facilities |
  | 4 | Green | APScheduler cron — 1st of month, 7 AM local | Department chair + lab manager |

- **HITL queue** — `/governance` shows pending requests; **Approve / Deny**
  buttons in the brown email link straight to `?hitl=<id>&action=…` and flip
  state in one click.
- **Analytics & governance** — KPI tiles, instrument utilization, booking
  equity (>40% flag), maintenance with severity + status + instrument filters
  + search, automation activity feed, email transport mix.
- **Profile** — `/profile` shows the signed-in user's identity, training
  certifications, and a prominent sign-out button.

## API surface

```
GET    /api/health
GET    /api/status
POST   /api/chat/intake
POST   /api/chat/confirm
GET    /api/instruments
GET    /api/bookings
GET    /api/bookings/utilization
POST   /api/postrun
GET    /api/admin/rag                   (chunks, docs, last-update)
POST   /api/admin/rag/reindex
GET    /api/admin/audit                 (agent decisions)
GET    /api/admin/equity?weeks=N        (booking concentration by group)
GET    /api/admin/work-orders[?status=]
POST   /api/admin/work-orders/{id}/status
GET    /api/admin/automations[?kind=]
GET    /api/admin/hitl[?status=]
POST   /api/admin/hitl/{event_id}/approve
POST   /api/admin/hitl/{event_id}/deny
POST   /api/admin/reports/monthly/send[?to=]
```

## Project structure

```
backend/                FastAPI app + routers
  routers/              chat, bookings, instruments, postrun, admin, system
  main.py               lifespan: bootstrap + APScheduler monthly cron

vein/                   Core library
  agents/               LangGraph pipeline, safety gate, scoring
  rag/                  Chunking + Chroma indexer
  services/             Email (4 templates), SOP docx, work order, Airtable
  db/                   psycopg pool, schema helpers, seed
  config.py             Settings (timezone-aware) + LOCAL_TZ helpers
  bootstrap.py          One-shot startup wiring

frontend/               React + Vite UI
  src/pages/            Login, Dashboard, IntakeChat, FitResults,
                        Bookings, Instruments, PostRun, Profile,
                        Governance, Admin
  src/components/       Layout, PageShell, Citations, StatusBanner
  src/lib/              api.ts, auth.tsx, supabase.ts, useRealtime.ts

scripts/                demo_emails.py, api_e2e.py, smoke_test*.py,
                        apply_migration.py, check_*.py

supabase/               SQL migrations + setup

data/                   Curated corpus (manuals/, sops/) — runtime
                        artifacts (chroma/, output/, outbox) are gitignored
ui_mocks/               Design reference PNGs
DEMO_SCENARIOS.md       Walkthrough for the 4 automation emails
.env.example            Canonical config template (LODE_TZ, Supabase, email)
```

## Configuration

All knobs live in `.env` at the repo root (backend) and `frontend/.env`
(Vite). See `.env.example` for the full list. Highlights:

- `DATABASE_URL` — pooled Postgres connection (Supabase Settings → Database).
- `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` /
  `SUPABASE_JWT_SECRET` — auth + service writes + JWT verification.
- `LODE_TZ` — IANA zone for the scheduler, emails, and ICS files. Empty =
  auto-detect from the system clock. Aligns the Postgres session timezone so
  naive `datetime.now()` inserts round-trip with the correct wall-clock time.
- `RESEND_API_KEY` (preferred) → `SENDGRID_API_KEY` → SMTP — first one set
  wins. Without any, emails go to `data/email_outbox/outbox.jsonl`.
- `ANTHROPIC_API_KEY` — optional. Without it, agents use rule-based parsing
  on the seeded Mines corpus (demo mode).

## Demo prompt

The canonical SEM-EDS intake message (exercises Agent 1 → 2 → 3 → safety
gate → Agent 4 + all three automations):

> I'm running hydrogen permeation tests on martensitic steel specimens. I
> need to characterize the fracture surface morphology. My samples are about
> 5mm × 5mm and they haven't been coated. I need results by Thursday for my
> advisor meeting.

Clearing the **Training** field on the intake form will exercise the
**brown HITL email**. Pasting `concentrated hydrofluoric acid` anywhere in
the message exercises the **hazmat HITL email**. Posting a post-run report
with `Detector saturation on consecutive scans at 40 mA tube current` in the
Anomalies field exercises the **purple work-order email**. Clicking
**Send monthly report** in the Analytics header fires the **green** one.

For a fast standalone demo of all four colors without the UI:

```powershell
python scripts\demo_emails.py all --to you@yourdomain.com
```
