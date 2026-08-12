"""Render AI-generated Markdown for the web UI and Telegram."""
import html
import re

import markdown


def render_markdown(text: str) -> str:
    """Convert Markdown to HTML while treating generated text as untrusted."""
    escaped_text = html.escape(text, quote=False)
    return markdown.markdown(escaped_text, extensions=["nl2br"])


def render_telegram_markdown(text: str) -> str:
    """Convert Markdown to Telegram-compatible HTML."""
    rendered = render_markdown(text)
    replacements = (
        (r"<h[1-6]>", "<b>"),
        (r"</h[1-6]>", "</b>\n\n"),
        (r"<p>", ""),
        (r"</p>", "\n\n"),
        (r"<ul>|</ul>|<ol>|</ol>", ""),
        (r"<li>", "• "),
        (r"</li>", "\n"),
        (r"<strong>", "<b>"),
        (r"</strong>", "</b>"),
        (r"<em>", "<i>"),
        (r"</em>", "</i>"),
        (r"<br />\s*", "\n"),
    )
    for pattern, replacement in replacements:
        rendered = re.sub(pattern, replacement, rendered)
    return rendered.strip()