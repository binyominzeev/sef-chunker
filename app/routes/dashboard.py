"""Dashboard route."""
import logging
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path

from app.database import get_db
from app import models

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Render the main dashboard."""
    books = db.query(models.Book).all()
    active_book = books[0] if books else None
    chunk_count = 0
    today_chunk = None
    last_sent = 0

    if active_book:
        chunk_count = db.query(models.Chunk).filter(models.Chunk.book_id == active_book.id).count()
        progress = db.query(models.Progress).filter(models.Progress.book_id == active_book.id).first()
        if progress:
            last_sent = progress.last_sent_chunk
            next_chunk_num = last_sent + 1
            today_chunk = (
                db.query(models.Chunk)
                .filter(models.Chunk.book_id == active_book.id, models.Chunk.chunk_number == next_chunk_num)
                .first()
            )

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "active_book": active_book,
            "books": books,
            "chunk_count": chunk_count,
            "today_chunk": today_chunk,
            "last_sent": last_sent,
        },
    )


@router.post("/send-today", response_class=HTMLResponse)
async def send_today(request: Request, db: Session = Depends(get_db)):
    """Manually send today's chunk."""
    from app.services.scheduler import send_daily_chunk
    try:
        result = await send_daily_chunk(db)
        msg = result.get("message", "Sent successfully")
        alert_class = "success"
    except Exception:
        logger.exception("Failed to send today's chunk")
        msg = "An error occurred while sending today's chunk. Check the server logs for details."
        alert_class = "danger"
    return HTMLResponse(
        f'<div class="alert alert-{alert_class} alert-dismissible fade show" role="alert">'
        f'{msg}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>'
    )


@router.post("/test-telegram", response_class=HTMLResponse)
async def test_telegram(request: Request):
    """Test Telegram connection."""
    from app.services.telegram_service import send_message
    try:
        await send_message("📖 Test message from Sefaria Daily AI!")
        return HTMLResponse(
            '<div class="alert alert-success alert-dismissible fade show" role="alert">'
            'Telegram test successful!<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>'
        )
    except Exception:
        logger.exception("Telegram test failed")
        return HTMLResponse(
            '<div class="alert alert-danger alert-dismissible fade show" role="alert">'
            'Telegram test failed. Check the bot token/chat ID in Settings and the server logs for details.'
            '<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>'
        )
