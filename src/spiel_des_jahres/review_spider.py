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

    custom_settings = {  # noqa: RUF012
        "DOWNLOAD_DELAY": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 16,
        "FEED_EXPORT_BATCH_ITEM_COUNT": 10_000,
        "FEEDS": {
            "results/reviews-%(time)s-%(batch_id)05d.jl": {
                "format": "jsonlines",
                "overwrite": False,
                "store_empty": False,
            },
        },
        "JOBDIR": ".jobs",
        # "EXTENSIONS": {
        #     "spiel.extensions.LLMExtractionExtension": 500,
        # },
    }

    def parse_review(self, response: Response) -> Generator[dict[str, Any]]:
        article_html = response.xpath("//article").get()
        if not article_html:
            self.logger.error("No article HTML found")
            return
        article_text = BeautifulSoup(article_html, "html.parser").get_text()

        yield {
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
