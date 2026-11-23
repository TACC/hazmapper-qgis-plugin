"""Helpers for turning Hazmapper (GeoJSON) features into QGIS layers. No QGIS imports."""

import json
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, TypeVar

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


# Column that holds the Hazmapper feature id on layers of plain features
FEATURE_ID_FIELD = "feature_id"


def property_columns(features: Iterable[Dict[str, Any]]) -> List[Tuple[str, str, str]]:
    """
    Work out the attribute columns for a set of features from their `properties`.

    Features on one map need not share the same properties, so this is the union of
    all keys, in first-seen order. Returns (property key, column name, kind) where kind
    is "int", "float" or "str": a column is numeric only if every value in it is.
    """
    kinds: Dict[str, set] = {}
    for feature in features:
        for key, value in (feature.get("properties") or {}).items():
            seen = kinds.setdefault(str(key), set())
            if value is None:
                continue
            if isinstance(value, bool):
                seen.add("str")
            elif isinstance(value, int):
                seen.add("int")
            elif isinstance(value, float):
                seen.add("float")
            else:
                seen.add("str")

    columns = []
    taken = {FEATURE_ID_FIELD}
    for key, seen in kinds.items():
        if seen == {"int"}:
            kind = "int"
        elif seen and seen <= {"int", "float"}:
            kind = "float"
        else:
            kind = "str"

        name = key
        while name in taken:  # keep column names unique
            name += "_"
        taken.add(name)
        columns.append((key, name, kind))
    return columns


def property_value(value: Any, kind: str) -> Any:
    """Convert one property value for a column of the given kind (None stays None)."""
    if value is None:
        return None
    if kind == "int":
        return int(value)
    if kind == "float":
        return float(value)
    if isinstance(value, str):
        return value
    # lists, objects and booleans are kept as their JSON text
    return json.dumps(value, ensure_ascii=False)
