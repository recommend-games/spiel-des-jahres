from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup
from scrapy.spiders.sitemap import SitemapSpider

if TYPE_CHECKING:
    from collections.abc import Generator

    from scrapy.http.response import Response


class SpielReviewSpider(SitemapSpider):
    name = "spiel_des_jahres"
    allowed_domains = ("spiel-des-jahres.de",)

    sitemap_urls = ("https://www.spiel-des-jahres.de/robots.txt",)
    sitemap_rules = ((r"/kritikenrundschau-", "parse_review"),)

    # custom_settings = {
    #     "EXTENSIONS": {
    #         "spiel.extensions.LLMExtractionExtension": 500,
    #     },
    # }

    def parse_review(self, response: Response) -> Generator[dict[str, Any]]:
        article_html = response.css("article").get()
        if not article_html:
            self.logger.error("No article HTML found")
            return
        article_text = BeautifulSoup(article_html, "html.parser").get_text()

        yield {
            "url": response.url,
            "title": response.css("title::text").get(),
            "description": response.css(
                'meta[name="description"]::attr(content)',
            ).get(),
            "date_published": response.css(
                'meta[property="article:published_time"]::attr(content)',
            ).get(),
            "raw_text": article_text,
            # LLM-enriched content will be added via extension
        }
