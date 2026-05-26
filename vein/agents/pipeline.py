"""LODE multi-agent pipeline — context, fit scoring, scheduling, SOP, post-run."""

from datetime import datetime, timedelta
from typing import Optional

from vein.agents.llm import format_citations, has_llm, invoke_structured, invoke_text
from vein.config import OUTPUT_DIR, settings, local_now, local_tz_label
from vein.db.database import (
    add_maintenance_log,
    add_run_log,
    create_booking,
    get_bookings,
    get_instrument,
    get_instruments,
    log_agent_decision,
)
from vein.models.experiment import (
    BookingOption,
    ChatResponse,
    Citation,
    ExperimentContext,
    InstrumentFit,
    PostRunReport,
    UrgencyLevel,
)
from vein.rag.indexer import index_corpus, query_corpus
from vein.services.airtable import push_booking_record
from vein.services.email import send_sop_email
from vein.services.sop_docx import generate_sop_document
from vein.services.work_order import generate_work_order


def parse_experiment_intake(
    message: str,
    history: list[dict],
    context: Optional[ExperimentContext],
    session_id: Optional[str] = None,
) -> ChatResponse:
    from vein.agents.graph import run_intake_graph

    return run_intake_graph(message, history, context, session_id=session_id)


def _demo_intake(
    message: str,
    ctx: ExperimentContext,
    rag_chunks: list[dict],
    citations: list[Citation],
    history: list[dict] | None = None,
) -> ChatResponse:
    from vein.agents.safety import annotate_hazmat

    history = history or []
    lower = message.lower()
    if "steel" in lower or "hydrogen" in lower or "fracture" in lower or "embrittl" in lower:
        ctx.material_type = ctx.material_type or "martensitic steel"
        ctx.analysis_goal = ctx.analysis_goal or "fracture surface morphology"
        ctx.surface_condition = ctx.surface_condition or "uncoated fracture surface"
    if "chalcopyrite" in lower or "ore" in lower or "xrd" in lower:
        ctx.material_type = ctx.material_type or "chalcopyrite"
        ctx.analysis_goal = ctx.analysis_goal or "phase identification"
    if "5mm" in lower:
        ctx.sample_dimensions = "5mm × 5mm"
    if "thursday" in lower or "deadline" in lower:
        ctx.urgency = UrgencyLevel.HIGH
        ctx.deadline = "Thursday"
    if "uncoated" in lower or "not been coated" in lower or "haven't been coated" in lower:
        ctx.coating_status = "uncoated"
    if any(w in lower for w in ("yes", "yeah", "sure", "include")) and (
        "coat" in lower or any("coat" in h.get("content", "").lower() for h in history if h.get("role") == "assistant")
    ):
        ctx.coating_status = "coating scheduled"

    ctx = annotate_hazmat(ctx, message)

    coated_ok = ctx.coating_status in ("coating scheduled", "coated")
    needs_prep = "uncoated" in (ctx.coating_status + ctx.surface_condition).lower() and not coated_ok
    if not ctx.analysis_goal:
        return ChatResponse(
            message="Tell me more about your research — what material are you analyzing and what characterization do you need?",
            context=ctx,
            citations=citations,
            needs_clarification=True,
        )
    if needs_prep and not coated_ok:
        return ChatResponse(
            message=(
                "Your samples aren't coated — for SEM imaging of steel fracture surfaces, "
                "carbon coating is typically required (~90 minutes at station 2B). "
                "Should I include coating prep time in your booking?"
            ),
            context=ctx,
            citations=citations,
            needs_clarification=True,
        )

    ctx.is_complete = True
    recs = score_instruments(ctx, rag_chunks)
    if all(r.fit_score < settings.fit_score_threshold for r in recs):
        return ChatResponse(
            message="No instrument meets the fit threshold. Escalating to lab coordinator.",
            context=ctx,
            recommendations=recs,
            citations=citations,
            escalated=True,
        )
    bookings = schedule_booking(ctx, recs[0])
    prep_note = ""
    if recs[0].prep_time_minutes:
        prep_note = f" I've included ~{recs[0].prep_time_minutes} min for carbon coating prep."
    return ChatResponse(
        message=(
            f"For {ctx.analysis_goal} on {ctx.material_type}, I recommend **{recs[0].instrument_name}** "
            f"(fit score {recs[0].fit_score}/100, grade {recs[0].grade}).{prep_note} "
            f"See scheduling options on the right."
        ),
        context=ctx,
        recommendations=recs,
        booking_options=bookings,
        citations=citations,
    )


