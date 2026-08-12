"""SQLAlchemy ORM models."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.database import Base


def _utcnow() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    sefaria_ref = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime, default=_utcnow)

    chunks = relationship("Chunk", back_populates="book", cascade="all, delete-orphan")
    progress = relationship("Progress", back_populates="book", uselist=False, cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    chunk_number = Column(Integer, nullable=False)
    start_ref = Column(String(255))
    end_ref = Column(String(255))
    hebrew_text = Column(Text, nullable=False)
    estimated_tokens = Column(Integer, default=0)

    book = relationship("Book", back_populates="chunks")
    summaries = relationship("Summary", back_populates="chunk", cascade="all, delete-orphan")


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(Integer, ForeignKey("chunks.id"), nullable=False)
    prompt = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    generated_at = Column(DateTime, default=_utcnow)
    model = Column(String(100), default="gpt-4o-mini")
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)

    chunk = relationship("Chunk", back_populates="summaries")


class Progress(Base):
    __tablename__ = "progress"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    last_sent_chunk = Column(Integer, default=0)

    book = relationship("Book", back_populates="progress")


class AppSettings(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), nullable=False, unique=True)
    value = Column(Text, default="")
