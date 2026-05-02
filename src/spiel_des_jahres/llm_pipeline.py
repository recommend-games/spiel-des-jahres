from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from typing import Any

    from scrapy.crawler import Crawler
    from scrapy.spiders import Spider


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
        )

    def __init__(
        self,
        *,
        api_base_url: str | None = None,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
    ):
        self.client = AsyncOpenAI(base_url=api_base_url, api_key=api_key)
        self.model = model

    async def process_item(
        self,
        item: dict[str, Any],
        spider: Spider,
    ) -> dict[str, Any] | None:
        if not item or not item.get("raw_text"):
            return item

        try:
            response = await self.client.responses.parse(
                model=self.model,
                input=item["raw_text"],
                instructions=(
                    "The following text is a collection of board game reviews. "
                    "For each game and reviewer mentioned, extract the details "
                    "into the structured format."
                ),
                text_format=ReviewList,
            )
            if response.output_parsed:
                item["reviews"] = [
                    r.model_dump() for r in response.output_parsed.reviews
                ]
            else:
                spider.logger.error("LLM returned empty or unparseable content")
                item["reviews"] = None
        except Exception:
            spider.logger.exception("LLM parsing failed")
            item["reviews"] = None

        return item
