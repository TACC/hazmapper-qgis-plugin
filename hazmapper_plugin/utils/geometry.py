from osgeo import ogr


def json_to_wkt(geometry_json: str) -> str:
    geom = ogr.CreateGeometryFromJson(geometry_json)
    return geom.ExportToWkt()
