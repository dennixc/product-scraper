# Product Data Scraper

A web app for scraping product data from manufacturer websites. Paste a product URL and get structured product info (name, model, images, descriptions) with processed images ready for Shopline e-commerce listings.

## Architecture

- **Frontend**: Next.js 15 + TypeScript + Tailwind CSS v4 + shadcn/ui → deployed to **Vercel**
- **Backend**: Python FastAPI + Playwright + Pillow → deployed to **Render** (Docker)

## Features

- Paste any product manufacturer URL to scrape product data
- Auto-extracts: product name, model number, summary, description
- Downloads and classifies images (white-background → main, others → gallery)
- Main images: cropped to 800x800 square
- Gallery images: resized to 1280px wide, original aspect ratio
- Download all results as a ZIP (images + JSON)

## Local Development

### Prerequisites

- Node.js 18+
- Python 3.11+
- Playwright system dependencies (or use Docker for backend)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# Copy env and configure
cp .env.example .env

# Run
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install

# Copy env and configure
cp .env.local.example .env.local

# Run
npm run dev
```

The frontend runs on http://localhost:3000, backend on http://localhost:8000.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/scrape` | Submit scraping job → returns `job_id` |
| `GET` | `/api/scrape/{job_id}` | Poll job status and results |
| `GET` | `/api/scrape/{job_id}/download` | Download ZIP (images + JSON) |
| `GET` | `/api/scrape/{job_id}/images/{filename}` | Serve individual image |
| `GET` | `/health` | Health check |

## Deployment

### Backend → Render

1. Create a new **Docker Web Service** on Render
2. Set root directory to `backend/`
3. Add env var: `CORS_ORIGINS=https://your-app.vercel.app`
4. Deploy

### Frontend → Vercel

1. Connect repo to Vercel
2. Set root directory to `frontend/`
3. Add env var: `NEXT_PUBLIC_API_URL=https://your-backend.onrender.com`
4. Deploy
