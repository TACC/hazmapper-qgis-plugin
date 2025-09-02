import pytest
import urllib.error
from unittest.mock import Mock, patch, call

from hazmapper_plugin.hazmapper_fetch_task import (
    LoadGeoApiProjectTask,
    GeoApiTaskState,
    GeoApiStep,
)

BASE_URL = "https://hazmapper-TESTING.tacc.utexas.edu/geoapi/projects"


@pytest.fixture
def task_with_mocks():
    """Set up a task instance and connect PyQt signals to mocks."""
    on_done = Mock()
    on_status = Mock()
    on_progress = Mock()

    task = LoadGeoApiProjectTask(uuid="test-uuid-123", base_url=BASE_URL)

    # wire up signal to mocks
    task.task_done.connect(on_done)
    task.status_update.connect(on_status)
    task.progress_data.connect(on_progress)

    return task, on_done, on_status, on_progress


@pytest.mark.qgis_required
def test_task_initialization(task_with_mocks):
    """Test the main task class."""
    task, *_ = task_with_mocks
    assert task.uuid == "test-uuid-123"
    assert task.base_url == BASE_URL
    assert task.project_id is None
    assert task.error is None


@pytest.mark.qgis_required
@patch("urllib.request.urlopen")
def test_request_data_success(mock_urlopen, task_with_mocks):
    # Mock response
    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"test": "data"}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    task, _on_done, on_status, _on_progress = task_with_mocks

    result = task._request_data_from_backend("/test", "test data")

    assert result == {"test": "data"}
    on_status.assert_called_with(GeoApiTaskState.RUNNING, "Fetching test data...")


@pytest.mark.qgis_required
@patch("urllib.request.urlopen")
def test_request_data_http_error(mock_urlopen, task_with_mocks):
    mock_response = Mock()
    mock_response.status = 404
    mock_urlopen.return_value.__enter__.return_value = mock_response

    task, *_ = task_with_mocks
    result = task._request_data_from_backend("/test", "test data")

    assert result is None
    assert "Fetching test data failed" in task.error
    assert "404" in task.error


@pytest.mark.qgis_required
@patch("urllib.request.urlopen")
def test_request_data_network_error(mock_urlopen, task_with_mocks):
    mock_urlopen.side_effect = urllib.error.URLError("Connection failed")

    task, *_ = task_with_mocks
    result = task._request_data_from_backend("/test", "test data")

    assert result is None
    assert "Fetching test data failed" in task.error


@pytest.mark.qgis_required
@patch("urllib.request.urlopen")
def test_request_data_json_error(mock_urlopen, task_with_mocks):
    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = b"invalid json"
    mock_urlopen.return_value.__enter__.return_value = mock_response

    task, *_ = task_with_mocks
    result = task._request_data_from_backend("/test", "test data")

    assert result is None
    assert "Fetching test data failed" in task.error


@pytest.mark.qgis_required
@patch.object(LoadGeoApiProjectTask, "_request_data_from_backend")
def test_run_success(
    mock_request, task_with_mocks, project_metadata, basemap_layers_data, features_data
):
    """Test successful task run."""
    # Arrange: return fixture JSON in sequence
    mock_request.side_effect = [
        project_metadata,  # project metadata fixture
        basemap_layers_data,  # basemap layers fixture
        features_data,  # features fixture
    ]

    task, _on_done, _on_status, on_progress = task_with_mocks

    # Act
    result = task.run()

    # Assert: task succeeded and project_id set
    assert result is True
    assert task.project_id == project_metadata[0]["id"]

    # Assert: progress_data was emitted with the right steps
    expected_calls = [
        call(GeoApiStep.PROJECT, project_metadata[0]),
        call(GeoApiStep.BASEMAP_LAYERS, basemap_layers_data),
        call(GeoApiStep.FEATURES, features_data),
    ]
    on_progress.assert_has_calls(expected_calls)
    assert on_progress.call_count == 3


@pytest.mark.qgis_required
@patch.object(LoadGeoApiProjectTask, "_request_data_from_backend")
def test_run_project_fetch_failure(mock_request, task_with_mocks):
    mock_request.return_value = None
    task, *_ = task_with_mocks
    result = task.run()
    assert result is False


@pytest.mark.qgis_required
def test_finished_success(task_with_mocks):
    # calling the task's finished() should emit task_done(success, message)
    task, on_done, *_ = task_with_mocks
    task.finished(True)
    on_done.assert_called_with(True, "Finished fetching data")


@pytest.mark.qgis_required
def test_finished_failure(task_with_mocks):
    task, on_done, *_ = task_with_mocks
    task.error = "Test error message"
    task.finished(False)
    on_done.assert_called_with(False, "Test error message")
