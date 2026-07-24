"""Celery tasks: thin wrappers around crawl_one() that let a queued job
trigger the same fetch -> parse -> store pipeline the demo scripts call
directly.

robots_checker and rate_limiter are created once at module import time (i.e.
once per worker process) rather than per task, so their per-domain caches
(robots.txt rules, last-request timestamps) actually persist across the many
tasks a single worker processes -- a fresh RateLimiter per task would never
remember the previous request and the delay would do nothing. This is
process-local: with more than one worker process, each has its own cache and
rate limiting is only enforced within a process, not across all of them. Now
that Day 2's scaling task actually runs multiple worker containers against
the same domain, this means the *aggregate* request rate to a domain scales
roughly linearly with worker count instead of staying fixed at
`REQUEST_DELAY_SECONDS` -- e.g. 3 workers means up to ~3x the intended rate,
not just "3x more parallel." A Redis-backed shared token bucket would be the
correct fix; see DECISIONS.md's Day 2 scaling entry for why that was deferred
for this project (and why a naive per-worker delay divisor would have made
this worse, not better -- N workers each waiting delay/N independently
produces an N^2, not Nx, over-rate).

Table creation (init_db) is deliberately NOT run at import time -- creating
the engine/sessionmaker here is safe (SQLAlchemy doesn't open a connection
until a query actually runs), but issuing DDL is a real database round trip,
and this module gets imported by tests that have no database available. It
runs instead on Celery's `worker_process_init` signal, which only fires when
an actual worker process boots.
"""

import logging
from datetime import UTC, datetime

import requests
from celery import Task
from celery.signals import worker_process_init
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from scraper.celery_app import celery_app
from scraper.chunk import chunk_processed_page
from scraper.crawl import crawl_one
from scraper.db import (
    Chunk,
    DeadLetterTask,
    Page,
    ProcessedPage,
    get_engine,
    get_session_factory,
    init_db,
)
from scraper.embed import embed_text
from scraper.fetch import RetryableFetchError
from scraper.process import process_page
from scraper.rate_limit import RateLimiter
from scraper.robots import RobotsChecker
from scraper.sites import SITES

logger = logging.getLogger(__name__)

_engine = get_engine()
_session_factory = get_session_factory(_engine)

_robots_checker = RobotsChecker()
_rate_limiter = RateLimiter()

# Shared retry policy for both tasks below: exponential backoff starting
# small and capping at 5 minutes, jittered so a burst of simultaneously
# retrying tasks doesn't all hammer the target again at the exact same
# instant, giving up (and landing in dead_letter_tasks) after 5 attempts.
RETRY_BACKOFF_MAX_SECONDS = 300
MAX_RETRIES = 5


@worker_process_init.connect
def _init_db_on_worker_start(**kwargs) -> None:
    init_db(_engine)


def _write_dead_letter(task_name: str, url: str | None, error: str, attempt_count: int) -> None:
    """Records a permanently failed task (retries exhausted, or a
    non-retryable error on the first attempt) so it's visible and queryable
    instead of only existing in worker logs. Deliberately swallows its own
    failures (e.g. DB unreachable) rather than raising -- a dead-letter write
    failing should never mask or replace the original task failure that
    triggered it.
    """
    session = _session_factory()
    try:
        session.add(
            DeadLetterTask(
                url=url,
                task_name=task_name,
                error=error,
                failed_at=datetime.now(UTC),
                attempt_count=attempt_count,
            )
        )
        session.commit()
    except Exception:
        logger.exception("failed to write dead-letter record for %s (%s)", task_name, url)
    finally:
        session.close()


