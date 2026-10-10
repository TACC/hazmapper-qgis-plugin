"""
Smoke tests: the plugin imports and builds its UI in the running QGIS/Qt version.

These catch Qt5 vs Qt6 problems (imports, enum names) that the mocked tests can't see.
"""

import importlib
import pkgutil
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("qgis")

import Hazmapper  # noqa: E402


def _plugin_modules():
    return sorted(
        m.name
        for m in pkgutil.walk_packages(Hazmapper.__path__, prefix="Hazmapper.")
        if not m.name.startswith("Hazmapper.test")
    )


@pytest.mark.qgis_required
@pytest.mark.parametrize("module_name", _plugin_modules())
def test_module_imports(module_name):
    importlib.import_module(module_name)


@pytest.mark.qgis_required
def test_dockwidget_builds(qgis_app):
    from Hazmapper.hazmapper_icons import PLUGIN_DIR
    from Hazmapper.hazmapper_plugin_dockwidget import HazmapperPluginDockWidget

    dock = HazmapperPluginDockWidget(iface=MagicMock(), plugin_dir=PLUGIN_DIR)

    assert dock.windowTitle() == "Hazmapper"
    assert dock.project_selector is not None
    assert dock.map_status is not None


@pytest.mark.qgis_required
def test_plugin_lifecycle(qgis_app):
    """Load the plugin the way QGIS does: classFactory, initGui, open dock, unload."""
    iface = MagicMock()
    iface.mainWindow.return_value = None

    with patch("Hazmapper.hazmapper_plugin.QSettings") as settings:
        settings.return_value.value.return_value = "en_US"
        plugin = Hazmapper.classFactory(iface)

    plugin.initGui()
    iface.addToolBarIcon.assert_called_once()

    plugin.toggle_dockwidget()
    iface.addDockWidget.assert_called_once()
    assert plugin.pluginIsActive

    plugin.unload()
    iface.removeToolBarIcon.assert_called_once()
