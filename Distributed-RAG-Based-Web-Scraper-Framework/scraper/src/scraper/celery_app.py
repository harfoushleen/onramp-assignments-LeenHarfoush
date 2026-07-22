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

celery_app = Celery("scraper", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.task_ignore_result = True
# Explicit rather than relying on Celery's (currently deprecated, changing in
# 6.0) default -- retry connecting to the broker on startup instead of
# failing immediately if Redis isn't up yet when the worker boots.
celery_app.conf.broker_connection_retry_on_startup = True

# Imported for its side effect of registering @celery_app.task-decorated
# functions; deferred to the bottom to avoid a circular import (tasks.py
# imports celery_app from this module).
from scraper import tasks  # noqa: E402,F401
