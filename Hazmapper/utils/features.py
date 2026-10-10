"""Helpers for turning Hazmapper (GeoJSON) features into QGIS layers. No QGIS imports."""

from typing import Any, Callable, Dict, Iterable, List, Optional, TypeVar

T = TypeVar("T")

# A QGIS layer holds one kind of geometry, so features are split into these families.
_FAMILY_BY_GEOMETRY_TYPE = {
    "Point": "point",
    "MultiPoint": "point",
    "LineString": "line",
    "MultiLineString": "line",
    "Polygon": "polygon",
    "MultiPolygon": "polygon",
}

# Memory-layer geometry type for each family (multi, so single and multi parts both fit)
MEMORY_LAYER_TYPE = {
    "point": "MultiPoint",
    "line": "MultiLineString",
    "polygon": "MultiPolygon",
}


def geometry_family(feature: Dict[str, Any]) -> Optional[str]:
    """Return "point", "line" or "polygon" for a feature, or None if it can't be shown."""
    geometry = feature.get("geometry") or {}
    return _FAMILY_BY_GEOMETRY_TYPE.get(geometry.get("type"))


def group_by_geometry_family(
    items: Iterable[T], get_feature: Callable[[T], Dict[str, Any]] = lambda item: item
) -> Dict[Optional[str], List[T]]:
    """Split items by geometry family. Items that can't be shown are under the key None."""
    groups: Dict[Optional[str], List[T]] = {}
    for item in items:
        groups.setdefault(geometry_family(get_feature(item)), []).append(item)
    return groups


def layer_name(base_name: str, family: str, families_present: Iterable[str]) -> str:
    """Name a layer; say which geometry it holds only when there is more than one."""
    if len(set(families_present)) <= 1:
        return base_name
    return f"{base_name} ({family}s)"
