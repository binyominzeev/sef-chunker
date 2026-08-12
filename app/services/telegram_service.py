"""Telegram bot message delivery service."""
import html
import logging
from telegram import Bot
from telegram.error import TelegramError
from app.config import get_settings
from app.services.markdown import render_telegram_markdown
from app.services.sefaria import build_sefaria_url

logger = logging.getLogger(__name__)


async def send_message(text: str, parse_mode: str = "HTML") -> None:
    """Send a message via Telegram bot.

    Args:
        text: Message text (HTML or Markdown).
        parse_mode: Telegram parse mode ('HTML' or 'Markdown').
    """
    settings = get_settings()
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if not token or not chat_id:
        raise RuntimeError("Telegram bot token or chat ID is not configured.")
    bot = Bot(token=token)
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        logger.info("Telegram message sent to chat_id=%s", chat_id)
    except TelegramError as exc:
        logger.error("Telegram send failed: %s", exc)
        raise


def format_daily_message(
    book_title: str,
    day: int,
    total_days: int,
    start_ref: str,
    end_ref: str,
    next_start_ref: str | None,
    summary: str,
) -> str:
    """Format the daily Telegram message.

    Args:
        book_title: Title of the book.
        day: Current day number.
        total_days: Total number of days.
        start_ref: Start reference of the chunk.
        end_ref: End reference of the chunk.
        next_start_ref: Start reference of the next chunk, if one exists.
        summary: AI-generated Hungarian summary.

    Returns:
        Formatted HTML message string.
    """
    ref_display = start_ref if start_ref == end_ref or not end_ref else f"{start_ref} – {end_ref}"
    reference_line = html.escape(ref_display) if ref_display else "Sefaria-hivatkozás nem elérhető"
    start_link = (
        f'<a href="{build_sefaria_url(start_ref)}">Olvasás kezdete</a>'
        if start_ref
        else "Olvasás kezdete nem elérhető"
    )
    next_link = (
        f'<a href="{build_sefaria_url(next_start_ref)}">Holnapi kezdés</a>'
        if next_start_ref
        else "<i>A könyv vége</i>"
    )
    return (
        f"📖 <b>{html.escape(book_title)}</b>\n\n"
        f"<b>{day}. nap / {total_days}</b>\n"
        f"<i>{reference_line}</i>\n"
        f"{start_link} · {next_link}\n\n"
        f"{render_telegram_markdown(summary)}"
    )
