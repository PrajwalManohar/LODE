# LODE — Lab Operations & Data Engine

**An agentic decision layer for a university Shared Instrumentation Facility.**

At a research university, dozens of researchers compete for a handful of expensive
scientific instruments (electron microscopes, X-ray diffractometers, mass
spectrometers). Today that is coordinated by hand over email and spreadsheets — a
coordinator decides which instrument fits each experiment, checks whether the
researcher is trained and the work is safe, finds a slot, and writes a standard
operating procedure manually. It is slow, error-prone, and unauditable.

**LODE replaces that manual loop with a five-agent pipeline plus a hard safety
gate.** A researcher describes their experiment (chat or form); LODE reasons about
the best instrument, proposes conflict-free slots, enforces non-bypassable safety
rules, and — on a clean request — **acts**: it creates the booking, generates a
RAG-cited SOP document and calendar invite, pushes the record to Airtable, and
emails the researcher. When a request is risky, it routes a human-in-the-loop
approval request to a supervisor instead. Built for the **Colorado School of Mines**
Shared Instrumentation Facility (synthetic data throughout).

> **Measurable outcome:** request-to-approved-SOP drops from ~1–2 days to under a
> minute for clean requests; **zero** untrained / unsafe / low-confidence bookings
> reach an instrument without human sign-off; **100%** of decisions carry an
> auditable, citation-grounded record; the department chair gets a monthly
> utilization & equity report with no manual effort.

---

## Table of contents

