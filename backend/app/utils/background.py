import asyncio
from datetime import datetime
from app.models.schemas import ScrapeStatus

# In-memory job storage
jobs: dict[str, ScrapeStatus] = {}
job_timestamps: dict[str, datetime] = {}

def create_job(job_id: str) -> ScrapeStatus:
    status = ScrapeStatus(job_id=job_id, status="processing", progress="Starting...")
    jobs[job_id] = status
    job_timestamps[job_id] = datetime.now()
    return status

def update_job(job_id: str, **kwargs):
    if job_id in jobs:
        updated = jobs[job_id].model_copy(update=kwargs)
        jobs[job_id] = updated
        return updated
    return None

def get_job(job_id: str) -> ScrapeStatus | None:
    return jobs.get(job_id)
