"""APScheduler-based daily sending scheduler."""
import logging
from datetime import datetime
from typing import Any, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None
JOB_ID = "daily_send"


def start_scheduler() -> None:
    """Initialize and start the APScheduler."""
    global _scheduler
    from app.config import get_settings
    settings = get_settings()
    hour, minute = _parse_time(settings.daily_send_time)
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _scheduled_send,
        CronTrigger(hour=hour, minute=minute),
        id=JOB_ID,
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started: daily send at %02d:%02d", hour, minute)


def stop_scheduler() -> None:
    """Stop the scheduler gracefully."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def reschedule(time_str: str) -> None:
    """Reschedule the daily job to a new time."""
    global _scheduler
    if not _scheduler:
        return
    hour, minute = _parse_time(time_str)
    _scheduler.reschedule_job(JOB_ID, trigger=CronTrigger(hour=hour, minute=minute))
    logger.info("Rescheduled daily send to %02d:%02d", hour, minute)


async def _scheduled_send() -> None:
    db = SessionLocal()
    try:
        result = await send_daily_chunk(db)
        logger.info("Scheduled send result: %s", result.get("message"))
    except Exception:
        logger.exception("Scheduled send failed")
    finally:
        db.close()


async def send_daily_chunk(db: Session) -> dict[str, Any]:
    """Determine next chunk, generate summary if needed, and send via Telegram.

    Args:
        db: SQLAlchemy session.

    Returns:
        Dictionary with 'message' key describing the result.
    """
    from app.routes.settings import _get_setting

    book = db.query(models.Book).first()
    if not book:
        return {"message": "No book configured."}

    progress = db.query(models.Progress).filter(models.Progress.book_id == book.id).first()
    if not progress:
        progress = models.Progress(book_id=book.id, last_sent_chunk=0)
        db.add(progress)
        db.commit()

    scheduled_setting_key = f"next_chunk_{book.id}"
    scheduled_chunk = _get_setting(db, scheduled_setting_key)
    try:
        next_chunk_num = int(scheduled_chunk) if scheduled_chunk else progress.last_sent_chunk + 1
    except ValueError:
        next_chunk_num = progress.last_sent_chunk + 1

    total_chunks = db.query(models.Chunk).filter(models.Chunk.book_id == book.id).count()

    if next_chunk_num > total_chunks:
        return {"message": "All chunks have been sent. The reading is complete!"}

    return await _send_chunk(db, book, next_chunk_num, total_chunks, advance_progress=True)


async def send_chunk(db: Session, chunk_number: int) -> dict[str, Any]:
    """Send an existing chunk without changing the daily progress."""
    book = db.query(models.Book).first()
    if not book:
        return {"message": "No book configured."}
    total_chunks = db.query(models.Chunk).filter(models.Chunk.book_id == book.id).count()
    if chunk_number < 1 or chunk_number > total_chunks:
        return {"message": f"Chunk {chunk_number} not found."}
    return await _send_chunk(db, book, chunk_number, total_chunks, advance_progress=False)


async def _send_chunk(
    db: Session,
    book: models.Book,
    chunk_number: int,
    total_chunks: int,
    advance_progress: bool,
) -> dict[str, Any]:
    from app.services.summarizer import AISummarizer, PROMPT_PATH
    from app.services.telegram_service import send_message, format_daily_message
    from app.routes.settings import _get_setting, _set_setting

    chunk = (
        db.query(models.Chunk)
        .filter(models.Chunk.book_id == book.id, models.Chunk.chunk_number == chunk_number)
        .first()
    )
    if not chunk:
        return {"message": f"Chunk {chunk_number} not found."}

    next_chunk = (
        db.query(models.Chunk)
        .filter(
            models.Chunk.book_id == book.id,
            models.Chunk.chunk_number == chunk_number + 1,
        )
        .first()
    )

    # Get or generate summary
    summary_obj = (
        db.query(models.Summary)
        .filter(models.Summary.chunk_id == chunk.id)
        .order_by(models.Summary.generated_at.desc())
        .first()
    )
    if not summary_obj:
        model = _get_setting(db, "default_model") or "gpt-4o-mini"
        summarizer = AISummarizer()
        result = await summarizer.generate(chunk.hebrew_text, model=model)
        prompt_text = PROMPT_PATH.read_text(encoding="utf-8") if PROMPT_PATH.exists() else "{text}"
        summary_obj = models.Summary(
            chunk_id=chunk.id,
            prompt=prompt_text,
            summary=result["summary"],
            model=model,
            input_tokens=result.get("input_tokens", 0),
            output_tokens=result.get("output_tokens", 0),
            cost_usd=result.get("cost_usd", 0.0),
        )
        db.add(summary_obj)
        db.commit()

    message = format_daily_message(
        book_title=book.title,
        day=chunk_number,
        total_days=total_chunks,
        start_ref=chunk.start_ref or "",
        end_ref=chunk.end_ref or "",
        next_start_ref=next_chunk.start_ref if next_chunk else None,
        summary=summary_obj.summary,
    )
    await send_message(message)

    if advance_progress:
        progress = db.query(models.Progress).filter(models.Progress.book_id == book.id).first()
        if not progress:
            progress = models.Progress(book_id=book.id, last_sent_chunk=0)
            db.add(progress)
        progress.last_sent_chunk = chunk_number
        _set_setting(db, f"next_chunk_{book.id}", str(chunk_number + 1))
        db.commit()
    logger.info("Sent chunk %d of %d for book '%s'", chunk_number, total_chunks, book.title)
    return {"message": f"Sent chunk {chunk_number} of {total_chunks}: {book.title}"}


def _parse_time(time_str: str) -> tuple[int, int]:
    """Parse HH:MM time string into (hour, minute) tuple."""
    try:
        parts = time_str.split(":")
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"Out of range: {hour}:{minute:02d}")
        return hour, minute
    except (ValueError, IndexError):
        logger.warning("Invalid time string '%s', defaulting to 08:00", time_str)
        return 8, 0
