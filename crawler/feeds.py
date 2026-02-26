"""RSS, Hacker News, and Reddit feed fetchers"""

import logging
from datetime import datetime, timezone
from typing import Optional

import feedparser
import httpx

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    # General tech
    "https://hnrss.org/newest?points=50",
    "https://www.techmeme.com/feed.xml",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "https://www.theverge.com/rss/index.xml",
    # Software Engineering
    "https://blog.pragmaticengineer.com/rss/",
    "https://martinfowler.com/feed.atom",
    "https://danluu.com/atom.xml",
    "https://jvns.ca/atom.xml",
    # Cloud / DevOps
    "https://aws.amazon.com/blogs/aws/feed/",
    "https://www.cncf.io/feed/",
    "https://kubernetes.io/feed.xml",
    "https://cloud.google.com/blog/rss",
    # Security
    "https://krebsonsecurity.com/feed/",
    "https://blog.cloudflare.com/rss",
    "https://www.schneier.com/feed/atom/",
    "https://www.troyhunt.com/rss/",
    # Databases
    "https://planetscale.com/blog/rss.xml",
    "https://www.timescale.com/blog/rss/",
    # Frontend / Web
    "https://web.dev/feed.xml",
    "https://css-tricks.com/feed/",
    "https://www.smashingmagazine.com/feed/",
    "https://www.joshwcomeau.com/rss.xml",
    # Mobile
    "https://android-developers.googleblog.com/feeds/posts/default",
    "https://developer.apple.com/news/rss/news.rss",
    "https://www.swiftbysundell.com/feed.rss",
    "https://blog.jetbrains.com/kotlin/feed/",
    # Open Source
    "https://github.blog/feed/",
    "https://blog.opensource.org/feed/",
    "https://lwn.net/headlines/rss",
    "https://www.theregister.com/software/open_source/headlines.atom",
    # AI / ML
    "https://simonwillison.net/atom/everything/",
    "https://openai.com/blog/rss.xml",
    "https://huggingface.co/blog/feed.xml",
    "https://blog.research.google/atom.xml",
    # Distributed Systems
    "https://www.allthingsdistributed.com/atom.xml",
    "https://blog.acolyer.org/feed/",
    "https://fly.io/blog/feed.xml",
]

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"
HN_LIMIT = 30


def _parse_date(entry) -> Optional[datetime]:
    """Try to extract a datetime from a feedparser entry"""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                from time import mktime
                return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
            except (ValueError, OverflowError):
                pass
    return None


async def fetch_rss() -> list:
    """Fetch articles from RSS feeds"""
    items = []
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for feed_url in RSS_FEEDS:
            try:
                resp = await client.get(feed_url)
                resp.raise_for_status()
                feed = feedparser.parse(resp.text)
                for entry in feed.entries[:20]:
                    url = getattr(entry, "link", None)
                    title = getattr(entry, "title", None)
                    if url and title:
                        items.append({
                            "url": url,
                            "title": title,
                            "source": f"rss:{feed_url.split('/')[2]}",
                            "published_at": _parse_date(entry),
                        })
                logger.info(f"RSS {feed_url}: {len(feed.entries)} entries")
            except Exception as e:
                logger.warning(f"RSS fetch failed for {feed_url}: {e}")
    return items


async def fetch_hn() -> list:
    """Fetch top stories from Hacker News API"""
    items = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(HN_TOP_URL)
            resp.raise_for_status()
            story_ids = resp.json()[:HN_LIMIT]

            for sid in story_ids:
                try:
                    resp = await client.get(HN_ITEM_URL.format(sid))
                    story = resp.json()
                    url = story.get("url")
                    title = story.get("title")
                    if url and title:
                        pub_time = None
                        if story.get("time"):
                            pub_time = datetime.fromtimestamp(story["time"], tz=timezone.utc)
                        items.append({
                            "url": url,
                            "title": title,
                            "source": "hackernews",
                            "published_at": pub_time,
                        })
                except Exception as e:
                    logger.warning(f"HN item {sid} failed: {e}")
            logger.info(f"HN: fetched {len(items)} stories")
        except Exception as e:
            logger.warning(f"HN top stories fetch failed: {e}")
    return items



async def fetch_all_feeds() -> list:
    """Fetch from all sources and return combined list"""
    rss = await fetch_rss()
    hn = await fetch_hn()
    all_items = rss + hn
    logger.info(f"Total feed items: {len(all_items)}")
    return all_items
