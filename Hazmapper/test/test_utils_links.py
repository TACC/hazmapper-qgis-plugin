import pytest

from Hazmapper.utils.links import asset_url, hazmapper_feature_url

MAP = "https://hazmapper.tacc.utexas.edu/hazmapper/project-public/1260cfdc"
GEOAPI = "https://hazmapper.tacc.utexas.edu/geoapi"


@pytest.mark.no_qgis_required
@pytest.mark.parametrize("map_url", [MAP, MAP + "/", MAP + "/?selectedFeature=1"])
def test_hazmapper_feature_url(map_url):
    assert hazmapper_feature_url(map_url, 587228) == f"{MAP}/?selectedFeature=587228"


@pytest.mark.no_qgis_required
def test_asset_url():
    assert asset_url(GEOAPI + "/", "833/abc.jpeg") == f"{GEOAPI}/assets/833/abc.jpeg"
    assert asset_url(GEOAPI, "/833/abc.jpeg") == f"{GEOAPI}/assets/833/abc.jpeg"
