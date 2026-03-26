"""Concept generator routes — persisted in DB, optionally auth'd."""

import uuid
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import ConceptSession, User
from ..auth import get_current_user_optional
from ..dependencies import get_db, get_concept_generator

log = logging.getLogger(__name__)
router = APIRouter(prefix="/concepts", tags=["concepts"])


class StartRequest(BaseModel):
    concept: str


class ContinueRequest(BaseModel):
    session_id: str
    message: str


class SessionResponse(BaseModel):
    session_id: str
    reply: str
    is_complete: bool
    story_data: dict | None = None
    message_count: int


@router.post("/start", response_model=SessionResponse)
async def start_concept(
    req: StartRequest,
    db: AsyncSession = Depends(get_db),
    generator=Depends(get_concept_generator),
    current_user: User | None = Depends(get_current_user_optional),
):
    if not req.concept.strip():
        raise HTTPException(400, "Concept cannot be empty")
    if len(req.concept) > 5000:
        raise HTTPException(400, "Concept too long. Max 5000 characters.")

    result = generator.start_session(req.concept)

    session = ConceptSession(
        id=str(uuid.uuid4()),
        user_id=current_user.id if current_user else None,
        messages=result["messages"],
        is_complete=result["is_complete"],
        story_data=result.get("story_data"),
    )
    db.add(session)
    await db.commit()

    return SessionResponse(
        session_id=session.id,
        reply=result["reply"],
        is_complete=result["is_complete"],
        story_data=result.get("story_data"),
        message_count=len(result["messages"]),
    )


@router.post("/continue", response_model=SessionResponse)
async def continue_concept(
    req: ContinueRequest,
    db: AsyncSession = Depends(get_db),
    generator=Depends(get_concept_generator),
):
    result_row = await db.execute(
        select(ConceptSession).where(ConceptSession.id == req.session_id)
    )
    session = result_row.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    if session.is_complete:
        raise HTTPException(400, "Session already complete")

    result = generator.continue_session(session.messages, req.message)

    session.messages = result["messages"]
    session.is_complete = result["is_complete"]
    if result.get("story_data"):
        session.story_data = result["story_data"]
    await db.commit()

    return SessionResponse(
        session_id=req.session_id,
        reply=result["reply"],
        is_complete=result["is_complete"],
        story_data=result.get("story_data"),
        message_count=len(result["messages"]),
    )


@router.get("/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ConceptSession).where(ConceptSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    return {
        "session_id": session.id,
        "messages": session.messages,
        "is_complete": session.is_complete,
        "story_data": session.story_data,
    }
