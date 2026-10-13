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


def _map_layer(name, fields, attributes, asset=True):
    """A one-feature memory layer tagged the way the plugin tags its layers."""
    from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsVectorLayer
    from Hazmapper.utils.qgis import GEOAPI_URL_PROPERTY, MAP_URL_PROPERTY

    layer = QgsVectorLayer(f"MultiPoint?crs=EPSG:4326&{fields}", name, "memory")
    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry.fromMultiPointXY([QgsPointXY(-97.7, 30.2)]))
    feature.setAttributes(attributes)
    layer.dataProvider().addFeatures([feature])
    layer.setCustomProperty(
        MAP_URL_PROPERTY, "https://example.org/hazmapper/project-public/abc/"
    )
    layer.setCustomProperty(GEOAPI_URL_PROPERTY, "https://example.org/geoapi")
    return layer


@pytest.mark.qgis_required
def test_feature_info_shows_a_plain_feature(qgis_app):
    from Hazmapper.components.feature_info import FeatureInfo

    layer = _map_layer(
        "Vector Features",
        "field=feature_id:long&field=State:string&field=Total Buildings:long&field=Empty:string",
        [8218649, "CA", 1079, None],
    )
    panel = FeatureInfo()

    panel.show_feature(layer, next(layer.getFeatures()))

    assert "Vector Features" in panel.title.text()
    assert "feature 8218649" in panel.title.text()
    assert "State" in panel.details.text() and "CA" in panel.details.text()
    assert "1079" in panel.details.text()
    assert "Empty" not in panel.details.text()  # nulls are left out
    assert "feature_id" not in panel.details.text()
    assert (
        '<a href="https://example.org/hazmapper/project-public/abc/?selectedFeature=8218649">'
        "View in Hazmapper</a>" in panel.links.text()
    )
    assert panel.has_feature


@pytest.mark.qgis_required
def test_feature_info_shows_a_photo_with_links(qgis_app):
    from Hazmapper.components.feature_info import FeatureInfo

    layer = _map_layer(
        "Images",
        "field=feature_id:long&field=asset_type:string&field=display_path:string"
        "&field=asset_path:string",
        [587228, "image", "/RApp/Pier 2/Photo 9.jpg", "833/31e21306.jpeg"],
    )
    panel = FeatureInfo()

    with patch.object(FeatureInfo, "_load_preview") as load_preview:
        panel.show_feature(layer, next(layer.getFeatures()))

    assert "Photo 9.jpg" in panel.title.text()
    assert "/RApp/Pier 2/Photo 9.jpg" in panel.details.text()
    assert "?selectedFeature=587228" in panel.links.text()
    # the only link is back to Hazmapper; the photo itself is shown as the preview
    assert panel.links.text().count("<a ") == 1
    assert "View in Hazmapper" in panel.links.text()
    load_preview.assert_called_once_with(
        "https://example.org/geoapi/assets/833/31e21306.jpeg"
    )

    panel.clear()
    assert not panel.has_feature
    assert "Pick on map" in panel.title.text()


@pytest.mark.qgis_required
def test_pick_button_shows_that_picking_is_on(qgis_app):
    from Hazmapper.components.feature_info import FeatureInfo

    panel = FeatureInfo()
    assert panel.pick_button.text() == "Pick on map"

    panel.pick_button.setChecked(True)
    assert panel.pick_button.text() == "Picking: click a feature"
    assert "Press Esc" in panel.title.text()
    assert ":checked" in panel.pick_button.styleSheet()

    panel.pick_button.setChecked(False)
    assert panel.pick_button.text() == "Pick on map"
    assert "Pick on map" in panel.title.text()


@pytest.mark.qgis_required
def test_picking_shows_a_feature_and_clicking_nothing_clears_it(qgis_app):
    from Hazmapper import hazmapper_plugin_dockwidget as dockwidget_module
    from Hazmapper.hazmapper_icons import PLUGIN_DIR

    dock = dockwidget_module.HazmapperPluginDockWidget(
        iface=MagicMock(), plugin_dir=PLUGIN_DIR
    )
    layer = _map_layer(
        "Vector Features", "field=feature_id:long&field=State:string", [42, "TX"]
    )

    dock._on_feature_picked(layer, next(layer.getFeatures()))
    assert "feature 42" in dock.feature_info.title.text()
    assert "?selectedFeature=42" in dock.feature_info.links.text()
    assert layer.selectedFeatureCount() == 0  # QGIS's own selection is left alone

    dock._clear_picked_feature()  # what a click on empty map does
    assert not dock.feature_info.has_feature
    assert "feature 42" not in dock.feature_info.title.text()


@pytest.mark.qgis_required
def test_selecting_with_qgis_tools_does_not_change_the_panel(qgis_app):
    from qgis.core import QgsLayerTreeGroup, QgsProject
    from Hazmapper import hazmapper_plugin_dockwidget as dockwidget_module
    from Hazmapper.hazmapper_icons import PLUGIN_DIR

    dock = dockwidget_module.HazmapperPluginDockWidget(
        iface=MagicMock(), plugin_dir=PLUGIN_DIR
    )
    layer = _map_layer(
        "Vector Features", "field=feature_id:long&field=State:string", [42, "TX"]
    )
    try:
        QgsProject.instance().addMapLayer(layer, False)
        dock.main_group = QgsLayerTreeGroup("map")
        dock.main_group.addLayer(layer)

        layer.selectAll()

        assert not dock.feature_info.has_feature
    finally:
        QgsProject.instance().removeAllMapLayers()


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


@pytest.mark.qgis_required
def test_pick_tool_can_be_created(qgis_app):
    from qgis.gui import QgsMapCanvas
    from Hazmapper.feature_picker import FeaturePickTool

    canvas = QgsMapCanvas()
    tool = FeaturePickTool(canvas, lambda: [])

    canvas.setMapTool(tool)
    assert canvas.mapTool() is tool
    assert tool.pick(10, 10) is None  # no layers to look in

    missed = MagicMock()
    tool.missed.connect(missed)
    event = MagicMock()
    event.pixelPoint.return_value.x.return_value = 10
    event.pixelPoint.return_value.y.return_value = 10
    tool.canvasReleaseEvent(event)
    missed.assert_called_once()  # a click on nothing is reported


@pytest.mark.qgis_required
def test_pick_prefers_points_over_polygons(qgis_app):
    """A photo inside a point cloud footprint must be pickable."""
    from Hazmapper.feature_picker import _pick_priority
    from qgis.core import QgsVectorLayer

    def result_for(geometry):
        result = MagicMock()
        result.mLayer = QgsVectorLayer(f"{geometry}?crs=EPSG:4326", geometry, "memory")
        return result

    polygon, line, point = (
        result_for("MultiPolygon"),
        result_for("MultiLineString"),
        result_for("MultiPoint"),
    )

    assert min([polygon, line, point], key=_pick_priority) is point
    assert min([polygon, line], key=_pick_priority) is line
