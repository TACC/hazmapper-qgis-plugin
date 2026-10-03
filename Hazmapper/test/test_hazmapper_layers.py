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
    from Hazmapper.hazmapper_layers import add_basemap_layers, add_features_layers

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
