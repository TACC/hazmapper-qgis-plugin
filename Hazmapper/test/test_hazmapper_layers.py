import pytest
from unittest.mock import patch, Mock, ANY


@pytest.mark.qgis_required
@patch("Hazmapper.hazmapper_layers.QgsProject")
@patch("Hazmapper.hazmapper_layers.QgsLayerTreeGroup")
def test_create_or_replace_main_group_new(mock_tree_group, mock_project):
    from Hazmapper.hazmapper_layers import create_main_group

    # Mock the QGIS project and layer tree
    mock_root = Mock()
    mock_root.children.return_value = []
    mock_project.instance.return_value.layerTreeRoot.return_value = mock_root

    # Mock the group creation
    mock_group = Mock()
    mock_tree_group.return_value = mock_group

    # Act
    result = create_main_group("Test Project", "uuid-123")

    # Assert
    mock_tree_group.assert_called_once_with("Test Project (uuid-123)")
    mock_group.setCustomProperty.assert_any_call("hazmapper_project_uuid", "uuid-123")
    mock_group.setCustomProperty.assert_any_call(
        "hazmapper_qgis_internal_group_uuid", ANY
    )
    mock_root.insertChildNode.assert_called_once_with(0, mock_group)
    assert result is mock_group


@pytest.mark.qgis_required
def test_add_layers_builds_real_layers(qgis_app):
    """Build basemap and feature layers with real QGIS objects (no mocks)."""
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsDataSourceUri,
        QgsLayerTreeGroup,
        QgsProject,
    )
    from Hazmapper.hazmapper_layers import (
        add_basemap_layers,
        add_features_layers,
        set_map_attribution,
    )

    point = {"type": "Point", "coordinates": [-97.7431, 30.2672]}
    polygon = {
        "type": "Polygon",
        "coordinates": [
            [[-97.75, 30.26], [-97.74, 30.26], [-97.74, 30.27], [-97.75, 30.26]]
        ],
    }
    features = {
        "features": [
            {
                "geometry": point,
                "assets": [{"asset_type": "image", "display_path": "a.jpg"}],
            },
            {
                "geometry": point,
                "assets": [{"asset_type": "image", "display_path": "b.jpg"}],
            },
            {
                "geometry": polygon,
                "assets": [{"asset_type": "point_cloud", "display_path": "scan"}],
            },
        ]
    }
    basemaps = [
        {
            "name": "OpenStreetMap",
            "type": "tms",
            "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            "attribution": '&copy; <a href="https://osm.org">OpenStreetMap</a>',
            "uiOptions": {"zIndex": 0, "opacity": 0.5},
        },
        {
            "name": "Ortho",
            "type": "xyz",
            "kind": "cog",
            "internal": True,
            "url": "/assets/833/4a026c0a.cog.tif",
            "tileOptions": {
                "bounds": [[17.9668, -66.6213], [17.9675, -66.6207]],
                "minZoom": 0,
                "maxZoom": 24,
                "maxNativeZoom": 23,
            },
            "uiOptions": {
                "zIndex": 1,
                "opacity": 1,
                "isActive": False,
                "renderOptions": {"colormap_name": "terrain"},
            },
        },
        {"name": "Unsupported", "type": "wms", "url": "x", "uiOptions": {}},
    ]
    group = QgsLayerTreeGroup("test group")
    on_progress = Mock()
    on_complete = Mock()

    try:
        add_basemap_layers(group, basemaps, on_progress, "https://example.org/geoapi")
        add_features_layers(group, features, on_progress, on_complete)

        nodes = {node.name(): node for node in group.findLayers()}
        layers = {name: node.layer() for name, node in nodes.items()}
        assert set(layers) == {"OpenStreetMap", "Ortho", "Images", "scan"}

        # The internal COG is a TiTiler tile layer carrying Hazmapper's styling
        ortho_uri = QgsDataSourceUri()
        ortho_uri.setEncodedUri(layers["Ortho"].source())
        assert ortho_uri.param("type") == "xyz"
        assert ortho_uri.param("url") == (
            "https://example.org/geoapi/tiles/cog/tiles/WebMercatorQuad/{z}/{x}/{y}.png"
            "?url=file%3A%2F%2F%2Fassets%2F833%2F4a026c0a.cog.tif&colormap_name=terrain"
        )
        assert ortho_uri.param("zmax") == "23"
        # its extent is the COG's footprint rather than the whole world
        to_wgs84 = QgsCoordinateTransform(
            layers["Ortho"].crs(),
            QgsCoordinateReferenceSystem("EPSG:4326"),
            QgsProject.instance(),
        )
        footprint = to_wgs84.transformBoundingBox(layers["Ortho"].extent())
        assert footprint.xMinimum() == pytest.approx(-66.6213, abs=1e-6)
        assert footprint.yMinimum() == pytest.approx(17.9668, abs=1e-6)
        assert footprint.xMaximum() == pytest.approx(-66.6207, abs=1e-6)
        assert footprint.yMaximum() == pytest.approx(17.9675, abs=1e-6)
        assert layers["OpenStreetMap"].extent().width() > 40_000_000  # world
        # switched off in Hazmapper, so present but unchecked; on top of the basemap
        assert not nodes["Ortho"].itemVisibilityChecked()
        assert nodes["OpenStreetMap"].itemVisibilityChecked()
        assert list(nodes).index("Ortho") < list(nodes).index("OpenStreetMap")

        assert layers["Images"].featureCount() == 2
        assert [f.name() for f in layers["Images"].fields()] == [
            "asset_type",
            "display_path",
        ]
        assert layers["scan"].featureCount() == 1
        assert layers["OpenStreetMap"].opacity() == 0.5
        on_progress.assert_called()
        on_complete.assert_called_once()

        # Attribution: basemaps keep their provider's; the map's own layers (features
        # and internal COGs) credit DesignSafe and Hazmapper and link to the sources
        map_url = (
            "https://hazmapper.tacc.utexas.edu/hazmapper/project-public/"
            "1260cfdc-00c5-42d2-ab4b-ac498b24e44c/"
        )
        set_map_attribution(group, map_url)

        assert layers["OpenStreetMap"].metadata().rights() == ["© OpenStreetMap"]
        basemap_links = [
            link.name for link in layers["OpenStreetMap"].metadata().links()
        ]
        assert "Hazmapper map" not in basemap_links
        for name in ("Images", "scan", "Ortho"):
            metadata = layers[name].metadata()
            assert metadata.rights() == ["DesignSafe", "Hazmapper"]
            links = {link.name: link.url for link in metadata.links()}
            assert links["Hazmapper map"] == map_url
            (ds_link,) = [n for n in links if n.startswith("DesignSafe project")]
            assert ds_link.startswith("DesignSafe project PRJ-2714 | ")
            assert links[ds_link].endswith("/designsafe.storage.published/PRJ-2714")

        # a map that isn't in a published DesignSafe project only links to the map
        set_map_attribution(group, "https://example.org/project-public/abc")
        assert [link.name for link in layers["Images"].metadata().links()] == [
            "Hazmapper map"
        ]
    finally:
        QgsProject.instance().removeAllMapLayers()


