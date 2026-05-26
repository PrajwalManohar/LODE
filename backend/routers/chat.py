from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from vein.agents.graph import run_confirm_graph, run_form_intake
from vein.agents.pipeline import parse_experiment_intake
from vein.models.experiment import BookingOption, ChatResponse, ExperimentContext, InstrumentFit
from vein.services.guardrails import check_input
from vein.services.privacy import audit

router = APIRouter()


def _refuse_with(reasons: list[str]) -> ChatResponse:
    """Build a ChatResponse that the UI can render as a refusal."""
    return ChatResponse(
        message=("Your request was blocked by the input guardrail. "
                 "Reason(s): " + "; ".join(reasons) +
                 ". Rephrase without instructions targeted at the assistant or "
                 "sensitive identifiers (SSN, card, API key)."),
    )


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    context: Optional[ExperimentContext] = None
    session_id: Optional[str] = None


class FormIntakeRequest(BaseModel):
    context: ExperimentContext
    session_id: Optional[str] = None


class ConfirmRequest(BaseModel):
    context: ExperimentContext
    option: BookingOption
    recommendation: InstrumentFit
    session_id: Optional[str] = None


@router.post("/intake", response_model=ChatResponse)
def intake(req: ChatRequest):
    verdict = check_input(req.message)
    if verdict.refused:
        audit("guardrail.refuse", actor=None, subject=None, detail={"reasons": verdict.reasons})
        return _refuse_with(verdict.reasons)
    # Redacted (sanitised) input is used when guardrail flagged PII but allowed.
    message = verdict.sanitized or req.message
    return parse_experiment_intake(message, req.history, req.context, session_id=req.session_id)


@router.post("/intake/form", response_model=ChatResponse)
def intake_form(req: FormIntakeRequest):
    """Form-based booking — same fit/schedule/safety pipeline as chat, but the
    structured context is supplied directly so no clarifying questions are
    needed. Confirms still go through `/chat/confirm`."""
    return run_form_intake(req.context, session_id=req.session_id)


@router.post("/confirm", response_model=ChatResponse)
def confirm(req: ConfirmRequest):
    return run_confirm_graph(req.context, req.option, req.recommendation, session_id=req.session_id)
