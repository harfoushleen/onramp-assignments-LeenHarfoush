"""Entry point for the scraper worker process.

Day 1 was a placeholder that just printed a line. This now starts a real
Celery worker listening for crawl jobs on the queue (see celery_app.py and
tasks.py) -- `python -m scraper.worker` (what the Dockerfile's CMD already
runs) delegates straight to Celery's own worker process rather than needing
a bespoke polling loop.

`--concurrency=1` is pinned rather than left at Celery's default (one prefork
process per CPU core). Discovered while running Day 2's scaling comparison:
with the default, a single container on a 12-core box already runs 12
concurrent task processors, so `--scale scraper=3` barely changed wall-clock
time (36 processes vs. 12 both drained the queue faster than the
single-threaded discovery script could feed it) -- the horizontal-scaling
timing comparison was measuring core count, not container count. Pinning
concurrency to 1 makes each container a single unit of processing capacity,
so `--scale scraper=N` is what actually controls throughput -- matching the
assignment's explicit "multiple independent worker instances... not just
multiple processes on one machine."
"""

import sys

from scraper.celery_app import celery_app


def main() -> None:
    args = ["worker", "--loglevel=info", "--concurrency=1"]
    if sys.platform == "win32":
        # Celery's default prefork pool needs os.fork(), which Windows doesn't
        # have. The container (Linux) doesn't need this; it only matters for
        # running the worker locally out of the venv.
        args.append("--pool=solo")
    celery_app.worker_main(args)


if __name__ == "__main__":
    main()
