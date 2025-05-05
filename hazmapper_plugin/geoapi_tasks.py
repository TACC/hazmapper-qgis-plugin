from qgis.core import QgsTask, QgsApplication, QgsMessageLog, Qgis
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

    def run(self):
        try:
            QgsMessageLog.logMessage(f"Task to load map project started: uuid:{self.uuid}", "Hazmapper", Qgis.Info)

            self.update_status(GeoApiTaskState.RUNNING, "Fetching project metadata...")

            # TODO: yse QgsNetworkAccessManager instead of urllib
            project_url = f"{self.base_url}/?uuid={self.uuid}"
            with urllib.request.urlopen(project_url) as response:
                if response.status != 200:
                    self.error = f"Server responded with status {response.status}"
                    return False

                raw = response.read().decode()
                data = json.loads(raw)
                self.project_id = data[0].get("project_id")
                self.on_progress_data(GeoApiStep.PROJECT, data[0])

        except urllib.error.URLError as e:
            self.error = f"Fetching project metadata. Network error: {e.reason}"
            return False
        except Exception as e:
            QgsMessageLog.logMessage(traceback.format_exc(), "Hazmapper", Qgis.Warning)
            self.error = f"Fetching project metadata. Unexpected error: {str(e)}"
            return False

        QgsMessageLog.logMessage(f"Task done: {self.uuid}", "Hazmapper", Qgis.Info)
        return True


    def finished(self, success):
        QgsMessageLog.logMessage(f"Finished() called with success={success}", "Hazmapper", Qgis.Info)
        if success:
            QgsMessageLog.logMessage(f"Finished importing {self.uuid}", "Hazmapper", Qgis.Info)
            self.update_status(GeoApiTaskState.DONE, "Finished fetching project.")
        else:
            QgsMessageLog.logMessage(self.error, "Hazmapper", Qgis.Critical)

    def cancel(self):
        QgsMessageLog.logMessage("Task was cancelled", "Hazmapper", Qgis.Warning)
        return True
