import pytest


def test_json_to_wkt_polygon():
    from Hazmapper.utils.geometry import json_to_wkt

    geometry_json = """
    {
        "type": "Polygon",
        "coordinates": [[
            [-97.7431, 30.2672],
            [-97.7430, 30.2672],
            [-97.7430, 30.2671],
            [-97.7431, 30.2671],
            [-97.7431, 30.2672]
        ]]
    }
    """
    wkt = json_to_wkt(geometry_json)
    assert "POLYGON" in wkt


def test_json_to_wkt_point():
    from Hazmapper.utils.geometry import json_to_wkt

    geometry_json = '{"type": "Point", "coordinates": [-97.7431, 30.2672]}'
    wkt = json_to_wkt(geometry_json)
    assert "POINT" in wkt
    assert "-97.7431" in wkt
    assert "30.2672" in wkt
