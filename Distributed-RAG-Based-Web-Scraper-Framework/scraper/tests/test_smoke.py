import sys
from unittest.mock import patch

from scraper.worker import main


def test_main_starts_a_celery_worker_listening_for_jobs():
    """main() now delegates to Celery's own worker process (which blocks
    forever listening for jobs), so celery_app.worker_main is mocked here --
    this just checks main() calls it correctly, not that a worker actually runs.
    """
    with patch("scraper.worker.celery_app") as mock_celery_app:
        main()

    mock_celery_app.worker_main.assert_called_once()
    args = mock_celery_app.worker_main.call_args[0][0]
    assert args[:2] == ["worker", "--loglevel=info"]
    if sys.platform == "win32":
        assert "--pool=solo" in args
