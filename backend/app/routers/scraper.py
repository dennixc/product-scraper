import gc
import re
import uuid
import os
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from bs4 import BeautifulSoup
from app.models.schemas import ScrapeRequest, ScrapeStatus, ProductResult
from app.utils.background import create_job, get_job, update_job
from app.services.scraper import (
    scrape_product, fetch_with_httpx, fetch_with_playwright,
    extract_all, detect_spa_heuristic,
)
from app.services.packager import create_package
from app.services.ai_analyzer import analyze_page_structure
from app.services.ai_cleaner import clean_description_with_ai
from app.services.ai_extractor import extract_description_with_ai
from app.services.shopline_formatter import generate_shopline_html

router = APIRouter(prefix="/api")

JOBS_DIR = "/tmp/scraper_jobs"

# Limit to 1 concurrent scrape to stay within Render free tier 512MB RAM
_scrape_semaphore = asyncio.Semaphore(1)

async def run_scrape_job(job_id: str, url: str, product_model: str | None, api_key: str | None = None, ai_model: str | None = None):
    try:
        update_job(job_id, progress="Waiting in queue...")
        async with _scrape_semaphore:
            await _execute_scrape_job(job_id, url, product_model, api_key, ai_model)
    except Exception as e:
        update_job(job_id, status="failed", error=str(e), progress=None)

async def _execute_scrape_job(job_id: str, url: str, product_model: str | None, api_key: str | None = None, ai_model: str | None = None):
    if api_key:
        await _execute_with_ai(job_id, url, product_model, api_key, ai_model)
    else:
        await _execute_legacy(job_id, url, product_model)


