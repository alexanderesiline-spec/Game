"""
PanelForge — AI Comic Generator API
"""

import logging
import structlog
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from api.dependencies import get_settings
from api.database import init_db
from api.routes import concepts, stories, comics, billing
from api.routes.auth import router as auth_router

# ── Logging setup ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
log = structlog.get_logger()

# ── Rate limiter ──────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# ── App startup / shutdown ────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    Path(settings.storage_path).mkdir(parents=True, exist_ok=True)
    for sub in ("uploads", "comics", "panels", "characters"):
        (Path(settings.storage_path) / sub).mkdir(exist_ok=True)
    await init_db(settings.database_url)
    log.info("PanelForge started", storage=settings.storage_path)
    yield
    log.info("PanelForge shutting down")


settings = get_settings()

app = FastAPI(
    title="PanelForge API",
    description="Turn stories into manga/manhwa/comics using AI",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static file serving ───────────────────────────────────────────────────────

storage = Path(settings.storage_path)
storage.mkdir(parents=True, exist_ok=True)  # must exist before StaticFiles mount
app.mount("/files", StaticFiles(directory=str(storage)), name="files")

# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(auth_router,    prefix="/api")
app.include_router(concepts.router, prefix="/api")
app.include_router(stories.router,  prefix="/api")
app.include_router(comics.router,   prefix="/api")
app.include_router(billing.router,  prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


# ── Global error handler ──────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    log.error("Unhandled exception", path=request.url.path, error=str(exc), exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
