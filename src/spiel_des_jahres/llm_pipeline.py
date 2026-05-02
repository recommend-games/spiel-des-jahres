from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from typing import Any

    from scrapy.crawler import Crawler
    from scrapy.spiders import Spider


LLM_INSTRUCTIONS = """
The following text is a collection of board game reviews.
For each game and reviewer mentioned, extract the details into the structured format.

- If a reviewer's name is not explicitly mentioned but an opinion is clearly
  attributed (e.g., via a quote), use the name from context.
- If a specific score or category is missing, set `score` to null.

For the 1-10 rating, use this rubric:
- 9-10: Glowing, exceptional, 'must play';
- 7-8: Very positive, minor flaws;
- 5-6: Mixed or neutral, significant reservations;
- 3-4: Mostly negative, 'disappointing';
- 1-2: Extremely negative, 'avoid'.
""".strip()


class Review(BaseModel):
    game_title: str = Field(description="The title of the board game.")
    reviewer_name: str = Field(description="The name of the reviewer.")
    reviewer_id: str = Field(description="The reviewer ID as lower snake case.")
    score: str | None = Field(
        description="The review score or category, e.g. '3 out of 5'.",
    )
    summary: str = Field(description="A short summary of their opinion.")
    sentiment: Literal["positive", "neutral", "negative"] = Field(
        description="The sentiment of the review.",
    )
    rating: int = Field(
        description="A 1–10 rating derived from their score and/or sentiment.",
        ge=1,
        le=10,
    )


class ReviewList(BaseModel):
    reviews: list[Review] = Field(description="A list of extracted reviews.")


class LLMExtractionPipeline:
    @classmethod
    def from_crawler(cls, crawler: Crawler) -> LLMExtractionPipeline:
        return cls(
            api_base_url=crawler.settings.get("LLM_API_BASE_URL"),
            api_key=crawler.settings.get("LLM_API_KEY"),
            model=crawler.settings.get("LLM_MODEL") or "gpt-4o-mini",
            temperature=crawler.settings.getfloat("LLM_TEMPERATURE", 0.0),
            max_output_tokens=crawler.settings.getint("LLM_MAX_OUTPUT_TOKENS", 1000),
        )

    def __init__(
        self,
        *,
        api_base_url: str | None = None,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
        max_output_tokens: int = 1000,
    ):
        self.client = AsyncOpenAI(base_url=api_base_url, api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
    )
    async def _call_llm(
        self,
        text: str,
        title: str | None = None,
        description: str | None = None,
        spider: Spider | None = None,
    ) -> ReviewList | None:
        prompt_content = (
            f"CONTEXT:\nTitle: {title}\nDescription: {description}\n\nTEXT:\n{text}"
        )
        response = await self.client.responses.parse(
            model=self.model,
            input=prompt_content,
            instructions=LLM_INSTRUCTIONS,
            text_format=ReviewList,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )

        if spider and response.usage:
            usage = response.usage
            stats = spider.crawler.stats
            if stats:
                stats.inc_value("llm/input_tokens", usage.input_tokens)
                stats.inc_value("llm/output_tokens", usage.output_tokens)
                stats.inc_value("llm/total_tokens", usage.total_tokens)

                if stats.get_value("llm/total_tokens", 0) % 50_000 < usage.total_tokens:
                    total_tokens = stats.get_value("llm/total_tokens", 0)
                    spider.logger.info(
                        "LLM usage check-in: %d total tokens so far",
                        total_tokens,
                    )

        return response.output_parsed

    async def process_item(
        self,
        item: dict[str, Any],
        spider: Spider,
    ) -> dict[str, Any] | None:
        if not item or not item.get("raw_text"):
            return item

        try:
            parsed = await self._call_llm(
                text=item["raw_text"],
                title=item.get("title"),
                description=item.get("description"),
                spider=spider,
            )
            if parsed:
                item["reviews"] = [r.model_dump() for r in parsed.reviews]
            else:
                spider.logger.error("LLM returned empty or unparseable content")
                item["reviews"] = None
        except Exception:
            spider.logger.exception("LLM parsing failed after retries")
            item["reviews"] = None

        return item
