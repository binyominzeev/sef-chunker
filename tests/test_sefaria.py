"""Tests for the Sefaria importer service."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.sefaria import SefariaImporter


MOCK_RESPONSE = {
    "heTitle": "תומר דבורה",
    "title": "Tomer Devorah",
    "ref": "Tomer Devorah",
    "he": ["פרק א\n\nטקסט ראשון", "פרק ב\n\nטקסט שני"],
}


class TestSefariaImporter:
    @pytest.mark.asyncio
    async def test_fetch_book_success(self):
        importer = SefariaImporter()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_RESPONSE
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await importer.fetch_book("Tomer Devorah")

        assert result["title"] == "תומר דבורה"
        assert result["ref"] == "Tomer Devorah"
        assert len(result["text"]) > 0

    @pytest.mark.asyncio
    async def test_fetch_book_not_found(self):
        importer = SefariaImporter()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(ValueError, match="not found"):
                await importer.fetch_book("NonExistentBook")

    def test_flatten_text_string(self):
        importer = SefariaImporter()
        assert importer._flatten_text("שלום") == "שלום"

    def test_flatten_text_nested_list(self):
        importer = SefariaImporter()
        result = importer._flatten_text([["א", "ב"], "ג"])
        assert "א" in result
        assert "ב" in result
        assert "ג" in result

    def test_flatten_text_empty(self):
        importer = SefariaImporter()
        assert importer._flatten_text([]) == ""
        assert importer._flatten_text("") == ""
