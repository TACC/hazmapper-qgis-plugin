import pytest

from Hazmapper.utils.tiles import (
    cog_tile_url,
    external_tile_url,
    is_internal_cog,
    resolve_tile_url,
    zoom_range,
)

GEOAPI_URL = "https://hazmapper.example.org/geoapi"


@pytest.fixture
def cog_layer():
    return {
        "name": "Pier ortho",
        "type": "xyz",
        "kind": "cog",
        "internal": True,
        "url": "/assets/833/4a026c0a.cog.tif",
        "tileOptions": {"minZoom": 0, "maxZoom": 24, "maxNativeZoom": 23},
        "uiOptions": {"zIndex": -4, "opacity": 1, "renderOptions": {}},
    }


@pytest.mark.no_qgis_required
@pytest.mark.parametrize(
    "layer, expected",
    [
        ({"internal": True, "kind": "cog"}, True),
        ({"internal": False, "kind": "cog"}, False),
        ({"internal": True, "kind": None}, False),
        ({"type": "tms"}, False),
    ],
)
def test_is_internal_cog(layer, expected):
    assert is_internal_cog(layer) is expected


@pytest.mark.no_qgis_required
def test_cog_tile_url(cog_layer):
    assert cog_tile_url(cog_layer, GEOAPI_URL) == (
        "https://hazmapper.example.org/geoapi/tiles/cog/tiles/WebMercatorQuad/"
        "{z}/{x}/{y}.png?url=file%3A%2F%2F%2Fassets%2F833%2F4a026c0a.cog.tif"
    )


@pytest.mark.no_qgis_required
def test_cog_tile_url_passes_render_options_to_titiler(cog_layer):
    cog_layer["uiOptions"]["renderOptions"] = {
        "colormap_name": "terrain",
        "rescale": "0,255",
    }

    url = cog_tile_url(cog_layer, GEOAPI_URL + "/")

    assert url.endswith(".cog.tif&colormap_name=terrain&rescale=0%2C255")
    assert "geoapi/tiles/cog" in url  # no double slash from the trailing "/"


@pytest.mark.no_qgis_required
@pytest.mark.parametrize(
    "layer, expected",
    [
        (
            {"type": "tms", "url": "https://{s}.tile.osm.org/{z}/{x}/{y}.png"},
            "https://a.tile.osm.org/{z}/{x}/{y}.png",
        ),
        (
            {"type": "tms", "url": "https://example.org/MapServer/tile/{z}/{y}/{x}"},
            "https://example.org/MapServer/tile/{z}/{y}/{x}",
        ),
        (
            {"type": "arcgis", "url": "https://example.org/tiles/abc/MapServer"},
            "https://example.org/tiles/abc/MapServer/tile/{z}/{y}/{x}",
        ),
        ({"type": "arcgis", "url": "https://example.org/rest/MapServer"}, None),
        ({"type": "wms", "url": "https://example.org/wms"}, None),
        # an "xyz" layer that isn't one of our COGs is still unsupported
        ({"type": "xyz", "url": "https://example.org/{z}/{x}/{y}.png"}, None),
    ],
)
def test_external_tile_url(layer, expected):
    assert external_tile_url(layer) == expected


@pytest.mark.no_qgis_required
def test_resolve_tile_url(cog_layer):
    assert "/tiles/cog/tiles/" in resolve_tile_url(cog_layer, GEOAPI_URL)
    assert (
        resolve_tile_url({"type": "tms", "url": "https://x.org/{z}/{x}/{y}"}, "")
        == "https://x.org/{z}/{x}/{y}"
    )


@pytest.mark.no_qgis_required
def test_zoom_range(cog_layer):
    assert zoom_range(cog_layer) == (0, 23)
    assert zoom_range({"internal": True, "kind": "cog"}) == (0, 22)
    # external layers keep the fixed range for now
    assert zoom_range({"type": "tms", "tileOptions": {"maxZoom": 19}}) == (0, 22)
