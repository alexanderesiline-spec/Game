"""Story routes — all scoped to authenticated user, persisted in DB."""

import uuid
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import Story, User
from ..auth import get_current_user
from ..dependencies import get_db, get_settings
from ..models.story import ComicStyle
from ..services.file_processor import extract_text_from_file

log = logging.getLogger(__name__)
router = APIRouter(prefix="/stories", tags=["stories"])


class CreateTextRequest(BaseModel):
    title: str
    content: str
    style: ComicStyle = ComicStyle.MANHWA


class StoryResponse(BaseModel):
    id: str
    title: str
    content_preview: str
    word_count: int
    style: str
    source_type: str


def _validate_content(content: str, title: str):
    if not title.strip():
        raise HTTPException(400, "Title cannot be empty")
    if not content.strip():
        raise HTTPException(400, "Content cannot be empty")
    if len(content) > 500_000:
        raise HTTPException(400, "Story too long. Max 500,000 characters.")


async def _save_story(db, user_id, title, content, style, source_type) -> Story:
    story = Story(
        id=str(uuid.uuid4()),
        user_id=user_id,
        title=title.strip(),
        content=content,
        style=style if isinstance(style, str) else style.value,
        source_type=source_type,
    )
    db.add(story)
    await db.commit()
    await db.refresh(story)
    return story


@router.post("/text", response_model=StoryResponse)
async def create_from_text(
    req: CreateTextRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _validate_content(req.content, req.title)
    story = await _save_story(db, current_user.id, req.title, req.content, req.style, "text")
    return StoryResponse(
        id=story.id, title=story.title,
        content_preview=story.content[:200],
        word_count=len(story.content.split()),
        style=story.style, source_type=story.source_type,
    )


@router.post("/upload", response_model=StoryResponse)
async def upload_story(
    title: str = Form(...),
    style: ComicStyle = Form(ComicStyle.MANHWA),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    allowed = {".txt", ".pdf", ".epub"}
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported file type. Allowed: {allowed}")

    # Size check
    content_bytes = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content_bytes) > max_bytes:
        raise HTTPException(400, f"File too large. Max {settings.max_upload_mb}MB.")

    upload_dir = Path(settings.storage_path) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = upload_dir / f"{uuid.uuid4()}{ext}"
    tmp_path.write_bytes(content_bytes)

    try:
        text = await extract_text_from_file(str(tmp_path), file.filename or "")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        log.error(f"File processing error: {e}")
        raise HTTPException(500, "Failed to process file")
    finally:
        tmp_path.unlink(missing_ok=True)

    if not text.strip():
        raise HTTPException(400, "No text could be extracted from the file")

    _validate_content(text, title)
    story = await _save_story(db, current_user.id, title, text, style, "upload")
    return StoryResponse(
        id=story.id, title=story.title,
        content_preview=story.content[:200],
        word_count=len(story.content.split()),
        style=story.style, source_type=story.source_type,
    )


@router.post("/from-concept", response_model=StoryResponse)
async def create_from_concept(
    req: CreateTextRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _validate_content(req.content, req.title)
    story = await _save_story(db, current_user.id, req.title, req.content, req.style, "concept")
    return StoryResponse(
        id=story.id, title=story.title,
        content_preview=story.content[:200],
        word_count=len(story.content.split()),
        style=story.style, source_type=story.source_type,
    )


@router.get("/{story_id}")
async def get_story(
    story_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Story).where(Story.id == story_id, Story.user_id == current_user.id)
    )
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(404, "Story not found")
    return {
        "id": story.id, "title": story.title, "content": story.content,
        "style": story.style, "source_type": story.source_type,
        "word_count": len(story.content.split()),
    }


@router.get("/")
async def list_stories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Story).where(Story.user_id == current_user.id).order_by(Story.created_at.desc())
    )
    stories = result.scalars().all()
    return [
        {"id": s.id, "title": s.title, "style": s.style,
         "word_count": len(s.content.split()), "source_type": s.source_type}
        for s in stories
    ]
