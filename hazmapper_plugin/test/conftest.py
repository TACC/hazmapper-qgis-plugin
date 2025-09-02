import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch


@pytest.fixture
def test_data_dir():
    """Return the path to test data directory."""
    return Path(__file__).parent / "test/fixtures"


@pytest.fixture
def project_metadata(test_data_dir):
    """Load project metadata from JSON file."""
    with open(test_data_dir / "project_metadata.json", "r") as f:
        return json.load(f)


@pytest.fixture
def basemap_layers(test_data_dir):
    """Load basemap layers from JSON file."""
    with open(test_data_dir / "basemap_layers.json", "r") as f:
        return json.load(f)


@pytest.fixture
def features_data(test_data_dir):
    """Load features data from JSON file."""
    with open(test_data_dir / "features.json", "r") as f:
        return json.load(f)


@pytest.fixture
def basemap_layers():
    """Mock the entire QGIS environment for testing."""
    with (
        patch("hazmapper_plugin.hazmapper_layers.QgsProject") as mock_project,
        patch("hazmapper_plugin.hazmapper_layers.QgsRasterLayer") as mock_raster_layer,
        patch("hazmapper_plugin.hazmapper_layers.QgsVectorLayer") as mock_vector_layer,
        patch("hazmapper_plugin.hazmapper_layers.QgsLayerTreeGroup") as mock_tree_group,
        patch("hazmapper_plugin.hazmapper_layers.QgsMessageLog") as mock_log,
    ):

        # Mock project instance
        mock_project_instance = Mock()
        mock_project.instance.return_value = mock_project_instance

        # Mock layer tree root
        mock_root = Mock()
        mock_root.children.return_value = []
        mock_project_instance.layerTreeRoot.return_value = mock_root

        # Mock group creation
        mock_group = Mock()
        mock_tree_group.return_value = mock_group

        # Mock valid raster layers
        mock_raster = Mock()
        mock_raster.isValid.return_value = True
        mock_raster_layer.return_value = mock_raster

        # Mock valid vector layers
        mock_vector = Mock()
        mock_vector.isValid.return_value = True
        mock_vector_layer.return_value = mock_vector

        yield {
            "project": mock_project,
            "project_instance": mock_project_instance,
            "raster_layer": mock_raster_layer,
            "vector_layer": mock_vector_layer,
            "tree_group": mock_tree_group,
            "group": mock_group,
            "root": mock_root,
            "log": mock_log,
        }


@pytest.fixture
def mock_http_responses(project_metadata, basemap_layers, features_data):
    """Mock HTTP responses for the entire API flow."""

    def mock_urlopen_side_effect(url):
        """Side effect function for urllib.request.urlopen mock."""
        mock_response = Mock()
        mock_response.status = 200

        if "?uuid=" in url:
            # Project metadata request
            mock_response.read.return_value = json.dumps(project_metadata).encode()
        elif "/tile-servers/" in url:
            # Basemap layers request
            mock_response.read.return_value = json.dumps(basemap_layers).encode()
        elif "/features/" in url:
            # Features request
            mock_response.read.return_value = json.dumps(features_data).encode()
        else:
            # Unknown request
            mock_response.status = 404
            mock_response.read.return_value = b'{"error": "Not found"}'

        return mock_response

    return mock_urlopen_side_effect
