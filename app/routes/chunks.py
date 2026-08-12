"""Chunk browser and generator routes."""
import logging
from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional

from app.database import get_db
from app import models
from app.services.chunker import ChunkGenerator

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/generate", response_class=HTMLResponse)
async def generate_form(request: Request, book_id: Optional[int] = None, db: Session = Depends(get_db)):
    books = db.query(models.Book).all()
    selected_book = None
    if book_id:
        selected_book = db.query(models.Book).filter(models.Book.id == book_id).first()
    return templates.TemplateResponse(
        request,
        "chunks/generate.html",
        {"books": books, "selected_book": selected_book},
    )


@router.post("/generate", response_class=HTMLResponse)
async def generate_chunks(
    request: Request,
    book_id: int = Form(...),
    mode: str = Form(...),
    num_days: Optional[int] = Form(None),
    char_count: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book:
        return HTMLResponse('<div class="alert alert-danger">Book not found.</div>')

    # Delete existing chunks
    db.query(models.Chunk).filter(models.Chunk.book_id == book_id).delete()
    db.commit()

    from app.services.sefaria import SefariaImporter
    importer = SefariaImporter()
    try:
        book_data = await importer.fetch_book(book.sefaria_ref)
    except Exception:
        logger.exception("Failed to fetch text for book %s", book_id)
        return HTMLResponse('<div class="alert alert-danger">Failed to fetch text from Sefaria. Check the server logs for details.</div>')

    generator = ChunkGenerator()
    try:
        if mode == "equal":
            chunks_data = generator.split_equal(book_data["text"], num_days or 30)
        else:
            chunks_data = generator.split_by_chars(book_data["text"], char_count or 1200)
    except Exception:
        logger.exception("Chunk generation failed for book %s", book_id)
        return HTMLResponse('<div class="alert alert-danger">Failed to generate chunks. Check the server logs for details.</div>')

    for i, chunk_text in enumerate(chunks_data, start=1):
        chunk = models.Chunk(
            book_id=book_id,
            chunk_number=i,
            hebrew_text=chunk_text,
            estimated_tokens=len(chunk_text) // 3,
        )
        db.add(chunk)

    # Reset progress
    progress = db.query(models.Progress).filter(models.Progress.book_id == book_id).first()
    if not progress:
        progress = models.Progress(book_id=book_id, last_sent_chunk=0)
        db.add(progress)
    else:
        progress.last_sent_chunk = 0
    db.commit()
    logger.info("Generated %d chunks for book %d", len(chunks_data), book_id)
    return RedirectResponse(url=f"/chunks/?book_id={int(book_id)}", status_code=303)


@router.get("/", response_class=HTMLResponse)
async def list_chunks(
    request: Request,
    book_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    books = db.query(models.Book).all()
    chunks = []
    selected_book = None
    if book_id:
        selected_book = db.query(models.Book).filter(models.Book.id == book_id).first()
        q = db.query(models.Chunk).filter(models.Chunk.book_id == book_id)
        if search:
            q = q.filter(models.Chunk.hebrew_text.contains(search))
        chunks = q.order_by(models.Chunk.chunk_number).all()
    return templates.TemplateResponse(
        request,
        "chunks/list.html",
        {"books": books, "chunks": chunks, "selected_book": selected_book, "search": search},
    )


@router.get("/{chunk_id}/preview", response_class=HTMLResponse)
async def preview_chunk(request: Request, chunk_id: int, db: Session = Depends(get_db)):
    chunk = db.query(models.Chunk).filter(models.Chunk.id == chunk_id).first()
    if not chunk:
        return HTMLResponse('<div class="alert alert-danger">Chunk not found.</div>', status_code=404)
    latest_summary = (
        db.query(models.Summary)
        .filter(models.Summary.chunk_id == chunk_id)
        .order_by(models.Summary.generated_at.desc())
        .first()
    )
    return templates.TemplateResponse(
        request,
        "chunks/preview.html",
        {"chunk": chunk, "summary": latest_summary},
    )
