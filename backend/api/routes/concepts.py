"""Concept generator routes — interactive Q&A to build story concepts."""

import uuid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..services.concept_generator import ConceptGenerator
from ..dependencies import get_concept_generator, get_db

router = APIRouter(prefix="/concepts", tags=["concepts"])


class StartConceptRequest(BaseModel):
    concept: str


class ContinueConceptRequest(BaseModel):
    session_id: str
    message: str


class ConceptSessionResponse(BaseModel):
    session_id: str
    reply: str
    is_complete: bool
    story_data: dict | None = None
    message_count: int


# In-memory session store (replace with Redis for production)
_sessions: dict[str, dict] = {}


@router.post("/start", response_model=ConceptSessionResponse)
async def start_concept(
    req: StartConceptRequest,
    generator: ConceptGenerator = Depends(get_concept_generator),
):
    """Start a new concept development session."""
    if not req.concept.strip():
        raise HTTPException(400, "Concept cannot be empty")

    result = generator.start_session(req.concept)
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "messages": result["messages"],
        "is_complete": False,
        "story_data": None,
    }

    return ConceptSessionResponse(
        session_id=session_id,
        reply=result["reply"],
        is_complete=False,
        message_count=len(result["messages"]),
    )


@router.post("/continue", response_model=ConceptSessionResponse)
async def continue_concept(
    req: ContinueConceptRequest,
    generator: ConceptGenerator = Depends(get_concept_generator),
):
    """Continue a concept development Q&A session."""
    session = _sessions.get(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    if session["is_complete"]:
        raise HTTPException(400, "This session is already complete")

    result = generator.continue_session(session["messages"], req.message)

    session["messages"] = result["messages"]
    session["is_complete"] = result["is_complete"]
    session["story_data"] = result["story_data"]

    return ConceptSessionResponse(
        session_id=req.session_id,
        reply=result["reply"],
        is_complete=result["is_complete"],
        story_data=result["story_data"],
        message_count=len(result["messages"]),
    )


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get the current state of a concept session."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return {
        "session_id": session_id,
        "messages": session["messages"],
        "is_complete": session["is_complete"],
        "story_data": session["story_data"],
    }
