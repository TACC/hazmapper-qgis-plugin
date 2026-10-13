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


@pytest.mark.no_qgis_required
def test_shorten_leaves_short_text_alone():
    from Hazmapper.utils.display import shorten

    assert shorten("A short description.") == "A short description."
    assert shorten("  spread   over\nlines  ") == "spread over lines"
    assert shorten("") == ""
    assert shorten(None) == ""


@pytest.mark.no_qgis_required
def test_shorten_cuts_at_a_word():
    from Hazmapper.utils.display import shorten

    text = (
        "This project aims to identify the compounding impacts of 2017 Hurricane Maria. "
        * 4
    )

    short = shorten(text, limit=60)

    assert len(short) <= 60
    assert text.startswith(short)
    assert short == "This project aims to identify the compounding impacts of"