def score_instruments(ctx: ExperimentContext, rag_chunks: list[dict]) -> list[InstrumentFit]:
    instruments = get_instruments()
    goal = (ctx.analysis_goal + " " + ctx.material_type).lower()
    recs: list[InstrumentFit] = []

    rules = {
        "sem-jeol": _score_sem(ctx, goal, rag_chunks),
        "xrd-d8": _score_xrd(ctx, goal, rag_chunks),
        "icp-ms": _score_icp(ctx, goal, rag_chunks),
        "rock-mech": _score_rock(ctx, goal),
        "tube-furnace": (10, "N/A", "High-temp treatment only; not for surface morphology."),
        # --- Additional SIF instruments (keyword-matched) ---
        "tem-talos": _score_kw(goal, ("tem", "nanostructure", "lattice", "dislocation",
            "nanoparticle", "crystallographic", "atomic resolution", "precipitate"), 90, "A",
            "200 kV (S)TEM with EDS — atomic-scale imaging, diffraction, and nano-EDS mapping."),
        "fib-helios": _score_kw(goal, ("fib", "lamella", "cross-section", "site-specific",
            "tem sample", "milling"), 88, "A",
            "Dual-beam FIB-SEM for site-specific cross-sections and TEM lamella prep."),
        "xrd-empyrean": _score_kw(goal, ("thin film", "texture", "residual stress",
            "reflectivity", "phase", "crystalline"), 82, "A-",
            "Empyrean XRD adds thin-film, texture and residual-stress configurations."),
        "raman-witec": _score_kw(goal, ("raman", "vibrational", "molecular", "bonding",
            "graphene", "carbon", "stress mapping"), 86, "A",
            "Confocal Raman for vibrational/molecular fingerprinting and stress mapping."),
        "afm-asylum": _score_kw(goal, ("afm", "topography", "roughness", "nanomechanical",
            "modulus", "surface topography"), 85, "A",
            "AFM for nanoscale topography, roughness and nanomechanical mapping."),
        "xps-kratos": _score_kw(goal, ("xps", "surface chemistry", "oxidation state",
            "binding energy", "chemical state", "passivation", "valence"), 88, "A",
            "XPS quantifies surface chemistry and oxidation/chemical state (top ~10 nm)."),
        "xct-versa": _score_kw(goal, ("ct", "tomography", "3d imaging", "porosity",
            "internal structure", "void", "non-destructive"), 87, "A",
            "Micro-CT for non-destructive 3D internal structure, porosity and voids."),
        "apt-leap": _score_kw(goal, ("atom probe", "apt", "3d composition", "solute",
            "segregation", "grain boundary composition", "clustering"), 89, "A",
            "Atom probe tomography for 3D, near-atomic compositional mapping."),
        "ms-orbitrap": _score_kw(goal, ("mass spec", "lc-ms", "molecular weight",
            "metabolite", "organic", "proteomic", "small molecule"), 84, "A",
            "High-res Orbitrap LC-MS for accurate-mass organic/biomolecule analysis."),
        "gleeble-3500": _score_kw(goal, ("gleeble", "thermomechanical", "hot deformation",
            "weld simulation", "transformation kinetics", "haz", "hot ductility"), 85, "A",
            "Gleeble physical simulation of thermomechanical and weld-HAZ processing."),
    }

    for inst in instruments:
        if inst["status"] == "maintenance" and inst["id"] != "tube-furnace":
            continue
        score, grade, rationale = rules.get(inst["id"], (20, "D", "Limited applicability for this experiment."))
        inst_chunks = [c for c in rag_chunks if c.get("instrument_id") == inst["id"]] or rag_chunks[:2]
        cites = [Citation(**c) for c in format_citations(inst_chunks)]
        trained = inst.get("required_training", "") in (ctx.trained_instruments or [])
        prep = 90 if inst["id"] == "sem-jeol" and "uncoated" in (ctx.coating_status + ctx.surface_condition).lower() else 0
        run_mins = 180 if inst["id"] == "sem-jeol" else 120
        recs.append(InstrumentFit(
            instrument_id=inst["id"],
            instrument_name=inst["name"],
            fit_score=score,
            grade=grade,
            rationale=rationale,
            citations=cites,
            requires_training=bool(inst.get("required_training")) and not trained,
            prep_time_minutes=prep,
            run_duration_minutes=run_mins,
        ))

    recs.sort(key=lambda r: r.fit_score, reverse=True)
    return recs


