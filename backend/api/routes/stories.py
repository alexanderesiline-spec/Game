"""Story management routes — upload, create, list stories."""

import uuid
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel

from ..services.file_processor import extract_text_from_file
from ..models.story import ComicStyle
from ..dependencies import get_settings

router = APIRouter(prefix="/stories", tags=["stories"])

# In-memory story store (replace with DB for production)
_stories: dict[str, dict] = {}


class CreateStoryRequest(BaseModel):
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


@router.post("/text", response_model=StoryResponse)
async def create_from_text(req: CreateStoryRequest):
    """Create a story from pasted text."""
    if not req.content.strip():
        raise HTTPException(400, "Content cannot be empty")

    story_id = str(uuid.uuid4())
    _stories[story_id] = {
        "id": story_id,
        "title": req.title,
        "content": req.content,
        "style": req.style.value,
        "source_type": "text",
    }

    return StoryResponse(
        id=story_id,
        title=req.title,
        content_preview=req.content[:200],
        word_count=len(req.content.split()),
        style=req.style.value,
        source_type="text",
    )


@router.post("/upload", response_model=StoryResponse)
async def upload_story(
    title: str = Form(...),
    style: ComicStyle = Form(ComicStyle.MANHWA),
    file: UploadFile = File(...),
    settings=Depends(get_settings),
):
    """Upload a story file (TXT, PDF, EPUB)."""
    allowed_extensions = {".txt", ".pdf", ".epub"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(400, f"Unsupported file type. Allowed: {allowed_extensions}")

    upload_dir = Path(settings.storage_path) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_id = str(uuid.uuid4())
    file_path = upload_dir / f"{file_id}{ext}"

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        text = await extract_text_from_file(str(file_path), file.filename)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to process file: {e}")

    if not text.strip():
        raise HTTPException(400, "Could not extract text from file")

    story_id = str(uuid.uuid4())
    _stories[story_id] = {
        "id": story_id,
        "title": title,
        "content": text,
        "style": style.value,
        "source_type": "upload",
        "original_filename": file.filename,
    }

    return StoryResponse(
        id=story_id,
        title=title,
        content_preview=text[:200],
        word_count=len(text.split()),
        style=style.value,
        source_type="upload",
    )


@router.post("/from-concept", response_model=StoryResponse)
async def create_from_concept(
    title: str,
    content: str,
    style: ComicStyle = ComicStyle.MANHWA,
):
    """Create a story from a generated concept's prose draft."""
    story_id = str(uuid.uuid4())
    _stories[story_id] = {
        "id": story_id,
        "title": title,
        "content": content,
        "style": style.value,
        "source_type": "concept",
    }

    return StoryResponse(
        id=story_id,
        title=title,
        content_preview=content[:200],
        word_count=len(content.split()),
        style=style.value,
        source_type="concept",
    )


@router.get("/{story_id}")
async def get_story(story_id: str):
    story = _stories.get(story_id)
    if not story:
        raise HTTPException(404, "Story not found")
    return story


@router.get("/")
async def list_stories():
    return [
        {
            "id": s["id"],
            "title": s["title"],
            "word_count": len(s["content"].split()),
            "style": s["style"],
            "source_type": s["source_type"],
        }
        for s in _stories.values()
    ]


def get_story_by_id(story_id: str) -> dict:
    story = _stories.get(story_id)
    if not story:
        raise HTTPException(404, "Story not found")
    return story
