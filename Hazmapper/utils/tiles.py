"""
Build tile URLs for the tile-server layers that geoapi returns from
GET /projects/{id}/tile-servers/.

Two shapes matter:

1. External tile layers (basemaps): `url` is a tile URL template.

2. Internal COG layers (GeoTIFFs imported through Hazmapper): internal=true,
   kind="cog", and `url` is the server-side path of the COG file, e.g.
   /assets/3/<uuid>.cog.tif. geoapi's TiTiler renders tiles from it; any styling
   chosen in Hazmapper (uiOptions.renderOptions) is passed to TiTiler as query
   parameters. Keep cog_tile_url() in step with hazmapper's
   react/src/utils/tiles.ts so both clients show the same thing.

Pure Python (no QGIS imports) so it can be tested without QGIS.
"""

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
