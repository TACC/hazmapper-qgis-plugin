import pytest

from Hazmapper.utils.environment import PRODUCTION_GEOAPI_URL, geoapi_url_for_map

BASE = "https://hazmapper.tacc.utexas.edu"


@pytest.mark.no_qgis_required
@pytest.mark.parametrize(
    "app_path, geoapi_path",
    [
        ("hazmapper", "geoapi"),
        ("staging", "geoapi-staging"),
        ("dev", "geoapi-dev"),
    ],
)
def test_geoapi_url_for_map(app_path, geoapi_path):
    map_url = f"{BASE}/{app_path}/project-public/1260cfdc-00c5/?selectedFeature=1"
    assert geoapi_url_for_map(map_url) == f"{BASE}/{geoapi_path}"


@pytest.mark.no_qgis_required
@pytest.mark.parametrize(
    "map_url",
    [
        f"{BASE}/something-else/project-public/abc",
        f"{BASE}/staging-tmp/project-public/abc",  # retired deployment
        f"{BASE}/project-public/abc",
        "https://example.org/staging/project-public/abc",
        "not a url",
        "",
        None,
    ],
)
def test_geoapi_url_for_map_defaults_to_production(map_url):
    assert geoapi_url_for_map(map_url) == PRODUCTION_GEOAPI_URL
    assert PRODUCTION_GEOAPI_URL == f"{BASE}/geoapi"
