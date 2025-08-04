from qgis.PyQt.QtWidgets import (
    QDockWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QWidget
)
from qgis.PyQt.QtCore import Qt, pyqtSignal, QTimer
from qgis.core import (QgsApplication, QgsMessageLog, Qgis, QgsNetworkAccessManager,
                       QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsProject)

from .hazmapper_fetch_task import LoadGeoApiProjectTask, GeoApiTaskState, GeoApiStep
from .hazmapper_layers import (
    add_basemap_layers,
    add_features_layers,
    create_main_group,
    remove_previous_main_group
)
from .components.map_status import MapStatus
from .components.project_selector import ProjectSelector

from typing import Dict, Any, List, Optional, Union
import traceback


def _setup_network_logger():
    """Log network request errors (403, 404) to QGIS message log for debugging basemaps."""

    def log_request(reply):
        try:
            # QGIS 3.32+ returns QgsNetworkReplyContent
            if hasattr(reply, "request"):
                url = reply.request().url().toString()
            # Older QGIS returns QNetworkReply
            elif hasattr(reply, "url"):
                url = reply.url().toString()
            else:
                url = "<unknown>"

            error_code = reply.error()

            if error_code != 0:  # Only log failures
                QgsMessageLog.logMessage(
                    f"[Network] Tile request failed ({error_code}): {url}",
                    "Hazmapper",
                    Qgis.Warning
                )
        except Exception as e:
            QgsMessageLog.logMessage(f"[Network] Failed to log request: {e}", "Hazmapper", Qgis.Warning)

    QgsNetworkAccessManager.instance().finished.connect(log_request)

# Log all network calls for debugging
#_setup_network_logger()


