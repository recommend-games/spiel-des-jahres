from __future__ import annotations

import json

from openai import OpenAI
from scrapy import signals


class LLMExtractionExtension:
    def __init__(self, api_base: str, api_key: str, model: str):
        self.client = OpenAI(base_url=api_base, api_key=api_key)
        self.model = model

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            api_base=crawler.settings.get("LLM_API_BASE", "http://localhost:8000/v1"),
            api_key=crawler.settings.get("LLM_API_KEY", "local-key"),
            model=crawler.settings.get("LLM_MODEL", "gpt-4"),
        )

    @classmethod
    def from_settings(cls, settings):
        return cls(
            api_base=settings.get("LLM_API_BASE"),
            api_key=settings.get("LLM_API_KEY"),
            model=settings.get("LLM_MODEL"),
        )

    @signals.item_scraped.connect
    def process_item(self, item, spider):
        if not item.get("raw_text"):
            return None

        prompt = f"""
        The following text is a collection of board game reviews.
        For each reviewer mentioned, extract:

        - their name,
        - their review score if any, including max score (e.g. 3 out of 5),
        - a short summary of their opinion,
        - the sentiment ('positive', 'neutral', 'negative'),
        - a 1–10 rating derived from their score and/or sentiment.

        Return a JSON array with objects having these keys:
        name, score, summary, sentiment, rating.

        TEXT:
        \"\"\"
        {item["raw_text"]}
        \"\"\"
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            content = response.choices[0].message.content
            item["reviews"] = json.loads(content)
        except Exception:
            spider.logger.exception("LLM parsing failed")
            item["reviews"] = content if "content" in locals() else None

        return item
