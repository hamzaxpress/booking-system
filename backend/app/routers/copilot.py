from typing import List, Optional

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_staff
from app.models.models import User
from app.services.copilot import answer_admin_question, answer_tracking_question


router = APIRouter(prefix="/copilot", tags=["Logi-Copilot"])


class CopilotMessage(BaseModel):
    role: str = Field(..., pattern="^(user|bot)$")
    text: str = Field(..., min_length=1, max_length=800)


class CopilotQuestion(BaseModel):
    question: str = Field(..., min_length=3, max_length=300)
    messages: Optional[List[CopilotMessage]] = None


class CopilotTrackQuestion(BaseModel):
    docket_number: str = Field(..., min_length=6, max_length=40)
    question: str = Field(..., min_length=3, max_length=300)
    messages: Optional[List[CopilotMessage]] = None


@router.post("/admin")
async def copilot_admin(
    payload: CopilotQuestion,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    history = [m.model_dump() for m in (payload.messages or [])]
    return await answer_admin_question(db, payload.question, current_user.role, history)


@router.post("/track")
async def copilot_track(payload: CopilotTrackQuestion, db: Session = Depends(get_db)):
    history = [m.model_dump() for m in (payload.messages or [])]
    return await answer_tracking_question(db, payload.docket_number, payload.question, history)
