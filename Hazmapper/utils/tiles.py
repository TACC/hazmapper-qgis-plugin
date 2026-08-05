from typing import Any, Dict, Optional

# Tile / raster source resolution for geoapi tile-server layers.
#
# geoapi returns tile-server records from GET /projects/{id}/tile-servers/.
# Two shapes matter here:
#
# 1. External tile layers (basemaps): internal=false, a full XYZ/TMS/arcgis
#    tile URL template in `url` (contains {z}/{x}/{y}).
#
# 2. Internal COG layers (created by importing a GeoTIFF in hazmapper):
#    type="xyz", kind="cog", internal=true, and `url` is the *server-side*
#    path to the generated COG asset, e.g. /assets/3/<uuid>.cog.tif
#    (see geoapi tasks/raster.py). The asset is served over HTTP range
#    requests under the geoapi base URL, so we load it as a native GDAL
#    raster via /vsicurl/ — this lets QGIS inspect actual pixel values
#    (Identify tool, histograms, band stats), unlike pre-rendered tiles.


def is_internal_cog(layer: Dict[str, Any]) -> bool:
    """True if the layer is an internal (geoapi-served) COG raster asset."""
    return bool(layer.get("internal")) and layer.get("kind") == "cog"


def resolve_cog_source(layer: Dict[str, Any], geoapi_url: str) -> Optional[str]:
    """
    Build the GDAL /vsicurl/ source string for an internal COG layer.

    `layer["url"]` is a server path like '/assets/3/<uuid>.cog.tif'; the asset
    is served under the geoapi base URL. Returns None if the layer is not an
    internal COG or has no url.
    """
    if not is_internal_cog(layer):
        return None

    path = layer.get("url")
    if not path:
        return None

    base = geoapi_url.rstrip("/")
    asset_url = f"{base}/{str(path).lstrip('/')}"
    return f"/vsicurl/{asset_url}"


def resolve_xyz_tile_url(layer: Dict[str, Any]) -> Optional[str]:
    """
    Build the XYZ tile URL template for an external tile-server layer.

    Preserves the original behavior from add_basemap_layers(): substitute the
    {s} subdomain placeholder, and normalize tms/arcgis-tiles URLs to the
    expected /tile/{z}/{y}/{x} form. Returns None for layer types we cannot
    render as XYZ tiles.
    """
    url = layer.get("url", "")
    layer_type = layer.get("type")

    # Handle subdomain placeholder (pick 'a' for QGIS)
    if "{s}" in url:
        url = url.replace("{s}", "a")

    if layer_type in ("tms", "xyz") or (layer_type == "arcgis" and "/tiles/" in url):
        # Ensure tile path includes expected XYZ format
        if not url.endswith("/tile/{z}/{y}/{x}") and "{z}/{x}/{y}" not in url:
            url = url.rstrip("/") + "/tile/{z}/{y}/{x}"
        return url

    return None
