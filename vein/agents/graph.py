"""
LangGraph orchestration for LODE / VEIN 2.0 five-agent pipeline.

Flow:
  Agent 1 (Context) → [clarify | escalate-no-fit | fit]
  Agent 2 (Fit)     → [escalate-no-fit | schedule]
  Agent 3 (Schedule)→ safety_gate
  safety_gate       → [escalate-human-review | END(intake)]
  Agent 4 (SOP)     → confirm endpoint (separate graph)
  Agent 5 (Post-run)→ separate entry via API

Every agent node writes to the audit log (agent_decisions table) with input,
output, reasoning, confidence, RAG chunks, and citations — per the spec's
Governance Framework "accountability artifact" requirement.
"""

from __future__ import annotations

import uuid
from typing import Literal, Optional, TypedDict

from langgraph.graph import END, StateGraph

from vein.agents.llm import format_citations, has_llm, invoke_structured
from vein.agents.pipeline import (
    _demo_intake,
    confirm_booking,
    process_post_run,
    schedule_booking,
    score_instruments,
)
from vein.agents.safety import annotate_hazmat, evaluate_safety_gate
from vein.config import local_now, local_tz_label, settings
from vein.db.database import (
    log_agent_decision,
    record_automation_event,
    update_automation_event_status,
)
from vein.services.email import send_hitl_email, send_user_hitl_pending_email
from vein.models.experiment import (
    BookingOption,
    ChatResponse,
    Citation,
    ExperimentContext,
    InstrumentFit,
    PostRunReport,
    SafetyGateResult,
)
from vein.rag.indexer import query_corpus


class LodeGraphState(TypedDict, total=False):
    session_id: str
    message: str
    history: list
    context: ExperimentContext
    rag_chunks: list
    citations: list
    recommendations: list
    booking_options: list
    response_message: str
    needs_clarification: bool
    escalated: bool
    sop_path: Optional[str]
    safety_gate: Optional[SafetyGateResult]


def _ensure_session(state: LodeGraphState) -> str:
    sid = state.get("session_id")
    if not sid:
        sid = f"sess_{uuid.uuid4().hex[:12]}"
    return sid


def _agent1_context(state: LodeGraphState) -> LodeGraphState:
    sid = _ensure_session(state)
    ctx = state.get("context") or ExperimentContext()
    message = state["message"]
    history = state.get("history", [])
    query = f"{message} {ctx.analysis_goal} {ctx.material_type}"
    rag_chunks = query_corpus(query, n_results=5)
    citations = [Citation(**c) for c in format_citations(rag_chunks)]

    parsed_via = "demo"
    if has_llm():
        from pydantic import Field

        class ParsedContext(ExperimentContext):
            assistant_reply: str = Field(description="Conversational reply to the researcher")
            needs_clarification: bool = False

        system = (
            "You are LODE Experiment Context Agent at Colorado School of Mines. "
            "Parse experiment descriptions into the structured ExperimentContext schema. "
            "Detect hazardous materials (HF, perchloric, radioactive, mercury, beryllium, etc) "
            "and surface them. Ask one clarifying question if a critical field is missing."
        )
        rag_ctx = "\n".join(f"[{c.source}]: {c.excerpt}" for c in citations)
        user = f"History: {history[-6:]}\nMessage: {message}\nContext so far: {ctx.model_dump()}\nRAG:\n{rag_ctx}"
        try:
            parsed = invoke_structured(system, user, ParsedContext)
            ctx = ExperimentContext(
                **{k: v for k, v in parsed.model_dump().items() if k in ExperimentContext.model_fields}
            )
            ctx = annotate_hazmat(ctx, message)
            complete = not parsed.needs_clarification and bool(ctx.analysis_goal and ctx.material_type)
            log_agent_decision(
                sid, "agent1_context",
                input_summary=message,
                output_summary=parsed.assistant_reply,
                reasoning=f"LLM-parsed; complete={complete}; hazmat={ctx.hazardous_materials}",
                confidence=85 if complete else 50,
                rag_chunks=rag_chunks,
                citations=[c.model_dump() for c in citations],
                outcome="clarify" if not complete else "advance",
            )
            if not complete:
                return {
                    "session_id": sid,
                    "context": ctx,
                    "rag_chunks": rag_chunks,
                    "citations": citations,
                    "response_message": parsed.assistant_reply,
                    "needs_clarification": True,
                    "escalated": False,
                }
            return {
                "session_id": sid,
                "context": ctx,
                "rag_chunks": rag_chunks,
                "citations": citations,
                "response_message": parsed.assistant_reply,
                "needs_clarification": False,
                "escalated": False,
            }
        except Exception:
            parsed_via = "demo-fallback"

    resp = _demo_intake(message, ctx, rag_chunks, citations, history)
    ctx = annotate_hazmat(resp.context or ctx, message)
    log_agent_decision(
        sid, "agent1_context",
        input_summary=message,
        output_summary=resp.message[:400],
        reasoning=f"rules-based ({parsed_via}); hazmat={ctx.hazardous_materials}",
        confidence=70 if not resp.needs_clarification else 40,
        rag_chunks=rag_chunks,
        citations=[c.model_dump() for c in resp.citations],
        outcome="clarify" if resp.needs_clarification else ("escalate" if resp.escalated else "advance"),
    )
    return {
        "session_id": sid,
        "context": ctx,
        "rag_chunks": rag_chunks,
        "citations": resp.citations,
        "recommendations": resp.recommendations,
        "booking_options": resp.booking_options,
        "response_message": resp.message,
        "needs_clarification": resp.needs_clarification,
        "escalated": resp.escalated,
    }


