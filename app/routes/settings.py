"""Settings routes."""
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

SETTING_KEYS = [
    "openai_api_key",
    "telegram_bot_token",
    "telegram_chat_id",
    "default_model",
    "daily_send_time",
]


@router.get("/", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    current = {key: _get_setting(db, key) for key in SETTING_KEYS}
    return templates.TemplateResponse(request, "settings.html", {"settings": current, "keys": SETTING_KEYS})


@router.post("/save", response_class=HTMLResponse)
async def save_settings(
    request: Request,
    openai_api_key: str = Form(""),
    telegram_bot_token: str = Form(""),
    telegram_chat_id: str = Form(""),
    default_model: str = Form("gpt-4o-mini"),
    daily_send_time: str = Form("08:00"),
    db: Session = Depends(get_db),
):
    values = {
        "openai_api_key": openai_api_key,
        "telegram_bot_token": telegram_bot_token,
        "telegram_chat_id": telegram_chat_id,
        "default_model": default_model,
        "daily_send_time": daily_send_time,
    }
    for key, value in values.items():
        _set_setting(db, key, value)
    db.commit()

    # Reschedule with new time
    try:
        from app.services.scheduler import reschedule
        reschedule(daily_send_time)
    except Exception:
        pass

    return HTMLResponse(
        '<div class="alert alert-success alert-dismissible fade show" role="alert">'
        'Settings saved!<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>'
    )


def _get_setting(db: Session, key: str) -> str:
    obj = db.query(models.AppSettings).filter(models.AppSettings.key == key).first()
    return obj.value if obj else ""


def _set_setting(db: Session, key: str, value: str) -> None:
    obj = db.query(models.AppSettings).filter(models.AppSettings.key == key).first()
    if obj:
        obj.value = value
    else:
        db.add(models.AppSettings(key=key, value=value))
