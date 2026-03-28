# CLAUDE.md

## Project Overview
Product Data Scraper — a full-stack app that scrapes product info (name, model, description, images) from manufacturer websites, uses AI to clean content and generate Shopline-ready HTML, and packages results as downloadable ZIP files.

## Architecture
- **Frontend** (`frontend/`): Next.js + TypeScript + Tailwind CSS + shadcn/ui
- **Backend** (`backend/`): FastAPI + Playwright + BeautifulSoup + Pillow
- **Deployment**: Vercel (frontend) + Render via Docker (backend)

## Key Files
- `backend/app/main.py` — FastAPI app entry, CORS config
- `backend/app/services/scraper.py` — Playwright-based page scraping logic
- `backend/app/services/ai_cleaner.py` — OpenRouter AI content cleaning (去重複/無關內容)
- `backend/app/services/shopline_formatter.py` — AI-powered Shopline HTML generator (inline styles, responsive)
- `backend/app/services/image_processor.py` — Image downloading & processing
- `backend/app/services/packager.py` — ZIP packaging
- `backend/app/routers/scraper.py` — API routes (`/api/scrape`, `/api/scrape/{id}`, etc.)
- `backend/app/models/schemas.py` — Pydantic models (ScrapeRequest, ProductResult, ScrapeStatus)
- `frontend/src/lib/api.ts` — Frontend API client
- `frontend/src/app/page.tsx` — Main page component
- `frontend/src/components/result-preview.tsx` — Result display (description HTML + Shopline HTML cards)
- `backend/Dockerfile` — Uses `python:3.12-slim` + `playwright install --with-deps chromium`

## AI Features (requires OpenRouter API key)
- **AI Content Cleaning** (`ai_cleaner.py`): 用 LLM 清理 description_html，移除重複/無關內容
- **Shopline HTML** (`shopline_formatter.py`): 將產品資料轉換為帶 inline styles 嘅 Shopline 兼容 HTML（hero banner、feature cards、styled sections）
- Default model: `minimax/minimax-m2.7`，用戶可自選 model

## Development

### Backend
```bash
cd backend
python -m venv venv
source venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Environment Variables
- **Backend**: `CORS_ORIGINS` (comma-separated allowed origins, default: `http://localhost:3000`)
- **Frontend**: `NEXT_PUBLIC_API_URL` (backend URL, default: `http://localhost:8000`)

## Deployment
- **Repo**: https://github.com/dennixc/product-scraper
- **Frontend (Vercel)**: https://product-scraper-six.vercel.app
- **Backend (Render)**: https://product-scraper-czi1.onrender.com
- Render auto-deploys from `main` branch

## Conventions
- Communicate in Cantonese/Chinese
- Keep responses concise
- Don't over-engineer; only change what's needed
