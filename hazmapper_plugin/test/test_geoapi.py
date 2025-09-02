import unittest
import pytest
from unittest.mock import Mock, patch, ANY
import urllib.error

from hazmapper_plugin.hazmapper_fetch_task import (
    LoadGeoApiProjectTask, GeoApiTaskState, GeoApiStep
)
from hazmapper_plugin.hazmapper_layers import (
    json_to_wkt,
    create_main_group,
)



@pytest.mark.qgis_required
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
        geometry_json = """
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
        """
        wkt = json_to_wkt(geometry_json)
        self.assertIn("POLYGON", wkt)


@pytest.mark.qgis_required
class TestLoadGeoApiProjectTask(unittest.TestCase):
    """Test the main task class."""

    def setUp(self):
        """Set up test fixtures."""
        self.on_done = Mock()
        self.on_status = Mock()
        self.on_progress = Mock()

        self.BASE_URL = "https://hazmapper-TESTING.tacc.utexas.edu/geoapi/projects"

        self.task = LoadGeoApiProjectTask(uuid="test-uuid-123", base_url=self.BASE_URL)

        # wire up signal to mocks
        self.task.task_done.connect(self.on_done)
        self.task.status_update.connect(self.on_status)
        self.task.progress_data.connect(self.on_progress)

    def test_task_initialization(self):
        self.assertEqual(self.task.uuid, "test-uuid-123")
        self.assertEqual(self.task.base_url, self.BASE_URL)
        self.assertIsNone(self.task.project_id)
        self.assertIsNone(self.task.error)

    @patch("urllib.request.urlopen")
    def test_request_data_success(self, mock_urlopen):
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"test": "data"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = self.task._request_data_from_backend("/test", "test data")

        self.assertEqual(result, {"test": "data"})
        self.on_status.assert_called_with(GeoApiTaskState.RUNNING, "Fetching test data...")

    @patch("urllib.request.urlopen")
    def test_request_data_http_error(self, mock_urlopen):
        mock_response = Mock()
        mock_response.status = 404
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = self.task._request_data_from_backend("/test", "test data")

        self.assertIsNone(result)
        self.assertIn("Fetching test data failed", self.task.error)
        self.assertIn("404", self.task.error)

    @patch("urllib.request.urlopen")
    def test_request_data_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection failed")

        result = self.task._request_data_from_backend("/test", "test data")

        self.assertIsNone(result)
        self.assertIn("Fetching test data failed", self.task.error)

    @patch("urllib.request.urlopen")
    def test_request_data_json_error(self, mock_urlopen):
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = b"invalid json"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = self.task._request_data_from_backend("/test", "test data")

        self.assertIsNone(result)
        self.assertIn("Fetching test data failed", self.task.error)

    @patch.object(LoadGeoApiProjectTask, "_request_data_from_backend")
    def test_run_success(self, mock_request):
        """Test successful task run."""
        # project metadata, basemap layers, features
        mock_request.side_effect = [
            [{"id": "project-123", "name": "Test Project"}],
            [{"name": "Basemap", "type": "tms", "url": "http://example.com"}],
            {"features": [{"geometry": {"type": "Point"}, "assets": []}]},
        ]

        result = self.task.run()

        self.assertTrue(result)
        self.assertEqual(self.task.project_id, "project-123")

        # 3 progress emissions
        self.assertEqual(self.on_progress.call_count, 3)
        calls = self.on_progress.call_args_list
        self.assertEqual(calls[0][0][0], GeoApiStep.PROJECT)
        self.assertEqual(calls[1][0][0], GeoApiStep.BASEMAP_LAYERS)
        self.assertEqual(calls[2][0][0], GeoApiStep.FEATURES)

    @patch.object(LoadGeoApiProjectTask, "_request_data_from_backend")
    def test_run_project_fetch_failure(self, mock_request):
        mock_request.return_value = None
        result = self.task.run()
        self.assertFalse(result)

    def test_finished_success(self):
        # calling the task's finished() should emit task_done(success, message)
        self.task.finished(True)
        self.on_done.assert_called_with(True, "Finished fetching data")

    def test_finished_failure(self):
        self.task.error = "Test error message"
        self.task.finished(False)
        self.on_done.assert_called_with(False, "Test error message")


@pytest.mark.qgis_required
class TestIntegration(unittest.TestCase):
    """Integration tests with mocked QGIS components."""

    @patch("hazmapper_plugin.hazmapper_layers.QgsProject")
    @patch("hazmapper_plugin.hazmapper_layers.QgsLayerTreeGroup")
    def test_create_or_replace_main_group_new(self, mock_tree_group, mock_project):
        mock_root = Mock()
        mock_root.children.return_value = []
        mock_project.instance.return_value.layerTreeRoot.return_value = mock_root

        mock_group = Mock()
        mock_tree_group.return_value = mock_group

        result = create_main_group("Test Project", "uuid-123")

        mock_tree_group.assert_called_once_with("Test Project (uuid-123)")
        # Expect two calls with specific keys; second value can be anything (uuid)
        mock_group.setCustomProperty.assert_any_call("hazmapper_project_uuid", "uuid-123")
        mock_group.setCustomProperty.assert_any_call("hazmapper_qgis_internal_group_uuid", ANY)

        mock_root.insertChildNode.assert_called_once_with(0, mock_group)
        self.assertIs(result, mock_group)


if __name__ == "__main__":
    # Run specific test classes or all tests
    unittest.main(verbosity=2)