def _score_kw(
    goal: str,
    keywords: tuple[str, ...],
    hit_score: int,
    hit_grade: str,
    hit_rationale: str,
) -> tuple[int, str, str]:
    """Generic keyword scorer for the additional SIF instruments. Returns the
    instrument's strong score when the analysis goal mentions a matching
    technique/keyword, otherwise a low 'not primary for this goal' score."""
    if any(k in goal for k in keywords):
        return hit_score, hit_grade, hit_rationale
    return 22, "D", "Available, but not the primary technique for this analysis goal."


def _score_sem(ctx: ExperimentContext, goal: str, chunks: list[dict]) -> tuple[int, str, str]:
    if any(w in goal for w in ("morphology", "fracture", "surface", "sem", "microstructure", "grain boundary")):
        rationale = (
            "SEM with EDS is optimal for fracture surface chemistry mapping at the sample scale described. "
            "[Source: JEOL JSM-IT800 Manual, Section 3.2, p.42]"
        )
        if "uncoated" in (ctx.coating_status + ctx.surface_condition).lower():
            rationale += " Carbon coating required before imaging."
        return 92, "A", rationale
    if "phase" in goal:
        return 55, "C+", "SEM can image but XRD is preferred for bulk phase ID."
    return 30, "D", "SEM not primary for this analysis goal."


def _score_xrd(ctx: ExperimentContext, goal: str, chunks: list[dict]) -> tuple[int, str, str]:
    if any(w in goal for w in ("phase", "chalcopyrite", "xrd", "crystalline", "martensite", "precipitate")):
        return 78, "B+", (
            "XRD suitable for phase identification; use Co Kα for steel to avoid fluorescence. "
            "[Source: Bruker D8 Advance Manual, Section 5.1, p.89]"
        )
    if any(w in goal for w in ("morphology", "fracture", "surface")):
        return 35, "D", "XRD cannot characterize surface morphology."
    return 40, "C", "May supplement SEM for phase ID if precipitates are of interest."


def _score_icp(ctx: ExperimentContext, goal: str, chunks: list[dict]) -> tuple[int, str, str]:
    if any(w in goal for w in ("trace", "water", "drainage", "dissolution", "elemental quant")):
        return 88, "A", "ICP-MS ideal for trace element quantification in aqueous samples."
    if any(w in goal for w in ("morphology", "fracture", "surface")):
        return 0, "N/A", "Destructive dissolution required; incompatible with morphology analysis."
    return 25, "D", "Requires full sample dissolution."


def _score_rock(ctx: ExperimentContext, goal: str) -> tuple[int, str, str]:
    if any(w in goal for w in ("compressive", "tensile", "rock", "mechanical", "strength")):
        return 85, "A", "Rock mechanics rig appropriate for mechanical testing."
    return 15, "N/A", "Not applicable for microscopy or diffraction goals."


def schedule_booking(ctx: ExperimentContext, top: InstrumentFit) -> list[BookingOption]:
    inst = get_instrument(top.instrument_id)
    if not inst:
        return []

    existing = get_bookings(top.instrument_id)
    warmup = inst.get("warmup_minutes", 30)
    prep = top.prep_time_minutes
    duration = top.run_duration_minutes
    total_min = warmup + prep + duration

    now = local_now().replace(minute=0, second=0, microsecond=0)
    options: list[BookingOption] = []

    for day_offset in range(1, 8):
        base = now + timedelta(days=day_offset)
        for hour in (9, 13, 15):
            start = base.replace(hour=hour)
            prep_start = start - timedelta(minutes=prep + warmup)
            end = start + timedelta(minutes=duration)
            conflict = any(
                datetime.fromisoformat(b["start_time"]) < end
                and datetime.fromisoformat(b["end_time"]) > prep_start
                for b in existing
                if b["status"] != "cancelled"
            )
            if conflict:
                continue
            urgency_bonus = 10 if ctx.urgency in (UrgencyLevel.HIGH, UrgencyLevel.CRITICAL) and day_offset <= 2 else 0
            score = 100 - day_offset * 5 - hour * 0.5 + urgency_bonus
            options.append(BookingOption(
                instrument_id=top.instrument_id,
                instrument_name=top.instrument_name,
                start_time=start,
                end_time=end,
                prep_start=prep_start,
                rank=len(options) + 1,
                score=score,
                notes=f"Includes {warmup} min warm-up and {prep} min prep.",
            ))
            if len(options) >= 3:
                break
        if len(options) >= 3:
            break

    options.sort(key=lambda o: o.score, reverse=True)
    for i, o in enumerate(options):
        o.rank = i + 1
    return options


