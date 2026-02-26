"""FastAPI application for Feed Digest"""

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.db import get_pool, close_pool, get_article_counts, create_job, get_job, get_digest
from app.k8s_status import get_vllm_pod_status
from app.models import DigestRequest, DigestResponse, JobStatus, DigestResult, ArticleCounts, PodStatus

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    logger.info("Database pool initialized")
    yield
    await close_pool()
    logger.info("Database pool closed")


app = FastAPI(title="Feed Digest", version="1.0.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html") as f:
        return f.read()


@app.get("/api/counts", response_model=ArticleCounts)
async def counts():
    article_counts = await get_article_counts()
    return ArticleCounts(counts=article_counts)


@app.post("/api/digest", response_model=DigestResponse)
async def create_digest(req: DigestRequest):
    if req.timeframe_hours not in (24, 72, 168):
        raise HTTPException(status_code=400, detail="timeframe_hours must be 24, 72, or 168")
    job_id = await create_job(req.timeframe_hours, interests=req.interests)
    return DigestResponse(job_id=job_id)


@app.get("/api/jobs/{job_id}", response_model=JobStatus)
async def job_status(job_id: str):
    row = await get_job(job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    pod_status = None
    if row['status'] in ('scaling_gpu', 'scoring', 'writing'):
        pod_dict = await get_vllm_pod_status()
        if pod_dict:
            pod_status = PodStatus.model_validate(pod_dict)

    return JobStatus(
        id=str(row['id']),
        status=row['status'],
        progress=row['progress'],
        article_count=row['article_count'],
        interests=row.get('interests'),
        pod_status=pod_status,
        created_at=row['created_at'],
        started_at=row['started_at'],
        completed_at=row['completed_at'],
        error=row['error']
    )


@app.get("/api/digests/{job_id}", response_model=DigestResult)
async def digest_result(job_id: str):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Job not yet completed")

    row = await get_digest(job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Digest not found")

    processing_time = None
    if job['started_at'] and job['completed_at']:
        processing_time = (job['completed_at'] - job['started_at']).total_seconds()

    scores = row['scores']
    if isinstance(scores, str):
        scores = json.loads(scores)

    return DigestResult(
        briefing=row['briefing'],
        article_count=len(row['article_ids']),
        total_scored=len(scores) if scores else None,
        interests=job.get('interests'),
        timeframe_hours=job['timeframe_hours'],
        scores=scores,
        created_at=row['created_at'],
        processing_time_seconds=processing_time
    )


@app.get("/health")
async def health():
    return {"status": "healthy"}
