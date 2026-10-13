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


@pytest.mark.qgis_required
@pytest.mark.parametrize(
    "app_path, geoapi_path",
    [("hazmapper", "geoapi"), ("staging", "geoapi-staging"), ("dev", "geoapi-dev")],
)
def test_load_request_uses_the_maps_own_geoapi(qgis_app, app_path, geoapi_path):
    """A staging or dev map is fetched from the staging or dev GeoAPI."""
    from Hazmapper import hazmapper_plugin_dockwidget as dockwidget_module
    from Hazmapper.hazmapper_icons import PLUGIN_DIR

    dock = dockwidget_module.HazmapperPluginDockWidget(
        iface=MagicMock(), plugin_dir=PLUGIN_DIR
    )
    host = "https://hazmapper.tacc.utexas.edu"

    with (
        patch.object(dockwidget_module, "LoadGeoApiProjectTask") as task_class,
        patch.object(dockwidget_module, "QgsApplication"),
    ):
        dock.handle_load_request(f"{host}/{app_path}/project-public/abc-123/", False)

    task_class.assert_called_once_with(
        "abc-123", base_url=f"{host}/{geoapi_path}/projects"
    )
    assert dock.geoapi_url == f"{host}/{geoapi_path}"


@pytest.mark.qgis_required
def test_long_description_is_cut_with_a_more_link(qgis_app):
    from Hazmapper.components.map_status import MapStatus

    status = MapStatus()
    long_text = (
        "This project aims to identify the compounding impacts of hurricanes. " * 8
    )

    status.set_description("Short & sweet")
    assert status.description_value.text() == "Short &amp; sweet"

    status.set_description(long_text)
    shown = status.description_value.text()
    assert len(shown) < 200
    assert shown.endswith('… <a href="#more">more</a>')
    assert status._description == long_text  # the window shows all of it


@pytest.mark.qgis_required
def test_dock_content_can_scroll(qgis_app):
    from qgis.PyQt.QtWidgets import QScrollArea
    from Hazmapper import hazmapper_plugin_dockwidget as dockwidget_module
    from Hazmapper.hazmapper_icons import PLUGIN_DIR

    dock = dockwidget_module.HazmapperPluginDockWidget(
        iface=MagicMock(), plugin_dir=PLUGIN_DIR
    )

    scroll_area = dock.widget()
    assert isinstance(scroll_area, QScrollArea)
    assert scroll_area.widgetResizable()
    # never narrower than its content, so nothing is cut off at the side
    content_width = scroll_area.widget().minimumSizeHint().width()
    assert scroll_area.minimumSizeHint().width() >= content_width