class CrawlUrlTask(Task):
    """Crawls a single URL using the named SITES fetch strategy, storing the
    result via the same crawl_one() pipeline used everywhere else. Returns
    the stored Page's id, or None if robots.txt disallowed the URL.

    crawl_one() itself decides whether a re-crawl is a new version (content
    changed) or a no-op (unchanged, returns the existing latest row). Either
    way this task gets a page id back -- what differs is whether that id has
    already been processed. Checking "does a ProcessedPage already exist for
    this id" (rather than trying to thread an explicit is-new-version flag
    through crawl_one()'s return value) is what decides whether to enqueue
    processing: a fresh id never has one yet, so it always gets processed; an
    unchanged re-crawl's id was already processed on a prior run, so
    reprocessing identical content is skipped. If a previous processing
    attempt failed and left no row, this also self-heals by retrying it.

    Retries only on RetryableFetchError (network timeouts, connection errors,
    HTTP 429/5xx) -- a robots.txt disallow isn't an exception at all
    (crawl_one() returns None for it, handled the same as always, untouched
    by any of this), and a permanent FetchError (404, 403, ...) isn't in
    autoretry_for, so it fails straight to the dead letter table instead of
    burning retries on a URL that will never succeed.
    """

    name = "scraper.crawl_url_task"
    autoretry_for = (RetryableFetchError,)
    retry_backoff = True
    retry_backoff_max = RETRY_BACKOFF_MAX_SECONDS
    retry_jitter = True
    max_retries = MAX_RETRIES

    def run(self, url: str, site_key: str) -> int | None:
        session = _session_factory()
        try:
            page = crawl_one(
                url,
                session,
                _robots_checker,
                _rate_limiter,
                fetch_fn=SITES[site_key].fetch_fn,
            )
            if page is None:
                return None
            already_processed = (
                session.query(ProcessedPage).filter_by(page_id=page.id).first() is not None
            )
            if already_processed:
                logger.info("page %s already processed for this version, skipping", page.id)
            else:
                process_page_task.delay(page.id)
            return page.id
        finally:
            session.close()

    def on_failure(self, exc, task_id, args, kwargs, einfo) -> None:
        url = args[0] if args else kwargs.get("url")
        _write_dead_letter(self.name, url, str(exc), self.request.retries + 1)
        super().on_failure(exc, task_id, args, kwargs, einfo)


crawl_url_task = celery_app.register_task(CrawlUrlTask())


class ProcessPageTask(Task):
    """Loads a stored Page, normalizes it via process_page(), and stores the
    validated result as a new ProcessedPage row. Runs as its own queued task
    (rather than inline in crawl_url_task) so raw storage and normalization
    are independently retryable -- a processing bug never loses the raw page,
    and this is the same shape the RAG indexing stage will use next.

    Retries only on OperationalError (a transient DB connectivity blip --
    this task does no network I/O of its own, so that's the realistic
    transient failure here). A pydantic ValidationError means process_page()
    built a record the schema rejects -- retrying the exact same stored
    page/HTML would produce the exact same invalid record every time, so
    that's non-retryable and goes straight to the dead letter table.

    Also re-checks "already processed" itself (not just crawl_url_task's
    check before enqueueing) as a safety net against duplicate delivery --
    e.g. task_acks_late redelivering a task whose worker crashed *after* it
    had already committed a ProcessedPage row but *before* the ack landed.
    Without this, that scenario would insert a second, redundant
    ProcessedPage row for the same page version.
    """

    name = "scraper.process_page_task"
    autoretry_for = (OperationalError,)
    retry_backoff = True
    retry_backoff_max = RETRY_BACKOFF_MAX_SECONDS
    retry_jitter = True
    max_retries = MAX_RETRIES

    def run(self, page_id: int) -> int | None:
        session = _session_factory()
        try:
            already_processed = (
                session.query(ProcessedPage).filter_by(page_id=page_id).first() is not None
            )
            if already_processed:
                logger.info("page %s already has a processed record, skipping", page_id)
                return None
            page = session.get(Page, page_id)
            try:
                record = process_page(page)
            except ValidationError as exc:
                # Non-retryable: re-processing identical input yields the
                # identical invalid record, so fail straight through to
                # on_failure() / the dead letter table rather than retrying.
                raise ValueError(f"processed record for page {page_id} failed validation") from exc
            processed = ProcessedPage(
                page_id=page.id,
                text=record.text,
                tables=record.tables,
                processed_at=datetime.now(UTC),
            )
            session.add(processed)
            session.commit()
            embed_page_task.delay(page.id)
            return processed.id
        finally:
            session.close()

    def on_failure(self, exc, task_id, args, kwargs, einfo) -> None:
        page_id = args[0] if args else kwargs.get("page_id")
        url = _best_effort_url_for_page(page_id)
        _write_dead_letter(self.name, url, str(exc), self.request.retries + 1)
        super().on_failure(exc, task_id, args, kwargs, einfo)


