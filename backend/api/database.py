"""
Database setup — SQLAlchemy async with SQLite.
Easily swap DATABASE_URL to PostgreSQL for production.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import Column, String, Integer, Text, JSON, DateTime, Float, Boolean, ForeignKey
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
import uuid


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    credits = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Story(Base):
    __tablename__ = "stories"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    style = Column(String, default="manhwa")
    source_type = Column(String, default="text")
    created_at = Column(DateTime, default=datetime.utcnow)


class Comic(Base):
    __tablename__ = "comics"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    story_id = Column(String, ForeignKey("stories.id"), nullable=False)
    title = Column(String, nullable=False)
    style = Column(String, nullable=False)
    status = Column(String, default="queued")
    progress = Column(Integer, default=0)
    status_message = Column(String, default="Queued...")
    pages = Column(JSON, default=list)
    characters = Column(JSON, default=list)
    character_references = Column(JSON, default=dict)   # name -> image_url
    export_paths = Column(JSON, default=dict)
    error = Column(Text, nullable=True)
    credits_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConceptSession(Base):
    __tablename__ = "concept_sessions"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    messages = Column(JSON, default=list)
    story_data = Column(JSON, nullable=True)
    is_complete = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class StripeOrder(Base):
    __tablename__ = "stripe_orders"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    stripe_session_id = Column(String, unique=True, nullable=False)
    credits = Column(Integer, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    status = Column(String, default="pending")    # pending | paid | failed
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Engine + session factory ──────────────────────────────────────────────────

_engine = None
_session_factory = None


def get_engine(database_url: str):
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            database_url,
            echo=False,
            connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
        )
    return _engine


def get_session_factory(database_url: str):
    global _session_factory
    if _session_factory is None:
        engine = get_engine(database_url)
        _session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory


async def init_db(database_url: str):
    engine = get_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
