from qgis.core import (QgsTask, QgsMessageLog, Qgis,
                       QgsProject, QgsLayerTreeGroup, QgsRasterLayer, QgsVectorLayer,
                       QgsFeature, QgsGeometry, QgsField, QgsFields)
from PyQt5.QtCore import QVariant, QSettings
from osgeo import ogr
import json
import uuid

from .utils.style import (
    apply_camera_icon_style,
    apply_point_cloud_style,
    apply_streetview_style
)


from qgis.core import QgsProject, QgsLayerTreeGroup, QgsMessageLog, Qgis
from qgis.PyQt.QtCore import QSettings

def remove_previous_main_group() -> None:
    """
    Safely remove Hazmapper project group and all its layers.
    Must be called in GUI thread.
    """
    settings = QSettings()
    internal_uuid = settings.value("HazmapperPlugin/internal_group_uuid", None)

    if not internal_uuid:
        QgsMessageLog.logMessage("[Hazmapper] No internal UUID set; nothing to remove.", "Hazmapper", Qgis.Info)
        return

    QgsMessageLog.logMessage(f"[Hazmapper] Removing group for internal UUID {internal_uuid}", "Hazmapper", Qgis.Info)

    root = QgsProject.instance().layerTreeRoot()
    if root is None:
        QgsMessageLog.logMessage("No layer tree root available.", "Hazmapper", Qgis.Warning)
        return

    for child in list(root.children()):
        if isinstance(child, QgsLayerTreeGroup) and child.customProperty("hazmapper_qgis_internal_group_uuid") == internal_uuid:
            # Remove all layers first
            for sublayer in child.findLayers():
                layer = sublayer.layer()
                if layer:
                    QgsProject.instance().removeMapLayer(layer.id())

            # Remove group node
            root.removeChildNode(child)
            QgsMessageLog.logMessage(f"[Hazmapper] Removed group with internal UUID {internal_uuid}", "Hazmapper", Qgis.Info)

            # Clear UUID in settings to avoid stale reference
            settings.remove("HazmapperPlugin/internal_group_uuid")
            return

    QgsMessageLog.logMessage(f"[Hazmapper] No group found for internal UUID {internal_uuid}", "Hazmapper", Qgis.Warning)


def create_main_group(project_name: str, project_uuid: str) -> QgsLayerTreeGroup:
    """
    Create new Hazmapper project group at top of layer tree.

    Returns:
        QgsLayerTreeGroup: The newly created group
    """
    try:
        QgsMessageLog.logMessage(f"[Hazmapper] Creating main group", "Hazmapper", Qgis.Info)

        internal_uuid = str(uuid.uuid4())
        group_name = f"{project_name} ({project_uuid[:8]})"

        root = QgsProject.instance().layerTreeRoot()

        # Create new group
        group = QgsLayerTreeGroup(group_name)

        # Store identifiers for map's uuid and our own uuid for the qgis group
        group.setCustomProperty("hazmapper_project_uuid", project_uuid)
        group.setCustomProperty("hazmapper_qgis_internal_group_uuid", internal_uuid)

        root.insertChildNode(0, group)
        QgsMessageLog.logMessage(f"[Hazmapper] Created new group: {group_name} with internal UUID: {internal_uuid}",
                                 "Hazmapper", Qgis.Info)
        settings = QSettings()
        settings.setValue("HazmapperPlugin/internal_group_uuid", internal_uuid)

        return group

    except Exception as e:
        QgsMessageLog.logMessage(f"[Hazmapper] Error in create_or_replace_main_group: {str(e)}", "Hazmapper", Qgis.Critical)
        raise


def add_basemap_layers(main_group, layers: list[dict]):
    # Sort by zIndex (ascending: lower zIndex means lower in stack)
    sorted_layers = sorted(layers, key=lambda x: x["uiOptions"].get("zIndex", 0))

    for layer_data in sorted_layers:
        try:
            name = layer_data["name"]
            url = layer_data["url"]
            layer_type = layer_data["type"]
            opacity = layer_data["uiOptions"].get("opacity", 1.0)

            QgsMessageLog.logMessage(
                f"[Basemap] Name: {name}\n"
                f"          Type: {layer_type}\n"
                f"          URL: {url}\n"
                f"          Tile Options: {layer_data.get('tileOptions')}\n"
                f"          UI Options: {layer_data.get('uiOptions')}",
                "Hazmapper", Qgis.Info
            )

            #  Need to pick a,b,c for QGIS
            if "{s}" in url:
                url = url.replace("{s}", "a")

            if layer_type == "tms" or (layer_type == "arcgis" and "/tiles/" in url):
                if not url.endswith("/tile/{z}/{y}/{x}") and not "{z}/{x}/{y}" in url:
                    tile_url = url.rstrip("/") + "/tile/{z}/{y}/{x}"
                else:
                    tile_url = url
                uri = f"type=xyz&url={tile_url}"
            else:
                QgsMessageLog.logMessage(f"Skipping unsupported layer type: {layer_type}", "Hazmapper", Qgis.Warning)
                continue

            # QGIS wants wms instead of xys TODO review what is going on here
            raster_layer = QgsRasterLayer(uri, name, "wms")
            if not raster_layer.isValid():
                QgsMessageLog.logMessage(f"Failed to load layer: {name}", "Hazmapper", Qgis.Warning)
                continue

            raster_layer.setOpacity(opacity)
            QgsProject.instance().addMapLayer(raster_layer, False)
            main_group.insertLayer(0, raster_layer)

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error processing layer '{layer_data.get('name', 'unnamed')}': {str(e)}",
                "Hazmapper", Qgis.Critical
            )


