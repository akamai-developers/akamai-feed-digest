"""Crawler CronJob entry point - fetch feeds and extract articles"""

import asyncio
import logging

from app.db import get_pool, close_pool, article_url_exists, insert_article
from crawler.feeds import fetch_all_feeds
from crawler.extractor import extract_content

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def crawl():
    """Main crawl function: fetch feeds, extract content, store in DB"""
    await get_pool()

    items = await fetch_all_feeds()
    new_count = 0
    skip_count = 0

    for item in items:
        url = item["url"]
        if await article_url_exists(url):
            skip_count += 1
            continue

        content = await extract_content(url)
        await insert_article(
            url=url,
            title=item["title"],
            source=item["source"],
            content=content,
            published_at=item.get("published_at"),
        )
        new_count += 1

    logger.info(f"Crawl complete: {new_count} new, {skip_count} skipped")
    await close_pool()


def main():
    asyncio.run(crawl())


if __name__ == "__main__":
    main()
