"""Build links from a Hazmapper feature to where it can be viewed. No QGIS imports."""


def hazmapper_feature_url(map_url: str, feature_id) -> str:
    """Link that opens the Hazmapper web map with one feature selected."""
    base = map_url.split("?")[0].rstrip("/")
    return f"{base}/?selectedFeature={feature_id}"


def asset_url(geoapi_url: str, asset_path: str) -> str:
    """Address of a feature's file (e.g. a photo) as geoapi serves it."""
    return f"{geoapi_url.rstrip('/')}/assets/{asset_path.lstrip('/')}"
