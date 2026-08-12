"""Prompt Lab route for experimenting with AI prompts."""
import logging
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional

from app.database import get_db
from app import models

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

DEFAULT_MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]


@router.get("/", response_class=HTMLResponse)
async def prompt_lab(request: Request, db: Session = Depends(get_db)):
    books = db.query(models.Book).all()
    prompt_template = _load_default_prompt()
    return templates.TemplateResponse(
        request,
        "prompt_lab.html",
        {"books": books, "prompt_template": prompt_template, "models": DEFAULT_MODELS},
    )


@router.get("/chunks", response_class=HTMLResponse)
async def get_chunks_for_book(request: Request, book_id: int, db: Session = Depends(get_db)):
    chunks = db.query(models.Chunk).filter(models.Chunk.book_id == book_id).order_by(models.Chunk.chunk_number).all()
    options = "".join(f'<option value="{c.id}">Chunk {c.chunk_number}</option>' for c in chunks)
    return HTMLResponse(f'<select name="chunk_id" class="form-select" id="chunkSelect">{options}</select>')


@router.post("/generate", response_class=HTMLResponse)
async def generate_summary(
    request: Request,
    book_id: int = Form(...),
    chunk_id: int = Form(...),
    model: str = Form("gpt-4o-mini"),
    temperature: float = Form(0.7),
    prompt: str = Form(...),
    save: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    from app.services.summarizer import AISummarizer
    chunk = db.query(models.Chunk).filter(models.Chunk.id == chunk_id).first()
    if not chunk:
        return HTMLResponse('<div class="alert alert-danger">Chunk not found.</div>')

    summarizer = AISummarizer()
    try:
        result = await summarizer.generate(
            hebrew_text=chunk.hebrew_text,
            prompt_template=prompt,
            model=model,
            temperature=temperature,
        )
    except Exception:
        logger.exception("Prompt lab generation failed")
        return HTMLResponse('<div class="alert alert-danger">AI generation failed. Check the server logs for details.</div>')

    if save:
        summary_obj = models.Summary(
            chunk_id=chunk_id,
            prompt=prompt,
            summary=result["summary"],
            model=model,
            input_tokens=result.get("input_tokens", 0),
            output_tokens=result.get("output_tokens", 0),
            cost_usd=result.get("cost_usd", 0.0),
        )
        db.add(summary_obj)
        db.commit()
        saved_note = '<div class="alert alert-success">Summary saved!</div>'
    else:
        saved_note = ""

    return templates.TemplateResponse(
        request,
        "partials/summary_result.html",
        {"result": result, "saved_note": saved_note},
    )


def _load_default_prompt() -> str:
    prompt_path = Path(__file__).parent.parent / "prompts" / "summary.txt"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return ""
