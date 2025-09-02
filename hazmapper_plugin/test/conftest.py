import pytest
import json
from pathlib import Path


@pytest.fixture
def test_data_dir():
    """Return the path to test data directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def project_metadata(test_data_dir):
    """Load project metadata from JSON file."""
    with open(test_data_dir / "project_metadata.json", "r") as f:
        return json.load(f)


@pytest.fixture
def basemap_layers_data(test_data_dir):
    """Load basemap layers from JSON file."""
    with open(test_data_dir / "basemap_layers.json", "r") as f:
        return json.load(f)


@pytest.fixture
def features_data(test_data_dir):
    """Load features data from JSON file."""
    with open(test_data_dir / "features.json", "r") as f:
        return json.load(f)