def _route_after_context(state: LodeGraphState) -> Literal["clarify", "escalate", "fit", "schedule"]:
    if state.get("needs_clarification"):
        return "clarify"
    if state.get("escalated"):
        return "escalate"
    if state.get("recommendations") and state.get("booking_options"):
        return "schedule"  # demo path already populated everything → go to safety gate
    return "fit"


def _agent2_fit(state: LodeGraphState) -> LodeGraphState:
    sid = state.get("session_id", "")
    if state.get("recommendations"):
        return state
    ctx = state["context"]
    rag_chunks = state.get("rag_chunks", [])
    recs = score_instruments(ctx, rag_chunks)
    for r in recs:
        r.confidence = r.fit_score  # surface confidence per spec
    msg = state.get("response_message", "")

    if all(r.fit_score < settings.fit_score_threshold for r in recs):
        log_agent_decision(
            sid, "agent2_fit",
            input_summary=f"{ctx.material_type}/{ctx.analysis_goal}",
            output_summary="no instrument above threshold",
            reasoning=f"All {len(recs)} scored < {settings.fit_score_threshold}",
            confidence=20,
            rag_chunks=rag_chunks,
            citations=[],
            outcome="escalate",
        )
        return {
            "recommendations": recs,
            "escalated": True,
            "response_message": msg + "\n\nNo suitable instrument found — escalating to lab coordinator.",
        }
    top = recs[0]
    log_agent_decision(
        sid, "agent2_fit",
        input_summary=f"{ctx.material_type}/{ctx.analysis_goal}",
        output_summary=f"top={top.instrument_name} score={top.fit_score} grade={top.grade}",
        reasoning=top.rationale,
        confidence=top.confidence,
        rag_chunks=rag_chunks,
        citations=[c.model_dump() for c in top.citations],
        outcome="advance",
    )
    return {
        "recommendations": recs,
        "response_message": msg + f"\n\n**Top recommendation:** {top.instrument_name} (fit {top.fit_score}/100, grade {top.grade}).",
    }


def _route_after_fit(state: LodeGraphState) -> Literal["escalate", "schedule"]:
    if state.get("escalated"):
        return "escalate"
    return "schedule"


def _agent3_schedule(state: LodeGraphState) -> LodeGraphState:
    sid = state.get("session_id", "")
    if state.get("booking_options"):
        return state
    ctx = state["context"]
    recs = state.get("recommendations", [])
    if not recs:
        return state
    top = recs[0]
    options = schedule_booking(ctx, top)
    msg = state.get("response_message", "")
    if top.prep_time_minutes:
        msg += f"\n\nSample prep (~{top.prep_time_minutes} min) included before session."
    log_agent_decision(
        sid, "agent3_schedule",
        input_summary=f"top={top.instrument_id}",
        output_summary=f"{len(options)} slots proposed",
        reasoning=f"warm-up {top.run_duration_minutes}m + prep {top.prep_time_minutes}m; urgency {ctx.urgency}",
        confidence=80 if options else 30,
        rag_chunks=[],
        citations=[],
        outcome="advance" if options else "escalate",
    )
    return {"booking_options": options, "response_message": msg}


