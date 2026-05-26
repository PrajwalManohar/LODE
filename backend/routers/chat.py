from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from vein.agents.graph import run_confirm_graph, run_form_intake
from vein.agents.pipeline import parse_experiment_intake
from vein.models.experiment import BookingOption, ChatResponse, ExperimentContext, InstrumentFit

router = APIRouter()


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
    return parse_experiment_intake(req.message, req.history, req.context, session_id=req.session_id)


@router.post("/intake/form", response_model=ChatResponse)
def intake_form(req: FormIntakeRequest):
    """Form-based booking — same fit/schedule/safety pipeline as chat, but the
    structured context is supplied directly so no clarifying questions are
    needed. Confirms still go through `/chat/confirm`."""
    return run_form_intake(req.context, session_id=req.session_id)


@router.post("/confirm", response_model=ChatResponse)
def confirm(req: ConfirmRequest):
    return run_confirm_graph(req.context, req.option, req.recommendation, session_id=req.session_id)