def confirm_booking(
    ctx: ExperimentContext,
    option: BookingOption,
    top: InstrumentFit,
    session_id: Optional[str] = None,
) -> ChatResponse:
    """Agent 4 — generates SOP and fires the three automations.

    Automation 1: Airtable booking record.
    Automation 2: SendGrid/SMTP email with .docx attachment (or local outbox).
    Automation 3: Maintenance work order if instrument is overdue for calibration.
    """
    # Create the booking first so the SOP header can show its real code.
    bid = create_booking(
        option.instrument_id,
        ctx.researcher_name or "Researcher",
        ctx.researcher_email or "",
        option.start_time,
        option.end_time,
        ctx.model_dump(),
        "",
    )
    booking_code = f"VEIN-{bid:04d}"
    sop_path = generate_sop_document(ctx, top, option, booking_code=booking_code)
    # Persist the rendered SOP path now that we have it.
    try:
        from vein.db.database import get_conn
        with get_conn() as conn:
            conn.execute("UPDATE bookings SET sop_path = %s WHERE id = %s",
                         (str(sop_path), bid))
    except Exception:  # noqa: BLE001 — non-critical bookkeeping
        pass

    # Automation 1 — Airtable booking record
    airtable_record = push_booking_record(
        booking_id=bid,
        researcher=ctx.researcher_name or "Researcher",
        instrument_name=top.instrument_name,
        instrument_id=top.instrument_id,
        start_time=option.start_time,
        end_time=option.end_time,
        experiment_type=ctx.analysis_goal,
        material_type=ctx.material_type,
        fit_score=top.fit_score,
        sop_status="generated",
        rationale=top.rationale,
        research_group=ctx.research_group,
    )

    # Automation 2 — Email 1: booking confirmation + SOP (+ cited checklist + .ics)
    inst_meta = get_instrument(top.instrument_id) or {}
    location = inst_meta.get("location", "")
    tz_label = local_tz_label()
    when_str = f"{option.start_time:%A, %b %d, %Y · %I:%M %p}–{option.end_time:%I:%M %p} {tz_label}"
    sop_chunks = query_corpus(
        f"{ctx.material_type} {ctx.analysis_goal} preparation procedure",
        n_results=3, instrument_id=top.instrument_id,
    )
    checklist = [
        {
            "text": c["text"][:170].rsplit(" ", 1)[0] + "…",
            "citation": f"{c['source']}{(' ' + c['section']) if c.get('section') else ''}"
                        + (f", p.{c['page']}" if c.get("page") else ""),
        }
        for c in sop_chunks
    ]
    # ICS — emit timestamps in UTC ("Z" suffix) so calendar apps interpret them
    # unambiguously regardless of the recipient's local timezone.
    _fmt = "%Y%m%dT%H%M%SZ"
    try:
        from zoneinfo import ZoneInfo
        from vein.config import LOCAL_TZ_NAME as _TZ
        _start_utc = option.start_time.replace(tzinfo=ZoneInfo(_TZ)).astimezone(ZoneInfo("UTC"))
        _end_utc = option.end_time.replace(tzinfo=ZoneInfo(_TZ)).astimezone(ZoneInfo("UTC"))
    except Exception:
        _start_utc, _end_utc = option.start_time, option.end_time
    ics_text = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//LODE//Lab//EN\r\nBEGIN:VEVENT\r\n"
        f"UID:{booking_code}@lode\r\nDTSTART:{_start_utc.strftime(_fmt)}\r\n"
        f"DTEND:{_end_utc.strftime(_fmt)}\r\nSUMMARY:LODE session — {top.instrument_name}\r\n"
        f"LOCATION:{location}\r\nDESCRIPTION:{ctx.analysis_goal or ctx.material_type}\r\n"
        "END:VEVENT\r\nEND:VCALENDAR"
    )
    # Surface the same RAG references that the SOP cites, so the email and the
    # attached .docx tell the same story.
    from vein.services.sop_builder import _references_from_chunks  # noqa: WPS437
    references = _references_from_chunks(sop_chunks)

    email_result = send_sop_email(
        ctx, str(sop_path),
        booking_code=booking_code,
        instrument=top.instrument_name,
        location=location,
        when=when_str,
        fit_score=top.fit_score,
        grade=top.grade,
        approved_by="Auto-approved · LODE safety gate",
        checklist=checklist,
        ics_text=ics_text,
        fit_rationale=top.rationale,
        references=references,
    )

    # Automation 3 — preemptive work order if calibration is overdue
    from vein.db.database import get_instrument_usage_hours
    inst = get_instrument(top.instrument_id) or {}
    interval = float(inst.get("calibration_interval_hours") or 0)
    usage = get_instrument_usage_hours(top.instrument_id)
    work_order = None
    if interval and usage >= interval:
        work_order = generate_work_order(
            instrument_id=top.instrument_id,
            issue=f"Calibration overdue: {usage:.1f}h logged vs {interval}h interval",
            severity="warning",
            source="safety_gate",
        )

    if session_id:
        log_agent_decision(
            session_id, "agent4_sop",
            input_summary=f"booking={bid} instrument={top.instrument_id}",
            output_summary=f"SOP={sop_path.name}; airtable={airtable_record['id']}; email={email_result['transport']}",
            reasoning="Generated cited SOP; fired booking, email, and (if overdue) work-order automations.",
            confidence=95,
            rag_chunks=[],
            citations=[c.model_dump() for c in top.citations],
            outcome="advance",
        )

    automations = {
        "airtable_booking": airtable_record,
        "email": email_result,
        "work_order": work_order,
    }
    return ChatResponse(
        message=(
            f"Booking confirmed (ID #{bid}). SOP generated, "
            f"booking pushed to {airtable_record['destination']}, "
            f"email queued via {email_result['transport']}."
            + (f" Maintenance work order #{work_order['id']} opened." if work_order else "")
        ),
        context=ctx,
        sop_path=str(sop_path),
        automations=automations,
        session_id=session_id,
    )