@pytest.mark.qgis_required
def test_zoom_to_group_uses_cog_footprint_not_basemap(qgis_app):
    """A map with only tile layers zooms to its COG, ignoring world-wide basemaps."""
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsLayerTreeGroup,
        QgsProject,
        QgsRectangle,
    )
    from Hazmapper.hazmapper_layers import add_basemap_layers
    from Hazmapper.utils import qgis as qgis_utils

    layers = [
        {
            "name": "OpenStreetMap",
            "type": "tms",
            "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            "uiOptions": {"zIndex": 0},
        },
        {
            "name": "Ortho",
            "type": "xyz",
            "kind": "cog",
            "internal": True,
            "url": "/assets/833/4a026c0a.cog.tif",
            "tileOptions": {"bounds": [[17.9668, -66.6213], [17.9675, -66.6207]]},
            "uiOptions": {"zIndex": 1},
        },
    ]
    group = QgsLayerTreeGroup("test group")
    canvas = Mock()
    canvas.mapSettings.return_value.destinationCrs.return_value = (
        QgsCoordinateReferenceSystem("EPSG:4326")
    )

    try:
        add_basemap_layers(group, layers, None, "https://example.org/geoapi")
        with patch.object(qgis_utils, "iface") as iface:
            iface.mapCanvas.return_value = canvas
            qgis_utils.zoom_to_group(group)

        canvas.setExtent.assert_called_once()
        extent: QgsRectangle = canvas.setExtent.call_args[0][0]
        assert extent.xMinimum() == pytest.approx(-66.6213, abs=1e-6)
        assert extent.yMaximum() == pytest.approx(17.9675, abs=1e-6)
    finally:
        QgsProject.instance().removeAllMapLayers()


def _feature(feature_id, geometry, asset_type=None, **properties):
    assets = [{"asset_type": asset_type, "display_path": f"{feature_id}.file"}]
    return {
        "id": feature_id,
        "geometry": geometry,
        "properties": properties,
        "assets": assets if asset_type else [],
    }


POINT = {"type": "Point", "coordinates": [-97.7431, 30.2672]}
LINE = {"type": "LineString", "coordinates": [[-97.75, 30.26], [-97.74, 30.27]]}
POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [[-97.75, 30.26], [-97.74, 30.26], [-97.74, 30.27], [-97.75, 30.26]]
    ],
}


