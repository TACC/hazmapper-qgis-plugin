from osgeo import ogr
from qgis.core import QgsGeometry
import json


def json_to_wkt(geometry_json: str) -> str:
    """Convert GeoJSON geometry to WKT using fast GDAL/OGR."""
    geom = ogr.CreateGeometryFromJson(geometry_json)
    return geom.ExportToWkt()


def geojson_to_qgs_geometry(geometry_dict: dict) -> QgsGeometry:
    """Convert GeoJSON geometry dict directly to QgsGeometry (version compatible)."""
    geometry_json = json.dumps(geometry_dict)

    # Try QGIS native method first (newer versions)
    try:
        if hasattr(QgsGeometry, "fromJson"):
            return QgsGeometry.fromJson(geometry_json)
    except (AttributeError, Exception):
        pass

    # Fallback to GDAL method (works in all versions)
    ogr_geom = ogr.CreateGeometryFromJson(geometry_json)
    if ogr_geom is None:
        raise ValueError(f"Invalid geometry: {geometry_dict}")

    wkt = ogr_geom.ExportToWkt()
    return QgsGeometry.fromWkt(wkt)
