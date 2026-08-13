"""Sefaria API importer."""
import json
import logging
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

SEFARIA_BASE_URL = "https://www.sefaria.org/api/texts"
SEFARIA_INDEX_URL = "https://www.sefaria.org/api/index"
SEFARIA_SITE_URL = "https://www.sefaria.org"
BOOK_CACHE_PATH = Path(__file__).parents[2] / "data" / "sefaria_books.json"
BOOK_CACHE_MAX_AGE_SECONDS = 60 * 60 * 24


def build_sefaria_url(ref: str) -> str:
    """Build the canonical public Sefaria URL for a textual reference."""
    match = re.fullmatch(r"(.*?)(?:\s+(\d+(?::\d+)*))?", ref.strip())
    if not match:
        raise ValueError("Sefaria reference cannot be empty")
    title, sections = match.groups()
    path = quote(title.replace(" ", "_"), safe="._-")
    if sections:
        path = f"{path}.{sections.replace(':', '.')}"
    return f"{SEFARIA_SITE_URL}/{path}"


class SefariaImporter:
    """Downloads book text from the Sefaria API."""

    def __init__(self, base_url: str = SEFARIA_BASE_URL) -> None:
        self.base_url = base_url

    async def get_available_books(self) -> list[str]:
        """Return cached Sefaria book titles, refreshing the cache when needed."""
        if self._cache_is_fresh():
            cached_books = self._read_book_cache()
            if cached_books:
                return cached_books

        try:
            books = await self._fetch_book_list()
            self._write_book_cache(books)
            return books
        except Exception:
            cached_books = self._read_book_cache()
            if cached_books:
                logger.warning("Could not refresh Sefaria book cache", exc_info=True)
                return cached_books
            raise

    async def _fetch_book_list(self) -> list[str]:
        """Fetch and flatten the hierarchical Sefaria index response."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(SEFARIA_INDEX_URL)
        response.raise_for_status()
        data = response.json()
        titles: set[str] = set()

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                title = value.get("title")
                if isinstance(title, str) and title.strip():
                    titles.add(title.strip())
                for child in value.get("contents", []):
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(data)
        return sorted(titles, key=str.casefold)

    @staticmethod
    def _cache_is_fresh() -> bool:
        if not BOOK_CACHE_PATH.is_file():
            return False
        return time.time() - BOOK_CACHE_PATH.stat().st_mtime < BOOK_CACHE_MAX_AGE_SECONDS

    @staticmethod
    def _read_book_cache() -> list[str]:
        try:
            data = json.loads(BOOK_CACHE_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return []
        if isinstance(data, list) and all(isinstance(item, str) for item in data):
            return data
        return []

    @staticmethod
    def _write_book_cache(books: list[str]) -> None:
        BOOK_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BOOK_CACHE_PATH.write_text(json.dumps(books, ensure_ascii=False, indent=2), encoding="utf-8")

    async def fetch_book(self, ref: str) -> dict[str, Any]:
        """Fetch a complete book from Sefaria by its reference.

        Args:
            ref: Sefaria book reference, e.g. "Tomer Devorah"

        Returns:
            Dictionary with keys: title, ref, text (flattened Hebrew text)
        """
        url = f"{self.base_url}/{ref}"
        params = {"lang": "he", "pad": 0, "commentary": 0}
        logger.info("Fetching Sefaria book: %s", ref)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
        if response.status_code == 404:
            raise ValueError(f"Book not found in Sefaria: '{ref}'")
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise ValueError(f"Sefaria error: {data['error']}")
        title = data.get("heTitle") or data.get("title") or ref
        canonical_ref = data.get("ref", ref)
        hebrew_text = data.get("he", data.get("text", []))
        text = self._flatten_text(hebrew_text)
        if not text:
            raise ValueError(f"No Hebrew text found for '{ref}'")
        logger.info("Fetched %d characters for '%s'", len(text), title)
        return {
            "title": title,
            "ref": canonical_ref,
            "text": text,
            "segments": self._extract_segments(hebrew_text, canonical_ref),
        }

    def _flatten_text(self, text_data: Any) -> str:
        """Recursively flatten nested Sefaria text arrays into a single string."""
        if isinstance(text_data, str):
            return text_data.strip()
        if isinstance(text_data, list):
            parts = []
            for item in text_data:
                part = self._flatten_text(item)
                if part:
                    parts.append(part)
            return "\n\n".join(parts)
        return ""

    def _extract_segments(self, text_data: Any, base_ref: str) -> list[dict[str, str]]:
        """Return non-empty Sefaria leaf texts with their canonical references."""
        segments: list[dict[str, str]] = []

        def visit(value: Any, path: list[int]) -> None:
            if isinstance(value, str):
                text = value.strip()
                if text:
                    suffix = ":".join(str(index) for index in path)
                    segment_ref = f"{base_ref} {suffix}" if suffix else base_ref
                    segments.append({"ref": segment_ref, "text": text})
                return
            if isinstance(value, list):
                for index, item in enumerate(value, start=1):
                    visit(item, [*path, index])

        visit(text_data, [])
        return segments
