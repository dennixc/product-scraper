import asyncio
from datetime import datetime
from app.models.schemas import ScrapeStatus

# In-memory job storage
jobs: dict[str, ScrapeStatus] = {}
job_timestamps: dict[str, datetime] = {}
# Internal data not exposed via API (raw_html, api_key, etc. for review/refine)
job_internal: dict[str, dict] = {}
# asyncio Task references for cancellation
job_tasks: dict[str, asyncio.Task] = {}

def create_job(job_id: str) -> ScrapeStatus:
    status = ScrapeStatus(job_id=job_id, status="processing", progress="Starting...")
    jobs[job_id] = status
    job_timestamps[job_id] = datetime.now()
    return status

def update_job(job_id: str, **kwargs):
    if job_id in jobs:
        job_timestamps[job_id] = datetime.now()
        updated = jobs[job_id].model_copy(update=kwargs)
        jobs[job_id] = updated
        return updated
    return None

def get_job(job_id: str) -> ScrapeStatus | None:
    return jobs.get(job_id)

def set_job_internal(job_id: str, **kwargs):
    if job_id not in job_internal:
        job_internal[job_id] = {}
    job_internal[job_id].update(kwargs)

def get_job_internal(job_id: str) -> dict:
    return job_internal.get(job_id, {})

def clear_job_internal(job_id: str):
    job_internal.pop(job_id, None)

def set_job_task(job_id: str, task: asyncio.Task):
    job_tasks[job_id] = task

def get_job_task(job_id: str) -> asyncio.Task | None:
    return job_tasks.get(job_id)

def clear_job_task(job_id: str):
    job_tasks.pop(job_id, None)
