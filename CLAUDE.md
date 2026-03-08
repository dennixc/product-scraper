# CLAUDE.md

## Project Overview
Product Data Scraper — a full-stack app that scrapes product info (name, model, specs, images) from manufacturer websites, processes images, and packages them as downloadable ZIP files.

## Architecture
- **Frontend** (`frontend/`): Next.js + TypeScript + Tailwind CSS + shadcn/ui
- **Backend** (`backend/`): FastAPI + Playwright + BeautifulSoup + Pillow
- **Deployment**: Vercel (frontend) + Render via Docker (backend)

## Key Files
- `backend/app/main.py` — FastAPI app entry, CORS config
- `backend/app/services/scraper.py` — Playwright-based page scraping logic
- `backend/app/services/image_processor.py` — Image downloading & processing
- `backend/app/services/packager.py` — ZIP packaging
- `backend/app/routers/scraper.py` — API routes (`/api/scrape`, `/api/scrape/{id}`, etc.)
- `frontend/src/lib/api.ts` — Frontend API client
- `frontend/src/app/page.tsx` — Main page component
- `backend/Dockerfile` — Uses `python:3.12-slim` + `playwright install --with-deps chromium`

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
