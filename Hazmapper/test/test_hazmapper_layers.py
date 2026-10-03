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
    from qgis.core import QgsLayerTreeGroup, QgsProject
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
        }
    ]
    group = QgsLayerTreeGroup("test group")
    on_progress = Mock()
    on_complete = Mock()

    try:
        add_basemap_layers(group, basemaps, on_progress)
        add_features_layers(group, features, on_progress, on_complete)

        layers = {node.name(): node.layer() for node in group.findLayers()}
        assert set(layers) == {"OpenStreetMap", "Images", "scan"}
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
