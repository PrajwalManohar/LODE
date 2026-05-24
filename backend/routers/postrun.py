from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from vein.agents.graph import run_postrun_graph
from vein.models.experiment import PostRunReport


router = APIRouter()


class PostRunRequest(PostRunReport):
    session_id: Optional[str] = None


@router.post("")
def submit_report(report: PostRunRequest):
    return run_postrun_graph(report, session_id=report.session_id)
