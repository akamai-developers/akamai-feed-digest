"""Database connection pool and queries using asyncpg"""

import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import asyncpg

from app.config import DATABASE_URL

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def init_schema():
    """Execute schema.sql to initialize the database"""
    schema_path = Path(__file__).parent / "schema.sql"
    sql = schema_path.read_text()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(sql)
    logger.info("Database schema initialized")


# Article queries

async def article_url_exists(url: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchval("SELECT 1 FROM articles WHERE url = $1", url)
        return row is not None


async def insert_article(url: str, title: str, source: str, content: str,
                         published_at: Optional[datetime] = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO articles (url, title, source, content, published_at)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (url) DO NOTHING""",
            url, title, source, content, published_at
        )


async def get_article_counts():
    """Get article counts for 6h, 24h, 48h timeframes"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        counts = {}
        for hours in [24, 72, 168]:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM articles WHERE published_at IS NOT NULL AND published_at >= NOW() - $1 * INTERVAL '1 hour'",
                hours
            )
            counts[str(hours)] = count
        return counts


async def get_articles_in_timeframe(hours: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """SELECT id, url, title, source, content, published_at
               FROM articles
               WHERE published_at IS NOT NULL
                 AND published_at >= NOW() - $1 * INTERVAL '1 hour'
                 AND content IS NOT NULL AND content != ''
               ORDER BY published_at DESC""",
            hours
        )


# Job queries

async def create_job(timeframe_hours: int, interests: str = "", user_profile_id: int = 1) -> str:
    job_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO jobs (id, user_profile_id, timeframe_hours, interests, status)
               VALUES ($1, $2, $3, $4, 'queued')""",
            job_id, user_profile_id, timeframe_hours, interests or None
        )
    return job_id


async def get_job(job_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM jobs WHERE id = $1", job_id
        )


async def claim_next_job(conn):
    """Claim the next queued job atomically using FOR UPDATE SKIP LOCKED"""
    return await conn.fetchrow(
        """UPDATE jobs SET status = 'scaling_gpu', started_at = NOW()
           WHERE id = (
               SELECT id FROM jobs
               WHERE status = 'queued'
               ORDER BY created_at ASC
               LIMIT 1
               FOR UPDATE SKIP LOCKED
           )
           RETURNING *"""
    )


async def update_job_status(job_id: str, status: str,
                            progress: Optional[str] = None,
                            article_count: Optional[int] = None,
                            error: Optional[str] = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if status in ('completed', 'failed'):
            await conn.execute(
                """UPDATE jobs
                   SET status = $2, progress = $3, article_count = $4,
                       error = $5, completed_at = NOW()
                   WHERE id = $1""",
                job_id, status, progress, article_count, error
            )
        else:
            await conn.execute(
                """UPDATE jobs
                   SET status = $2, progress = $3, article_count = $4, error = $5
                   WHERE id = $1""",
                job_id, status, progress, article_count, error
            )


# Score queries

async def get_cached_scores(article_ids: list, user_profile_id: int = 1):
    """Get already-scored articles to avoid re-scoring"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT article_id, score FROM article_scores
               WHERE article_id = ANY($1) AND user_profile_id = $2""",
            article_ids, user_profile_id
        )
        return {row['article_id']: row['score'] for row in rows}


async def save_scores(scores: dict, user_profile_id: int = 1):
    """Save article scores, upserting on conflict"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        for article_id, score in scores.items():
            await conn.execute(
                """INSERT INTO article_scores (article_id, user_profile_id, score)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (article_id, user_profile_id)
                   DO UPDATE SET score = $3, scored_at = NOW()""",
                article_id, user_profile_id, score
            )


# Digest queries

async def save_digest(job_id: str, briefing: str, article_ids: list, scores: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO digests (job_id, briefing, article_ids, scores)
               VALUES ($1, $2, $3, $4::jsonb)""",
            job_id, briefing, article_ids,
            __import__('json').dumps(scores)
        )


async def get_digest(job_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM digests WHERE job_id = $1", job_id
        )


# User profile queries

async def get_user_profile(profile_id: int = 1):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM user_profiles WHERE id = $1", profile_id
        )


# CLI entry point for DB init
if __name__ == "__main__":
    if "--init" in sys.argv:
        asyncio.run(init_schema())
        print("Database schema initialized successfully")
    else:
        print("Usage: python -m app.db --init")
