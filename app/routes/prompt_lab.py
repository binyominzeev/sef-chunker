"""Prompt Lab route for experimenting with AI prompts."""
import logging
from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional

from app.database import get_db
from app import models
from app.services.sefaria import build_sefaria_url
from app.services.markdown import render_markdown

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
templates.env.filters["markdown"] = render_markdown

DEFAULT_MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]


@router.get("/", response_class=HTMLResponse)
async def prompt_lab(
    request: Request,
    book_id: Optional[int] = Query(None),
    chunk_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    books = db.query(models.Book).all()
    selected_book_id = book_id
    selected_chunk_id = chunk_id
    selected_chunks = []
    if selected_book_id:
        selected_chunks = (
            db.query(models.Chunk)
            .filter(models.Chunk.book_id == selected_book_id)
            .order_by(models.Chunk.chunk_number)
            .all()
        )
        if not any(chunk.id == selected_chunk_id for chunk in selected_chunks):
            selected_chunk_id = None
    prompt_template = _load_default_prompt()
    return templates.TemplateResponse(
        request,
        "prompt_lab.html",
        {
            "books": books,
            "prompt_template": prompt_template,
            "models": DEFAULT_MODELS,
            "selected_book_id": selected_book_id,
            "selected_chunk_id": selected_chunk_id,
            "selected_chunks": selected_chunks,
        },
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
    db: Session = Depends(get_db),
):
    from app.services.summarizer import AISummarizer
    chunk = (
        db.query(models.Chunk)
        .filter(models.Chunk.id == chunk_id, models.Chunk.book_id == book_id)
        .first()
    )
    if not chunk:
        return HTMLResponse('<div class="alert alert-danger">Chunk not found.</div>')

    next_chunk = (
        db.query(models.Chunk)
        .filter(
            models.Chunk.book_id == book_id,
            models.Chunk.chunk_number == chunk.chunk_number + 1,
        )
        .first()
    )

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

    result["prompt"] = prompt
    result["model"] = model

    return templates.TemplateResponse(
        request,
        "partials/summary_result.html",
        {
            "result": result,
            "saved_note": "",
            "saved": False,
            "chunk": chunk,
            "start_url": build_sefaria_url(chunk.start_ref) if chunk.start_ref else None,
            "next_start_url": build_sefaria_url(next_chunk.start_ref) if next_chunk and next_chunk.start_ref else None,
        },
    )


@router.post("/save", response_class=HTMLResponse)
async def save_summary(
    request: Request,
    book_id: int = Form(...),
    chunk_id: int = Form(...),
    model: str = Form(...),
    prompt: str = Form(...),
    summary: str = Form(...),
    input_tokens: int = Form(0),
    output_tokens: int = Form(0),
    cost_usd: float = Form(0.0),
    db: Session = Depends(get_db),
):
    chunk = (
        db.query(models.Chunk)
        .filter(models.Chunk.id == chunk_id, models.Chunk.book_id == book_id)
        .first()
    )
    if not chunk:
        return HTMLResponse('<div class="alert alert-danger">Chunk not found.</div>')

    _save_default_prompt(prompt)
    db.add(models.Summary(
        chunk_id=chunk_id,
        prompt=prompt,
        summary=summary,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
    ))
    db.commit()

    next_chunk = (
        db.query(models.Chunk)
        .filter(
            models.Chunk.book_id == book_id,
            models.Chunk.chunk_number == chunk.chunk_number + 1,
        )
        .first()
    )
    return templates.TemplateResponse(
        request,
        "partials/summary_result.html",
        {
            "result": {
                "summary": summary,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
            },
            "saved_note": '<div class="alert alert-success">Prompt és összefoglaló mentve.</div>',
            "saved": True,
            "chunk": chunk,
            "start_url": build_sefaria_url(chunk.start_ref) if chunk.start_ref else None,
            "next_start_url": build_sefaria_url(next_chunk.start_ref) if next_chunk and next_chunk.start_ref else None,
        },
    )


def _load_default_prompt() -> str:
    prompt_path = _default_prompt_path()
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return ""


def _save_default_prompt(prompt: str) -> None:
    _default_prompt_path().write_text(prompt, encoding="utf-8")


def _default_prompt_path() -> Path:
    return Path(__file__).parent.parent / "prompts" / "summary.txt"
