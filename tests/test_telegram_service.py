"""Tests for Telegram message formatting."""
from app.services.sefaria import build_sefaria_url
from app.services.markdown import render_markdown, render_telegram_markdown
from app.services.telegram_service import format_daily_message


def test_markdown_is_rendered_for_preview_and_telegram():
    summary = "**Főcím**\n\n*kiemelt rész*\n\n- első pont\n- második pont"

    preview = render_markdown(summary)
    telegram = render_telegram_markdown(summary)

    assert "<strong>Főcím</strong>" in preview
    assert "<em>kiemelt rész</em>" in preview
    assert "<b>Főcím</b>" in telegram
    assert "<i>kiemelt rész</i>" in telegram
    assert "• első pont" in telegram
    assert "• második pont" in telegram


def test_markdown_line_breaks_are_preserved():
    assert "első sor<br />\nmásodik sor" in render_markdown("első sor\nmásodik sor")
    assert "első sor\nmásodik sor" in render_telegram_markdown("első sor\nmásodik sor")


def test_build_sefaria_url_uses_canonical_path_format():
    assert build_sefaria_url("Tomer Devorah 1:3") == "https://www.sefaria.org/Tomer_Devorah.1.3"
    assert build_sefaria_url("ספר לדוגמה 1:3") == "https://www.sefaria.org/%D7%A1%D7%A4%D7%A8_%D7%9C%D7%93%D7%95%D7%92%D7%9E%D7%94.1.3"


def test_daily_message_includes_current_and_next_reading_links():
    message = format_daily_message(
        book_title="Tomer Devorah",
        day=1,
        total_days=2,
        start_ref="Tomer Devorah 1:1",
        end_ref="Tomer Devorah 1:3",
        next_start_ref="Tomer Devorah 2:1",
        summary="Összefoglaló",
    )

    assert '<a href="https://www.sefaria.org/Tomer_Devorah.1.1">Olvasás kezdete</a>' in message
    assert '<a href="https://www.sefaria.org/Tomer_Devorah.2.1">Holnapi kezdés</a>' in message
    assert "Tomer Devorah 1:1 – Tomer Devorah 1:3" in message


def test_last_daily_message_marks_end_of_book():
    message = format_daily_message(
        book_title="Tomer Devorah",
        day=2,
        total_days=2,
        start_ref="Tomer Devorah 2:1",
        end_ref="Tomer Devorah 2:2",
        next_start_ref=None,
        summary="Összefoglaló",
    )

    assert "<i>A könyv vége</i>" in message
    assert "Holnapi kezdés" not in message