def _safety_gate(state: LodeGraphState) -> LodeGraphState:
    sid = state.get("session_id", "")
    ctx = state.get("context") or ExperimentContext()
    recs = state.get("recommendations") or []
    options = state.get("booking_options") or []
    top = recs[0] if recs else None
    result = evaluate_safety_gate(ctx, top)
    msg = state.get("response_message", "")
    if not result.passed:
        msg += (
            "\n\n**Safety gate — human review required.** "
            + " ".join(f"• {r}" for r in result.reasons)
        )
    log_agent_decision(
        sid, "safety_gate",
        input_summary=f"top={top.instrument_id if top else 'none'}",
        output_summary="pass" if result.passed else "; ".join(result.reasons),
        reasoning="Hard refusal rules: training, maintenance/calibration, hazmat, confidence floor.",
        confidence=100,
        rag_chunks=[],
        citations=[],
        outcome="advance" if result.passed else "escalate",
    )

    # Auto-fire HITL email + persist pending-request row when the gate refuses.
    # This is the only place in the intake flow that knows enough to write the
    # researcher's name, the picked instrument, and the proposed slot.
    if not result.passed and top is not None:
        try:
            booking_code = f"HITL-{sid.replace('sess_', '').upper()[:6]}"
            slot = options[0] if options else None
            when_str = "Not yet scheduled"
            if slot is not None:
                tz = local_tz_label()
                when_str = (
                    f"{slot.start_time:%A, %b %d, %Y · %I:%M %p}"
                    f"–{slot.end_time:%I:%M %p} {tz}"
                )

            # Classify the lead reason so the email's alert callout matches
            # the dominant refusal rule.
            lead = next(iter(result.reasons), "")
            if "training" in lead.lower():
                alert_title = "Training certification missing"
                training_status = f"{ctx.researcher_name or 'Researcher'}: cert not on file"
            elif "hazard" in lead.lower() or "hf" in lead.lower():
                alert_title = "Hazardous materials detected"
                training_status = "Hazmat keyword match — EH&S review required"
            elif "calibration" in lead.lower() or "maintenance" in lead.lower():
                alert_title = "Instrument calibration / maintenance flag"
                training_status = "Calibration interval exceeded"
            elif "confidence" in lead.lower():
                alert_title = "Fit Scorer confidence below 80%"
                training_status = "No high-confidence recommendation"
            else:
                alert_title = "Booking flagged for review"
                training_status = "—"

            # Persist a pending HITL request with the *full* booking state so
            # an approval can later auto-complete the booking (run_confirm_graph)
            # without making the user re-enter the form. The payload carries:
            #   - the structured ExperimentContext
            #   - the picked InstrumentFit (top)
            #   - the preferred BookingOption (first slot proposed)
            slot_payload = None
            if slot is not None:
                slot_payload = slot.model_dump(mode="json")
            event_id = record_automation_event(
                kind="hitl_request",
                status="pending",
                target=sid,
                detail=f"{booking_code} — {alert_title}",
                payload={
                    "booking_code": booking_code,
                    "session_id": sid,
                    "researcher_name": ctx.researcher_name,
                    "researcher_email": ctx.researcher_email,
                    "research_group": ctx.research_group,
                    "instrument_id": top.instrument_id,
                    "instrument_name": top.instrument_name,
                    "experiment": ctx.analysis_goal or ctx.material_type,
                    "fit_score": top.fit_score,
                    "grade": top.grade,
                    "confidence": getattr(top, "confidence", None) or top.fit_score,
                    "when": when_str,
                    "alert_title": alert_title,
                    "alert_text": lead,
                    "reasons": result.reasons,
                    # The next three are what /requests/{id}/complete replays.
                    "context": ctx.model_dump(mode="json"),
                    "recommendation": top.model_dump(mode="json"),
                    "option": slot_payload,
                },
            )

            send_hitl_email(
                booking_code=booking_code,
                researcher=f"{ctx.researcher_name or 'Researcher'} ({ctx.researcher_email or '—'})",
                instrument=top.instrument_name,
                location="—",
                when=when_str,
                experiment=ctx.analysis_goal or ctx.material_type or "—",
                fit_score=top.fit_score,
                grade=top.grade,
                confidence=getattr(top, "confidence", None) or top.fit_score,
                training_status=training_status,
                alert_title=alert_title,
                alert_text=lead or "; ".join(result.reasons),
                reasoning=result.reasons,
                event_id=event_id,
            )
            # Tell the researcher their booking is awaiting review so they don't
            # think the submission was lost. This is the user-side counterpart
            # to the supervisor email — same booking_code, same data.
            try:
                send_user_hitl_pending_email(
                    researcher_email=ctx.researcher_email or "",
                    researcher_name=ctx.researcher_name or "",
                    booking_code=booking_code,
                    instrument=top.instrument_name,
                    when=when_str,
                    experiment=ctx.analysis_goal or ctx.material_type or "—",
                    reasons=result.reasons,
                    alert_title=alert_title,
                )
            except Exception as exc:  # noqa: BLE001
                log_agent_decision(
                    sid, "safety_gate",
                    input_summary=f"top={top.instrument_id}",
                    output_summary=f"user-pending email failed: {exc}",
                    reasoning="Email transport raised — supervisor still notified.",
                    confidence=0, rag_chunks=[], citations=[], outcome="escalate",
                )
            # Stash the new event id on the response so the UI can surface it
            # in the success banner (and link to /governance?hitl=<id>).
            state["hitl_event_id"] = event_id  # type: ignore[typeddict-unknown-key]
        except Exception as exc:  # noqa: BLE001
            # Telemetry only — refusal is still reported in the UI banner.
            log_agent_decision(
                sid, "safety_gate",
                input_summary=f"top={top.instrument_id}",
                output_summary=f"HITL dispatch failed: {exc}",
                reasoning="Email transport raised — see backend logs.",
                confidence=0, rag_chunks=[], citations=[], outcome="escalate",
            )

    return {
        "safety_gate": result,
        "escalated": state.get("escalated") or not result.passed,
        "response_message": msg,
    }


