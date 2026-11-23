import pytest

from Hazmapper.utils.published_maps import designsafe_project_url, find_published_map

PUERTO_RICO_MAP = (
    "https://hazmapper.tacc.utexas.edu/hazmapper/project-public/"
    "1260cfdc-00c5-42d2-ab4b-ac498b24e44c"
)


@pytest.mark.no_qgis_required
@pytest.mark.parametrize(
    "map_url", [PUERTO_RICO_MAP, PUERTO_RICO_MAP + "/", PUERTO_RICO_MAP.upper()]
)
def test_find_published_map(map_url):
    assert find_published_map(map_url)["designSafeProjectId"] == "PRJ-2714"


@pytest.mark.no_qgis_required
@pytest.mark.parametrize(
    "map_url",
    ["https://hazmapper.tacc.utexas.edu/hazmapper/project-public/x", "", None],
)
def test_find_published_map_not_listed(map_url):
    assert find_published_map(map_url) is None


@pytest.mark.no_qgis_required
def test_designsafe_project_url():
    assert designsafe_project_url("PRJ-2714") == (
        "https://www.designsafe-ci.org/data/browser/public/"
        "designsafe.storage.published/PRJ-2714"
    )
