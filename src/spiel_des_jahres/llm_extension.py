from __future__ import annotations

import json
from typing import TYPE_CHECKING

from openai import OpenAI
from scrapy import signals

if TYPE_CHECKING:
    from typing import Any

    from scrapy.crawler import Crawler
    from scrapy.spiders import Spider


class LLMExtractionExtension:
    def __init__(
        self,
        api_base_url: str | None = None,
        api_key: str | None = None,
        model: str = "gpt-4",
    ):
        self.client = OpenAI(base_url=api_base_url, api_key=api_key)
        self.model = model

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> LLMExtractionExtension:
        extension = cls(
            api_base_url=crawler.settings.get("LLM_API_BASE_URL"),
            api_key=crawler.settings.get("LLM_API_KEY"),
            model=crawler.settings.get("LLM_MODEL") or "gpt-4",
        )
        crawler.signals.connect(extension.process_item, signals.item_scraped)
        return extension

    def process_item(
        self,
        item: dict[str, Any],
        spider: Spider,
    ) -> dict[str, Any] | None:
        if not item.get("raw_text"):
            return None

        prompt = f"""The following text is a collection of board game reviews.
For each game and reviewer mentioned, extract:

- game title,
- reviewer name (both plain and reviewer ID as lower snake case),
- their review score or category if any,
  including max score (e.g. 3 out of 5 or "Excellent"),
- a short summary of their opinion,
- the sentiment ('positive', 'neutral', 'negative'),
- a 1–10 rating derived from their score and/or sentiment.

Return a JSON array with objects having these keys:
game_title, reviewer_name, reviewer_id, score, summary, sentiment, rating.

TEXT:
\"\"\"
{item["raw_text"]}
\"\"\"
"""

        try:
            response = self.client.responses.create(
                model=self.model,
                input=prompt,
                # TODO: instructions
            )
            content = response.output_text
        except Exception:
            spider.logger.exception("LLM parsing failed")
            content = None

        if not content:
            spider.logger.error("LLM returned empty content")
            item["reviews"] = None
            return item

        try:
            item["reviews"] = json.loads(content)
        except Exception:
            spider.logger.exception("Failed to parse LLM response")
            item["reviews"] = json.dumps(content)

        return item
