import pytest

pytest.importorskip("qgis")

from Hazmapper.utils.ui import make_ui_pacer  # noqa: E402
from unittest.mock import Mock, patch  # noqa: E402


@pytest.mark.qgis_required
def test_failed_progress_update_is_logged_and_loading_continues():
    progress = Mock(side_effect=RuntimeError("Boom"))
    update_progress = make_ui_pacer(progress)

    # QApplication is patched so timers left by other tests don't fire here
    with (
        patch("Hazmapper.utils.ui.QgsMessageLog") as log,
        patch("Hazmapper.utils.ui.QApplication"),
    ):
        update_progress("Loading", 10, force=True)

    progress.assert_called_once_with("Loading", 10)
    assert "Boom" in log.logMessage.call_args.args[0]