def _finalize(state: LodeGraphState) -> LodeGraphState:
    return state


def build_intake_graph():
    g = StateGraph(LodeGraphState)
    g.add_node("context", _agent1_context)
    g.add_node("fit", _agent2_fit)
    g.add_node("schedule", _agent3_schedule)
    g.add_node("safety", _safety_gate)
    g.add_node("finalize", _finalize)

    g.set_entry_point("context")
    g.add_conditional_edges(
        "context",
        _route_after_context,
        {"clarify": "finalize", "escalate": "finalize", "fit": "fit", "schedule": "safety"},
    )
    g.add_conditional_edges(
        "fit",
        _route_after_fit,
        {"escalate": "finalize", "schedule": "schedule"},
    )
    g.add_edge("schedule", "safety")
    g.add_edge("safety", "finalize")
    g.add_edge("finalize", END)
    return g.compile()


_intake_graph = None


def get_intake_graph():
    global _intake_graph
    if _intake_graph is None:
        _intake_graph = build_intake_graph()
    return _intake_graph


def run_intake_graph(
    message: str,
    history: list[dict],
    context: Optional[ExperimentContext] = None,
    session_id: Optional[str] = None,
) -> ChatResponse:
    initial: LodeGraphState = {
        "message": message,
        "history": history,
        "context": context or ExperimentContext(),
        "session_id": session_id or f"sess_{uuid.uuid4().hex[:12]}",
    }
    final = get_intake_graph().invoke(initial)
    return ChatResponse(
        message=final.get("response_message", ""),
        context=final.get("context"),
        recommendations=final.get("recommendations", []),
        booking_options=final.get("booking_options", []),
        citations=final.get("citations", []),
        needs_clarification=final.get("needs_clarification", False),
        escalated=final.get("escalated", False),
        sop_path=final.get("sop_path"),
        safety_gate=final.get("safety_gate"),
        session_id=final.get("session_id"),
    )


