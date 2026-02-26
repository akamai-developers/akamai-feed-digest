"""Pydantic models for request/response validation"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class DigestRequest(BaseModel):
    timeframe_hours: int = 24
    interests: str = ""


class DigestResponse(BaseModel):
    job_id: str


class PodEvent(BaseModel):
    reason: str
    message: str
    timestamp: Optional[str] = None
    type: str = "Normal"


class PodStatus(BaseModel):
    phase: Optional[str] = None
    container_state: Optional[str] = None
    ready: bool = False
    events: List[PodEvent] = []


class JobStatus(BaseModel):
    id: str
    status: str
    progress: Optional[str] = None
    article_count: Optional[int] = None
    interests: Optional[str] = None
    pod_status: Optional[PodStatus] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class DigestResult(BaseModel):
    briefing: str
    article_count: int
    total_scored: Optional[int] = None
    interests: Optional[str] = None
    timeframe_hours: Optional[int] = None
    scores: Optional[Dict[str, Any]] = None
    created_at: datetime
    processing_time_seconds: Optional[float] = None


class ArticleCounts(BaseModel):
    counts: Dict[str, int]
