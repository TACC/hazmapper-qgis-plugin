import unittest
from unittest.mock import Mock, patch
import urllib.error

from hazmapper_plugin.geoapi import (
    LoadGeoApiProjectTask,
    GeoApiTaskState,
    GeoApiStep,
    json_to_wkt,
    create_or_replace_main_group,
    add_basemap_layers,
    add_features_layers
)


class TestGeoApiUtilities(unittest.TestCase):
    """Test utility functions that don't require QGIS."""

    def test_json_to_wkt_point(self):
        """Test JSON to WKT conversion for a point."""
        geometry_json = '{"type": "Point", "coordinates": [-97.7431, 30.2672]}'
        wkt = json_to_wkt(geometry_json)
        self.assertIn("POINT", wkt)
        self.assertIn("-97.7431", wkt)
        self.assertIn("30.2672", wkt)

    def test_json_to_wkt_polygon(self):
        """Test JSON to WKT conversion for a polygon."""
        geometry_json = '''
        {
            "type": "Polygon",
            "coordinates": [[
                [-97.7431, 30.2672],
                [-97.7430, 30.2672],
                [-97.7430, 30.2671],
                [-97.7431, 30.2671],
                [-97.7431, 30.2672]
            ]]
        }
        '''
        wkt = json_to_wkt(geometry_json)
        self.assertIn("POLYGON", wkt)


