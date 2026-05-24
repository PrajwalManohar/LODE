from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class UrgencyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExperimentContext(BaseModel):
    material_type: str = ""
    analysis_goal: str = ""
    sample_dimensions: str = ""
    surface_condition: str = ""
    coating_status: str = ""
    urgency: UrgencyLevel = UrgencyLevel.MEDIUM
    deadline: Optional[str] = None
    researcher_name: str = ""
    researcher_email: str = ""
    research_group: str = ""
    trained_instruments: list[str] = Field(default_factory=list)
    notes: str = ""
    is_complete: bool = False
    clarifying_questions: list[str] = Field(default_factory=list)
    hazardous_materials: list[str] = Field(default_factory=list)
    hazmat_review_required: bool = False


class Citation(BaseModel):
    source: str
    section: str = ""
    page: str = ""
    excerpt: str = ""


class InstrumentFit(BaseModel):
    instrument_id: str
    instrument_name: str
    fit_score: int = Field(ge=0, le=100)
    grade: str
    rationale: str
    citations: list[Citation] = Field(default_factory=list)
    requires_training: bool = False
    prep_time_minutes: int = 0
    run_duration_minutes: int = 0
    confidence: int = Field(default=0, ge=0, le=100)


class BookingOption(BaseModel):
    instrument_id: str
    instrument_name: str
    start_time: datetime
    end_time: datetime
    prep_start: datetime
    rank: int
    score: float
    notes: str = ""


class ChatMessage(BaseModel):
    role: str
    content: str


class SafetyGateResult(BaseModel):
    passed: bool
    reasons: list[str] = Field(default_factory=list)
    requires_review: bool = False


class ChatResponse(BaseModel):
    message: str
    context: Optional[ExperimentContext] = None
    recommendations: list[InstrumentFit] = Field(default_factory=list)
    booking_options: list[BookingOption] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    needs_clarification: bool = False
    escalated: bool = False
    sop_path: Optional[str] = None
    safety_gate: Optional[SafetyGateResult] = None
    session_id: Optional[str] = None
    automations: dict = Field(default_factory=dict)


class PostRunReport(BaseModel):
    booking_id: int
    ran_as_planned: bool
    actual_parameters: str
    anomalies: str = ""
    data_quality_rating: int = Field(ge=1, le=5)
    notes: str = ""
    researcher_name: str = ""
