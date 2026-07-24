FROM python:3.12-slim

WORKDIR /app

# Build context is the repo root (see docker-compose.yml) so scraper/ is
# reachable here -- the API installs it as a library (editable install) to
# reuse its db models, retrieve.py, and rag.py directly instead of
# duplicating that logic. scraper/requirements.txt still lists celery/
# playwright (needed by the worker, not by anything api imports), which end
# up installed here unused; accepted as pip-package weight, not worth a
# package split for this project's scale (see DECISIONS.md).
COPY scraper/requirements.txt scraper/requirements.txt
RUN pip install --no-cache-dir -r scraper/requirements.txt
COPY scraper/pyproject.toml scraper/pyproject.toml
COPY scraper/src scraper/src
RUN pip install --no-cache-dir -e scraper

COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt

COPY api/pyproject.toml api/pyproject.toml
COPY api/src api/src
RUN pip install --no-cache-dir -e api

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
