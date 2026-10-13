"""Look up the DesignSafe publication that a Hazmapper map belongs to."""

from typing import Any, Dict, Optional

from .maps_of_published_projects import predefined_published_maps


def _normalize_url(url: str) -> str:
    return (url or "").strip().rstrip("/").lower()


def find_published_map(map_url: str) -> Optional[Dict[str, Any]]:
    """Return the published-maps entry for a Hazmapper map URL, or None if not listed."""
    # TODO this should come from DesignSafe eventually but right now
    # we are using our predefined_published_maps list
    # See https://github.com/TACC/hazmapper-qgis-plugin/issues/8
    norm = _normalize_url(map_url)
    for item in predefined_published_maps:
        if _normalize_url(item.get("url", "")) == norm:
            return item
    return None


def designsafe_project_url(project_id: str) -> str:
    """Return the DesignSafe page of a published project (e.g. PRJ-2714)."""
    return (
        "https://www.designsafe-ci.org/"
        f"data/browser/public/designsafe.storage.published/{project_id}"
    )
