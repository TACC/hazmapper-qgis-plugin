"""
Build tile URLs for the tile-server layers that geoapi returns from
GET /projects/{id}/tile-servers/.

Two shapes matter:

1. External tile layers (basemaps): `url` is a tile URL template, or the address of
   a WMS service when type="wms".

2. Internal COG layers (GeoTIFFs imported through Hazmapper): internal=true,
   kind="cog", and `url` is the server-side path of the COG file, e.g.
   /assets/3/<uuid>.cog.tif. geoapi's TiTiler renders tiles from it; any styling
   chosen in Hazmapper (uiOptions.renderOptions) is passed to TiTiler as query
   parameters. Keep cog_tile_url() in step with hazmapper's
   react/src/utils/tiles.ts so both clients show the same thing.

Pure Python (no QGIS imports) so it can be tested without QGIS.
"""

import html
import re
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote, urlencode

DEFAULT_MIN_ZOOM = 0
DEFAULT_MAX_ZOOM = 22


def is_internal_cog(layer: Dict[str, Any]) -> bool:
    """True if the layer is a COG served by geoapi (rather than an external tile server)."""
    return bool(layer.get("internal")) and layer.get("kind") == "cog"


def cog_tile_url(layer: Dict[str, Any], geoapi_url: str) -> str:
    """Build the TiTiler tile URL template for an internal COG layer."""
    file_url = quote(f"file://{layer['url']}", safe="")
    tile_url = (
        f"{geoapi_url.rstrip('/')}/tiles/cog/tiles/WebMercatorQuad/"
        f"{{z}}/{{x}}/{{y}}.png?url={file_url}"
    )

    render_options = (layer.get("uiOptions") or {}).get("renderOptions") or {}
    if render_options:
        tile_url += "&" + urlencode(render_options)

    return tile_url


def external_tile_url(layer: Dict[str, Any]) -> Optional[str]:
    """
    Build the XYZ tile URL template for an external tile-server layer.

    Returns None for layer types we cannot show as XYZ tiles.
    """
    url = layer.get("url", "")
    layer_type = layer.get("type")

    # Handle subdomain placeholder (pick 'a' for QGIS)
    if "{s}" in url:
        url = url.replace("{s}", "a")

    if layer_type == "tms" or (layer_type == "arcgis" and "/tiles/" in url):
        # Ensure tile path includes expected XYZ format
        if not url.endswith("/tile/{z}/{y}/{x}") and "{z}/{x}/{y}" not in url:
            return url.rstrip("/") + "/tile/{z}/{y}/{x}"
        return url

    return None


def cog_bounds(layer: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
    """
    Return an internal COG's footprint as (west, south, east, north) in degrees
    (EPSG:4326), or None if geoapi did not provide one.

    geoapi stores it Leaflet-style in tileOptions.bounds: [[south, west], [north, east]].
    """
    bounds = (layer.get("tileOptions") or {}).get("bounds")
    try:
        (south, west), (north, east) = bounds
        return float(west), float(south), float(east), float(north)
    except (TypeError, ValueError):
        return None


def is_wms(layer: Dict[str, Any]) -> bool:
    """True if the layer is a WMS service (drawn by the server per request, not tiles)."""
    return layer.get("type") == "wms"


def wms_params(layer: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Return what QGIS needs to open a WMS layer: url, layers, styles, format and crs.

    geoapi keeps the Leaflet options in tileOptions, e.g. {"layers": "71", "format": "jpeg"}.
    Returns None if the record names no WMS layers.
    """
    tile_options = layer.get("tileOptions") or {}
    params = tile_options.get("params") or {}

    def names(value) -> list:
        return [name.strip() for name in str(value or "").split(",") if name.strip()]

    layers = names(tile_options.get("layers") or params.get("layers"))
    if not layer.get("url") or not layers:
        return None

    # one style per layer; "" asks the server for that layer's default style
    styles = names(tile_options.get("styles") or params.get("styles"))
    styles = (styles + [""] * len(layers))[: len(layers)]

    image_format = str(tile_options.get("format") or params.get("format") or "png")
    if "/" not in image_format:
        image_format = f"image/{image_format}"

    return {
        "url": layer["url"],
        "layers": layers,
        "styles": styles,
        "format": image_format,
        "crs": "EPSG:3857",
    }


def resolve_tile_url(layer: Dict[str, Any], geoapi_url: str) -> Optional[str]:
    """Return the XYZ tile URL template for a layer, or None if it is unsupported."""
    if is_internal_cog(layer):
        return cog_tile_url(layer, geoapi_url)
    return external_tile_url(layer)


def zoom_range(layer: Dict[str, Any]) -> tuple[int, int]:
    """
    Return (min zoom, max zoom) of the tiles to request for a layer.

    The max is the deepest zoom the server has tiles for (maxNativeZoom); past it,
    QGIS enlarges those tiles. tileOptions.maxZoom is not used: it is how far the
    web map lets you zoom in, which can be deeper than the tiles go.
    """
    tile_options = layer.get("tileOptions") or {}
    return (
        int(tile_options.get("minZoom") or DEFAULT_MIN_ZOOM),
        int(tile_options.get("maxNativeZoom") or DEFAULT_MAX_ZOOM),
    )


def attribution_text(layer: Dict[str, Any]) -> str:
    """
    Return a tile layer's attribution as plain text ("" if it has none).

    geoapi stores it as the HTML shown on the web map, e.g.
    '&copy; <a href="...">OpenStreetMap</a> contributors'.
    """
    without_tags = re.sub(r"<[^>]+>", "", layer.get("attribution") or "")
    return " ".join(html.unescape(without_tags).split())
