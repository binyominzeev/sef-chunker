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
    from app.services.summarizer import AISummarizer, PROMPT_PATH
    from app.services.telegram_service import send_message, format_daily_message
    from app.routes.settings import _get_setting

    book = db.query(models.Book).first()
    if not book:
        return {"message": "No book configured."}

    progress = db.query(models.Progress).filter(models.Progress.book_id == book.id).first()
    if not progress:
        progress = models.Progress(book_id=book.id, last_sent_chunk=0)
        db.add(progress)
        db.commit()

    next_chunk_num = progress.last_sent_chunk + 1
    total_chunks = db.query(models.Chunk).filter(models.Chunk.book_id == book.id).count()

    if next_chunk_num > total_chunks:
        return {"message": "All chunks have been sent. The reading is complete!"}

    chunk = (
        db.query(models.Chunk)
        .filter(models.Chunk.book_id == book.id, models.Chunk.chunk_number == next_chunk_num)
        .first()
    )
    if not chunk:
        return {"message": f"Chunk {next_chunk_num} not found."}

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
        day=next_chunk_num,
        total_days=total_chunks,
        start_ref=chunk.start_ref or "",
        end_ref=chunk.end_ref or "",
        summary=summary_obj.summary,
    )
    await send_message(message)

    progress.last_sent_chunk = next_chunk_num
    db.commit()
    logger.info("Sent chunk %d of %d for book '%s'", next_chunk_num, total_chunks, book.title)
    return {"message": f"Sent chunk {next_chunk_num} of {total_chunks}: {book.title}"}


def _parse_time(time_str: str) -> tuple[int, int]:
    """Parse HH:MM time string into (hour, minute) tuple."""
    try:
        parts = time_str.split(":")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        logger.warning("Invalid time string '%s', defaulting to 08:00", time_str)
        return 8, 0
