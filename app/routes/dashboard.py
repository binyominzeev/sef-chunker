"""Dashboard route."""
import logging
from fastapi import APIRouter, Request, Depends, Form
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
    from app.routes.settings import _get_setting
    active_book_id = _get_setting(db, "active_book_id")
    active_book = None
    if active_book_id:
        try:
            active_book = db.query(models.Book).filter(models.Book.id == int(active_book_id)).first()
        except ValueError:
            pass
    active_book = active_book or (books[0] if books else None)
    chunk_count = 0
    today_chunk = None
    scheduled_chunk = None
    last_sent = 0
    send_time = "08:00"

    if active_book:
        send_time = _get_setting(db, "daily_send_time") or "08:00"
        chunk_count = db.query(models.Chunk).filter(models.Chunk.book_id == active_book.id).count()
        progress = db.query(models.Progress).filter(models.Progress.book_id == active_book.id).first()
        next_chunk_num = 1
        if progress:
            last_sent = progress.last_sent_chunk
            next_chunk_num = last_sent + 1
            today_chunk = (
                db.query(models.Chunk)
                .filter(models.Chunk.book_id == active_book.id, models.Chunk.chunk_number == next_chunk_num)
                .first()
            )
        scheduled_value = _get_setting(db, f"next_chunk_{active_book.id}")
        try:
            scheduled_number = int(scheduled_value) if scheduled_value else next_chunk_num
        except ValueError:
            scheduled_number = next_chunk_num
        scheduled_chunk = (
            db.query(models.Chunk)
            .filter(
                models.Chunk.book_id == active_book.id,
                models.Chunk.chunk_number == scheduled_number,
            )
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
            "scheduled_chunk": scheduled_chunk,
            "send_time": send_time,
        },
    )


@router.post("/set-active-book", response_class=HTMLResponse)
async def set_active_book(book_id: int = Form(...), db: Session = Depends(get_db)):
    """Set the book used by the dashboard and daily sender."""
    from app.routes.settings import _set_setting

    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book:
        return HTMLResponse('<div class="alert alert-danger">A kiválasztott könyv nem található.</div>')
    _set_setting(db, "active_book_id", str(book.id))
    db.commit()
    return HTMLResponse(f'<div class="alert alert-success">Aktív könyv: {book.title}</div>')


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


@router.post("/send-chunk", response_class=HTMLResponse)
async def send_chunk_for_test(chunk_number: int = Form(...), db: Session = Depends(get_db)):
    """Send a selected existing chunk without advancing the schedule."""
    from app.services.scheduler import send_chunk
    try:
        result = await send_chunk(db, chunk_number)
        return HTMLResponse(f'<div class="alert alert-success">Tesztküldés: {result["message"]}</div>')
    except Exception:
        logger.exception("Failed to send test chunk %s", chunk_number)
        return HTMLResponse('<div class="alert alert-danger">A tesztküldés nem sikerült. Ellenőrizd a beállításokat és a naplót.</div>')


@router.post("/set-next-chunk", response_class=HTMLResponse)
async def set_next_chunk(chunk_number: int = Form(...), db: Session = Depends(get_db)):
    """Set which chunk the next scheduled send should deliver."""
    from app.routes.settings import _get_setting, _set_setting
    active_book_id = _get_setting(db, "active_book_id")
    book = None
    if active_book_id:
        try:
            book = db.query(models.Book).filter(models.Book.id == int(active_book_id)).first()
        except ValueError:
            pass
    book = book or db.query(models.Book).first()
    if not book:
        return HTMLResponse('<div class="alert alert-danger">Nincs aktív könyv.</div>')
    chunk = (
        db.query(models.Chunk)
        .filter(models.Chunk.book_id == book.id, models.Chunk.chunk_number == chunk_number)
        .first()
    )
    if not chunk:
        return HTMLResponse('<div class="alert alert-danger">A kiválasztott chunk nem található.</div>')
    _set_setting(db, f"next_chunk_{book.id}", str(chunk_number))
    db.commit()
    return HTMLResponse(f'<div class="alert alert-success">A következő automatikus küldés: {chunk_number}. chunk.</div>')


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
