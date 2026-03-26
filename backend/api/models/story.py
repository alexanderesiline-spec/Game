from enum import Enum
from sqlalchemy import Column, String, Text, JSON, Integer
from .base import Base, TimestampMixin


class StoryStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class ComicStyle(str, Enum):
    MANGA = "manga"          # B&W, screen tones, right-to-left
    MANHWA = "manhwa"        # Full color, webtoon vertical
    WESTERN = "western"      # Full color, traditional panels


class Story(Base, TimestampMixin):
    __tablename__ = "stories"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    style = Column(String, default=ComicStyle.MANHWA)
    source_type = Column(String, default="text")  # text | upload | concept
    status = Column(String, default=StoryStatus.PENDING)
    metadata = Column(JSON, default={})