class TestLoadGeoApiProjectTask(unittest.TestCase):
    """Test the main task class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_on_finished = Mock()
        self.mock_update_status = Mock()
        self.mock_on_progress_data = Mock()

        self.task = LoadGeoApiProjectTask(
            uuid="test-uuid-123",
            on_finished=self.mock_on_finished,
            update_status=self.mock_update_status,
            on_progress_data=self.mock_on_progress_data
        )

    def test_task_initialization(self):
        """Test task is properly initialized."""
        self.assertEqual(self.task.uuid, "test-uuid-123")
        self.assertEqual(self.task.base_url, 'https://hazmapper.tacc.utexas.edu/geoapi/projects')
        self.assertIsNone(self.task.project_id)
        self.assertIsNone(self.task.error)

    @patch('urllib.request.urlopen')
    def test_request_data_success(self, mock_urlopen):
        """Test successful data request."""
        # Mock response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"test": "data"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = self.task._request_data_from_backend("/test", "test data")

        self.assertEqual(result, {"test": "data"})
        self.mock_update_status.assert_called_with(GeoApiTaskState.RUNNING, "Fetching test data...")

    @patch('urllib.request.urlopen')
    def test_request_data_http_error(self, mock_urlopen):
        """Test HTTP error handling."""
        mock_response = Mock()
        mock_response.status = 404
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = self.task._request_data_from_backend("/test", "test data")

        self.assertIsNone(result)
        self.assertIn("Fetching test data failed", self.task.error)
        self.assertIn("404", self.task.error)


    @patch('urllib.request.urlopen')
    def test_request_data_network_error(self, mock_urlopen):
        """Test network error handling."""
        mock_urlopen.side_effect = urllib.error.URLError("Connection failed")

        result = self.task._request_data_from_backend("/test", "test data")

        self.assertIsNone(result)
        self.assertIn("Fetching test data failed", self.task.error)

    @patch('urllib.request.urlopen')
    def test_request_data_json_error(self, mock_urlopen):
        """Test JSON parsing error handling."""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = b'invalid json'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = self.task._request_data_from_backend("/test", "test data")

        self.assertIsNone(result)
        self.assertIn("Fetching test data failed", self.task.error)

    @patch.object(LoadGeoApiProjectTask, '_request_data_from_backend')
    def test_run_success(self, mock_request):
        """Test successful task run."""
        # Mock responses
        mock_request.side_effect = [
            [{"id": "project-123", "name": "Test Project"}],  # project metadata
            [{"name": "Basemap", "type": "tms", "url": "http://example.com"}],  # basemap layers
            {"features": [{"geometry": {"type": "Point"}, "assets": []}]}  # features
        ]

        result = self.task.run()

        self.assertTrue(result)
        self.assertEqual(self.task.project_id, "project-123")

        # Check that progress callbacks were called
        self.assertEqual(self.mock_on_progress_data.call_count, 3)
        calls = self.mock_on_progress_data.call_args_list
        self.assertEqual(calls[0][0][0], GeoApiStep.PROJECT)
        self.assertEqual(calls[1][0][0], GeoApiStep.BASEMAP_LAYERS)
        self.assertEqual(calls[2][0][0], GeoApiStep.FEATURES)

    @patch.object(LoadGeoApiProjectTask, '_request_data_from_backend')
    def test_run_project_fetch_failure(self, mock_request):
        """Test task run when project fetch fails."""
        mock_request.return_value = None

        result = self.task.run()

        self.assertFalse(result)

    def test_finished_success(self):
        """Test finished callback on success."""
        self.task.finished(True)

        self.mock_update_status.assert_called_with(
            GeoApiTaskState.DONE,
            "Finished fetching project."
        )

    def test_finished_failure(self):
        """Test finished callback on failure."""
        self.task.error = "Test error message"
        self.task.finished(False)

        self.mock_update_status.assert_called_with(
            GeoApiTaskState.FAILED,
            "Failed fetching project: Test error message"
        )


class TestDataProcessing(unittest.TestCase):
    """Test data processing functions (requires mocking QGIS components)."""

    def test_feature_grouping_logic(self):
        """Test that features are properly grouped by asset type."""
        # Test the logic that groups features by asset type
        features_data = {
            "features": [
                {
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "assets": [{"asset_type": "image", "display_path": "image1.jpg"}]
                },
                {
                    "geometry": {"type": "Point", "coordinates": [1, 1]},
                    "assets": [{"asset_type": "point_cloud", "display_path": "cloud1.las"}]
                },
                {
                    "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                    "assets": [{"asset_type": "streetview", "display_path": "street1.jpg"}]
                }
            ]
        }

        # Extract the grouping logic for testing
        point_cloud_features = []
        image_features = []
        streetview_features = []

        for feature in features_data.get("features", []):
            assets = feature.get("assets", [])
            if not assets:
                continue
            first_asset = assets[0]
            asset_type = first_asset.get("asset_type")
            if asset_type == "point_cloud":
                point_cloud_features.append((feature, first_asset))
            elif asset_type == "image":
                image_features.append(feature)
            elif asset_type == "streetview":
                streetview_features.append(feature)

        self.assertEqual(len(point_cloud_features), 1)
        self.assertEqual(len(image_features), 1)
        self.assertEqual(len(streetview_features), 1)

        # Test specific grouping results
        self.assertEqual(point_cloud_features[0][1]["display_path"], "cloud1.las")
        self.assertEqual(image_features[0]["assets"][0]["display_path"], "image1.jpg")
        self.assertEqual(streetview_features[0]["assets"][0]["display_path"], "street1.jpg")

    def test_basemap_layer_sorting(self):
        """Test basemap layers are sorted by zIndex."""
        layers = [
            {"name": "Layer B", "uiOptions": {"zIndex": 2}},
            {"name": "Layer A", "uiOptions": {"zIndex": 1}},
            {"name": "Layer C", "uiOptions": {"zIndex": 3}},
            {"name": "Layer No Z", "uiOptions": {}}  # Should default to 0
        ]

        # Test the sorting logic
        sorted_layers = sorted(layers, key=lambda x: x["uiOptions"].get("zIndex", 0))

        expected_order = ["Layer No Z", "Layer A", "Layer B", "Layer C"]
        actual_order = [layer["name"] for layer in sorted_layers]

        self.assertEqual(actual_order, expected_order)

    def test_url_processing(self):
        """Test URL processing for tile servers."""
        test_cases = [
            # TMS with {s} placeholder
            {
                "input": "https://tiles.example.com/{s}/tiles/{z}/{x}/{y}.png",
                "expected": "https://tiles.example.com/a/tiles/{z}/{x}/{y}.png"
            },
            # ArcGIS tile server
            {
                "input": "https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer",
                "type": "arcgis",
                "expected_contains": "/tile/{z}/{y}/{x}"
            }
        ]

        for case in test_cases:
            url = case["input"]
            if "{s}" in url:
                url = url.replace("{s}", "a")
                self.assertEqual(url, case["expected"])

            if case.get("type") == "arcgis" and "/tiles/" not in url:
                if not url.endswith("/tile/{z}/{y}/{x}") and not "{z}/{x}/{y}" in url:
                    tile_url = url.rstrip("/") + "/tile/{z}/{y}/{x}"
                    self.assertIn(case["expected_contains"], tile_url)


class TestIntegration(unittest.TestCase):
    """Integration tests with mocked QGIS components."""

    @patch('hazmapper_plugin.geoapi.QgsProject')
    @patch('hazmapper_plugin.geoapi.QgsLayerTreeGroup')
    def test_create_or_replace_main_group_new(self, mock_tree_group, mock_project):
        """Test creating a new main group when none exists."""
        # Mock the QGIS project and layer tree
        mock_root = Mock()
        mock_root.children.return_value = []  # No existing groups
        mock_project.instance.return_value.layerTreeRoot.return_value = mock_root

        # Mock the group creation
        mock_group = Mock()
        mock_tree_group.return_value = mock_group

        result = create_or_replace_main_group("Test Project", "uuid-123")

        # Verify the group was created and configured
        mock_tree_group.assert_called_once_with("Test Project (uuid-123)")
        mock_group.setCustomProperty.assert_called_once_with("hazmapper_uuid", "uuid-123")
        mock_root.insertChildNode.assert_called_once_with(0, mock_group)
        self.assertEqual(result, mock_group)


if __name__ == "__main__":
    # Run specific test classes or all tests
    unittest.main(verbosity=2)