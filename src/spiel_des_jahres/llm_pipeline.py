from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from openai import OpenAI

if TYPE_CHECKING:
    from typing import Any

    from scrapy.crawler import Crawler
    from scrapy.spiders import Spider


class LLMExtractionPipeline:
    json_regex = re.compile(r"\[.*\]", re.DOTALL)

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
        self.client = OpenAI(base_url=api_base_url, api_key=api_key)
        self.model = model

    def process_item(
        self,
        item: dict[str, Any],
        spider: Spider,
    ) -> dict[str, Any] | None:
        if not item or not item.get("raw_text"):
            return item

        prompt = f"""The following text is a collection of board game reviews.
For each game and reviewer mentioned, extract:

- game title,
- reviewer name (both plain and reviewer ID as lower snake case),
- their review score or category if any,
  including max score (e.g. 3 out of 5 or "Excellent"),
- a short summary of their opinion,
- the sentiment ('positive', 'neutral', 'negative'),
- a 1–10 rating derived from their score and/or sentiment.

Return a JSON array (no other markdown etc) with objects having these keys:
game_title, reviewer_name, reviewer_id, score, summary, sentiment, rating.

TEXT:
\"\"\"
{item["raw_text"]}
\"\"\"
"""

        try:
            # TODO: this call should be async
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
        else:
            return item

        match = self.json_regex.search(content)

        if not match:
            spider.logger.error("LLM returned invalid JSON")
            item["reviews"] = content
            return item

        try:
            item["reviews"] = json.loads(match.group(0))
        except Exception:
            spider.logger.exception("Failed to parse LLM response")
            item["reviews"] = match.group(0)

        return item
