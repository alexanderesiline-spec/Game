"""
Comic generation routes with:
- Auth (credits deducted per comic)
- Real DB persistence
- WebSocket progress updates
- Proper error handling
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import Comic, Story, User
from ..auth import get_current_user
from ..dependencies import get_db, get_story_parser, get_image_generator, get_assembler, get_settings
from ..models.story import ComicStyle

log = logging.getLogger(__name__)
router = APIRouter(prefix="/comics", tags=["comics"])

CREDITS_PER_COMIC = 1

# WebSocket connection manager
class _WSManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, comic_id: str, ws: WebSocket):
        await ws.accept()
        self._connections.setdefault(comic_id, []).append(ws)

    def disconnect(self, comic_id: str, ws: WebSocket):
        if comic_id in self._connections:
            self._connections[comic_id].discard(ws) if hasattr(self._connections[comic_id], 'discard') else None
            try:
                self._connections[comic_id].remove(ws)
            except ValueError:
                pass

    async def broadcast(self, comic_id: str, data: dict):
        for ws in list(self._connections.get(comic_id, [])):
            try:
                await ws.send_json(data)
            except Exception:
                pass


ws_manager = _WSManager()


# ── Schemas ───────────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    story_id: str
    title: str | None = None
    style: ComicStyle = ComicStyle.MANHWA
    quality: str = "standard"
    include_text_overlays: bool = True


class ComicResponse(BaseModel):
    id: str
    story_id: str
    title: str
    style: str
    status: str
    progress: int
    status_message: str
    page_count: int
    error: str | None = None
    created_at: datetime


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=ComicResponse)
async def generate_comic(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    # Check credits
    if current_user.credits < CREDITS_PER_COMIC:
        raise HTTPException(402, f"Insufficient credits. You need {CREDITS_PER_COMIC}, you have {current_user.credits}.")

    # Verify story belongs to user
    result = await db.execute(
        select(Story).where(Story.id == req.story_id, Story.user_id == current_user.id)
    )
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(404, "Story not found")

    title = req.title or story.title

    # Deduct credits immediately (prevent double-spend)
    current_user.credits -= CREDITS_PER_COMIC

    comic = Comic(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        story_id=story.id,
        title=title,
        style=req.style.value,
        status="queued",
        progress=0,
        status_message="Queued — starting shortly...",
        credits_used=CREDITS_PER_COMIC,
    )
    db.add(comic)
    await db.commit()
    await db.refresh(comic)

    log.info(f"Comic {comic.id} queued for user {current_user.id}")

    background_tasks.add_task(
        _run_pipeline,
        comic_id=comic.id,
        story_content=story.content,
        style=req.style,
        quality=req.quality,
        include_text=req.include_text_overlays,
        settings=settings,
    )

    return ComicResponse(
        id=comic.id,
        story_id=story.id,
        title=title,
        style=req.style.value,
        status="queued",
        progress=0,
        status_message="Queued...",
        page_count=0,
        created_at=comic.created_at,
    )


@router.get("/{comic_id}", response_model=ComicResponse)
async def get_comic(
    comic_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    comic = await _get_comic_or_404(comic_id, current_user.id, db)
    return ComicResponse(
        id=comic.id,
        story_id=comic.story_id,
        title=comic.title,
        style=comic.style,
        status=comic.status,
        progress=comic.progress,
        status_message=comic.status_message or "",
        page_count=len(comic.pages or []),
        error=comic.error,
        created_at=comic.created_at,
    )


@router.get("/{comic_id}/pages")
async def get_comic_pages(
    comic_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    comic = await _get_comic_or_404(comic_id, current_user.id, db)
    return {
        "id": comic.id,
        "title": comic.title,
        "style": comic.style,
        "status": comic.status,
        "pages": comic.pages or [],
        "characters": comic.characters or [],
        "character_references": comic.character_references or {},
        "export_paths": comic.export_paths or {},
    }


@router.get("/")
async def list_comics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Comic).where(Comic.user_id == current_user.id).order_by(Comic.created_at.desc())
    )
    comics = result.scalars().all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "style": c.style,
            "status": c.status,
            "progress": c.progress,
            "page_count": len(c.pages or []),
            "created_at": c.created_at,
        }
        for c in comics
    ]


@router.websocket("/{comic_id}/ws")
async def comic_progress_ws(comic_id: str, websocket: WebSocket):
    """WebSocket endpoint — client subscribes and receives live progress updates."""
    await ws_manager.connect(comic_id, websocket)
    try:
        while True:
            # Keep connection alive; server pushes updates via ws_manager.broadcast
            await asyncio.sleep(30)
            await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        ws_manager.disconnect(comic_id, websocket)


# ── Pipeline ──────────────────────────────────────────────────────────────────

async def _update(comic_id: str, status: str, progress: int, message: str, **extra):
    """Update comic in DB and push to WebSocket subscribers."""
    from .comics import ws_manager
    from ..database import get_session_factory
    from ..dependencies import get_settings

    settings = get_settings()
    factory = get_session_factory(settings.database_url)
    async with factory() as db:
        result = await db.execute(select(Comic).where(Comic.id == comic_id))
        comic = result.scalar_one_or_none()
        if comic:
            comic.status = status
            comic.progress = progress
            comic.status_message = message
            for k, v in extra.items():
                setattr(comic, k, v)
            await db.commit()

    await ws_manager.broadcast(comic_id, {
        "type": "progress",
        "status": status,
        "progress": progress,
        "message": message,
        **extra,
    })


async def _run_pipeline(
    comic_id: str,
    story_content: str,
    style: ComicStyle,
    quality: str,
    include_text: bool,
    settings,
):
    from .comics import _update
    from ..services.story_parser import StoryParser
    from ..services.image_generator import ImageGenerator
    from ..services.comic_assembler import ComicAssembler
    from ..database import get_session_factory

    parser = StoryParser(api_key=settings.anthropic_api_key)
    generator = ImageGenerator(api_token=settings.replicate_api_token, storage_path=settings.storage_path)
    assembler = ComicAssembler(storage_path=settings.storage_path)

    try:
        # Step 1: Extract characters
        await _update(comic_id, "parsing", 5, "Extracting characters...")
        char_data = parser.extract_characters(story_content)
        characters = char_data.get("characters", [])
        log.info(f"[{comic_id}] Found {len(characters)} characters")

        # Step 2: Parse scenes
        await _update(comic_id, "parsing", 18, "Breaking story into panels...")
        scene_data = parser.parse_scenes(story_content, style=style, characters=characters)
        pages_raw = scene_data.get("pages", [])
        log.info(f"[{comic_id}] Generated {len(pages_raw)} pages")

        # Step 3: Character reference images (for consistency)
        await _update(comic_id, "generating", 28, "Generating character references...")
        char_refs: dict[str, str] = {}
        main_chars = [c for c in characters if c.get("role") in ("protagonist", "antagonist")][:3]

        async def gen_ref(char):
            try:
                ref = await generator.generate_character_reference(char, style.value)
                char_refs[char["name"]] = ref["url"]
            except Exception as e:
                log.warning(f"[{comic_id}] Reference for {char.get('name')} failed: {e}")

        await asyncio.gather(*[gen_ref(c) for c in main_chars])

        # Step 4: Enrich prompts + generate all panels
        all_panels = [p for page in pages_raw for p in page.get("panels", [])]
        for panel in all_panels:
            panel["image_generation_prompt"] = parser.build_panel_prompt(panel, characters, style)

        total = len(all_panels)
        await _update(comic_id, "generating", 32, f"Generating {total} panels...")

        async def progress_cb(done: int, total_: int):
            pct = 32 + int((done / max(total_, 1)) * 50)
            await _update(comic_id, "generating", pct, f"Generating panels ({done}/{total_})...")

        generated_panels = await generator.generate_panels_batch(
            panels=all_panels,
            style=style.value,
            character_references=char_refs,
            quality=quality,
            concurrency=3,
            progress_callback=progress_cb,
        )

        # Reassemble panels back into pages
        idx = 0
        for page in pages_raw:
            count = len(page.get("panels", []))
            page["panels"] = generated_panels[idx: idx + count]
            idx += count

        # Step 5: Assemble pages
        await _update(comic_id, "assembling", 84, "Assembling pages...")
        assembled = []
        for page_data in pages_raw:
            img = await assembler.assemble_page(page_data, style.value, add_text=include_text)
            assembled.append(img)

        # Step 6: Export
        await _update(comic_id, "assembling", 93, "Exporting files...")
        export_paths: dict[str, str] = {}

        cbz = await assembler.export_cbz(comic_id, assembled)
        export_paths["cbz"] = cbz

        if style == ComicStyle.MANHWA:
            strip = await assembler.export_webp_strip(comic_id, assembled)
            export_paths["webp_strip"] = strip

        # Final DB update
        factory = get_session_factory(settings.database_url)
        async with factory() as db:
            result = await db.execute(select(Comic).where(Comic.id == comic_id))
            comic = result.scalar_one_or_none()
            if comic:
                comic.status = "complete"
                comic.progress = 100
                comic.status_message = "Done!"
                comic.pages = pages_raw
                comic.characters = characters
                comic.character_references = char_refs
                comic.export_paths = export_paths
                await db.commit()

        await ws_manager.broadcast(comic_id, {
            "type": "complete",
            "status": "complete",
            "progress": 100,
            "message": "Done!",
        })
        log.info(f"[{comic_id}] Generation complete")

    except Exception as e:
        log.exception(f"[{comic_id}] Pipeline failed: {e}")
        factory = get_session_factory(settings.database_url)
        async with factory() as db:
            result = await db.execute(select(Comic).where(Comic.id == comic_id))
            comic = result.scalar_one_or_none()
            if comic:
                comic.status = "failed"
                comic.error = str(e)
                comic.status_message = "Generation failed"
                await db.commit()
        await ws_manager.broadcast(comic_id, {
            "type": "error",
            "status": "failed",
            "message": str(e),
        })


async def _get_comic_or_404(comic_id: str, user_id: str, db: AsyncSession) -> Comic:
    result = await db.execute(
        select(Comic).where(Comic.id == comic_id, Comic.user_id == user_id)
    )
    comic = result.scalar_one_or_none()
    if not comic:
        raise HTTPException(404, "Comic not found")
    return comic
