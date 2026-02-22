import asyncio
import shutil
import os
from datetime import datetime, timedelta
from app.utils.background import jobs, job_timestamps

JOBS_DIR = "/tmp/scraper_jobs"
MAX_AGE_MINUTES = 30
CLEANUP_INTERVAL_SECONDS = 600  # 10 minutes

async def start_cleanup_task():
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        cleanup_old_jobs()

def cleanup_old_jobs():
    cutoff = datetime.now() - timedelta(minutes=MAX_AGE_MINUTES)
    expired = [jid for jid, ts in job_timestamps.items() if ts < cutoff]
    for jid in expired:
        jobs.pop(jid, None)
        job_timestamps.pop(jid, None)
        job_dir = os.path.join(JOBS_DIR, jid)
        if os.path.exists(job_dir):
            shutil.rmtree(job_dir, ignore_errors=True)
