from scraper.worker import main


def test_main_runs(capsys):
    main()
    captured = capsys.readouterr()
    assert "scraper worker starting" in captured.out
