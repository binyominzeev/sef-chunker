"""Tests for the ChunkGenerator service."""
import pytest
from app.services.chunker import ChunkGenerator


SAMPLE_TEXT = "\n\n".join([f"פרק {i}: " + "א" * 100 for i in range(1, 21)])


class TestSplitEqual:
    def test_basic_split(self):
        gen = ChunkGenerator()
        chunks = gen.split_equal(SAMPLE_TEXT, 5)
        assert len(chunks) >= 4
        assert all(len(c) > 0 for c in chunks)

    def test_single_day(self):
        gen = ChunkGenerator()
        chunks = gen.split_equal("Hello world", 1)
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"

    def test_empty_text(self):
        gen = ChunkGenerator()
        assert gen.split_equal("", 5) == []

    def test_invalid_num_days(self):
        gen = ChunkGenerator()
        with pytest.raises(ValueError):
            gen.split_equal("text", 0)

    def test_chunks_cover_full_text(self):
        gen = ChunkGenerator()
        text = "אבג " * 1000
        chunks = gen.split_equal(text, 10)
        combined = " ".join(chunks)
        # All original content should be present
        assert len(combined) >= len(text) * 0.9

    def test_more_days_than_chars(self):
        gen = ChunkGenerator()
        chunks = gen.split_equal("אבג", 100)
        assert len(chunks) >= 1


class TestSplitByChars:
    def test_basic_split(self):
        gen = ChunkGenerator()
        text = "א" * 5000
        chunks = gen.split_by_chars(text, 1000)
        assert len(chunks) >= 4

    def test_empty_text(self):
        gen = ChunkGenerator()
        assert gen.split_by_chars("", 1000) == []

    def test_invalid_char_count(self):
        gen = ChunkGenerator()
        with pytest.raises(ValueError):
            gen.split_by_chars("text", 0)

    def test_approximate_size(self):
        gen = ChunkGenerator()
        text = "ב" * 3000
        chunks = gen.split_by_chars(text, 1000)
        for chunk in chunks:
            assert len(chunk) <= 1300  # Allow some overshoot

    def test_no_empty_chunks(self):
        gen = ChunkGenerator()
        chunks = gen.split_by_chars("שלום עולם " * 200, 500)
        assert all(c.strip() for c in chunks)


class TestReferencedSegments:
    SEGMENTS = [
        {"ref": "Book 1:1", "text": "א" * 10},
        {"ref": "Book 1:2", "text": "ב" * 10},
        {"ref": "Book 1:3", "text": "ג" * 10},
    ]

    def test_split_segments_keeps_reference_boundaries(self):
        gen = ChunkGenerator()

        chunks = gen.split_segments_by_chars(self.SEGMENTS, 20)

        assert chunks == [
            {
                "hebrew_text": "א" * 10,
                "start_ref": "Book 1:1",
                "end_ref": "Book 1:1",
            },
            {
                "hebrew_text": "ב" * 10,
                "start_ref": "Book 1:2",
                "end_ref": "Book 1:2",
            },
            {
                "hebrew_text": "ג" * 10,
                "start_ref": "Book 1:3",
                "end_ref": "Book 1:3",
            },
        ]

    def test_split_segments_equal_preserves_all_text_and_refs(self):
        gen = ChunkGenerator()

        chunks = gen.split_segments_equal(self.SEGMENTS, 2)

        assert "".join(chunk["hebrew_text"].replace("\n", "") for chunk in chunks) == "".join(
            segment["text"] for segment in self.SEGMENTS
        )
        assert [chunk["start_ref"] for chunk in chunks] == ["Book 1:1", "Book 1:2", "Book 1:3"]
        assert [chunk["end_ref"] for chunk in chunks] == ["Book 1:1", "Book 1:2", "Book 1:3"]

    def test_single_oversized_segment_is_not_split(self):
        gen = ChunkGenerator()

        chunks = gen.split_segments_by_chars([{"ref": "Book 1:1", "text": "א" * 100}], 10)

        assert chunks == [
            {"hebrew_text": "א" * 100, "start_ref": "Book 1:1", "end_ref": "Book 1:1"}
        ]
