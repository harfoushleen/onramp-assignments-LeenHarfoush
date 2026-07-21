# Distributed RAG-Based Web Scraper Framework

A distributed, fault-tolerant web scraping framework augmented with Retrieval-Augmented
Generation (RAG). Extracts data from multiple sites at scale, indexes it, and exposes it
through an API that answers natural-language queries grounded in the scraped content with
cited sources.

## Layout

- `scraper/` — Python worker: crawling, parsing, politeness/rate-limiting, job queue consumer.
- `api/` — FastAPI service: raw data, processed data, search, and RAG Q&A endpoints.
- `ui/` — React (Vite) single-page frontend: search + Q&A with citations.

Each service has its own `Dockerfile` and is deployable as an independent, replicable unit.

## Status

Day 1 scaffold: repo structure, CI (lint + test per service), and Dockerfiles. Crawler logic,
job queue wiring, RAG pipeline, and UI functionality land in subsequent days per the project plan.

## Local development

Both Python services use a per-folder virtual environment — installing straight into your global
Python (skipping `venv`) will silently upgrade/downgrade whatever's already installed there for
other projects, and puts `ruff`/`pytest` in a Scripts folder that's usually not on PATH.

**scraper**
```powershell
cd scraper
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt -e .
.venv\Scripts\ruff check .
.venv\Scripts\pytest
```

**api**
```powershell
cd api
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt -e .
.venv\Scripts\ruff check .
.venv\Scripts\pytest
.venv\Scripts\uvicorn api.main:app --reload
```

(Or activate the venv first with `.venv\Scripts\Activate.ps1` and drop the `.venv\Scripts\` prefix
on each command.)

**ui**
```
cd ui
npm install
npm run lint
npm test
npm run dev
```
