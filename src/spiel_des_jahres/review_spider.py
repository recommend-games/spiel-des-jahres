from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup
from scrapy import Request
from scrapy.http.response.text import TextResponse
from scrapy.spiders.sitemap import SitemapSpider

if TYPE_CHECKING:
    from scrapy.http.response import Response


class SpielReviewSpider(SitemapSpider):
    name = "spiel_des_jahres"
    allowed_domains = ("spiel-des-jahres.de",)

    sitemap_urls = ("https://www.spiel-des-jahres.de/sitemap_index.xml",)
    sitemap_rules = ((r"/kritikenrundschau-", "parse_review"),)

    custom_settings = {  # noqa: RUF012
        "USER_AGENT": os.getenv("SCRAPER_USER_AGENT"),
        "DOWNLOAD_DELAY": float(os.getenv("SCRAPER_DOWNLOAD_DELAY") or 1.0),
        "CONCURRENT_REQUESTS_PER_DOMAIN": int(
            os.getenv("SCRAPER_CONCURRENT_REQUESTS") or 4,
        ),
        "FEED_EXPORT_BATCH_ITEM_COUNT": int(
            os.getenv("SCRAPER_EXPORT_BATCH_ITEM_COUNT") or 10_000,
        ),
        "FEEDS": {
            os.getenv("SCRAPER_FEED_URI")
            or "results/reviews-%(time)s-%(batch_id)05d.jl": {
                "format": "jsonlines",
                "overwrite": False,
                "store_empty": False,
            },
        },
        "JOBDIR": os.getenv("SCRAPER_JOBDIR") or ".jobs",
        "ITEM_PIPELINES": {
            "spiel_des_jahres.llm_pipeline.LLMExtractionPipeline": 500,
        },
        # LLM Pipeline Settings
        "LLM_MODEL": os.getenv("LLM_MODEL") or None,
        "LLM_API_KEY": os.getenv("LLM_API_KEY"),
        "LLM_API_BASE_URL": os.getenv("LLM_API_BASE_URL") or None,
        "LLM_TEMPERATURE": os.getenv("LLM_TEMPERATURE") or None,
        "LLM_MAX_OUTPUT_TOKENS": os.getenv("LLM_MAX_OUTPUT_TOKENS") or None,
    }

    def parse_review(self, response: Response) -> dict[str, Any] | Request | None:
        article_html = response.xpath("//article").get()
        if not article_html:
            self.logger.error("No article HTML found")
            return None
        article_text = BeautifulSoup(article_html, "html.parser").get_text()

        item = {
            "url": response.url,
            "title": response.xpath("//title/text()").get(),
            "description": response.xpath("//meta[@name='description']/@content").get(),
            "date_published": response.xpath(
                "//meta[@property='article:published_time']/@content",
            ).get(),
            "image": response.xpath("//meta[@property='og:image']/@content").get(),
            "wp_json_url": response.xpath(
                "//link[@rel='alternate' and @type='application/json' "
                + "and @title='JSON']/@href",
            ).get(),
            "oembed_json_url": response.xpath(
                "//link[@rel='alternate' and @type='application/json+oembed']/@href",
            ).get(),
            "raw_text": article_text,
            # LLM-enriched content will be added via extension
        }

        if item["wp_json_url"]:
            return Request(
                item["wp_json_url"],
                callback=self.parse_wp_json,
                cb_kwargs={"item": item},
            )

        if item["oembed_json_url"]:
            return Request(
                item["oembed_json_url"],
                callback=self.parse_oembed_json,
                cb_kwargs={"item": item},
            )

        return item

    def parse_wp_json(
        self,
        response: Response,
        item: dict[str, Any],
    ) -> dict[str, Any] | Request:
        if not isinstance(response, TextResponse):
            self.logger.error("Expected TextResponse, got %s", type(response))
            return item

        try:
            item["wp_json"] = response.json()
        except Exception:
            self.logger.exception("Failed to parse wp_json: %s", response.text)
            item["wp_json"] = None

        if item["oembed_json_url"]:
            return Request(
                item["oembed_json_url"],
                callback=self.parse_oembed_json,
                cb_kwargs={"item": item},
            )

        return item

    def parse_oembed_json(
        self,
        response: Response,
        item: dict[str, Any],
    ) -> dict[str, Any] | Request:
        if not isinstance(response, TextResponse):
            self.logger.error("Expected TextResponse, got %s", type(response))
            return item

        try:
            item["oembed_json"] = response.json()
        except Exception:
            self.logger.exception("Failed to parse oembed_json: %s", response.text)
            item["oembed_json"] = None

        return item
