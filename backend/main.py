"""
AI Comic Generator — FastAPI Backend
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from api.dependencies import get_settings
from api.routes import concepts, stories, comics

settings = get_settings()

app = FastAPI(
    title="AI Comic Generator API",
    description="Turn stories into manga/manhwa/comics using AI",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated comic files
storage = Path(settings.storage_path)
storage.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(storage)), name="files")

app.include_router(concepts.router, prefix="/api")
app.include_router(stories.router, prefix="/api")
app.include_router(comics.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
