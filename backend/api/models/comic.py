from enum import Enum
from sqlalchemy import Column, String, Text, JSON, Integer, ForeignKey
from .base import Base, TimestampMixin


class ComicStatus(str, Enum):
    QUEUED = "queued"
    PARSING = "parsing"
    PLANNING = "planning"
    GENERATING = "generating"
    ASSEMBLING = "assembling"
    COMPLETE = "complete"
    FAILED = "failed"


class Comic(Base, TimestampMixin):
    __tablename__ = "comics"

    id = Column(String, primary_key=True)
    story_id = Column(String, ForeignKey("stories.id"), nullable=False)
    title = Column(String, nullable=False)
    style = Column(String, nullable=False)
    status = Column(String, default=ComicStatus.QUEUED)
    progress = Column(Integer, default=0)
    pages = Column(JSON, default=[])          # list of page objects with panel data
    characters = Column(JSON, default=[])     # extracted character sheets
    export_path = Column(String, nullable=True)
    error = Column(Text, nullable=True)
    generation_config = Column(JSON, default={})


class ConceptSession(Base, TimestampMixin):
    __tablename__ = "concept_sessions"

    id = Column(String, primary_key=True)
    messages = Column(JSON, default=[])       # Q&A conversation history
    story_draft = Column(Text, nullable=True)
    is_complete = Column(Integer, default=0)
