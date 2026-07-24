# Distributed RAG-Based Web Scraper Framework — Project Report

## 1. Overview

This project implements a distributed, fault-tolerant web scraping framework augmented with
Retrieval-Augmented Generation (RAG). It extracts data from multiple websites, processes and
indexes that data, and exposes it through an API capable of answering natural-language questions
grounded in the scraped content, with citations back to source URLs.

**Language/runtime:** Python, chosen for its mature scraping ecosystem (BeautifulSoup, Playwright)
and distributed-task-queue support (Celery), and because it was the language I was already most
comfortable working quickly in — an important factor given the project's short timeline.

**Services:**
- `scraper/` — the crawling/worker service (Python)
- `api/` — FastAPI service exposing raw data, processed data, search, and RAG Q&A endpoints
- `ui/` — a minimal React (Vite) frontend for search and Q&A

Each service has its own Dockerfile and runs as an independent, replicable container, per the
assignment's requirement that components be independently deployable.

---

## 2. Phase 1: Project Setup

### 2.1 Repository, CI, and Containerization

I set up a three-service skeleton (scraper, API, UI), a GitHub Actions CI workflow that lints and
tests all three services on every push, and a per-service Dockerfile so each can run as a
standalone container.

**Technology choices and justification:**

| Choice | Alternative considered | Why I went this way |
|---|---|---|
| Python (scraper + API) | TypeScript/Node.js | Python's scraping ecosystem (BeautifulSoup, Playwright, Celery) is more mature and I already knew the language well, which mattered for a short build timeline. Node would have meant one fewer language to juggle, but weaker libraries for this specific job. |
| FastAPI (API service) | Flask / Django REST | FastAPI gives async support and request validation out of the box. Flask would need extra libraries (e.g. marshmallow, flask-restx) to match that, adding setup time. |
| Vite + React (UI) | Create React App | CRA is effectively unmaintained; Vite is the current standard and needed no extra configuration for TypeScript, a dev server, or production builds. |
| Three separate services, each independently containerized | A single monolithic app | The assignment explicitly requires each component to be deployable as an independent, replicable unit — this also sets up the ability to scale worker containers independently from the API later. |

**Other implementation notes:**
- The CI workflow lives at the repository root (`.github/workflows/`) rather than inside the
  project subfolder, because GitHub Actions only discovers workflows at the repo root. `paths:`
  filters scope it to only run when this project's files change, since the repository also
  contains the previous assignment.

**How each container works:**
- The scraper's image runs the worker entrypoint.
- The API's image serves FastAPI via `uvicorn` on port 8000.
- The UI's image builds the static React app and serves it with a lightweight static server on
  port 4173.

### 📸 Screenshots

**Figure 2.1** — Repo structure (`scraper/`, `api/`, `ui/` folders):

![Figure 2.1 — repo structure](images/figure_2.1.png)

**Figure 2.2** — CI passing (three parallel jobs: scraper / api / ui):

![Figure 2.2 — CI passing](images/figure_2.2.png)


---

## 3. Phase 2: Single-Worker Crawler (Static Site)

### 3.1 What was built

A complete fetch → parse → store pipeline: given a URL, the crawler checks robots.txt
permissions, respects a per-domain rate limit, fetches the page, strips it down to its title and
main text (discarding scripts/styles), computes a content hash, and stores the result in
Postgres. This was verified end-to-end against 10 real pages of `quotes.toscrape.com`.

### 3.2 Technology choices and justification

| Choice | Alternative considered | Why I went this way |
|---|---|---|
| `quotes.toscrape.com` as the static test site | A real-world commercial site | Purpose-built for scraping practice, so no real Terms of Service concern. Also has a JS-rendered variant (/js/), reused later for the JS-rendering requirement instead of vetting a fourth site. |
| SQLAlchemy (ORM) | Raw `psycopg` queries | queries via psycopg	The API service needs to query the same table later — one shared, typed model avoids duplicating query logic across services. |


### 3.3 How it works

`crawl_one()` is the core pipeline function: it checks robots.txt permission, waits for the
per-domain rate limiter, fetches the page with a real User-Agent and timeout, parses it with
BeautifulSoup (stripping `<script>`/`<style>` tags and normalizing whitespace), computes a
SHA-256 hash of the extracted text, and inserts a row (URL, raw HTML, extracted text, content
hash, timestamp) into Postgres.

