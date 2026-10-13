import pytest

from Hazmapper.utils.tiles import (
    attribution_text,
    cog_bounds,
    cog_tile_url,
    external_tile_url,
    is_internal_cog,
    is_wms,
    resolve_tile_url,
    wms_params,
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
        "tileOptions": {
            "bounds": [[17.9668, -66.6213], [17.9675, -66.6207]],
            "minZoom": 0,
            "maxZoom": 24,
            "maxNativeZoom": 23,
        },
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
@pytest.mark.parametrize(
    "tile_options, expected",
    [
        # OpenStreetMap as geoapi returns it: zoomable to 24, tiles only to 19
        ({"minZoom": 0, "maxZoom": 24, "maxNativeZoom": 19}, (0, 19)),
        ({"minZoom": 5, "maxNativeZoom": 23}, (5, 23)),
        ({"maxZoom": 24}, (0, 22)),
        ({}, (0, 22)),
        (None, (0, 22)),
    ],
)
def test_zoom_range(tile_options, expected):
    assert zoom_range({"tileOptions": tile_options}) == expected


@pytest.mark.no_qgis_required
def test_cog_bounds(cog_layer):
    # geoapi: [[south, west], [north, east]] -> (west, south, east, north)
    assert cog_bounds(cog_layer) == (-66.6213, 17.9668, -66.6207, 17.9675)


@pytest.mark.no_qgis_required
@pytest.mark.parametrize(
    "tile_options", [None, {}, {"bounds": None}, {"bounds": [[1, 2]]}, {"bounds": "x"}]
)
def test_cog_bounds_missing_or_malformed(tile_options):
    assert cog_bounds({"tileOptions": tile_options}) is None


@pytest.mark.no_qgis_required
@pytest.mark.parametrize(
    "attribution, expected",
    [
        (
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            " contributors",
            "© OpenStreetMap contributors",
        ),
        ("Tiles &copy; Esri &mdash; Source: Esri", "Tiles © Esri — Source: Esri"),
        ("", ""),
        (None, ""),
    ],
)
def test_attribution_text(attribution, expected):
    assert attribution_text({"attribution": attribution}) == expected
    assert attribution_text({}) == ""


CENSUS_WMS = {
    "name": "Census Bound",
    "type": "wms",
    "url": (
        "https://tigerweb.geo.census.gov/arcgis/services/TIGERweb/"
        "tigerWMS_Current/MapServer/WMSServer"
    ),
    "tileOptions": {"format": "jpeg", "layers": "71"},
    "uiOptions": {"zIndex": -3, "opacity": 0.3, "isActive": True},
}


@pytest.mark.no_qgis_required
def test_is_wms():
    assert is_wms(CENSUS_WMS)
    assert not is_wms({"type": "tms"})
    assert not is_wms({})


@pytest.mark.no_qgis_required
def test_wms_params():
    assert wms_params(CENSUS_WMS) == {
        "url": CENSUS_WMS["url"],
        "layers": ["71"],
        "styles": [""],
        "format": "image/jpeg",
        "crs": "EPSG:3857",
    }


@pytest.mark.no_qgis_required
def test_wms_params_several_layers_and_styles():
    layer = {
        "type": "wms",
        "url": "https://example.org/wms",
        "tileOptions": {
            "layers": "roads, rivers ,lakes",
            "format": "image/png",
            "params": {"styles": "thick"},
        },
    }

    params = wms_params(layer)

    assert params["layers"] == ["roads", "rivers", "lakes"]
    assert params["styles"] == [
        "thick",
        "",
        "",
    ]  # one per layer, default when not given
    assert params["format"] == "image/png"


@pytest.mark.no_qgis_required
@pytest.mark.parametrize(
    "layer",
    [
        {"type": "wms", "url": "https://example.org/wms", "tileOptions": {}},
        {"type": "wms", "url": "https://example.org/wms"},
        {"type": "wms", "url": "", "tileOptions": {"layers": "71"}},
    ],
)
def test_wms_params_incomplete_record(layer):
    assert wms_params(layer) is None


@pytest.mark.no_qgis_required
def test_wms_params_defaults_to_png():
    layer = {"type": "wms", "url": "https://x.org/wms", "tileOptions": {"layers": "a"}}
    assert wms_params(layer)["format"] == "image/png"
