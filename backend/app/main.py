import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import scraper
from app.utils.cleanup import start_cleanup_task

@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_task = asyncio.create_task(start_cleanup_task())
    yield
    cleanup_task.cancel()

app = FastAPI(title="Product Scraper API", lifespan=lifespan)

origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scraper.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
