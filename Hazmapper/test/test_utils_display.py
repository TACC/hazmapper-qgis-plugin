import pytest
from Hazmapper.utils.display import get_display_name  # adjust path to where you put it


@pytest.mark.no_qgis_required
@pytest.mark.parametrize(
    "asset_type,expected",
    [
        ("point_cloud", "Point Clouds"),
        ("image", "Images"),
        ("streetview", "StreetView"),
        ("video", "Videos"),
        ("questionnaire", "Questionnaires"),
        ("no_asset_vector", "Vector Features"),
    ],
)
def test_known_asset_types(asset_type, expected):
    assert get_display_name(asset_type) == expected


@pytest.mark.no_qgis_required
def test_unknown_asset_type_titleized():
    assert get_display_name("some_custom_type") == "Some Custom Type"
    assert get_display_name("another_one") == "Another One"
