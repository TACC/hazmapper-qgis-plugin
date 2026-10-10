import pytest

from Hazmapper.utils.features import (
    MEMORY_LAYER_TYPE,
    geometry_family,
    group_by_geometry_family,
    layer_name,
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
