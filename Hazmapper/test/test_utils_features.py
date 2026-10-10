import pytest

from Hazmapper.utils.features import (
    MEMORY_LAYER_TYPE,
    geometry_family,
    group_by_geometry_family,
    layer_name,
    property_columns,
    property_value,
)


def _feature(geometry_type):
    return {"geometry": {"type": geometry_type, "coordinates": []}}


@pytest.mark.no_qgis_required
@pytest.mark.parametrize(
    "geometry_type, family",
    [
        ("Point", "point"),
        ("MultiPoint", "point"),
        ("LineString", "line"),
        ("MultiLineString", "line"),
        ("Polygon", "polygon"),
        ("MultiPolygon", "polygon"),
        ("GeometryCollection", None),
    ],
)
def test_geometry_family(geometry_type, family):
    assert geometry_family(_feature(geometry_type)) == family


@pytest.mark.no_qgis_required
def test_geometry_family_without_geometry():
    assert geometry_family({"geometry": None}) is None
    assert geometry_family({}) is None


@pytest.mark.no_qgis_required
def test_every_family_has_a_memory_layer_type():
    assert MEMORY_LAYER_TYPE == {
        "point": "MultiPoint",
        "line": "MultiLineString",
        "polygon": "MultiPolygon",
    }


@pytest.mark.no_qgis_required
def test_group_by_geometry_family():
    point, line, multiline, broken = (
        _feature("Point"),
        _feature("LineString"),
        _feature("MultiLineString"),
        {"geometry": None},
    )

    groups = group_by_geometry_family([point, line, multiline, broken])

    assert groups == {"point": [point], "line": [line, multiline], None: [broken]}


@pytest.mark.no_qgis_required
def test_group_by_geometry_family_with_accessor():
    items = [(_feature("Polygon"), {"asset_type": "image"})]

    assert group_by_geometry_family(items, lambda item: item[0]) == {"polygon": items}


@pytest.mark.no_qgis_required
def test_layer_name_mentions_geometry_only_when_needed():
    assert layer_name("Images", "point", ["point"]) == "Images"
    assert layer_name("Images", "point", ["point", "polygon"]) == "Images (points)"
    assert layer_name("Images", "polygon", ["point", "polygon"]) == "Images (polygons)"


@pytest.mark.no_qgis_required
def test_property_columns_union_and_kinds():
    features = [
        {"properties": {"name": "A", "stories": 2, "height": 3}},
        {"properties": {"name": "B", "stories": None, "height": 4.5, "tags": ["x"]}},
        {"properties": {"stories": 1, "flag": True, "mixed": 1}},
        {"properties": {"mixed": "one"}},
        {"properties": None},
        {},
    ]

    assert property_columns(features) == [
        ("name", "name", "str"),
        ("stories", "stories", "int"),  # None does not stop it being numeric
        ("height", "height", "float"),  # int and float together
        ("tags", "tags", "str"),
        ("flag", "flag", "str"),  # booleans are kept as text
        ("mixed", "mixed", "str"),  # number and text together
    ]


@pytest.mark.no_qgis_required
def test_property_columns_all_null_is_text():
    assert property_columns([{"properties": {"Field23": None}}]) == [
        ("Field23", "Field23", "str")
    ]


@pytest.mark.no_qgis_required
def test_property_columns_avoid_the_feature_id_column():
    assert property_columns([{"properties": {"feature_id": 7}}]) == [
        ("feature_id", "feature_id_", "int")
    ]


@pytest.mark.no_qgis_required
@pytest.mark.parametrize(
    "value, kind, expected",
    [
        (None, "int", None),
        (None, "str", None),
        (3, "int", 3),
        (3, "float", 3.0),
        (4.5, "float", 4.5),
        ("text", "str", "text"),
        (7, "str", "7"),
        (True, "str", "true"),
        (["WG-4, 6thSt"], "str", '["WG-4, 6thSt"]'),
        ({"a": 1}, "str", '{"a": 1}'),
    ],
)
def test_property_value(value, kind, expected):
    assert property_value(value, kind) == expected
