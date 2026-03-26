"""Dependency injection — settings, DB session, services."""

from functools import lru_cache
from typing import AsyncGenerator

from pydantic_settings import BaseSettings
from sqlalchemy.ext.asyncio import AsyncSession


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    replicate_api_token: str = ""
    storage_path: str = "./storage"
    database_url: str = "sqlite+aiosqlite:///./storage/panelforge.db"
    secret_key: str = "change-me-in-production-minimum-32-chars!!"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    cors_origins: list[str] = ["http://localhost:3000"]
    max_upload_mb: int = 50
    rate_limit_per_minute: int = 30

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    from .database import get_session_factory
    settings = get_settings()
    factory = get_session_factory(settings.database_url)
    async with factory() as session:
        yield session


def get_story_parser():
    from .services.story_parser import StoryParser
    return StoryParser(api_key=get_settings().anthropic_api_key)


def get_image_generator():
    from .services.image_generator import ImageGenerator
    s = get_settings()
    return ImageGenerator(api_token=s.replicate_api_token, storage_path=s.storage_path)


def get_concept_generator():
    from .services.concept_generator import ConceptGenerator
    return ConceptGenerator(api_key=get_settings().anthropic_api_key)


def get_assembler():
    from .services.comic_assembler import ComicAssembler
    return ComicAssembler(storage_path=get_settings().storage_path)