process_page_task = celery_app.register_task(ProcessPageTask())


class EmbedPageTask(Task):
    """Loads a page's ProcessedPage record, splits it into chunks
    (chunk.py), embeds each chunk via Ollama, and stores the results as
    Chunk rows. Third link in the crawl -> process -> embed chain, kept as
    its own task for the same reason process_page_task is separate from
    crawl_url_task: independent retries, and a slow/unavailable embedding
    service never blocks or loses the raw/processed data already stored.

    Skips work if this page_id already has chunks -- `pages.id` gets a new
    row per content version (see db.py), so "chunks already exist for this
    page_id" means this exact version was already embedded, the same
    versioning-aware skip pattern process_page_task uses for `already
    processed`. Also doubles as the redelivery safety net for
    task_acks_late, same reasoning as ProcessPageTask's own check.

    Retries on RequestException (Ollama unreachable, still loading the
    model, or a transient HTTP error from /api/embed) and OperationalError
    (transient DB connectivity). A partially-embedded page from a failed
    mid-loop attempt is safe to simply retry from scratch: chunk_processed_page()
    is deterministic for a given page_id, so re-running just re-embeds and
    re-inserts the same chunks -- there is no partial-row cleanup needed
    because nothing is written to the DB until the full chunk list is ready.
    """

    name = "scraper.embed_page_task"
    autoretry_for = (requests.exceptions.RequestException, OperationalError)
    retry_backoff = True
    retry_backoff_max = RETRY_BACKOFF_MAX_SECONDS
    retry_jitter = True
    max_retries = MAX_RETRIES

    def run(self, page_id: int) -> int | None:
        session = _session_factory()
        try:
            already_embedded = session.query(Chunk).filter_by(page_id=page_id).first() is not None
            if already_embedded:
                logger.info("page %s already has chunks for this version, skipping", page_id)
                return None
            processed = (
                session.query(ProcessedPage)
                .filter_by(page_id=page_id)
                .order_by(ProcessedPage.processed_at.desc(), ProcessedPage.id.desc())
                .first()
            )
            chunk_texts = chunk_processed_page(processed.text, processed.tables)
            embeddings = [embed_text(chunk) for chunk in chunk_texts]
            now = datetime.now(UTC)
            paired = zip(chunk_texts, embeddings, strict=True)
            for index, (chunk_text_value, embedding) in enumerate(paired):
                session.add(
                    Chunk(
                        page_id=page_id,
                        chunk_text=chunk_text_value,
                        embedding=embedding,
                        chunk_index=index,
                        created_at=now,
                    )
                )
            session.commit()
            return len(chunk_texts)
        finally:
            session.close()

    def on_failure(self, exc, task_id, args, kwargs, einfo) -> None:
        page_id = args[0] if args else kwargs.get("page_id")
        url = _best_effort_url_for_page(page_id)
        _write_dead_letter(self.name, url, str(exc), self.request.retries + 1)
        super().on_failure(exc, task_id, args, kwargs, einfo)


embed_page_task = celery_app.register_task(EmbedPageTask())


def _best_effort_url_for_page(page_id: int | None) -> str | None:
    """process_page_task only has a page_id, not a URL -- this resolves one
    for the dead-letter record when possible. Best-effort: if the DB itself
    is unreachable (a plausible reason process_page_task failed), this
    returns None rather than raising, so a dead-letter write for a DB-related
    failure doesn't itself try and fail to hit the DB a second time.
    """
    if page_id is None:
        return None
    session = _session_factory()
    try:
        page = session.get(Page, page_id)
        return page.url if page is not None else None
    except Exception:
        return None
    finally:
        session.close()
