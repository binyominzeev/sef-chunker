"""AI summarizer using OpenAI Responses API."""
import logging
from pathlib import Path
from typing import Any
from openai import AsyncOpenAI
from app.config import get_settings

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "summary.txt"

# Cost per 1K tokens (approximate, adjust as needed)
COST_PER_1K_INPUT = {"gpt-4o": 0.005, "gpt-4o-mini": 0.000150, "gpt-3.5-turbo": 0.0005}
COST_PER_1K_OUTPUT = {"gpt-4o": 0.015, "gpt-4o-mini": 0.000600, "gpt-3.5-turbo": 0.0015}
DEFAULT_ESTIMATED_OUTPUT_TOKENS = 200


class AISummarizer:
    """Generates Hungarian summaries using the OpenAI Responses API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.openai_api_key
        self._default_model = settings.default_model

    async def generate(
        self,
        hebrew_text: str,
        prompt_template: str = "",
        model: str = "",
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """Generate a summary for the given Hebrew text.

        Args:
            hebrew_text: The Hebrew source text to summarize.
            prompt_template: Prompt template with {text} placeholder.
            model: OpenAI model name.
            temperature: Sampling temperature.

        Returns:
            Dictionary with: summary, input_tokens, output_tokens, cost_usd
        """
        if not self._api_key:
            raise RuntimeError("OpenAI API key is not configured.")
        if not model:
            model = self._default_model
        if not prompt_template:
            prompt_template = self._load_prompt()

        prompt = prompt_template.replace("{text}", hebrew_text)
        client = AsyncOpenAI(api_key=self._api_key)
        logger.info("Generating summary with model=%s", model)

        response = await client.responses.create(
            model=model,
            input=prompt,
            temperature=temperature,
        )
        summary_text = response.output_text
        input_tokens = response.usage.input_tokens if response.usage else 0
        output_tokens = response.usage.output_tokens if response.usage else 0
        cost = estimate_cost(model, input_tokens, output_tokens)

        logger.info(
            "Summary generated: %d in / %d out tokens, cost=$%.4f",
            input_tokens,
            output_tokens,
            cost,
        )
        return {
            "summary": summary_text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
        }

    def _load_prompt(self) -> str:
        if PROMPT_PATH.exists():
            return PROMPT_PATH.read_text(encoding="utf-8")
        return "Summarize the following Hebrew text in Hungarian:\n\n{text}"



def estimate_tokens(text: str) -> int:
    """Approximate token count using the same ratio as generated chunks."""
    return max(1, len(text) // 3)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate OpenAI cost in USD from token counts and the configured model."""
    in_cost = next((v for k, v in COST_PER_1K_INPUT.items() if k in model), 0.002)
    out_cost = next((v for k, v in COST_PER_1K_OUTPUT.items() if k in model), 0.002)
    return (input_tokens * in_cost + output_tokens * out_cost) / 1000
