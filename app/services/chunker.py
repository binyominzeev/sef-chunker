"""Chunk generator service."""
import logging
import re
from typing import List, TypedDict

logger = logging.getLogger(__name__)

# Paragraph and chapter boundary patterns
CHAPTER_BOUNDARY = re.compile(r"\n{3,}")
PARAGRAPH_BOUNDARY = re.compile(r"\n{2}")
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?:׃])\s+")


class SefariaSegment(TypedDict):
    ref: str
    text: str


class ReferencedChunk(TypedDict):
    hebrew_text: str
    start_ref: str
    end_ref: str


class ChunkGenerator:
    """Splits book text into daily portions."""

    def split_segments_equal(
        self, segments: List[SefariaSegment], num_days: int
    ) -> List[ReferencedChunk]:
        """Split referenced Sefaria segments into roughly equal daily portions."""
        if num_days <= 0:
            raise ValueError("num_days must be positive")
        target_size = max(1, self._segments_length(segments) // num_days)
        return self._split_segments(segments, target_size)

    def split_segments_by_chars(
        self, segments: List[SefariaSegment], char_count: int
    ) -> List[ReferencedChunk]:
        """Split referenced Sefaria segments into portions near char_count."""
        if char_count <= 0:
            raise ValueError("char_count must be positive")
        return self._split_segments(segments, char_count)

    def split_equal(self, text: str, num_days: int) -> List[str]:
        """Split text into num_days roughly equal portions.

        Prefers to split at chapter, paragraph, or sentence boundaries.

        Args:
            text: Full Hebrew text of the book.
            num_days: Target number of daily portions.

        Returns:
            List of text chunks.
        """
        if num_days <= 0:
            raise ValueError("num_days must be positive")
        text = text.strip()
        if not text:
            return []
        target_size = max(1, len(text) // num_days)
        return self._split_at_boundaries(text, target_size)

    def split_by_chars(self, text: str, char_count: int) -> List[str]:
        """Split text into portions of approximately char_count characters.

        Args:
            text: Full Hebrew text of the book.
            char_count: Target character count per portion.

        Returns:
            List of text chunks.
        """
        if char_count <= 0:
            raise ValueError("char_count must be positive")
        text = text.strip()
        if not text:
            return []
        return self._split_at_boundaries(text, char_count)

    def _split_at_boundaries(self, text: str, target_size: int) -> List[str]:
        """Split text near target_size, preferring natural boundaries."""
        chunks: List[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + target_size, text_len)
            if end == text_len:
                chunks.append(text[start:].strip())
                break

            # Look forward up to 20% more for a better boundary
            search_end = min(end + target_size // 5, text_len)
            window = text[start:search_end]

            split_pos = self._find_best_boundary(window, target_size)
            actual_end = start + split_pos
            if actual_end <= start:
                actual_end = end
            chunk = text[start:actual_end].strip()
            if chunk:
                chunks.append(chunk)
            start = actual_end

        return [c for c in chunks if c]

    def _find_best_boundary(self, window: str, target: int) -> int:
        """Find the best split position in window, starting near target."""
        # Try chapter boundary first
        for pattern in [CHAPTER_BOUNDARY, PARAGRAPH_BOUNDARY, SENTENCE_BOUNDARY]:
            for match in pattern.finditer(window):
                if match.start() >= target:
                    return match.end()
            # Take the last match before target
            last = None
            for match in pattern.finditer(window):
                if match.end() <= target:
                    last = match
            if last:
                return last.end()

        # Fall back to target position
        return target

    def _split_segments(
        self, segments: List[SefariaSegment], target_size: int
    ) -> List[ReferencedChunk]:
        """Join whole Sefaria segments without splitting their references."""
        clean_segments = [segment for segment in segments if segment["text"].strip()]
        chunks: List[ReferencedChunk] = []
        current_segments: List[SefariaSegment] = []
        current_length = 0

        for segment in clean_segments:
            text = segment["text"].strip()
            separator_length = 2 if current_segments else 0
            prospective_length = current_length + separator_length + len(text)

            if current_segments and prospective_length > target_size:
                chunks.append(self._make_referenced_chunk(current_segments))
                current_segments = []
                current_length = 0

            current_segments.append({"ref": segment["ref"], "text": text})
            current_length += (2 if current_length else 0) + len(text)

        if current_segments:
            chunks.append(self._make_referenced_chunk(current_segments))
        return chunks

    def _segments_length(self, segments: List[SefariaSegment]) -> int:
        return sum(len(segment["text"].strip()) for segment in segments if segment["text"].strip())

    def _make_referenced_chunk(self, segments: List[SefariaSegment]) -> ReferencedChunk:
        return {
            "hebrew_text": "\n\n".join(segment["text"] for segment in segments),
            "start_ref": segments[0]["ref"],
            "end_ref": segments[-1]["ref"],
        }