def process_post_run(report: PostRunReport, session_id: Optional[str] = None) -> dict:
    """Agent 5 — post-run analysis, RAG re-index, optional work-order automation."""
    booking = None
    inst_id = "sem-jeol"
    material = ""

    from vein.db.database import get_conn

    with get_conn() as conn:
        row = conn.execute("SELECT * FROM bookings WHERE id = %s", (report.booking_id,)).fetchone()
        if row:
            booking = dict(row)
            inst_id = booking["instrument_id"]
            import json
            ec = booking.get("experiment_context") or {}
            if isinstance(ec, str):
                try:
                    ec = json.loads(ec or "{}")
                except json.JSONDecodeError:
                    ec = {}
            material = ec.get("material_type", "") if isinstance(ec, dict) else ""

    rid = add_run_log(
        inst_id,
        report.researcher_name,
        material,
        report.actual_parameters,
        "Success" if report.ran_as_planned else "Issues reported",
        report.data_quality_rating,
        report.booking_id,
    )

    maintenance_alert = False
    work_order = None
    if report.anomalies:
        severity = "critical" if any(
            kw in report.anomalies.lower() for kw in ("saturation", "failure", "leak", "smoke", "fire")
        ) else "warning"
        add_maintenance_log(inst_id, "USER-REPORT", report.anomalies, "Logged from post-run report", severity)
        maintenance_alert = severity == "critical"
        # Automation 3 — generate maintenance work order routed via Airtable
        work_order = generate_work_order(
            instrument_id=inst_id,
            issue=report.anomalies,
            severity=severity,
            source="post_run",
        )

    # Re-index so a future booking inherits the new run/maintenance context.
    # A synchronous force-reindex re-embeds the whole corpus and can take 20s+,
    # which made the post-run submission appear to hang (and, under load, time
    # out). Run it in a background thread so the response returns immediately;
    # it's non-critical to the submission itself.
    def _bg_reindex() -> None:
        try:
            index_corpus(force=True)
        except Exception as exc:  # noqa: BLE001
            import logging
            logging.getLogger("vein.pipeline").warning("post-run re-index failed: %s", exc)

    import threading
    threading.Thread(target=_bg_reindex, daemon=True, name="postrun-reindex").start()

    if session_id:
        log_agent_decision(
            session_id, "agent5_postrun",
            input_summary=f"booking={report.booking_id} quality={report.data_quality_rating}/5",
            output_summary=(
                f"run_log={rid}"
                + (f"; work_order={work_order['id']}" if work_order else "")
            ),
            reasoning=(
                f"Logged run, re-indexed ChromaDB"
                + (f"; anomalies={report.anomalies[:120]} (severity={'critical' if maintenance_alert else 'warning'})" if report.anomalies else "")
            ),
            confidence=90 if report.ran_as_planned else 60,
            rag_chunks=[],
            citations=[],
            outcome="advance",
        )

    return {
        "run_log_id": rid,
        "maintenance_alert": maintenance_alert,
        "work_order": work_order,
        "message": "Post-run report processed; knowledge base updating in the background."
        + (f" Work order #{work_order['id']} opened." if work_order else ""),
    }
