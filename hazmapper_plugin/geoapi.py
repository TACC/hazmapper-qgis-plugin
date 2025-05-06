from typing import Optional, Union, Dict, List, Any

from qgis.core import (QgsTask, QgsApplication, QgsMessageLog, Qgis,
                       QgsProject, QgsLayerTreeGroup, QgsRasterLayer)
import urllib.request
import urllib.error
import json
import traceback
import uuid as py_uuid


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
        # TODO: yse QgsNetworkAccessManager instead of urllib

        self.update_status(GeoApiTaskState.RUNNING, f"Fetching {user_description}...")

        if base is None:
            base = self.base_url
        full_url = f"{base}{endpoint}"

        # TODO: add header to signify QGIS and guest user (x-geoapi-application, x-geoapi-ispublicview, x-guest-uuid)
        try:
            with urllib.request.urlopen(full_url) as response:
                if response.status != 200:
                    self.error = f"Server responded with status {response.status}"
                    return None

                raw = response.read().decode()
                data = json.loads(raw)
                return data

        except urllib.error.URLError as e:
            QgsMessageLog.logMessage(traceback.format_exc(), "Hazmapper", Qgis.Warning)
            self.error = f"Fetching {user_description}. full_url:{full_url};  Network error: {e.reason}"
            return None
        except Exception as e:
            QgsMessageLog.logMessage(traceback.format_exc(), "Hazmapper", Qgis.Warning)
            self.error = f"Fetching {user_description}. full_url:{full_url}; Unexpected error: {str(e)}"
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
    import time; time.sleep(4)

    root = QgsProject.instance().layerTreeRoot()
    import time;   time.sleep(4)

    QgsMessageLog.logMessage(f"[Hazmapper] Removing existing main group2", "Hazmapper", Qgis.Info)

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

            if layer_type == "tms" or (layer_type == "arcgis" and "/tiles/" in url):
                # XYZ tile layer
                tile_url = url.rstrip("/") + "/tile/{z}/{y}/{x}"
                uri = f"type=xyz&url={tile_url}"
            elif layer_type == "arcgis":
                # Use native arcgisrest if not a tile service
                # TODO: untested
                uri = f"type=arcgisrest&url={url}"
            else:
                QgsMessageLog.logMessage(f"Skipping unsupported layer type: {layer_type}", "Hazmapper", Qgis.Warning)
                continue

            raster_layer = QgsRasterLayer(uri, name, "wms")
            if not raster_layer.isValid():
                QgsMessageLog.logMessage(f"Failed to load layer: {name}", "Hazmapper", Qgis.Warning)
                continue

            raster_layer.setOpacity(opacity)
            QgsProject.instance().addMapLayer(raster_layer, False)
            main_group.addLayer(raster_layer)

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error processing layer '{layer_data.get('name', 'unnamed')}': {str(e)}",
                "Hazmapper", Qgis.Critical
            )
