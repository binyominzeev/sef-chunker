"""Book import routes."""
import logging
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path

from app.database import get_db
from app import models
from app.services.sefaria import SefariaImporter

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def list_books(request: Request, db: Session = Depends(get_db)):
    books = db.query(models.Book).all()
    return templates.TemplateResponse(request, "books/list.html", {"books": books})


@router.get("/import", response_class=HTMLResponse)
async def import_form(request: Request):
    return templates.TemplateResponse(request, "books/import.html", {})


@router.post("/import", response_class=HTMLResponse)
async def import_book(request: Request, sefaria_ref: str = Form(...), db: Session = Depends(get_db)):
    importer = SefariaImporter()
    try:
        book_data = await importer.fetch_book(sefaria_ref)
    except Exception as exc:
        logger.exception("Failed to import book %s", sefaria_ref)
        return templates.TemplateResponse(
            request,
            "books/import.html",
            {"error": str(exc)},
        )

    existing = db.query(models.Book).filter(models.Book.sefaria_ref == book_data["ref"]).first()
    if existing:
        return templates.TemplateResponse(
            request,
            "books/import.html",
            {"error": f"Book '{book_data['title']}' is already imported."},
        )

    book = models.Book(title=book_data["title"], sefaria_ref=book_data["ref"])
    db.add(book)
    db.commit()
    db.refresh(book)
    logger.info("Imported book: %s (ref=%s)", book.title, book.sefaria_ref)
    return RedirectResponse(url=f"/chunks/generate?book_id={book.id}", status_code=303)


@router.post("/{book_id}/delete", response_class=HTMLResponse)
async def delete_book(book_id: int, db: Session = Depends(get_db)):
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if book:
        db.delete(book)
        db.commit()
    return RedirectResponse(url="/books/", status_code=303)