def run_confirm_graph(
    ctx: ExperimentContext,
    option: BookingOption,
    recommendation: InstrumentFit,
    session_id: Optional[str] = None,
) -> ChatResponse:
    """Agent 4 — SOP generation + the three automations (Airtable, email, work order if needed)."""
    sid = session_id or f"sess_{uuid.uuid4().hex[:12]}"
    # Re-run safety gate at confirm-time to refuse silently-bypassed bookings.
    gate = evaluate_safety_gate(ctx, recommendation)
    if not gate.passed:
        log_agent_decision(
            sid, "safety_gate",
            input_summary=f"confirm:{recommendation.instrument_id}",
            output_summary="; ".join(gate.reasons),
            reasoning="Confirm-time re-check.",
            confidence=100,
            rag_chunks=[],
            citations=[],
            outcome="escalate",
        )
        return ChatResponse(
            message="Booking refused by safety gate: " + " ".join(gate.reasons),
            context=ctx,
            recommendations=[recommendation],
            booking_options=[option],
            citations=[],
            escalated=True,
            safety_gate=gate,
            session_id=sid,
        )

    resp = confirm_booking(ctx, option, recommendation, session_id=sid)
    resp.session_id = sid
    return resp


def run_postrun_graph(report: PostRunReport, session_id: Optional[str] = None) -> dict:
    """Agent 5 — post-run analysis, RAG re-index, optional work order."""
    sid = session_id or f"sess_{uuid.uuid4().hex[:12]}"
    return process_post_run(report, session_id=sid)


def run_form_intake(
    context: ExperimentContext,
    session_id: Optional[str] = None,
) -> ChatResponse:
    """Form-mode entry: take a structured ExperimentContext, run fit + schedule
    + safety in one shot, return slot options. Same automations as chat after
    confirm, just without the back-and-forth.

    This is the path the manual booking form uses. It mirrors what the chat
    graph does after the context is complete: hazmat annotation → fit → schedule
    → safety gate (with HITL email + automation_events row if it refuses).
    """
    sid = session_id or f"sess_{uuid.uuid4().hex[:12]}"
    ctx = annotate_hazmat(context.model_copy(deep=True),
                          " ".join(filter(None, [context.material_type, context.analysis_goal,
                                                 context.surface_condition, context.coating_status,
                                                 context.notes])))
    ctx.is_complete = True

    # Quick RAG query for citations on the form summary card.
    rag_chunks = query_corpus(
        f"{ctx.material_type} {ctx.analysis_goal}", n_results=5
    )
    citations = [Citation(**c) for c in format_citations(rag_chunks)]

    log_agent_decision(
        sid, "agent1_context",
        input_summary=f"form-intake: {ctx.material_type} / {ctx.analysis_goal}",
        output_summary="structured context accepted",
        reasoning=f"form-mode (no chat); hazmat={ctx.hazardous_materials}",
        confidence=90,
        rag_chunks=rag_chunks,
        citations=[c.model_dump() for c in citations],
        outcome="advance",
    )

    # Reuse the chat graph nodes via direct calls so the same telemetry +
    # safety_gate behavior fires.
    state: LodeGraphState = {
        "session_id": sid,
        "message": f"[form] {ctx.material_type} · {ctx.analysis_goal}",
        "history": [],
        "context": ctx,
        "rag_chunks": rag_chunks,
        "citations": citations,
        "recommendations": [],
        "booking_options": [],
        "response_message": "",
        "needs_clarification": False,
        "escalated": False,
    }
    state = {**state, **_agent2_fit(state)}
    if not state.get("escalated"):
        state = {**state, **_agent3_schedule(state)}
    state = {**state, **_safety_gate(state)}

    return ChatResponse(
        message=state.get("response_message", "") or "Recommendation ready — review slots and confirm.",
        context=state.get("context"),
        recommendations=state.get("recommendations", []),
        booking_options=state.get("booking_options", []),
        citations=state.get("citations", []),
        needs_clarification=False,
        escalated=state.get("escalated", False),
        safety_gate=state.get("safety_gate"),
        session_id=sid,
    )
