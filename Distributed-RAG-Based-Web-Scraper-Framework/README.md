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

Day 1: repo structure, CI (lint + test per service), Dockerfiles, and a single-worker crawler
(fetch → parse → store) proven end to end against `quotes.toscrape.com`, storing rows in
Postgres. Job queue wiring, multi-worker scaling, RAG pipeline, and UI functionality land in
subsequent days per the project plan.

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
Then open http://localhost:5173 in a browser.

## Running everything together (Docker Compose)

`docker-compose.yml` (at this folder's root) wires up Postgres, the API, and the UI. Postgres is
mapped to **host port 5434** (not the default 5432) because this machine already has other,
unrelated projects' Postgres containers bound to 5432/5433 — 5434 avoids clashing with those.
That only affects the host-side port; containers still talk to each other over 5432 internally.

```
cd Distributed-RAG-Based-Web-Scraper-Framework
docker compose up --build postgres api ui
```

Then check:
- http://localhost:4173 — the UI
- http://localhost:8000/docs — FastAPI's interactive Swagger page
- http://localhost:8000/health — raw JSON health check

The `scraper` service isn't included in that `up` command on purpose: its container's default
command still runs Day 1's placeholder (`python -m scraper.worker`), which just prints one line
and exits — that gets replaced by the real job-queue worker once that's built. To actually run a
crawl against the compose-managed Postgres:

```
docker compose run --rm scraper python -m scraper.demo
docker compose exec postgres psql -U rag -d rag_scraper -c "SELECT id, url, content_hash FROM pages ORDER BY id;"
```

Shut everything down with `docker compose down` (add `-v` to also delete the Postgres volume and
its crawled data).
