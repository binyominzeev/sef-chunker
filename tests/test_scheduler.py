"""Tests for the scheduler service."""
import pytest
from app.services.scheduler import _parse_time


class TestParseTime:
    def test_valid_time(self):
        assert _parse_time("08:00") == (8, 0)
        assert _parse_time("23:59") == (23, 59)
        assert _parse_time("00:00") == (0, 0)
        assert _parse_time("12:30") == (12, 30)

    def test_invalid_time_defaults(self):
        assert _parse_time("invalid") == (8, 0)
        assert _parse_time("") == (8, 0)
        assert _parse_time("25:00") == (8, 0)  # out-of-range hour defaults to 08:00
        assert _parse_time("12:60") == (8, 0)  # out-of-range minute defaults to 08:00

    def test_missing_minutes(self):
        assert _parse_time("10") == (8, 0)  # falls back
