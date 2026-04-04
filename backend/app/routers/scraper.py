import gc
import re
import uuid
import os
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from bs4 import BeautifulSoup
from app.models.schemas import ScrapeRequest, ScrapeStatus, ProductResult, ReviewAction, TranslateRequest, TranslateResponse
from app.utils.background import (
    create_job, get_job, update_job,
    set_job_internal, get_job_internal, clear_job_internal,
    set_job_task, get_job_task, clear_job_task,
)
from app.services.scraper import (
    scrape_product, fetch_with_httpx, fetch_with_playwright,
    extract_all, detect_spa_heuristic,
)
from app.services.packager import create_package
from app.services.ai_analyzer import analyze_page_structure
from app.services.ai_cleaner import clean_description_with_ai
from app.services.ai_extractor import extract_description_with_ai
from app.services.shopline_formatter import generate_shopline_html
from app.services.ai_translator import translate_html

router = APIRouter(prefix="/api")

JOBS_DIR = "/tmp/scraper_jobs"

# Limit to 1 concurrent scrape to stay within Render free tier 512MB RAM
_scrape_semaphore = asyncio.Semaphore(1)
_EFFORT_TIMEOUTS = {"high": 900, "medium": 600}  # seconds

def _get_job_timeout(reasoning_effort: str | None) -> tuple[int, int]:
    """Return (timeout_seconds, timeout_minutes) based on reasoning effort."""
    timeout = _EFFORT_TIMEOUTS.get(reasoning_effort or "", 480)
    return timeout, timeout // 60

async def run_scrape_job(job_id: str, url: str, product_model: str | None, api_key: str | None = None, ai_model: str | None = None, reasoning_effort: str | None = None):
    timeout_secs, timeout_mins = _get_job_timeout(reasoning_effort)
    try:
        update_job(job_id, progress="Waiting in queue...")
        async with _scrape_semaphore:
            try:
                await asyncio.wait_for(
                    _execute_scrape_job(job_id, url, product_model, api_key, ai_model, reasoning_effort),
                    timeout=timeout_secs,
                )
            except asyncio.TimeoutError:
                update_job(job_id, status="failed", error=f"工作執行超時（超過{timeout_mins}分鐘）", progress=None)
            except asyncio.CancelledError:
                update_job(job_id, status="failed", error="工作已取消", progress=None)
    except asyncio.CancelledError:
        update_job(job_id, status="failed", error="工作已取消", progress=None)
    except Exception as e:
        update_job(job_id, status="failed", error=str(e), progress=None)
    finally:
        clear_job_task(job_id)

async def _execute_scrape_job(job_id: str, url: str, product_model: str | None, api_key: str | None = None, ai_model: str | None = None, reasoning_effort: str | None = None):
    if api_key:
        await _execute_with_ai(job_id, url, product_model, api_key, ai_model, reasoning_effort)
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


async def _execute_with_ai(job_id: str, url: str, product_model: str | None, api_key: str, ai_model: str | None, reasoning_effort: str | None = None):
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
            analysis = await analyze_page_structure(html, url, api_key, ai_model, reasoning_effort=reasoning_effort)

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
                analysis = await analyze_page_structure(html, url, api_key, ai_model, reasoning_effort=reasoning_effort)
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
                analysis=analysis, reasoning_effort=reasoning_effort,
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
                    analysis=analysis, reasoning_effort=reasoning_effort,
                )
                if ai_desc:
                    raw_data["description_html"] = ai_desc

        # Step 7: AI cleaner
        if raw_data.get("description_html"):
            update_job(job_id, progress="AI 正在優化內容...")
            raw_data["description_html"] = await clean_description_with_ai(
                raw_data["description_html"],
                raw_data.get("product_name", ""),
                api_key,
                ai_model,
                analysis=analysis, reasoning_effort=reasoning_effort,
            )

        model = product_model or raw_data.get("product_model", "product")

        # Step 8: Pause for user review — store context for refine/finalize
        set_job_internal(job_id,
            raw_html=html,
            api_key=api_key,
            ai_model=ai_model,
            reasoning_effort=reasoning_effort,
            analysis=analysis,
            product_name=raw_data.get("product_name", ""),
            product_model=model,
        )
        del html
        gc.collect()

        review_result = ProductResult(
            product_name=raw_data.get("product_name", "Unknown"),
            product_model=model,
            summary=raw_data.get("summary", ""),
            description=raw_data.get("description", ""),
            description_html=raw_data.get("description_html", ""),
            description_shopline="",
            source_url=raw_data.get("source_url", url),
        )
        update_job(job_id, status="awaiting_review", progress=None, result=review_result)
    except Exception as e:
        update_job(job_id, status="failed", error=str(e), progress=None)

