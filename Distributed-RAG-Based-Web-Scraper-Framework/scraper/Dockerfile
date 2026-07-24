FROM python:3.12-slim

WORKDIR /app

# Playwright/Chromium is its own layer, pinned in its own file
# (requirements-playwright.txt) and installed before everything else --
# `playwright install --with-deps chromium` needs the `playwright` pip
# package to exist first, so this can't be a pure reorder of the old
# single-requirements.txt flow. Isolating it like this means a change to
# requirements.txt (any other Python dependency) only invalidates the
# layers below this one; Docker's cache invalidation cascades downward from
# whichever layer changed, so Chromium -- unchanged, ~30+ minutes to
# reinstall with --with-deps -- stays cached unless requirements-playwright.txt
# itself changes.
COPY requirements-playwright.txt .
RUN pip install --no-cache-dir -r requirements-playwright.txt
RUN playwright install --with-deps chromium

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY src ./src

RUN pip install --no-cache-dir -e .

CMD ["python", "-m", "scraper.worker"]
