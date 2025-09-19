from typing import Optional, Dict, List, Any

from qgis.core import (
    QgsTask,
    QgsMessageLog,
    Qgis,
)
from qgis.PyQt.QtCore import pyqtSignal

from urllib import request
import json
import traceback

from .utils.user import get_or_create_guest_uuid


class GeoApiTaskState:
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class GeoApiStep:
    PROJECT = "project"
    BASEMAP_LAYERS = "basemap_layers"
    FEATURES = "features"


class LoadGeoApiProjectTask(QgsTask):
    progress_data = pyqtSignal(object, object)  # step, result
    status_update = pyqtSignal(object, str)  # state, message
    task_done = pyqtSignal(bool, str)  # success, errorMessage

    def __init__(self, uuid, base_url):
        super().__init__("LoadGeoApiProjectTask", QgsTask.CanCancel)
        self.base_url = base_url
        self.uuid = uuid
        self.project_id = None
        self.error = None

    def _request_data_from_backend(
        self, endpoint, user_description
    ) -> Optional[List[Dict[str, Any]]]:
        self.status_update.emit(
            GeoApiTaskState.RUNNING, f"Fetching {user_description}..."
        )

        QgsMessageLog.logMessage(f"Fetching {user_description}", "Hazmapper", Qgis.Info)

        full_url = f"{self.base_url}{endpoint}"

        headers = {
            "X-Geoapi-Application": "QGIS",
            "X-Geoapi-IsPublicView": "true",  # Plugin only supports public maps
            "X-Guest-Uuid": get_or_create_guest_uuid(),
        }

        # TODO: use QgsNetworkAccessManager instead of urllib; receiving compressed json is
        #  missing right now in this implementation
        #  See https://github.com/TACC/hazmapper-qgis-plugin/issues/6

        # Create request with headers used by hazmapper backend for metrics
        req = request.Request(full_url, headers=headers)

        try:
            with request.urlopen(req) as response:
                QgsMessageLog.logMessage(
                    f"Received {user_description}", "Hazmapper", Qgis.Info
                )

                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                result = json.loads(response.read().decode())
                QgsMessageLog.logMessage(
                    f"Read received {user_description}", "Hazmapper", Qgis.Info
                )
                return result
        except Exception as e:
            self.error = f"Fetching {user_description} failed: {str(e)}"
            QgsMessageLog.logMessage(traceback.format_exc(), "Hazmapper", Qgis.Warning)
            return None

    def run(self):
        QgsMessageLog.logMessage(
            f"Task to load map project started: uuid:{self.uuid}",
            "Hazmapper",
            Qgis.Info,
        )

        projects = self._request_data_from_backend(
            endpoint=f"/?uuid={self.uuid}", user_description="project metadata"
        )
        if not projects:
            return False
        else:
            project = projects[0]
            self.progress_data.emit(GeoApiStep.PROJECT, project)
            self.project_id = project.get("id")

        # TODO Get DS info (link to DS project, and PRJ-124 number and project description
        # uuid for making this call is derived from project-uuid in project.system_name
        # https://www.designsafe-ci.org/api/projects/v2/159846449346309655-242ac119-0001-012/
        # See https://github.com/TACC/hazmapper-qgis-plugin/issues/8

        basemap_layers = self._request_data_from_backend(
            endpoint=f"/{self.project_id}/tile-servers/",
            user_description="map data (basemap/tile layers)",
        )
        if not basemap_layers:
            return False
        else:
            self.progress_data.emit(GeoApiStep.BASEMAP_LAYERS, basemap_layers)

        features = self._request_data_from_backend(
            endpoint=f"/{self.project_id}/features/?assetType=image,video,"
            f"point_cloud,streetview,questionnaire,no_asset_vector",
            user_description="map data (features)",
        )
        if not features:
            return False
        else:
            self.progress_data.emit(GeoApiStep.FEATURES, features)

        QgsMessageLog.logMessage(
            f"Fetch tasking done: {self.uuid}", "Hazmapper", Qgis.Info
        )
        return True

    def finished(self, success):
        QgsMessageLog.logMessage(
            f"Finished task to fetch data (uuid={self.uuid}), called with success={success}",
            "Hazmapper",
            Qgis.Info,
        )
        if success:
            QgsMessageLog.logMessage(
                f"Finished fetching data (uuid={self.uuid})", "Hazmapper", Qgis.Info
            )
            self.task_done.emit(True, "Finished fetching data")
        else:
            QgsMessageLog.logMessage(
                f"Finished fetching data (uuid={self.uuid}), error: {self.error}",
                "Hazmapper",
                Qgis.Critical,
            )
            self.task_done.emit(False, self.error)

    def cancel(self):
        QgsMessageLog.logMessage("Task was cancelled", "Hazmapper", Qgis.Warning)
        return True