async def _finalize_job(job_id: str, description_html: str, product_name: str,
                        product_model: str, summary: str, description: str,
                        source_url: str, api_key: str, ai_model: str | None,
                        reasoning_effort: str | None = None):
    """Generate Shopline HTML and package results."""
    try:
        update_job(job_id, status="processing", progress="正在生成 Shopline HTML...")
        shopline_html = ""
        if description_html:
            shopline_html = await generate_shopline_html(
                product_name, product_model, summary,
                description_html, api_key, ai_model,
                reasoning_effort=reasoning_effort,
            )

        result = ProductResult(
            product_name=product_name,
            product_model=product_model,
            summary=summary,
            description=description,
            description_html=description_html,
            description_shopline=shopline_html,
            source_url=source_url,
        )

        update_job(job_id, progress="Packaging results...")
        job_dir = os.path.join(JOBS_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        await create_package(result, job_dir)
        clear_job_internal(job_id)
        update_job(job_id, status="completed", progress=None, result=result)
    except Exception as e:
        update_job(job_id, status="failed", error=str(e), progress=None)


async def _refine_extraction(job_id: str, instructions: str):
    """Re-run AI extraction with user instructions, then return to review."""
    try:
        internal = get_job_internal(job_id)
        raw_html = internal.get("raw_html", "")
        api_key = internal["api_key"]
        ai_model = internal.get("ai_model")
        reasoning_effort = internal.get("reasoning_effort")
        analysis = internal.get("analysis")
        product_name = internal.get("product_name", "")

        if not raw_html:
            update_job(job_id, status="failed", error="Raw HTML not available for refine", progress=None)
            return

        update_job(job_id, status="processing", progress="AI 正在根據指示重新提取...")
        ai_desc = await extract_description_with_ai(
            raw_html, product_name, api_key, ai_model,
            analysis=analysis, extra_instructions=instructions,
            reasoning_effort=reasoning_effort,
        )

        if ai_desc:
            update_job(job_id, progress="AI 正在優化內容...")
            ai_desc = await clean_description_with_ai(
                ai_desc, product_name, api_key, ai_model,
                analysis=analysis, reasoning_effort=reasoning_effort,
            )

        # Update the review result with refined description
        job = get_job(job_id)
        if job and job.result:
            updated_result = job.result.model_copy(update={
                "description_html": ai_desc or job.result.description_html,
            })
            update_job(job_id, status="awaiting_review", progress=None, result=updated_result)
        else:
            update_job(job_id, status="awaiting_review", progress=None)
    except Exception as e:
        update_job(job_id, status="failed", error=str(e), progress=None)


@router.post("/scrape/{job_id}/review")
async def submit_review(job_id: str, review: ReviewAction):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="工作已過期或伺服器已重啟，請重新提交網址。")
    if job.status != "awaiting_review":
        raise HTTPException(status_code=400, detail="Job is not awaiting review")

    if review.action == "confirm":
        internal = get_job_internal(job_id)
        asyncio.create_task(_finalize_job(
            job_id,
            description_html=job.result.description_html if job.result else "",
            product_name=job.result.product_name if job.result else "",
            product_model=job.result.product_model if job.result else "product",
            summary=job.result.summary if job.result else "",
            description=job.result.description if job.result else "",
            source_url=job.result.source_url if job.result else "",
            api_key=internal.get("api_key", ""),
            ai_model=internal.get("ai_model"),
            reasoning_effort=internal.get("reasoning_effort"),
        ))
        update_job(job_id, status="processing", progress="正在生成 Shopline HTML...")
        return {"status": "processing"}
    else:
        asyncio.create_task(_refine_extraction(job_id, review.instructions))
        update_job(job_id, status="processing", progress="AI 正在根據指示重新提取...")
        return {"status": "processing"}


@router.post("/scrape/{job_id}/translate")
async def translate_job(job_id: str, req: TranslateRequest):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="工作已過期或伺服器已重啟，請重新提交網址。")
    if job.status not in ("completed", "awaiting_review"):
        raise HTTPException(status_code=400, detail="Job is not ready for translation")
    if not job.result:
        raise HTTPException(status_code=400, detail="No result to translate")

    translated_html, translated_shopline = await asyncio.gather(
        translate_html(job.result.description_html, req.target_language, req.api_key, req.ai_model),
        translate_html(job.result.description_shopline, req.target_language, req.api_key, req.ai_model),
    )

    return TranslateResponse(
        description_html=translated_html,
        description_shopline=translated_shopline,
    )


@router.post("/scrape")
async def submit_scrape(request: ScrapeRequest):
    job_id = str(uuid.uuid4())
    create_job(job_id)
    task = asyncio.create_task(run_scrape_job(job_id, str(request.url), request.product_model, request.api_key, request.ai_model, request.reasoning_effort))
    set_job_task(job_id, task)
    return {"job_id": job_id, "status": "processing"}

@router.get("/scrape/{job_id}")
async def get_scrape_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="工作已過期或伺服器已重啟，請重新提交網址。")
    return job

@router.post("/scrape/{job_id}/cancel")
async def cancel_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="工作已過期或伺服器已重啟，請重新提交網址。")
    if job.status in ("completed", "failed"):
        raise HTTPException(status_code=400, detail="Job already finished")

    task = get_job_task(job_id)
    if task and not task.done():
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
            pass

    update_job(job_id, status="failed", error="工作已取消", progress=None)
    clear_job_task(job_id)
    clear_job_internal(job_id)
    return {"status": "cancelled"}

@router.get("/scrape/{job_id}/download")
async def download_zip(job_id: str, background_tasks: BackgroundTasks):
    job = get_job(job_id)
    if not job or job.status != "completed":
        raise HTTPException(status_code=404, detail="工作已過期或未完成，請重新提交網址。")
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