- [What it does](#what-it-does)
- [How the app works](#how-the-app-works)
- [Project architecture](#project-architecture)
- [Tech stack](#tech-stack)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [API surface](#api-surface)
- [Safety, privacy & governance](#safety-privacy--governance)
- [Evaluation](#evaluation)
- [Project structure](#project-structure)
- [Demo](#demo)

---

## What it does

- **Conversational + form intake** — describe an experiment in natural language or
  via a structured form; both feed the same pipeline.
- **Instrument fit scoring** — ranks 15 seeded Mines instruments with a grade
  (A / B+ / …), rationale, and RAG citation pills.
- **Smart scheduler** — proposes conflict-free slots with sample-prep and warm-up
  time folded in.
- **Safety gate** — four hard, architectural refusal rules (missing training,
  hazardous materials, instrument under maintenance / calibration overdue, fit
  confidence < 80%). Enforced inside the graph and re-checked at confirm time —
  the UI cannot bypass it.
- **Custom SOPs** — generates a cited `.docx` per booking plus an `.ics` invite.
- **Post-run analyzer** — logs the run, re-indexes the knowledge base, and opens a
  critical work order when anomalies are detected.
- **Human-in-the-loop queue** — refused requests become approval tasks routed to
  supervisors; one-click **Approve / Deny** from the dashboard *or* the email.
- **Booking changes** — researchers can request a reschedule or cancellation; both
  go back through the same HITL approval + email loop.
- **Five branded automation emails** (all fire from real triggers):

  | # | Color | Trigger | Recipients |
  |---|---|---|---|
  | 1 | Navy | Successful booking confirm | Researcher + lab tech |
  | 2 | Brown | Safety-gate refusal / change request | Lab manager (all admins) |
  | 3 | Purple | Post-run anomaly or calibration overdue | Lab manager + facilities |
  | 4 | Green | Monthly utilization report (cron, 1st @ 07:00 local) | Chair + lab manager |
  | 5 | Green / Crimson | Change approved (reschedule confirmed / booking removed) | Researcher |

- **Analytics & governance** — KPI tiles, instrument utilization, booking-equity
  flag (>40% of hours by one group), maintenance with severity/status filters, an
  automation activity feed, and the HITL approval queue.
- **Privacy & compliance** — per-user data export, erasure, and audit endpoints
  (GDPR Art. 15/17/20), input/output guardrails, and an append-only redacted audit
  log. See [`COMPLIANCE.md`](COMPLIANCE.md).

---

## How the app works

LODE has **three runtime flows**. The first is the headline path; the other two
are triggered by post-run reports and a monthly cron.

### Flow 1 — Intake → decision → action

```
Researcher (chat msg or form)
        │
        ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Agent 1 · Context        Parse experiment → ExperimentContext.            │
│                           RAG query for citations. Detect hazmat keywords. │
│                           → clarify (missing field) | escalate | advance   │
├──────────────────────────────────────────────────────────────────────────┤
│  Agent 2 · Fit            Score all 15 instruments; pick top + grade.      │
│                           → escalate (nothing above threshold) | advance   │
├──────────────────────────────────────────────────────────────────────────┤
│  Agent 3 · Schedule       Propose 3 conflict-free slots (prep + warm-up).  │
├──────────────────────────────────────────────────────────────────────────┤
│  ⛔ SAFETY GATE           4 hard rules: training · hazmat · maintenance/   │
│     (non-bypassable)      calibration · confidence < 80%.                   │
│                           ┌─ PASS ─────────────► return slots to UI        │
│                           └─ REFUSE ───────────► create HITL request +     │
│                                                  email supervisor + email  │
│                                                  researcher ("pending")    │
└──────────────────────────────────────────────────────────────────────────┘
        │ (PASS) researcher picks a slot and confirms
        ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Agent 4 · Confirm        Re-runs the safety gate, then ACTS:              │
│                           1. create booking row (Postgres)                 │
│                           2. generate cited SOP .docx + .ics invite        │
│                           3. push record to Airtable                       │
│                           4. send navy confirmation email                  │
│                           5. open a work order if calibration is overdue   │
└──────────────────────────────────────────────────────────────────────────┘
```

**The refusal branch (human-in-the-loop):** when the gate refuses, LODE writes a
`hitl_request` row that carries the *full replayable state* (context +
recommendation + chosen slot), emails the supervisor an **Approve / Deny** message
(buttons deep-link to `/governance?hitl=<id>&action=…`), and emails the researcher
that their request is pending. On approval, the researcher confirms from
**My Requests** and the booking *replays through the exact same Agent 4 pipeline*
(with a one-time manager-override marker), so an approved booking produces an
identical SOP and email to an auto-approved one.

### Flow 2 — Post-run analysis → maintenance

A researcher submits a post-run report (`POST /api/postrun`). **Agent 5** logs the
run, re-indexes the RAG corpus in a background thread, and classifies anomalies. A
critical keyword (`saturation`, `failure`, `leak`, `smoke`, `fire`) opens a work
order, booking-blocks the instrument, and fires the **purple** maintenance email to
facilities + every researcher with an upcoming booking on that instrument. Closing
the work order fires a green "back online" email to the same people.

### Flow 3 — Monthly report (cron)

`APScheduler` runs on the 1st of each month at 07:00 local time
(`backend/main.py` lifespan) and emails the **green** utilization report (KPIs,
per-instrument bars, an insights paragraph) to the chair + lab manager. Also
available on demand via `POST /api/admin/reports/monthly/send`.

### Every step is audited

Each agent node writes to the `agent_decisions` table with its input, output,
reasoning, confidence, the RAG chunks it retrieved, and the citations it used —
this is the "accountability artifact" behind the Governance view.

---

## Project architecture

### Layered view

```
┌─────────────────────────────────────────────────────────────────────────┐
│  CLIENT  ·  React 18 + TypeScript + Vite  (port 5173)                     │
│  Pages: Login · Dashboard · IntakeForm/Chat · FitResults · Bookings ·     │
│         Instruments · PostRun · MyRequests · Governance · Admin · Profile │
│  State: TanStack Query · Supabase Auth (JWT) · realtime change-feed hook  │
└───────────────────────────────────┬───────────────────────────────────────┘
                    HTTPS  /api/*    │   (Vite dev-proxy → :8000)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  API  ·  FastAPI  (port 8000)                                             │
│  Routers: system · chat · instruments · bookings · postrun · admin · me   │
│  Lifespan: bootstrap() + APScheduler monthly cron · CORS · static SOPs    │
│  Auth: Supabase JWT verification (HS256)                                  │
├─────────────────────────────────────────────────────────────────────────┤
│  AGENTS  ·  vein/agents  (LangGraph state machine)                        │
│    Agent 1 Context → Agent 2 Fit → Agent 3 Schedule → ⛔ Safety Gate      │
│                                  → Agent 4 Confirm   ·  Agent 5 Post-run  │
│    llm.py: provider router (Gemini ▸ Claude ▸ rule-based fallback)        │
├─────────────────────────────────────────────────────────────────────────┤
│  SERVICES  ·  vein/services                                               │
│    email + email_templates · sop_builder + sop_docx · airtable ·          │
│    work_order · notifications · guardrails · privacy (audit + redaction)  │
├─────────────────────────────────────────────────────────────────────────┤
│  RAG  ·  vein/rag                                                         │
│    corpus + chunking → sentence-transformers (all-MiniLM-L6-v2, 384-dim)  │
│    → match_documents() cosine search                                      │
├─────────────────────────────────────────────────────────────────────────┤
│  DATA  ·  vein/db                                                         │
│    psycopg3 connection pool (tz-aligned per connection) · seed · helpers  │
└───────────────────────────────────┬───────────────────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  SUPABASE  ·  Postgres + pgvector                                         │
│  Tables: profiles · instruments · bookings · run_logs · work_orders ·     │
│          agent_decisions · automation_events · documents(vector) ·        │
│          rag_metadata     | RLS policies · realtime publication           │
└─────────────────────────────────────────────────────────────────────────┘

External integrations:  Resend (email) · Airtable (record sync) ·
                        Google Gemini / Anthropic Claude (LLM, optional)
```

### Design decisions worth knowing

- **The safety gate is architectural, not advisory.** It lives inside the
  LangGraph and is re-evaluated at confirm time (`vein/agents/safety.py`,
  `vein/agents/graph.py:run_confirm_graph`). The only bypass is an explicit
  `[approved-by-manager]` marker injected after a supervisor approves — and that
  marker can only be set by the HITL completion path.
- **Deterministic core, LLM-optional shell.** Fit scoring and the safety rules are
  rule-based, so they are testable and auditable (100% on a 200-case golden set).
  The LLM (Gemini by default, Claude as fallback) handles natural-language parsing
  and email/SOP copy. With no API key, LODE runs fully on rule-based fallbacks.
- **HITL requests carry replayable state.** A refusal stores the full
  `ExperimentContext` + recommendation + slot in `automation_events.payload`, so an
  approval re-runs the real pipeline rather than just flipping a flag.
- **Postgres is authoritative; everything in `data/` is regenerable.** Generated
  SOPs, the Airtable queue, the email outbox, and the audit log are scratch
  artifacts.
- **Timezone correctness.** The psycopg pool sets each connection's session
  timezone to `LODE_TZ` so naive `datetime.now()` inserts round-trip with the
  correct wall-clock time; emails and `.ics` files carry the right zone label.

### Request lifecycle (sequence)

```
Browser → POST /api/chat/intake ──► guardrail.check_input
                                    │ (refused → return, audit "guardrail.refuse")
                                    ▼
                              run_intake_graph()  ── Agents 1→2→3 → Safety Gate
                                    │
        PASS ◄──────────────────────┴──────────────────────► REFUSE
          │                                                     │
   return slots                                    record_automation_event(hitl)
          │                                        + send_hitl_email (supervisor)
   POST /api/chat/confirm                          + pending email (researcher)
          ▼                                                     │
   run_confirm_graph() → create booking, SOP,        Governance: Approve
   .ics, Airtable push, navy email, work order         │
                                                        ▼
                                          POST /api/me/requests/{id}/complete
                                          → replays run_confirm_graph()
```

---

## Tech stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 18, TypeScript, Vite, Tailwind, TanStack Query, Recharts, lucide-react, `supabase-js` |
| **Backend** | FastAPI, Pydantic v2, psycopg3 + connection pool, APScheduler (monthly cron) |
| **Agents** | 5-agent LangGraph pipeline (Context → Fit → Schedule → SOP → Post-run) + Safety Gate |
| **LLM (optional)** | Google Gemini (`gemini-3.5-flash`, default) or Anthropic Claude; deterministic rule-based fallback when no key is set |
| **RAG** | Supabase Postgres + **pgvector**; `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim); `match_documents()` cosine search |
| **Data** | Supabase Postgres (`timestamptz`, RLS) + pgvector; psycopg pool (min/max 2/12) |
| **Auth / Realtime** | Supabase Auth (JWT HS256) + Postgres change feed |
| **Email** | Resend → SendGrid → SMTP → local outbox (auto-failover) |
| **Artifacts** | `python-docx` (SOP & work-order `.docx`), `.ics` calendar invites |

---

## Quick start

```powershell
# ── Backend (Window 1, project root) ─────────────────────────────────────
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env       # then fill in DATABASE_URL + SUPABASE_* keys
uvicorn backend.main:app --port 8000

# ── Frontend (Window 2) ──────────────────────────────────────────────────
# IMPORTANT: Vite must be started from inside `frontend/`. Running it from the
# project root makes Vite resolve index.html against the wrong directory and
# every route 404s.
cd frontend
copy .env.example .env       # set VITE_SUPABASE_URL + VITE_SUPABASE_ANON_KEY
npm install
npm run dev                  # http://127.0.0.1:5173
```

Open **http://127.0.0.1:5173** and sign in. Health check:
`curl http://127.0.0.1:8000/api/health` → `{"status":"ok",...}`.

### One-shot launcher

```powershell
.\scripts\demo.ps1            # starts backend + frontend, opens browser
.\scripts\demo.ps1 -Stop      # kills :8000 and :5173
.\scripts\demo.ps1 -Reset     # clears chroma + queues + outbox + generated SOPs
.\scripts\demo.ps1 -Smoke     # runs scripts\smoke_test_full.py headless
```

> **No API keys?** LODE still runs end-to-end: the LLM falls back to rule-based
> parsing on the seeded corpus, and emails are written to
> `data/email_outbox/outbox.jsonl` instead of being sent.

---

## Configuration

All backend knobs live in `.env` at the repo root; the frontend reads
`frontend/.env`. See `.env.example` for the full list. Highlights:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Pooled Postgres connection (Supabase → Database). |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_JWT_SECRET` | Auth, trusted server writes, and JWT verification. |
| `LODE_TZ` | IANA zone (e.g. `America/Denver`) for the scheduler, emails, and `.ics`. Empty = auto-detect. |
| `LLM_PROVIDER` | `google` \| `anthropic` \| `auto` (default `auto`, prefers Google). |
| `GOOGLE_API_KEY` / `GOOGLE_MODEL` | Gemini (default `gemini-3.5-flash`). |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | Claude (fallback provider). |
| `RESEND_API_KEY` → `SENDGRID_API_KEY` → SMTP | First one set wins; none = local outbox. |
| `EMAIL_OVERRIDE` | Demo: route all mail to one inbox (the intended recipient is shown in the email body). |
| `FIT_SCORE_THRESHOLD` | Minimum fit score to advance (default 40). |

> **Never commit a real `.env`.** It is gitignored; `.env.example` is the template.

---

## API surface

```
# System
GET    /api/health
GET    /api/status
POST   /api/bootstrap
GET    /api/notifications

# Intake / decision pipeline
POST   /api/chat/intake                 (chat message → Agents 1–3 + gate)
POST   /api/chat/intake/form            (structured form → same pipeline)
POST   /api/chat/confirm                (Agent 4 → booking + automations)

# Catalog & schedule
GET    /api/instruments
GET    /api/instruments/{id}
GET    /api/bookings[?email=]
GET    /api/bookings/lab-day[?email=]
GET    /api/bookings/utilization

# Post-run (Agent 5)
POST   /api/postrun

# Admin / governance
GET    /api/admin/rag                    /api/admin/rag/reindex   /api/admin/rag/chunks
GET    /api/admin/runs                   /api/admin/audit         /api/admin/equity?weeks=N
GET    /api/admin/work-orders[?status=]
POST   /api/admin/work-orders/{id}/status   /assign   /note
GET    /api/admin/automations[?kind=]    /automations/airtable    /automations/email
GET    /api/admin/hitl[?status=]
POST   /api/admin/hitl/{event_id}/approve   /deny
POST   /api/admin/reports/monthly/send[?to=]

# "My Requests" / self-service (per researcher_email)
GET    /api/me/requests                  /requests/{id}/slots
POST   /api/me/requests/{id}/complete    /requests/{id}/dismiss
POST   /api/me/bookings/{id}/request-edit    /request-cancel
GET    /api/me/export    POST /api/me/delete    GET /api/me/audit   (GDPR Art. 15/17/20)
```

---

## Safety, privacy & governance

The assignment asks for *one* safety control; LODE ships the full stack:

- **Grounding / citations** — every agent decision, SOP, and email cites the RAG
  chunks it used; citations deep-link into the `/knowledge` browser.
- **Refusal rules** — the four-rule safety gate (`vein/agents/safety.py`), enforced
  in the graph and re-checked at confirm time.
- **Human-in-the-loop** — full `pending → approved/denied → confirmed` state machine
  with email + dashboard actions.
- **Input/output guardrails** (`vein/services/guardrails.py`, wired into
  `/api/chat/intake`) — prompt-injection refusal, PII redaction before any LLM
  call, secret masking in outputs, and an 8 000-char input cap.
- **Append-only audit log** (`vein/services/privacy.py`) — JSONL with automatic
  SSN / card / API-key redaction.
- **Data-subject rights** — export, erasure, and per-user audit endpoints;
  see [`COMPLIANCE.md`](COMPLIANCE.md) for the GDPR / FERPA / HIPAA control mapping.

All demo data is synthetic. No secrets are committed.

---

## Evaluation

A programmatically generated golden set validates the deterministic decision core:

```powershell
$env:PYTHONIOENCODING="utf-8"
.\.venv\Scripts\python.exe evals\run.py        # all suites; writes evals/REPORT.md
.\.venv\Scripts\python.exe evals\run.py --suite safety
```

| Suite | Cases | Headline metric |
|---|---|---|
| fit-score    | 100 | top-1 instrument-match accuracy |
| safety-gate  |  60 | accuracy / precision / recall / F1 |
| hazmat-parse |  40 | exact-match + token F1 |

Cases live in `evals/cases.py` and run against the same `score_instruments`,
`evaluate_safety_gate`, and `detect_hazardous_materials` the app uses — so the
metrics tie directly to production code paths.

---

## Project structure

```
backend/                FastAPI app + routers
  main.py               lifespan: bootstrap + APScheduler monthly cron + static SOPs
  auth.py               Supabase JWT verification
  routers/              system · chat · instruments · bookings · postrun · admin · me

vein/                   Core library
  agents/               graph.py (LangGraph), pipeline.py (scoring/scheduling/confirm),
                        safety.py (gate), llm.py (Gemini/Claude/rule-based router)
  rag/                  corpus.py · chunking.py · indexer.py (pgvector + embeddings)
  services/             email + email_templates · sop_builder + sop_docx · airtable ·
                        work_order · notifications · guardrails · privacy
  db/                   database.py (psycopg pool + helpers) · seed.py (15 instruments)
  models/               experiment.py (Pydantic schemas)
  config.py             Settings + timezone helpers     bootstrap.py  startup wiring

frontend/               React + Vite UI
  src/pages/            Login · Dashboard · IntakeForm/Chat · FitResults · Bookings ·
                        Instruments · PostRun · MyRequests · Governance · Admin · Profile
  src/components/       Layout · PageShell · Citations · StatusBanner · ErrorBoundary
  src/lib/              api.ts · auth.tsx · supabase.ts · useRealtime.ts

supabase/migrations/    0001…0008 schema, pgvector, RLS, realtime, automation events
scripts/                demo.ps1 · seed_demo_users.py · smoke_test*.py · check_*.py
evals/                  cases.py · run.py · REPORT.md
data/corpus/            Curated instrument manuals + SOPs (the RAG source)
COMPLIANCE.md           GDPR / FERPA / HIPAA control mapping
DEMO_SCENARIOS.md       Presenter walkthrough     DEMO_DATA.md   copy-paste inputs
```

---

## Demo

See **[`DEMO_SCENARIOS.md`](DEMO_SCENARIOS.md)** for the full presenter script and
**[`DEMO_DATA.md`](DEMO_DATA.md)** for copy-paste inputs. The canonical clean-booking
intake (exercises Agents 1→4 + the navy email and SOP):

> I'm running hydrogen permeation tests on martensitic steel specimens. I need to
> characterize the **fracture surface morphology**. My samples are about 5mm × 5mm
> and they haven't been coated. I need results by Thursday for my advisor meeting.

- Leave **Training** empty → brown HITL email (missing-training refusal).
- Put `concentrated hydrofluoric acid` in any field → brown HITL email (hazmat).
- A `chalcopyrite · phase identification` request → escalates on the 80% confidence
  floor (XRD tops out at 78/B+).
- Post a report with `Detector saturation…` in Anomalies → purple work-order email.
- Click **Send monthly report** in Analytics → green report email.
```