def _load_features(features):
    """Run add_features_layers and return {layer name: layer}."""
    from qgis.core import QgsLayerTreeGroup
    from Hazmapper.hazmapper_layers import add_features_layers

    group = QgsLayerTreeGroup("test group")
    add_features_layers(group, {"features": features})
    return {node.name(): node.layer() for node in group.findLayers()}


@pytest.mark.qgis_required
def test_streetview_lines_are_kept(qgis_app):
    """Streetview features are lines; they must not be lost in a points layer."""
    from qgis.core import QgsProject, QgsWkbTypes

    try:
        layers = _load_features(
            [_feature(1, LINE, "streetview"), _feature(2, LINE, "streetview")]
        )

        assert set(layers) == {"StreetView"}
        assert layers["StreetView"].featureCount() == 2
        assert (
            QgsWkbTypes.geometryType(layers["StreetView"].wkbType())
            == QgsWkbTypes.LineGeometry
        )
    finally:
        QgsProject.instance().removeAllMapLayers()


@pytest.mark.qgis_required
def test_media_on_other_geometry_gets_its_own_layer(qgis_app):
    """A photo attached to a polygon is shown, in a layer of its own."""
    from qgis.core import QgsProject

    try:
        layers = _load_features(
            [
                _feature(1, POINT, "image"),
                _feature(2, POINT, "image"),
                _feature(3, POLYGON, "image"),
            ]
        )

        assert set(layers) == {"Images (points)", "Images (polygons)"}
        assert layers["Images (points)"].featureCount() == 2
        assert layers["Images (polygons)"].featureCount() == 1
        assert layers["Images (polygons)"].getFeature(1)["display_path"] == "3.file"
    finally:
        QgsProject.instance().removeAllMapLayers()


@pytest.mark.qgis_required
def test_features_that_cannot_be_shown_are_reported(qgis_app):
    from qgis.core import QgsProject

    collection = {"type": "GeometryCollection", "geometries": [POINT]}
    try:
        with patch("Hazmapper.hazmapper_layers.QgsMessageLog") as log:
            layers = _load_features(
                [_feature(1, POINT, "image"), _feature(2, collection, "image")]
            )

        assert layers["Images"].featureCount() == 1
        messages = [c.args[0] for c in log.logMessage.call_args_list]
        assert any("Skipped 1 image feature(s)" in m for m in messages)
    finally:
        QgsProject.instance().removeAllMapLayers()


@pytest.mark.qgis_required
def test_features_without_assets_are_shown(qgis_app):
    """Plain features become one layer per kind of geometry, with their properties."""
    from qgis.core import QgsProject

    try:
        layers = _load_features(
            [
                _feature(11, POINT, name="A", stories=2, height=3),
                _feature(12, POINT, name="B", stories=None, height=4.5, tags=["x"]),
                _feature(13, LINE, Id=0),
                _feature(14, POINT, "image"),
            ]
        )

        assert set(layers) == {
            "Images",
            "Vector Features (points)",
            "Vector Features (lines)",
        }

        points = layers["Vector Features (points)"]
        assert [f.name() for f in points.fields()] == [
            "feature_id",
            "name",
            "stories",
            "height",
            "tags",
        ]
        rows = {f["feature_id"]: f for f in points.getFeatures()}
        assert set(rows) == {11, 12}
        assert (rows[11]["name"], rows[11]["stories"], rows[11]["height"]) == (
            "A",
            2,
            3.0,
        )
        assert rows[12]["height"] == 4.5
        assert rows[12]["tags"] == '["x"]'
        assert not rows[12]["stories"]  # null
        assert not rows[11]["tags"]  # null

        lines = layers["Vector Features (lines)"]
        assert lines.featureCount() == 1
        assert [f.name() for f in lines.fields()] == ["feature_id", "Id"]
    finally:
        QgsProject.instance().removeAllMapLayers()


@pytest.mark.qgis_required
def test_single_kind_of_plain_feature_gets_the_plain_name(qgis_app):
    from qgis.core import QgsProject

    try:
        layers = _load_features([_feature(1, POLYGON), _feature(2, POLYGON)])

        assert set(layers) == {"Vector Features"}
        assert layers["Vector Features"].featureCount() == 2
    finally:
        QgsProject.instance().removeAllMapLayers()


@pytest.mark.qgis_required
def test_missing_previous_group_is_not_a_warning(qgis_app):
    """A saved group id from an earlier session is cleared quietly."""
    from qgis.core import Qgis
    from qgis.PyQt.QtCore import QSettings
    from Hazmapper.hazmapper_layers import remove_previous_main_group

    key = "HazmapperPlugin/internal_group_uuid"
    QSettings().setValue(key, "id-of-a-group-that-is-gone")

    with patch("Hazmapper.hazmapper_layers.QgsMessageLog") as log:
        remove_previous_main_group()

    levels = [c.args[2] for c in log.logMessage.call_args_list]
    assert Qgis.Warning not in levels and Qgis.Critical not in levels
    assert QSettings().value(key, None) is None
