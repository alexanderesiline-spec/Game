"""
Comic generation routes — the main pipeline endpoint.

POST /comics/generate  → starts generation job
GET  /comics/{id}      → job status + progress
GET  /comics/{id}/pages → assembled pages data
GET  /comics/          → list all comics
"""

import uuid
import asyncio
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import Any

from ..models.story import ComicStyle
from ..models.comic import ComicStatus
from ..services.story_parser import StoryParser
from ..services.image_generator import ImageGenerator
from ..services.comic_assembler import ComicAssembler
from ..dependencies import get_story_parser, get_image_generator, get_settings
from .stories import get_story_by_id

router = APIRouter(prefix="/comics", tags=["comics"])

# In-memory comic store
_comics: dict[str, dict] = {}


class GenerateComicRequest(BaseModel):
    story_id: str
    title: str | None = None
    style: ComicStyle = ComicStyle.MANHWA
    quality: str = "standard"   # standard | high
    include_text_overlays: bool = True


class ComicStatusResponse(BaseModel):
    id: str
    story_id: str
    title: str
    style: str
    status: str
    progress: int
    page_count: int
    error: str | None = None


@router.post("/generate", response_model=ComicStatusResponse)
async def generate_comic(
    req: GenerateComicRequest,
    background_tasks: BackgroundTasks,
    parser: StoryParser = Depends(get_story_parser),
    generator: ImageGenerator = Depends(get_image_generator),
    settings=Depends(get_settings),
):
    """Start comic generation for a story."""
    story = get_story_by_id(req.story_id)

    comic_id = str(uuid.uuid4())
    title = req.title or story["title"]
    style = req.style or ComicStyle(story["style"])

    _comics[comic_id] = {
        "id": comic_id,
        "story_id": req.story_id,
        "title": title,
        "style": style.value,
        "status": ComicStatus.QUEUED,
        "progress": 0,
        "pages": [],
        "characters": [],
        "export_paths": {},
        "error": None,
    }

    background_tasks.add_task(
        run_generation_pipeline,
        comic_id=comic_id,
        story=story,
        style=style,
        quality=req.quality,
        include_text=req.include_text_overlays,
        parser=parser,
        generator=generator,
        assembler=ComicAssembler(settings.storage_path),
    )

    return ComicStatusResponse(
        id=comic_id,
        story_id=req.story_id,
        title=title,
        style=style.value,
        status=ComicStatus.QUEUED,
        progress=0,
        page_count=0,
    )


@router.get("/{comic_id}", response_model=ComicStatusResponse)
async def get_comic(comic_id: str):
    comic = _comics.get(comic_id)
    if not comic:
        raise HTTPException(404, "Comic not found")
    return ComicStatusResponse(
        id=comic["id"],
        story_id=comic["story_id"],
        title=comic["title"],
        style=comic["style"],
        status=comic["status"],
        progress=comic["progress"],
        page_count=len(comic["pages"]),
        error=comic.get("error"),
    )


@router.get("/{comic_id}/pages")
async def get_comic_pages(comic_id: str):
    """Get all page/panel data for a completed comic."""
    comic = _comics.get(comic_id)
    if not comic:
        raise HTTPException(404, "Comic not found")
    return {
        "id": comic_id,
        "title": comic["title"],
        "style": comic["style"],
        "status": comic["status"],
        "pages": comic["pages"],
        "characters": comic["characters"],
        "export_paths": comic.get("export_paths", {}),
    }


@router.get("/")
async def list_comics():
    return [
        {
            "id": c["id"],
            "title": c["title"],
            "style": c["style"],
            "status": c["status"],
            "progress": c["progress"],
            "page_count": len(c["pages"]),
        }
        for c in _comics.values()
    ]


async def run_generation_pipeline(
    comic_id: str,
    story: dict,
    style: ComicStyle,
    quality: str,
    include_text: bool,
    parser: StoryParser,
    generator: ImageGenerator,
    assembler: ComicAssembler,
):
    """Full generation pipeline — runs in background."""
    comic = _comics[comic_id]

    try:
        # Step 1: Extract characters
        comic["status"] = ComicStatus.PARSING
        comic["progress"] = 5
        char_data = parser.extract_characters(story["content"])
        characters = char_data.get("characters", [])
        comic["characters"] = characters

        # Step 2: Parse scenes into panel/page structure
        comic["progress"] = 20
        scene_data = parser.parse_scenes(
            story["content"],
            style=style,
            characters=characters,
        )
        pages_raw = scene_data.get("pages", [])

        # Step 3: Generate character reference images for consistency
        comic["status"] = ComicStatus.GENERATING
        comic["progress"] = 30

        character_references: dict[str, str] = {}
        main_chars = [c for c in characters if c.get("role") in ("protagonist", "antagonist")][:3]
        for char in main_chars:
            try:
                ref = await generator.generate_character_reference(char, style.value)
                character_references[char["name"]] = ref["url"]
            except Exception:
                pass  # Reference generation is best-effort

        # Step 4: Generate all panel images
        all_panels = [p for page in pages_raw for p in page.get("panels", [])]
        total = len(all_panels)
        generated_count = 0

        async def progress_cb(done: int, total_: int):
            nonlocal generated_count
            generated_count = done
            pct = 30 + int((done / max(total_, 1)) * 50)
            comic["progress"] = pct

        # Enrich prompts using parser helper
        for panel in all_panels:
            panel["image_generation_prompt"] = parser.refine_panel_prompt(
                panel, characters, style
            )

        generated_panels = await generator.generate_panels_batch(
            panels=all_panels,
            style=style.value,
            character_references=character_references,
            concurrency=3,
            progress_callback=progress_cb,
        )

        # Reassemble into pages
        panel_idx = 0
        for page in pages_raw:
            page_panel_count = len(page.get("panels", []))
            page["panels"] = generated_panels[panel_idx : panel_idx + page_panel_count]
            panel_idx += page_panel_count

        # Step 5: Assemble pages
        comic["status"] = ComicStatus.ASSEMBLING
        comic["progress"] = 82

        assembled_pages = []
        for page_data in pages_raw:
            img = await assembler.assemble_page(page_data, style.value, add_text=include_text)
            assembled_pages.append(img)

        # Step 6: Export
        comic["progress"] = 92
        cbz_path = await assembler.export_cbz(comic_id, assembled_pages)
        export_paths = {"cbz": cbz_path}

        if style == ComicStyle.MANHWA:
            strip_path = await assembler.export_webp_strip(comic_id, assembled_pages)
            export_paths["webp_strip"] = strip_path

        # Finalize
        comic["pages"] = pages_raw
        comic["export_paths"] = export_paths
        comic["status"] = ComicStatus.COMPLETE
        comic["progress"] = 100

    except Exception as e:
        comic["status"] = ComicStatus.FAILED
        comic["error"] = str(e)
        raise