class HazmapperPluginDockWidget(QDockWidget):
    closingPlugin = pyqtSignal()

    def __init__(self, iface, plugin_dir, parent=None):
        super().__init__(parent)

        self._step_data = {}
        self.active_task = None
        self.iface = iface
        self.plugin_dir = plugin_dir
        self.current_project_url = None
        self.main_group = None

        self.setWindowTitle("Hazmapper")

        # Restrict docking to right side only
        self.setAllowedAreas(Qt.RightDockWidgetArea)

        # Central widget
        main_widget = QWidget()
        self.setWidget(main_widget)

        # Layout containers
        layout = QVBoxLayout()
        layout.setSpacing(4)  # Reduce from default spacing
        layout.setContentsMargins(6, 6, 6, 6)  # Smaller margins
        main_widget.setLayout(layout)

        # --- Project Selector Component ---
        self.project_selector = ProjectSelector()
        self.project_selector.load_requested.connect(self.handle_load_request)
        layout.addWidget(self.project_selector)

        # --- Map Status Component (includes status + all metadata) ---
        self.map_status = MapStatus()
        layout.addWidget(self.map_status)

        layout.addStretch()

    def handle_load_request(self, url, remove_previous_map):
        """Handle load request from project selector"""
        try:
            try:
                uuid = url.split("/project-public/")[1].split("/")[0]
            except IndexError:
                QgsMessageLog.logMessage("Error parsing URL", "Hazmapper", Qgis.Critical)
                self.update_status(GeoApiTaskState.FAILED, "Invalid project URL format.")
                return

            self.current_project_url = url

            # Update UI state
            self.project_selector.set_loading_state(True)
            self.map_status.set_running()

            if remove_previous_map:
                QgsMessageLog.logMessage(f"Remove previous map", "Hazmapper",
                                         Qgis.Info)
                remove_previous_main_group()

            QgsMessageLog.logMessage(f"Starting task to load map project: {url}, uuid: {uuid}", "Hazmapper", Qgis.Info)

            # Create async task to get map project data
            self.active_task = LoadGeoApiProjectTask(uuid, base_url='https://hazmapper.tacc.utexas.edu/geoapi/projects')
            # Connect signals
            self.active_task.progress_data.connect(self.on_load_data)
            self.active_task.status_update.connect(self.update_status)
            self.active_task.task_done.connect(self.on_load_geoapi_project_done)

            added = QgsApplication.taskManager().addTask(self.active_task)
            QgsMessageLog.logMessage(f"Task added #{added}", "Hazmapper", Qgis.Info)

        except Exception:
            QgsMessageLog.logMessage(traceback.format_exc(), "Hazmapper", Qgis.Critical)
            self.update_status(GeoApiTaskState.FAILED, "Error starting task")

    def update_status(self, geoapi_state, message):
        """Update status display and UI state"""
        if geoapi_state == GeoApiTaskState.RUNNING:
            self.map_status.set_running()
            self.project_selector.set_loading_state(True)
        elif geoapi_state == GeoApiTaskState.DONE:
            self.map_status.set_success("Hazmapper map loaded successfully.")
            self.project_selector.set_loading_state(False)
        elif geoapi_state == GeoApiTaskState.FAILED:
            self.map_status.set_error(message)
            self.project_selector.set_loading_state(False)
        else:
            self.map_status.set_error("Unknown state")
            self.project_selector.set_loading_state(False)

    def on_load_data(self, geoapi_step: GeoApiStep,
                     result: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]):
        # Log incoming data
        QgsMessageLog.logMessage(f"Received {geoapi_step} data", "Hazmapper", Qgis.Info)

        # Store result
        self._step_data[geoapi_step] = result

        # Check if we have all required steps
        required = {GeoApiStep.PROJECT, GeoApiStep.BASEMAP_LAYERS, GeoApiStep.FEATURES}
        if required.issubset(self._step_data.keys()):
            # Process once everything is ready
            QgsMessageLog.logMessage(f"All data received; processing", "Hazmapper", Qgis.Info)
            self._process_all_steps()

    def _process_all_steps(self):
        """Process project, basemaps, and features once all steps have arrived."""
        project_data = self._step_data.get(GeoApiStep.PROJECT, {})
        basemap_data = self._step_data.get(GeoApiStep.BASEMAP_LAYERS, [])
        feature_data = self._step_data.get(GeoApiStep.FEATURES, [])

        # Clear step data for next load
        self._step_data.clear()

        # Update project metadata + create group
        def step1():
            self.map_status.update_project_data(
                name=project_data.get("name", "–"),
                description=project_data.get("description", "–"),
                url=self.current_project_url
            )

            self.main_group = create_main_group(
                project_name=project_data.get("name", "Unnamed"),
                project_uuid=project_data.get("uuid", "unknown"),
            )

            QgsMessageLog.logMessage("Created main group", "Hazmapper", Qgis.Info)
            QTimer.singleShot(0, step2)

        # Step 2: Add basemap layers
        def step2():
            add_basemap_layers(self.main_group, basemap_data)
            QgsMessageLog.logMessage("Added basemap layers", "Hazmapper", Qgis.Info)
            QTimer.singleShot(0, step3)

        # Step 3: Add feature layers
        def step3():
            add_features_layers(self.main_group, feature_data)
            QgsMessageLog.logMessage("Added feature layers", "Hazmapper", Qgis.Info)

            # Zoom to features (ignore basemap layers with global extents)
            self._zoom_to_main_group()

        # Start chain of processing steps
        QTimer.singleShot(0, step1)

    def _zoom_to_main_group(self):
        """Zoom to combined extent of feature layers inside main group (i.e. current map data)"""
        extent = None

        for child in self.main_group.children():
            if child.nodeType() == child.NodeLayer:
                layer = child.layer()
                if layer and layer.type() == layer.VectorLayer:
                    # Merge extents
                    if extent is None:
                        extent = layer.extent()
                    else:
                        extent.combineExtentWith(layer.extent())

        if extent and not extent.isEmpty():
            canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()

            # Assume Hazmapper features are EPSG:4326 (set at creation)
            layer_crs = QgsCoordinateReferenceSystem(4326)

            if layer_crs != canvas_crs:
                xform = QgsCoordinateTransform(layer_crs, canvas_crs, QgsProject.instance())
                extent = xform.transformBoundingBox(extent)

            self.iface.mapCanvas().setExtent(extent)
            self.iface.mapCanvas().refresh()
            QgsMessageLog.logMessage("Zoomed to Hazmapper features", "Hazmapper", Qgis.Info)
        else:
            QgsMessageLog.logMessage("No Hazmapper features to zoom to", "Hazmapper", Qgis.Info)

    def on_load_geoapi_project_done(self, status: bool, message: str):
        """Callback triggered when the GeoAPI task finishes successfully."""
        if status:
            self.update_status(GeoApiTaskState.DONE, "Hazmapper map loaded successfully.")
            self.iface.messageBar().pushMessage("Hazmapper", "Hazmapper map loaded successfully.", level=Qgis.Info)
        else:
            self.update_status(GeoApiTaskState.FAILED, message)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()