def add_features_layers(main_group: QgsLayerTreeGroup, features: dict):
    # Group features by asset type
    #  TODO should be grouped by both asset type AND geometry type (i.e. not all images are points)
    point_cloud_features = []
    image_features = []
    streetview_features = []

    for feature in features.get("features", []):
        assets = feature.get("assets", [])
        if not assets:
            continue
        first_asset = assets[0]
        asset_type = first_asset.get("asset_type")
        if asset_type == "point_cloud":
            point_cloud_features.append((feature, first_asset))
        elif asset_type == "image":
            image_features.append(feature)
        elif asset_type == "streetview":
            streetview_features.append(feature)

    # Create point cloud layers — one per feature
    for feature, asset in point_cloud_features:
        layer_name = asset.get("display_path", "Unnamed Point Cloud")
        vl = _create_memory_layer(feature, layer_name)
        _set_feature_metadata(vl, feature, asset)
        apply_point_cloud_style(vl)
        QgsProject.instance().addMapLayer(vl, False)
        main_group.insertLayer(0, vl)

    # Create a single image layer
    if image_features:
        vl = _create_memory_layer_collection(image_features, "Images")
        apply_camera_icon_style(vl)
        QgsProject.instance().addMapLayer(vl, False)
        main_group.insertLayer(0, vl)

    # Create a single streetview layer
    if streetview_features:
        vl = _create_memory_layer_collection(streetview_features, "StreetView")
        apply_streetview_style(vl)
        QgsProject.instance().addMapLayer(vl, False)
        main_group.insertLayer(0, vl)

    # TODO handle other types of assets or just plain geometry

def json_to_wkt(geometry_json: str) -> str:
    geom = ogr.CreateGeometryFromJson(geometry_json)
    return geom.ExportToWkt()

def _create_memory_layer(feature: dict, name: str) -> QgsVectorLayer:
    geom_type = feature["geometry"]["type"]
    layer = QgsVectorLayer(f"{geom_type}?crs=EPSG:4326", name, "memory")
    provider = layer.dataProvider()

    # Define fields
    fields = QgsFields()
    fields.append(QgsField("asset_type", QVariant.String))
    fields.append(QgsField("display_path", QVariant.String))
    provider.addAttributes(fields)
    layer.updateFields()


    # Build feature
    f = QgsFeature()
    geometry_json = json.dumps(feature["geometry"])
    f.setGeometry(QgsGeometry.fromWkt(json_to_wkt(geometry_json)))

    asset = feature.get("assets", [{}])[0] or {}
    f.setAttributes([
        asset.get("asset_type", ""),
        asset.get("display_path", "")
    ])

    provider.addFeature(f)
    layer.updateExtents()
    return layer


def _create_memory_layer_collection(features: list, name: str) -> QgsVectorLayer:
    first_geom_type = features[0]["geometry"]["type"]
    layer = QgsVectorLayer(f"{first_geom_type}?crs=EPSG:4326", name, "memory")
    provider = layer.dataProvider()

    # Define fields
    fields = QgsFields()
    fields.append(QgsField("asset_type", QVariant.String))
    fields.append(QgsField("display_path", QVariant.String))
    provider.addAttributes(fields)
    layer.updateFields()

    features_to_add = []
    for feature in features:
        asset = feature.get("assets", [{}])[0] or {}

        f = QgsFeature()
        geometry_json = json.dumps(feature["geometry"])
        geometry = QgsGeometry.fromWkt(json_to_wkt(geometry_json))
        f.setGeometry(geometry)

        # Set attributes
        f.setAttributes([
            asset.get("asset_type", ""),
            asset.get("display_path", "")
        ])
        features_to_add.append(f)

    provider.addFeatures(features_to_add)
    layer.updateExtents()
    return layer

def _set_feature_metadata(feature_or_layer, feature, asset):
    # Set metadata on QgsFeature or layer depending on type
    for k, v in asset.items():
        feature_or_layer.setCustomProperty(f"asset_{k}", v)