### 📸 Screenshots

**Figure 3.1** — Live crawl output (each page fetched/stored) and the resulting `pages` rows in Postgres:

![Figure 3.1 — live crawl and stored rows](images/figure_3.1.png)

---

## 4. Phase 3: Robots.txt Compliance and Rate Limiting

*(This section doubles as the assignment's required ethics/compliance note.)*

### 4.1 Compliance approach

Before fetching any URL, the crawler fetches and caches that domain's `robots.txt` once per run
(not once per page) via Python's standard library `urllib.robotparser`. I confirmed directly that
`quotes.toscrape.com` returns a 404 for `/robots.txt`, which `RobotFileParser` correctly
interprets as "no restrictions" — every path checked (`/`, `/page/1/`, `/login`, `/api/quotes`)
came back allowed.

If a URL is disallowed, the crawler logs a clear message and skips it — this is treated as a
normal, expected outcome of polite crawling, not an error, so no exception is raised and nothing
is written to the database.

Separately, a per-domain rate limiter enforces a configurable minimum delay between requests to
the same domain (`REQUEST_DELAY_SECONDS`, defaulting to 1.5 seconds), so the crawler never
requests pages from a single site faster than a human clicking through it would.

### 4.2 Key decisions

- The robots.txt check uses the exact same User-Agent string as the actual page fetch, since
  robots.txt rules can be User-Agent-specific — checking permissions under a different UA than
  the one actually used could produce an incorrect answer on sites with UA-specific rules.
- Rate limiting is applied **per domain**, not globally, so that being polite to one slow site
  doesn't unnecessarily delay requests to a different site.

### 📸 Screenshots

**Figure 4.1** — Robots.txt check (`True`) and the test suite passing:

![Figure 4.1 — robots.txt check and passing tests](images/figure_4.1.png)

---

## 5. Phase 2 (continued): JavaScript-Rendered Crawling
 
### 5.1 What was built
 
A second fetch strategy, using Playwright to drive headless Chromium, for pages whose content is
rendered by JavaScript rather than present in the initial HTML. This is selected per site via a
simple configuration registry rather than automatic detection, and proven against
`quotes.toscrape.com/js/` — the same site's JS-rendering variant, avoiding the need to separately
vet a fourth domain for compliance. Every downstream step (parsing, hashing, storage) is
unchanged; only how the HTML is obtained differs.
 
### 5.2 Technology choices and justification
 
| Choice | Alternative considered | Why I went this way |
|---|---|---|
| Playwright | Selenium | Playwright's Python API has built-in auto-waiting and integrates `wait_for_selector` directly, rather than a separate `WebDriverWait` bolted onto a lower-level driver protocol. It also ships browser binaries via a single install step, avoiding Selenium's separate driver-version-matching requirement. |
| A per-site fetch-strategy registry (static vs. JS-rendered), not automatic JS-detection | Sniffing whether a page needs JS rendering | The assignment only requires handling both page types, not detecting which is which automatically. An explicit, simple configuration is easier to reason about and to justify. |
| Wait for a specific CSS selector to appear, not a fixed sleep | A fixed delay (e.g. `sleep(3)`) before reading the page | Waiting for actual content confirms the page is genuinely ready, and avoids either wasting time on a fast-loading page or failing on a slow one. |
 
### 5.3 Compliance check
 
Confirmed directly that `robots.txt` permissions were re-checked for the `/js/` path
specifically (not just assumed from the static site's check) — `quotes.toscrape.com` still
returns no `robots.txt` at all, so every path checked came back allowed.
 
### 5.4 Verifying the two fetch strategies agree
 
To confirm the JavaScript-rendering path was extracting real content — not an empty page shell —
I compared text extracted from the static and JS-rendered versions of the same pages. The two are
not byte-for-byte identical (the JS-rendered template omits one small link label and swaps a
sidebar for a footer credit line), but after accounting for that known difference, the actual
quote and author content extracted by both strategies matched closely across every page tested —
confirming both fetch paths retrieve equivalent real content, not placeholder or partial HTML.
 
### 📸 Screenshots
 
**Figure 5.1** — Robots.txt permission check for the `/js/` path:
 
![Figure 5.1 — robots.txt check for JS-rendered path](images/robots.txt_check.png)
 
**Figure 5.2** — JS-rendered vs. static content comparison, confirming equivalent extracted text:
 
![Figure 5.2 — JS vs static comparison](images/JS-vs-static_comparison.png)
 
**Figure 5.3** — Full test suite passing, including the JS-rendering strategy tests:
 
![Figure 5.3 — test suite passing](images/nice_to_have_test.png)
 
---
 
## 6. Phase 2 (continued): Large-Scale, Paginated Crawling
 
### 6.1 What was built
 
A crawler that walks `books.toscrape.com`'s paginated book catalog, following the site's own
"next page" link rather than a hardcoded URL pattern, and — on each listing page — also visits
every linked book's detail page. This satisfies the assignment's requirement for a site with a
large number of pages: the crawl comfortably reaches several hundred stored pages, well within
the "practical equivalent of 500+" the brief allows for.
 
### 6.2 What content is stored, and why
 
Both listing pages and individual book detail pages are stored. Listing pages are thin (a
title, price, and rating per book) but establish the pagination structure; book detail pages
contain a full text description **and** a structured product-information table (UPC, price,
tax, availability, review count). Storing both gives a realistic, mixed dataset and directly
satisfies a later requirement to handle more than one content type — the product table is a
genuine structured (non-paragraph) content type, distinct from the free-text descriptions and
quote content collected elsewhere.
 
### 6.3 Key design decisions
 
| Choice | Alternative considered | Why I went this way |
|---|---|---|
| Discover the "next page" link from each page's own HTML | A hardcoded `page-N.html` URL pattern | More robust — if the site's page count changes, the crawl still terminates correctly at the real last page instead of guessing. |
| Store both listing and detail pages | Detail pages only | Produces a more realistic dataset (thin index pages alongside rich content) and provides a table-based content type needed later, at the cost of roughly doubling total page count for the same crawl range. |
 
### 6.4 Compliance check
 
`books.toscrape.com/robots.txt` also returns no file (same convention as the other test sites
used), so no site-specific restrictions apply. Every request made during this crawl — listing
page or detail page — goes through the same robots-check and rate-limiting logic already used
elsewhere in the project.
 
### 📸 Screenshots
 
**Figure 6.1** — A full crawl run, showing pages being stored and the final count/timing:
 
![Figure 6.1 — 300-page crawl baseline run](images/real_300-page_baseline_run.png)
 
**Figure 6.2** — Stored data showing both content types (thin listing pages and rich detail pages with structured product tables):
 
![Figure 6.2 — mixed content types stored](images/proof_of_the_mixed_content_types.png)
 
---
 
## 7. Phase 2 (continued): Distributed Job Queue
 
### 7.1 What was built
 
Crawling now happens through a message queue rather than being called directly: a worker
process consumes jobs from the queue, and each job runs the same fetch → parse → store pipeline
used throughout the project. This directly satisfies the requirement to distribute scraping
tasks using a job queue rather than running everything as one script.
 
### 7.2 Technology choices and justification
 
| Choice | Alternative considered | Why I went this way |
|---|---|---|
| Celery + Redis | RabbitMQ, Kafka, BullMQ | Both listed as acceptable options in the assignment brief. Redis serving as both the message broker and the results store keeps the system to one additional moving part instead of two; this project has no need for a heavier broker (RabbitMQ) or a log-structured one (Kafka). |
 
### 7.3 How it works
 
Every page that ends up stored — including listing pages — is the result of a worker having
processed a queued job, not of a script writing to the database directly. A lightweight
discovery step still has to read each listing page to find its "next" link and its book links,
since that information only exists in the page's own HTML, but that step does not store
anything itself; it queues a job for every page it finds, including the listing page. This
keeps a clean guarantee: everything in the database was produced by a worker consuming a job
from the queue.
 
### 📸 Screenshots
 
**Figure 7.1** — Enqueuing a batch of crawl jobs, and the resulting stored rows:
 
![Figure 7.1 — enqueue script and database proof](images/enque_script+database_proof.png)
 
**Figure 7.2** — A worker process receiving and completing queued jobs in real time:
 
![Figure 7.2 — worker consuming queued jobs](images/worker_log.png)
 
---
 
## 8. Phase 2 (continued): Horizontal Scaling
 
### 8.1 What was built and measured
 
The crawler worker is packaged so that multiple independent instances can run at once, each in
its own container, all consuming jobs from the same shared queue. I measured the same 300-page
crawl of `books.toscrape.com` with 1 worker container versus 3 worker containers to directly
demonstrate the assignment's horizontal-scaling requirement.
 
| Workers | Time | Rate |
|---|---|---|
| 1 container | 474.9s | 1.58s/page |
| 3 containers | 160.3s | 0.53s/page |
 
**Result: a 2.96x speedup with 3 containers** — close to linear, as expected for a workload
where each page is fetched and processed independently.
 
### 8.2 A note on measurement validity
 
An initial comparison showed almost no difference between 1 and 3 containers. This was traced
to the worker's task pool defaulting to one process per CPU core, meaning a single container was
already running many crawl processes in parallel — the comparison was measuring available CPU
cores, not container count, which does not demonstrate genuine multi-instance distribution. This
was corrected by pinning each container to one task at a time, so that container count is what
actually drives throughput in the measurement above. This distinction — multiple independent
worker instances, not simply multiple processes on one machine — is explicitly called out in the
assignment brief, so I verified the fix restored an apples-to-apples comparison before reporting
the final numbers.
 
### 8.3 A known, documented limitation
 
Per-domain rate limiting (Section 4) is tracked independently by each worker process rather than
shared across containers. With N containers crawling the same domain concurrently, the aggregate
request rate to that domain can scale up to roughly Nx the configured per-worker delay, rather
than staying capped at the single-worker rate. I considered building a shared, Redis-backed rate
limiter to enforce a single global rate across all containers, but this would cap total crawl
throughput at the single-worker rate regardless of how many containers are running — which would
prevent the horizontal-scaling speedup above from being demonstrated at all. Given that the
target site is a public scraping-practice site with no real compliance risk from a bounded,
documented over-rate, I accepted this as a known limitation for this project's scope rather than
building additional shared-state infrastructure to close it.
 
### 📸 Screenshots
 
**Figure 8.1** — Timed crawl runs at 1 container and at 3 containers:
 
![Figure 8.1 — 1 vs 3 container timing runs](images/1_Vs_3_container_runs.png)
 
**Figure 8.2** — Three independent worker containers running simultaneously:
 
![Figure 8.2 — 3 containers running](images/3_containers_running.png)
 
---
 
## 9. Phase 3: Data Processing — Normalization, Structured Content, and Versioning
 
### 9.1 Normalization and a second content type
 
Building on the raw `pages` table (Section 3), a second processing step now produces a
validated, structured record for each page, stored separately in a new `processed_pages` table
that references the original raw row rather than overwriting it — both the raw and processed
versions are retained. This runs as its own queued step, triggered after a page is successfully
crawled, so a failure in processing never puts the already-stored raw data at risk.
 
Beyond plain body text, processed records also capture a second, structured content type where
present: for book detail pages, the product-information table (UPC, price, tax, availability,
review count) is extracted as genuine key–value data, separate from the free-text description.
Pages with no such table (e.g. quote pages) simply produce an empty table list, satisfying the
requirement to handle more than one content type without forcing every page into the same shape.
 
**Technology choices and justification:**
 
| Choice | Alternative considered | Why I went this way |
|---|---|---|
| Pydantic for schema validation | A hand-written validation function | Provides real, typed validation (malformed data raises immediately) with substantially less code, and is a natural fit alongside FastAPI in the API service. |
| A separate `processed_pages` table, referencing the raw page | Adding processed columns directly to `pages` | Keeps the raw and processed versions both retained and independently queryable, per the requirement — nothing is overwritten. |
| Processing as a second, independently queued task | Running processing inline as part of the same crawl task | Isolates failures — if processing fails on an unusual page shape, the already-crawled raw data is unaffected and only the processing step needs to retry. This also matches the pipeline shape the assignment itself describes (scraped → processed → indexed → queried). |
 
### 9.2 Basic versioning
 
Re-crawling a URL no longer blindly inserts a new row. The content hash of the freshly fetched
page is compared against the most recent stored version for that URL: if unchanged, nothing new
is written; if changed (or this is the first crawl), a new version is stored alongside the
existing history rather than overwriting it. The same logic extends to processed records, so an
unchanged page is not needlessly reprocessed either. A small query helper determines which
version of a page is current, rather than maintaining a separate "is current" flag that would
need updating on every prior row each time a new version lands.
 
This was verified with a real crawl: fetching the same live page twice in a row correctly
produced no duplicate, since its content genuinely hadn't changed; simulating a subsequent
content change then correctly produced a second, distinct version.
 
### 📸 Screenshots
 
**Figure 9.1** — A processed page's structured table sitting alongside a page with no table (`tables: []`), proving the second content type is handled correctly:
 
![Figure 9.1 — table vs. no-table content types](images/table-vs-no-table_proof.png)
 
**Figure 9.2** — Test suite passing after the processing module was added:
 
![Figure 9.2 — tests passing after processing module](images/test_suite_passing.png)
 
**Figure 9.3** — Versioning demo: an unchanged re-crawl produces no duplicate, and a genuine content change produces a new version:
 
![Figure 9.3 — versioning demo](images/versioning_demo.png)
 
**Figure 9.4** — Two real, distinct versions of the same URL stored in the database:
 
![Figure 9.4 — two stored versions of the same page](images/proof_of_2_real_dbs.png)
 
**Figure 9.5** — Test suite passing after versioning was added:
 
![Figure 9.5 — tests passing after versioning](images/test_suite_passing_2.0.png)
 
---
 
## 10. Phase 3 (continued): Fault Tolerance
 
### 10.1 What was built
 
The scraping pipeline now handles realistic failure scenarios rather than assuming every
crawl succeeds: transient failures (network timeouts, connection errors, rate-limiting or
server errors) are automatically retried with exponential backoff, while failures that
retrying cannot fix (a permanent 4xx response, or content that fails schema validation) are not
retried and instead recorded in a dedicated, queryable `dead_letter_tasks` table rather than
disappearing into logs. A robots.txt disallow continues to be treated as a normal skip, not a
failure, and is explicitly excluded from this retry/dead-letter logic.
 
Separately, the system was verified to recover from an actual worker process crashing mid-task:
a job held by a worker that dies does not get silently lost — it is picked up and completed by a
different, surviving worker.
 
**Technology choices and justification:**
 
| Choice | Alternative considered | Why I went this way |
|---|---|---|
| Celery's built-in retry/backoff (`autoretry_for`, exponential backoff with jitter, capped retries) | Hand-rolled retry logic | Celery already implements correct exponential-backoff-with-jitter behavior; no reason to reimplement it. |
| A dedicated `dead_letter_tasks` table | Relying on Celery/worker logs alone | Makes permanently failed tasks visible and queryable directly, rather than requiring someone to search logs to discover what failed and why. |
 
### 10.2 Retryable vs. non-retryable failures
 
Network timeouts, connection errors, and HTTP 429/5xx responses are treated as transient and
retried. A permanent HTTP error (e.g. 404) is not retried, since the same request will fail
identically every time. Similarly, content that fails schema validation during processing is not
retried, since reprocessing the same stored content would produce the same invalid result again.
This distinction matters for the same reason rate limiting does: retrying failures that cannot
possibly succeed only wastes time and delays surfacing a real problem.
 
### 10.3 Demonstrating recovery from a worker crash
 
Two worker processes were run concurrently, consuming from the same shared queue while crawling
a real, larger batch of pages. One worker was force-killed mid-task while jobs were still in
progress. The system was configured so that a job is only considered complete once a worker
finishes it — not the moment a worker merely picks it up — so a job held by a worker that dies
before finishing remains recoverable rather than being silently lost.
 
In practice, recovery of the abandoned job did not happen purely by waiting: investigating the
underlying message queue directly showed the abandoned job was correctly marked as eligible for
reassignment, but the periodic check that normally triggers reassignment wasn't firing often
enough under the surviving worker's single-task-at-a-time execution. Starting a third worker
process immediately triggered that check as part of its own startup, and the abandoned job was
picked up and completed within seconds — by a worker other than the one that had crashed, which
is precisely the outcome this requirement is meant to demonstrate. The final state confirmed
every job completed successfully with no permanent failures recorded.
 
This is included in the report in this level of detail deliberately: the recovery mechanism did
not behave exactly as a first, simpler prediction assumed, and understanding why — rather than
only reporting that recovery eventually happened — is itself evidence that the fault-tolerance
design is genuinely understood rather than just configured and left untested.
 
### 📸 Screenshots
 
**Figure 10.1** — Test suite passing after fault-tolerance handling was added:
 
![Figure 10.1 — tests passing after fault tolerance](images/test_suite_3.0.png)
 
**Figure 10.2** — Clean state confirmed before the crash-recovery demo:
 
![Figure 10.2 — reset before crash demo](images/fault_tolerance_reset_before_demo.png)
 
**Figure 10.3** — A worker process being force-killed mid-task:
 
![Figure 10.3 — killing a worker mid-task](images/fault_tolerance_kill_worker.png)
 
**Figure 10.4** — Jobs completing normally before the crash:
 
![Figure 10.4 — progress before the crash](images/fault_tolerance_progress_before_crash.png)
 
**Figure 10.5** — The abandoned job being recovered and completed after the crash:
 
![Figure 10.5 — recovery after the crash](images/fault_tolerance_recovery_after_crash.png)
 
**Figure 10.6** — Final verification: all jobs completed successfully, with no permanent failures recorded:
 
![Figure 10.6 — final verification, no dead letters](images/fault_tolerance_final_verification.png)
 
---
 
## 11. Phase 4: Chunking and Embedding
 
### 11.1 What was built
 
Processed pages are now split into overlap-based chunks and embedded into vector
representations, stored in the same Postgres database as the rest of the project's data. This
is the first stage of the RAG pipeline, chained onto the existing crawl → process pipeline as a
third queued step, so a page automatically moves from raw → processed → chunked-and-embedded
without any manual intervention.
 
### 11.2 Technology choices and justification
 
| Choice | Alternative considered | Why I went this way |
|---|---|---|
| Overlap-based chunking (fixed-size chunks with a percentage overlap between consecutive chunks) | Naive fixed-length splitting with no overlap | A hard cut at a fixed length can slice a fact or sentence across a chunk boundary, so whichever chunk retrieval picks up loses the other half. Carrying part of one chunk into the next means a boundary-straddling fact is very likely to appear whole in at least one chunk. |
| pgvector on the existing Postgres | A separate vector database (e.g. Chroma, Pinecone) | Keeps one database for both relational and vector data rather than running a second store and keeping the two in sync — consistent with the project's Day 1 database decision. |
| Ollama, running locally, for both embeddings and answer generation (next section) | A paid API-based embedding/LLM service | Free, requires no API key, and works fully offline once models are downloaded — meaning anyone running this project doesn't need their own paid API credentials just to see it work, which matters for a project meant to be run and graded by someone else. |
 
### 11.3 Handling table content in chunks
 
Structured table data (Section 9) is serialized into readable "Key: Value" text and stored as
its own chunk, rather than being split apart or given a separate storage mechanism. This keeps
table content searchable using the exact same retrieval mechanism as ordinary text, without
adding schema complexity for a distinction nothing downstream currently needs.
 
### 11.4 Versioning applies to embeddings too
 
Re-embedding is skipped for a page whose content hasn't changed, using the same versioning logic
introduced in Section 9 — an unchanged re-crawl doesn't trigger redundant chunking or embedding
work, since it would produce identical results.
 
### 📸 Screenshots
 
**Figure 11.1** — The full crawl → process → embed task chain completing for real pages:
 
![Figure 11.1 — full pipeline task chain](images/worker_log_three_task_chain.png)
 
**Figure 11.2** — Real stored chunks with embeddings, including a table serialized as chunk text:
 
![Figure 11.2 — chunks and embeddings verification](images/chucks_verification_query.png)
 
---
 
## 12. Phase 4 (continued): Retrieval and Grounded Answer Generation
 
### 12.1 What was built
 
Given a natural-language question, the system embeds the query, finds the most relevant stored
chunks by vector similarity search, and passes them to a locally-running LLM to generate an
answer — with the answer citing exactly which source URLs it drew from. This is the core
capability the assignment asks for: retrieval grounded in the scraped content, not a general
open-ended chat response.
 
### 12.2 Technology choice and justification
 
| Choice | Alternative considered | Why I went this way |
|---|---|---|
| `llama3.2:3b` for answer generation | A smaller 1B-parameter model, or a larger 7B-class model | The smaller model was noticeably weaker at reliably following "only answer from this context, cite your sources" instructions — a real risk for citation accuracy. A larger model gave better prose quality but ran meaningfully slower on CPU-only inference, for a quality gain not needed for a grounded Q&A demo. The 3B model was the best balance of instruction-following and practical response time. |
 
### 12.3 Only searching the latest version of each page
 
Since pages are versioned rather than overwritten (Section 9), retrieval is explicitly
restricted to each URL's most recent version. Without this, a page re-crawled multiple times
could surface a stale chunk from an old version, or the same fact could misleadingly appear to
come from two different sources when really it's two versions of the same page.
 
### 12.4 Multi-source synthesis and citations
 
Retrieval is not artificially limited to one result per page — if the best-matching chunks for
a question legitimately span multiple pages, all of them are returned and used together. Each
citation number corresponds to one source URL (not one chunk), so an answer can draw facts from
several sources at once while citing each one clearly. If nothing relevant is found, the system
returns a fixed "no relevant content" response rather than letting the model improvise an
answer with nothing to ground it.
 
Verified directly, live, with real questions: one query correctly compared prices across three
different real book pages, citing all three distinctly. A separate query asking to compare two
books on a specific topic that didn't actually both exist in the data correctly declined to
compare them and explained why, rather than fabricating a comparison. An unrelated question
(asking about the weather) correctly reported that the retrieved sources contained no relevant
information, rather than hallucinating an answer — demonstrating that grounding actually
prevents fabricated responses, not just that citations are technically present.
 
### 📸 Screenshots
 
**Figure 12.1** — Retrieval ranking verified against a real vector database:
 
![Figure 12.1 — retrieval tests passing against real pgvector](images/DB_retrieval_passing.png)
 
**Figure 12.2** — Three real queries demonstrating multi-source synthesis, honest refusal, and correct handling of irrelevant questions:
 
![Figure 12.2 — grounded answer demos](images/Demo_3_runs.png)
 
---
 
## 13. Phase 5: API for Data Access
 
### 13.1 What was built
 
A FastAPI service exposes everything built so far through a set of typed, documented HTTP
endpoints: raw scraped data, processed/structured content, keyword and semantic search, and a
grounded question-answering endpoint — covering every category the assignment asks for.
 
| Endpoint | Purpose |
|---|---|
| `GET /pages`, `GET /pages/{id}` | Fetching raw scraped data |
| `GET /processed-pages`, `GET /processed-pages/{id}` | Querying processed/structured content |
| `GET /search/keyword` | Keyword search over processed content |
| `GET /search/semantic` | Semantic (vector similarity) search |
| `POST /ask` | Grounded question-answering with citations |
 
All responses are typed with Pydantic models, giving automatic, interactive documentation for
every endpoint.
 
### 13.2 Reusing existing logic rather than duplicating it
 
The API does not reimplement any scraping, retrieval, or answer-generation logic — it calls the
same underlying functions built for the scraper service directly, so there is exactly one
implementation of each piece of logic rather than two versions that could drift out of sync.
Semantic search and the question-answering endpoint are thin wrappers around the retrieval and
generation functions from Section 12.
 
### 13.3 Search: keyword vs. semantic
 
Keyword search performs a straightforward substring match over processed page text. Given the
project's corpus size (a few hundred pages), this is fast and simple, and the added complexity
of a dedicated full-text search index would provide no measurable benefit at this scale.
Semantic search, by contrast, uses the vector-similarity retrieval built in Section 12, so the
two search endpoints are genuinely different retrieval methods, not the same thing exposed
twice — one matches literal words, the other matches meaning.
 
Both search endpoints filter to each URL's latest version only, for the same reason retrieval
does (Section 12.3). The raw and processed data endpoints, by contrast, deliberately expose
every stored version, since they're meant to show the full versioned crawl history rather than
just current state.
 
### 13.4 Error handling
 
A database failure or a failure reaching the locally-running embedding/generation service
returns a clean, structured error response rather than an unhandled exception, and a request
for a page or processed record that doesn't exist returns a proper "not found" response.
Invalid input (e.g. an empty search query, or a pagination value out of range) is rejected with
a clear validation error before any database or model call is made.
 
### 13.5 A data-quality bug found and fixed while testing the API
 
While verifying `/ask` responses against real data, currency symbols were found to be corrupted
in stored text (e.g. "£" appearing as "Â£"). The root cause was an incorrect character-encoding
fallback in the original fetch step: when a site's response headers didn't declare a character
set, the HTTP library defaulted to an outdated encoding assumption instead of detecting the
actual encoding of the page. This was fixed in the scraper's fetch logic, and the affected pages
were re-crawled — the existing versioning system (Section 9) automatically treated the corrected
pages as new versions and re-processed, re-chunked, and re-embedded them without any special
cleanup logic being needed. This is included in the report because it demonstrates the
versioning and pipeline-chaining design working exactly as intended when a real correction was
needed, not just in the scenario it was originally built for.
 
### 📸 Screenshots
 
**Figure 13.1** — API test suite passing:
 
![Figure 13.1 — API test suite passing](images/api_test_suite_passing_6.0.png)
 
**Figure 13.2** — `GET /pages` returning real, paginated raw data:
 
![Figure 13.2 — raw data endpoint](images/GET_processed-pages.png)
 
**Figure 13.3** — `GET /search/keyword` returning real keyword-matched results:
 
![Figure 13.3 — keyword search endpoint](images/GET_search_keyword.png)
 
**Figure 13.4** — `GET /search/semantic` returning real vector-similarity results:
 
![Figure 13.4 — semantic search endpoint](images/GET_search_semantic.png)
 
**Figure 13.5** — `POST /ask` returning a clean, multi-source grounded answer with correct citations:
 
![Figure 13.5 — grounded Q&A endpoint](images/Post_ask.png)
 
---
 
## 14. Phase 6: Web UI
 
### 14.1 What was built
 
A basic React (Vite) interface with two views: a search box (toggle between keyword and
semantic search) and a question-answering view, both connected to the live API for real-time
data access — no mock or hardcoded data. Search results display as cards linking back to the
original scraped page. The Q&A view renders the generated answer with its citations as numbered
chips, both inline in the answer text and listed below as clickable links to each source URL,
so a reader can see exactly which citation refers to which page. Kept deliberately simple per
the assignment's own wording ("a basic interface") — one page, two views, no routing or state
management libraries.
 
### 14.2 Technology choices and justification
 
| Choice | Alternative considered | Why I went this way |
|---|---|---|
| Plain CSS, no UI/component framework | A CSS/component library (e.g. Tailwind, MUI) | The interface is small enough (two views) that a framework would add setup overhead without a real benefit; the project's existing Vite/React scaffold already covered everything needed. |
| `allow_origins=["*"]` CORS policy on the API | A restricted origin list | Appropriate for this project's local/demo scope, where there is no authentication or sensitive data to protect — the standard, permissive default for local development. |
 
### 14.3 Connecting the UI to the backend
 
The UI calls the API's existing `/search/keyword`, `/search/semantic`, and `/ask` endpoints
directly and renders whatever comes back — there is no separate or duplicated logic on the
frontend. One integration detail worth noting: since the UI's JavaScript runs in the browser
rather than inside a container, its API base URL has to be a host-reachable address rather than
an internal container name, even when the UI itself is running in its own Docker container.
 
### 14.4 A known limitation of the local LLM, worth noting honestly
 
While testing the Q&A view, a query asking the model to compute an average price across several
retrieved books returned an answer with a genuine arithmetic error, despite correctly retrieving
and citing the right sources. Retrieval and citation accuracy were correct; the small
(3-billion-parameter) local model's multi-step arithmetic was not. This is a known limitation of
smaller LLMs generally, not a defect in the retrieval or grounding logic — worth being upfront
about, since it's a genuine tradeoff of the technology choice: a local, free, no-API-key model
that runs quickly, at the cost of weaker reasoning than a larger hosted model would provide.
 
### 📸 Note
 
No new screenshots are included for this section — the finished UI is demonstrated directly in
the accompanying video walkthrough: [Demo link](https://drive.google.com/file/d/16T5buqkUHDDuA1fYyjOFXCjhjtZhpEVh/view?usp=sharing)
 
---
 
## 15. Summary
 
This project implements every required component of the assignment: a distributed, containerized
scraping system with a real message queue and demonstrated horizontal scaling; politeness
(robots.txt, per-domain rate limiting) and fault tolerance (retries, backoff, a dead-letter
mechanism, and verified recovery from an actual worker crash); a processing pipeline with schema
validation, a second structured content type, and content-hash-based versioning; a full RAG
pipeline (overlap-based chunking, pgvector embeddings, grounded retrieval, multi-source citation);
and an API and basic web UI exposing all of it. Technology choices are justified throughout
against real alternatives, and known limitations (per-worker rate limiting under horizontal
scaling, and the local LLM's arithmetic reliability) are documented honestly rather than glossed
over.
 
