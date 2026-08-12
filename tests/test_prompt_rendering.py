"""Tests for prompt template rendering."""
import pytest
from pathlib import Path


class TestPromptRendering:
    def test_prompt_file_exists(self):
        prompt_path = Path(__file__).parent.parent / "app" / "prompts" / "summary.txt"
        assert prompt_path.exists(), "summary.txt prompt file must exist"

    def test_prompt_contains_placeholder(self):
        prompt_path = Path(__file__).parent.parent / "app" / "prompts" / "summary.txt"
        content = prompt_path.read_text(encoding="utf-8")
        assert "{text}" in content, "Prompt must contain {text} placeholder"

    def test_prompt_rendering(self):
        template = "Summarize: {text}"
        text = "שלום עולם"
        rendered = template.replace("{text}", text)
        assert text in rendered
        assert "Summarize:" in rendered

    def test_prompt_template_not_empty(self):
        prompt_path = Path(__file__).parent.parent / "app" / "prompts" / "summary.txt"
        content = prompt_path.read_text(encoding="utf-8")
        assert len(content.strip()) > 50, "Prompt should have substantial content"
