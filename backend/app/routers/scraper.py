import uuid
import os
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.models.schemas import ScrapeRequest, ScrapeStatus
from app.utils.background import create_job, get_job, update_job
from app.services.scraper import scrape_product
from app.services.image_processor import process_images
from app.services.packager import create_package

router = APIRouter(prefix="/api")

JOBS_DIR = "/tmp/scraper_jobs"

async def run_scrape_job(job_id: str, url: str, product_model: str | None):
    try:
        update_job(job_id, progress="Connecting to page...")
        raw_data = await scrape_product(url)

        update_job(job_id, progress="Processing images...")
        job_dir = os.path.join(JOBS_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)

        model = product_model or raw_data.get("product_model", "product")
        result = await process_images(raw_data, job_dir, model)

        update_job(job_id, progress="Packaging results...")
        await create_package(result, job_dir)

        update_job(job_id, status="completed", progress=None, result=result)
    except Exception as e:
        update_job(job_id, status="failed", error=str(e), progress=None)

@router.post("/scrape")
async def submit_scrape(request: ScrapeRequest):
    job_id = str(uuid.uuid4())
    create_job(job_id)
    asyncio.create_task(run_scrape_job(job_id, str(request.url), request.product_model))
    return {"job_id": job_id, "status": "processing"}

@router.get("/scrape/{job_id}")
async def get_scrape_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/scrape/{job_id}/download")
async def download_zip(job_id: str):
    job = get_job(job_id)
    if not job or job.status != "completed":
        raise HTTPException(status_code=404, detail="Job not found or not completed")
    zip_path = os.path.join(JOBS_DIR, job_id, "result.zip")
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="ZIP file not found")
    model_name = job.result.product_model if job.result else "product"
    return FileResponse(zip_path, media_type="application/zip", filename=f"{model_name}.zip")

@router.get("/scrape/{job_id}/images/{filename}")
async def get_image(job_id: str, filename: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # Prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    image_path = os.path.join(JOBS_DIR, job_id, "images", filename)
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(image_path, media_type="image/jpeg")
