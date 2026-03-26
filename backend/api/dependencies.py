"""FastAPI dependency injection."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    replicate_api_token: str = ""
    storage_path: str = "./storage"
    cors_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_story_parser():
    from .services.story_parser import StoryParser
    settings = get_settings()
    return StoryParser(api_key=settings.anthropic_api_key)


def get_image_generator():
    from .services.image_generator import ImageGenerator
    settings = get_settings()
    return ImageGenerator(
        api_token=settings.replicate_api_token,
        storage_path=settings.storage_path,
    )


def get_concept_generator():
    from .services.concept_generator import ConceptGenerator
    settings = get_settings()
    return ConceptGenerator(api_key=settings.anthropic_api_key)


def get_db():
    pass  # placeholder for SQLAlchemy session
