"""Article content extraction using trafilatura"""

import logging

import httpx
import trafilatura

logger = logging.getLogger(__name__)


async def extract_content(url: str) -> str | None:
    """Fetch a URL and extract the main article text"""
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text

        text = trafilatura.extract(html)
        if text and len(text.strip()) > 100:
            return text.strip()
        return None
    except Exception as e:
        logger.debug(f"Content extraction failed for {url}: {e}")
        return None