async def _execute_legacy(job_id: str, url: str, product_model: str | None):
    """No API key path — pure rule-based scraping, identical to previous behavior."""
    try:
        update_job(job_id, progress="Connecting to page...")
        raw_data = await scrape_product(url)
        raw_data.pop("_raw_html", None)

        model = product_model or raw_data.get("product_model", "product")
        result = ProductResult(
            product_name=raw_data.get("product_name", "Unknown"),
            product_model=model,
            summary=raw_data.get("summary", ""),
            description=raw_data.get("description", ""),
            description_html=raw_data.get("description_html", ""),
            description_shopline="",
            source_url=raw_data.get("source_url", url),
        )

        update_job(job_id, progress="Packaging results...")
        job_dir = os.path.join(JOBS_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        await create_package(result, job_dir)
        update_job(job_id, status="completed", progress=None, result=result)
    except Exception as e:
        update_job(job_id, status="failed", error=str(e), progress=None)


async def _execute_with_ai(job_id: str, url: str, product_model: str | None, api_key: str, ai_model: str | None):
    """AI-guided path — uses AI to analyze page structure and choose optimal strategy."""
    try:
        # Step 1: Lightweight httpx fetch
        update_job(job_id, progress="Connecting to page...")
        html = await fetch_with_httpx(url)

        # Step 2: AI structure analysis
        needs_javascript = False
        extraction_strategy = "rule_based"
        analysis = None

        if html:
            update_job(job_id, progress="AI 正在分析頁面結構...")
            analysis = await analyze_page_structure(html, url, api_key, ai_model)

            if analysis:
                needs_javascript = analysis["needs_javascript"]
                extraction_strategy = analysis["extraction_strategy"]
            else:
                # Step 3: AI analysis failed — fallback to heuristic
                needs_javascript = detect_spa_heuristic(html)
        else:
            # httpx failed entirely — need Playwright
            needs_javascript = True

        # Step 4: Re-fetch with Playwright if needed
        if needs_javascript:
            if html:
                del html
                gc.collect()
            update_job(job_id, progress="啟動瀏覽器渲染頁面...")
            html = await fetch_with_playwright(url)

            # If we had no analysis yet (httpx failed), try analyzing Playwright HTML
            if analysis is None and html:
                analysis = await analyze_page_structure(html, url, api_key, ai_model)
                if analysis:
                    extraction_strategy = analysis["extraction_strategy"]

        # Step 5: Always run rule-based extraction for name/model/summary
        soup = BeautifulSoup(html, 'lxml')
        raw_data = extract_all(soup, url, analysis=analysis)
        del soup

        # Step 6: Description extraction based on strategy
        if extraction_strategy == "ai_extraction":
            update_job(job_id, progress="AI 正在提取產品描述...")
            ai_desc = await extract_description_with_ai(
                html, raw_data.get("product_name", ""), api_key, ai_model,
                analysis=analysis,
            )
            if ai_desc:
                raw_data["description_html"] = ai_desc
            # If AI extraction failed, keep rule-based description_html as fallback
        else:
            # rule_based — check if result is sufficient, AI fallback if not
            desc_html = raw_data.get("description_html", "")
            plain_text = re.sub(r'<[^>]+>', ' ', desc_html)
            plain_text = re.sub(r'\s+', ' ', plain_text).strip()
            if len(plain_text) < 500 and html:
                update_job(job_id, progress="AI 正在補充提取描述...")
                ai_desc = await extract_description_with_ai(
                    html, raw_data.get("product_name", ""), api_key, ai_model,
                    analysis=analysis,
                )
                if ai_desc:
                    raw_data["description_html"] = ai_desc

        # Step 7: Release raw HTML
        del html
        gc.collect()

        # Step 8: AI cleaner → Shopline formatter → package
        if raw_data.get("description_html"):
            update_job(job_id, progress="AI 正在優化內容...")
            raw_data["description_html"] = await clean_description_with_ai(
                raw_data["description_html"],
                raw_data.get("product_name", ""),
                api_key,
                ai_model,
                analysis=analysis,
            )

        model = product_model or raw_data.get("product_model", "product")

        shopline_html = ""
        if raw_data.get("description_html"):
            update_job(job_id, progress="正在生成 Shopline HTML...")
            shopline_html = await generate_shopline_html(
                raw_data.get("product_name", ""),
                model,
                raw_data.get("summary", ""),
                raw_data["description_html"],
                api_key,
                ai_model,
            )

        result = ProductResult(
            product_name=raw_data.get("product_name", "Unknown"),
            product_model=model,
            summary=raw_data.get("summary", ""),
            description=raw_data.get("description", ""),
            description_html=raw_data.get("description_html", ""),
            description_shopline=shopline_html,
            source_url=raw_data.get("source_url", url),
        )

        update_job(job_id, progress="Packaging results...")
        job_dir = os.path.join(JOBS_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        await create_package(result, job_dir)
        update_job(job_id, status="completed", progress=None, result=result)
    except Exception as e:
        update_job(job_id, status="failed", error=str(e), progress=None)

@router.post("/scrape")
async def submit_scrape(request: ScrapeRequest):
    job_id = str(uuid.uuid4())
    create_job(job_id)
    asyncio.create_task(run_scrape_job(job_id, str(request.url), request.product_model, request.api_key, request.ai_model))
    return {"job_id": job_id, "status": "processing"}

@router.get("/scrape/{job_id}")
async def get_scrape_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/scrape/{job_id}/download")
async def download_zip(job_id: str, background_tasks: BackgroundTasks):
    job = get_job(job_id)
    if not job or job.status != "completed":
        raise HTTPException(status_code=404, detail="Job not found or not completed")
    zip_path = os.path.join(JOBS_DIR, job_id, "result.zip")
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="ZIP file not found")
    model_name = job.result.product_model if job.result else "product"
    # Free result data from memory after download
    background_tasks.add_task(_clear_job_result, job_id)
    return FileResponse(zip_path, media_type="application/zip", filename=f"{model_name}.zip")

def _clear_job_result(job_id: str):
    job = get_job(job_id)
    if job:
        job.result = None
