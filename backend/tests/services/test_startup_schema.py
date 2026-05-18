from unittest.mock import patch

import main


def test_app_startup_runs_init_db() -> None:
    with patch("main.init_db") as mock_init_db:
        for handler in main.app.router.on_startup:
            handler()

    mock_init_db.assert_called_once()
