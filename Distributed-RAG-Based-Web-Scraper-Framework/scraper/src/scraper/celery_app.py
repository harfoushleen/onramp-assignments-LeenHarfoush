"""Celery application instance shared by the worker entrypoint and every task.

Redis serves as both broker and result backend -- one moving part instead of
two, and this project already has no other message-queue dependency to make
a separate broker choice worthwhile. Results aren't actually consumed by
anything today (crawl jobs are fire-and-forget), so `task_ignore_result` is
on to skip writing them.
"""

import os

from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# How long Redis waits before assuming a worker that grabbed a task has died
# and redelivering it to another worker (Day 3's fault-tolerance requirement:
# a worker crashing mid-task shouldn't silently lose that job). 30s is a
# demo-scale value chosen to make the crash-recovery demo finish in a
# reasonable time -- a real deployment crawling pages that can legitimately
# take longer than 30s would want this much higher (Celery's Redis-transport
# default is 3600s/1h), since too short a timeout risks redelivering -- and
# therefore double-running -- a task that's simply still working, not dead.
TASK_VISIBILITY_TIMEOUT_SECONDS = int(os.environ.get("TASK_VISIBILITY_TIMEOUT_SECONDS", 30))

celery_app = Celery("scraper", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.task_ignore_result = True
# Explicit rather than relying on Celery's (currently deprecated, changing in
# 6.0) default -- retry connecting to the broker on startup instead of
# failing immediately if Redis isn't up yet when the worker boots.
celery_app.conf.broker_connection_retry_on_startup = True

# task_acks_late: acknowledge a task to Redis only *after* it finishes (success
# or failure), not the moment a worker picks it up. Combined with
# worker_prefetch_multiplier=1 (never hold more than one unstarted task per
# worker process at a time), this is what makes a worker crash mid-task
# recoverable -- if the worker dies before acking, Redis's visibility timeout
# eventually treats the message as undelivered and hands it to another
# worker, instead of the job vanishing with the process that was holding it.
celery_app.conf.task_acks_late = True
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.broker_transport_options = {
    "visibility_timeout": TASK_VISIBILITY_TIMEOUT_SECONDS,
}

# Imported for its side effect of registering @celery_app.task-decorated
# functions; deferred to the bottom to avoid a circular import (tasks.py
# imports celery_app from this module).
from scraper import tasks  # noqa: E402,F401
