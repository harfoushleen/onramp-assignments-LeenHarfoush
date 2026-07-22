"""Entry point for the scraper worker process.

Day 1 was a placeholder that just printed a line. This now starts a real
Celery worker listening for crawl jobs on the queue (see celery_app.py and
tasks.py) -- `python -m scraper.worker` (what the Dockerfile's CMD already
runs) delegates straight to Celery's own worker process rather than needing
a bespoke polling loop.
"""

import sys

from scraper.celery_app import celery_app


def main() -> None:
    args = ["worker", "--loglevel=info"]
    if sys.platform == "win32":
        # Celery's default prefork pool needs os.fork(), which Windows doesn't
        # have. The container (Linux) doesn't need this; it only matters for
        # running the worker locally out of the venv.
        args.append("--pool=solo")
    celery_app.worker_main(args)


if __name__ == "__main__":
    main()
