from typing import Optional, Union, Dict, List, Any

from qgis.core import (QgsTask, QgsApplication, QgsMessageLog, Qgis,
                       QgsProject, QgsLayerTreeGroup, QgsRasterLayer, QgsVectorLayer,
                       QgsFeature, QgsGeometry, QgsFillSymbol, QgsSimpleFillSymbolLayer,
                       QgsLineSymbol, QgsJsonUtils, QgsField, QgsFields, QgsSvgMarkerSymbolLayer,
                       QgsMarkerSymbol)
from PyQt5.QtCore import QVariant
from osgeo import ogr
from urllib import request, error
import json
import traceback
import uuid as py_uuid

from .user import get_or_create_guest_uuid


class GeoApiTaskState:
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class GeoApiStep:
    PROJECT = "project"
    BASEMAP_LAYERS = "basemap_layers"
    FEATURES = "features"


class LoadGeoApiProjectTask(QgsTask):
    def __init__(self, uuid, on_finished, update_status, on_progress_data):
        super().__init__(f"Load Hazmapper project uuid-{uuid} task-uuid-{py_uuid.uuid4()}")

        self.uuid = uuid
        self.base_url = 'https://hazmapper.tacc.utexas.edu/geoapi/projects'
        self.project_id = None
        self.on_finished = on_finished
        self.update_status = update_status
        self.on_progress_data = on_progress_data
        self.error = None

    def _request_data_from_backend(self, endpoint, user_description, base=None) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        self.update_status(GeoApiTaskState.RUNNING, f"Fetching {user_description}...")

        if base is None:
            base = self.base_url
        full_url = f"{base}{endpoint}"

        headers = {
            "X-Geoapi-Application": "QGIS",
            "X-Geoapi-IsPublicView": "true", # currently
            "X-Guest-Uuid": get_or_create_guest_uuid(),
        }

        # TODO: use QgsNetworkAccessManager instead of urllib


        # Create request with headers used by hazmapper backend for metrics
        req = request.Request(full_url, headers=headers)
        try:
            with request.urlopen(req) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                return json.loads(response.read().decode())
        except Exception as e:
            self.error = f"Fetching {user_description} failed: {str(e)}"
            QgsMessageLog.logMessage(traceback.format_exc(), "Hazmapper", Qgis.Warning)
            return None

    def run(self):
        QgsMessageLog.logMessage(f"Task to load map project started: uuid:{self.uuid}", "Hazmapper", Qgis.Info)

        projects = self._request_data_from_backend(endpoint=f"/?uuid={self.uuid}",
                                                   user_description="project metadata")
        if not projects:
            return False
        else:
            project = projects[0]
            self.on_progress_data(GeoApiStep.PROJECT, project)
            self.project_id = project.get("id")

        # TODO Get DS info (link to DS project, and PRJ-124 number and project description
        # uuid for making this call is derived from project-uuid in project.system_name
        # https://www.designsafe-ci.org/api/projects/v2/159846449346309655-242ac119-0001-012/

        basemap_layers = self._request_data_from_backend(endpoint=f"/{self.project_id}/tile-servers/",
                                                         user_description="map data (basemap/tile layers)")
        if not basemap_layers:
            return False
        else:
            self.on_progress_data(GeoApiStep.BASEMAP_LAYERS, basemap_layers)

        features = self._request_data_from_backend(endpoint=f"/{self.project_id}/features/?assetType=image,video,"
                                                            f"point_cloud,streetview,questionnaire,no_asset_vector",
                                                   user_description="map data (features")
        if not features:
            return False
        else:
            self.on_progress_data(GeoApiStep.FEATURES, features)

        QgsMessageLog.logMessage(f"Task done: {self.uuid}", "Hazmapper", Qgis.Info)
        return True


    def finished(self, success):
        QgsMessageLog.logMessage(f"Finished() called with success={success}", "Hazmapper", Qgis.Info)
        if success:
            QgsMessageLog.logMessage(f"Finished importing {self.uuid}", "Hazmapper", Qgis.Info)
            self.update_status(GeoApiTaskState.DONE, "Finished fetching project.")
        else:
            self.update_status(GeoApiTaskState.FAILED, f"Failed fetching project: {self.error}")
            QgsMessageLog.logMessage(self.error, "Hazmapper", Qgis.Critical)

    def cancel(self):
        # TODO
        QgsMessageLog.logMessage("Task was cancelled", "Hazmapper", Qgis.Warning)
        return True


