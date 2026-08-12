"""Sefaria API importer."""
import logging
import httpx
from typing import Any

logger = logging.getLogger(__name__)

SEFARIA_BASE_URL = "https://www.sefaria.org/api/texts"


class SefariaImporter:
    """Downloads book text from the Sefaria API."""

    def __init__(self, base_url: str = SEFARIA_BASE_URL) -> None:
        self.base_url = base_url

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
        text = self._flatten_text(data.get("he", data.get("text", [])))
        if not text:
            raise ValueError(f"No Hebrew text found for '{ref}'")
        logger.info("Fetched %d characters for '%s'", len(text), title)
        return {"title": title, "ref": data.get("ref", ref), "text": text}

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
