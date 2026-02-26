"""Worker job polling loop and orchestration"""

import asyncio
import logging
import time

import httpx

from app.config import VLLM_BASE_URL
from app.db import (
    get_pool, close_pool, claim_next_job, update_job_status,
    get_articles_in_timeframe, save_digest
)
from worker.llm import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

POLL_INTERVAL = 5

DEFAULT_INTERESTS = "software engineering, cloud computing, AI and machine learning, open source, DevOps, distributed systems"


async def wait_for_vllm():
    """Wait for vLLM to be ready, triggering scale-up if needed"""
    logger.info("Checking vLLM availability (may trigger scale-up)...")
    async with httpx.AsyncClient(timeout=600.0) as client:
        while True:
            try:
                resp = await client.get(f"{VLLM_BASE_URL}/v1/models")
                if resp.status_code == 200:
                    logger.info("vLLM is ready")
                    return
            except (httpx.ConnectError, httpx.ReadTimeout):
                pass
            logger.info("vLLM not ready yet, waiting...")
            await asyncio.sleep(10)


async def process_job(job):
    """Process a single job through the full pipeline"""
    job_id = str(job['id'])
    timeframe = job['timeframe_hours']

    interests = job.get('interests') or DEFAULT_INTERESTS

    logger.info(f"Processing job {job_id}: {timeframe}h timeframe, interests: {interests}")

    try:
        # Phase 1: Scale GPU
        await update_job_status(job_id, "scaling_gpu", "Scaling GPU...")
        await wait_for_vllm()

        # Phase 2: Gather articles
        await update_job_status(job_id, "scoring", "Gathering articles...")
        articles = await get_articles_in_timeframe(timeframe)
        article_list = [dict(r) for r in articles]

        if not article_list:
            await update_job_status(job_id, "completed",
                                    "No articles found in timeframe",
                                    article_count=0)
            await save_digest(job_id, "No articles found in the selected timeframe.",
                              [], {})
            return

        await update_job_status(job_id, "scoring",
                                f"Scoring {len(article_list)} articles...",
                                article_count=len(article_list))

        # Phase 3: Score and write briefing
        briefing, top_ids, scores = run_pipeline(
            article_list, interests, VLLM_BASE_URL
        )

        await update_job_status(job_id, "writing", "Writing briefing...")

        # Phase 4: Save and complete
        scores_dict = {str(k): v for k, v in scores.items()}
        await save_digest(job_id, briefing, top_ids, scores_dict)
        await update_job_status(job_id, "completed", "Done",
                                article_count=len(top_ids))
        logger.info(f"Job {job_id} completed: {len(top_ids)} articles in briefing")

    except Exception as e:
        logger.exception(f"Job {job_id} failed")
        await update_job_status(job_id, "failed", error=str(e))


async def poll_loop():
    """Main polling loop: claim and process jobs"""
    pool = await get_pool()
    logger.info("Worker started, polling for jobs...")

    while True:
        try:
            async with pool.acquire() as conn:
                job = await claim_next_job(conn)

            if job:
                await process_job(job)
            else:
                await asyncio.sleep(POLL_INTERVAL)
        except Exception:
            logger.exception("Error in poll loop")
            await asyncio.sleep(POLL_INTERVAL)


def main():
    try:
        asyncio.run(poll_loop())
    except KeyboardInterrupt:
        logger.info("Worker shutting down")


if __name__ == "__main__":
    main()