def create_or_replace_main_group(project_name: str, project_uuid: str) -> QgsLayerTreeGroup:
    QgsMessageLog.logMessage(f"[Hazmapper] Removing existing main group", "Hazmapper", Qgis.Info)
    root = QgsProject.instance().layerTreeRoot()

    try:
        # Look for and remove any existing group with this UUID
        for child in root.children():
            if isinstance(child, QgsLayerTreeGroup) and child.customProperty("hazmapper_uuid") == project_uuid:
                QgsMessageLog.logMessage(f"[Hazmapper] Removing existing group: {child.name()}", "Hazmapper", Qgis.Info)

                # Remove all layers inside before removing the group
                for sublayer in child.findLayers():
                    QgsMessageLog.logMessage(f"[Hazmapper] Removing existing group2: {child.name()}", "Hazmapper", Qgis.Info)
                    QgsProject.instance().removeMapLayer(sublayer.layerId())
                QgsMessageLog.logMessage(f"[Hazmapper] Removing existing group3: {child.name()}", "Hazmapper", Qgis.Info)
                root.removeChildNode(child)
                break

        # Create new group
        group_name = f"{project_name} ({project_uuid[:8]})"
        group = QgsLayerTreeGroup(group_name)
        group.setCustomProperty("hazmapper_uuid", project_uuid)

        root.insertChildNode(0, group)
        QgsMessageLog.logMessage(f"[Hazmapper] Created new group: {group_name}", "Hazmapper", Qgis.Info)
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
        _apply_point_cloud_style(vl)
        QgsProject.instance().addMapLayer(vl, False)
        main_group.insertLayer(0, vl)

    # Create a single image layer
    if image_features:
        vl = _create_memory_layer_collection(image_features, "Images")
        _apply_camera_icon_style(vl)
        QgsProject.instance().addMapLayer(vl, False)
        main_group.insertLayer(0, vl)

    # Create a single streetview layer
    if streetview_features:
        vl = _create_memory_layer_collection(streetview_features, "StreetView")
        _apply_streetview_style(vl)
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


def _apply_default_style(layer):
    symbol = QgsFillSymbol.createSimple({
        'color': '#3388ff',
        'outline_color': '#3388ff',
        'outline_width': '0.66',  # 3px-ish
        'style': 'solid',
        'outline_style': 'solid',
        'fill_opacity': '0.2',
    })
    layer.renderer().setSymbol(symbol)
    layer.triggerRepaint()


def _apply_camera_icon_style(layer):
    # TODO refactor to make portable
    svg_path = "/Applications/QGIS.app/Contents/Resources/svg/gpsicons/camera.svg"
    svg_layer = QgsSvgMarkerSymbolLayer(svg_path, 6.0, 0)

    symbol = QgsMarkerSymbol()
    symbol.changeSymbolLayer(0, svg_layer)
    layer.renderer().setSymbol(symbol)
    layer.triggerRepaint()


def _apply_point_cloud_style(layer):
    symbol = QgsFillSymbol.createSimple({
        'style': 'no',
        'color': '0,0,0,0',  # transparent fill
        'outline_color': '#3388ff',
        'outline_width': '0.66'
    })
    layer.renderer().setSymbol(symbol)
    layer.triggerRepaint()


def _apply_streetview_style(layer, style_name='default'):
    styles = {
        'default': {'color': '#22C7FF', 'width': '2.5', 'opacity': '0.6'},
        'select': {'color': '#22C7FF', 'width': '3', 'opacity': '1.0'},
        'hover': {'color': '#22C7FF', 'width': '3', 'opacity': '0.8'},
    }
    style = styles.get(style_name, styles['default'])

    symbol = QgsLineSymbol.createSimple({
        'color': style['color'],
        'width': style['width'],
        'line_style': 'solid',
    })
    symbol.setOpacity(float(style['opacity']))
    layer.renderer().setSymbol(symbol)
    layer.triggerRepaint()
