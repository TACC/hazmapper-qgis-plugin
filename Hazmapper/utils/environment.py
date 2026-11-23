"""Work out which GeoAPI deployment a Hazmapper map URL belongs to."""

from urllib.parse import urlparse

HAZMAPPER_HOST = "hazmapper.tacc.utexas.edu"
PRODUCTION_GEOAPI_URL = f"https://{HAZMAPPER_HOST}/geoapi"

# First path segment of the Hazmapper web app -> path of the GeoAPI it talks to.
# Mirrors hazmapper's react/src/hooks/environment (useAppConfiguration, getGeoapiUrl).
_GEOAPI_PATH_BY_APP_PATH = {
    "hazmapper": "geoapi",
    "staging": "geoapi-staging",
    "dev": "geoapi-dev",
}


def geoapi_url_for_map(map_url: str) -> str:
    """
    Return the GeoAPI base URL for a Hazmapper map URL.

    e.g. https://hazmapper.tacc.utexas.edu/staging/project-public/<uuid>
         -> https://hazmapper.tacc.utexas.edu/geoapi-staging

    Anything unrecognised is treated as production.
    """
    parsed = urlparse((map_url or "").strip())
    if parsed.hostname != HAZMAPPER_HOST:
        return PRODUCTION_GEOAPI_URL

    app_path = parsed.path.strip("/").split("/")[0]
    geoapi_path = _GEOAPI_PATH_BY_APP_PATH.get(app_path)
    if geoapi_path is None:
        return PRODUCTION_GEOAPI_URL

    return f"https://{HAZMAPPER_HOST}/{geoapi_path}"
