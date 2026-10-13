from qgis.PyQt.QtWidgets import (
    QFrame,
    QLabel,
    QDockWidget,
    QScrollArea,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from qgis.PyQt.QtGui import QColor, QIcon
from qgis.gui import QgsHighlight, QgsMapCanvas
from qgis.PyQt.QtCore import Qt, pyqtSignal, QTimer
from qgis.core import (
    QgsApplication,
    QgsMessageLog,
    Qgis,
    QgsNetworkAccessManager,
    QgsProject,
    QgsVectorLayer,
)

from .hazmapper_fetch_task import LoadGeoApiProjectTask, GeoApiTaskState, GeoApiStep
from .hazmapper_layers import (
    add_basemap_layers,
    add_features_layers,
    create_main_group,
    remove_previous_main_group,
    set_layer_source,
    set_map_attribution,
)
from .hazmapper_icons import plugin_icon_path
from .utils.environment import PRODUCTION_GEOAPI_URL, geoapi_url_for_map
from .utils.qgis import zoom_to_group
from .components.feature_info import FeatureInfo
from .components.map_status import MapStatus
from .feature_picker import FeaturePickTool
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
                    Qgis.Warning,
                )
        except Exception as e:
            QgsMessageLog.logMessage(
                f"[Network] Failed to log request: {e}", "Hazmapper", Qgis.Warning
            )

    QgsNetworkAccessManager.instance().finished.connect(log_request)


# Log all network calls for debugging
# _setup_network_logger()


class _VerticalScrollArea(QScrollArea):
    """
    Scroll area for the dock's content: scrolls up and down only, and asks for at least
    its content's width so nothing is cut off at the side.
    """

    def _scrollbar_width(self) -> int:
        return self.verticalScrollBar().sizeHint().width()

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        if self.widget() is not None:
            content = self.widget().minimumSizeHint()
            hint.setWidth(content.width() + self._scrollbar_width())
        return hint

    def sizeHint(self):
        hint = super().sizeHint()
        if self.widget() is not None:
            content = self.widget().sizeHint()
            hint.setWidth(content.width() + self._scrollbar_width())
            hint.setHeight(content.height())
        return hint


class HazmapperPluginDockWidget(QDockWidget):
    closingPlugin = pyqtSignal()

    def __init__(self, iface, plugin_dir, parent=None):
        super().__init__(parent)

        self._step_data = {}
        self.active_task = None
        self.iface = iface
        self.plugin_dir = plugin_dir
        self.current_project_url = None
        self.geoapi_url = PRODUCTION_GEOAPI_URL
        self.main_group = None

        self.setWindowTitle("Hazmapper")
        self.setWindowIcon(QIcon(plugin_icon_path("Hazmapper.svg")))

        # Restrict docking to right side only
        self.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)

        # Central widget, scrollable so a tall panel still fits a small screen
        main_widget = QWidget()
        scroll_area = _VerticalScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setWidget(main_widget)
        self.setWidget(scroll_area)

        # Layout containers
        layout = QVBoxLayout()
        layout.setSpacing(4)  # Reduce from default spacing
        layout.setContentsMargins(6, 6, 6, 6)  # Smaller margins
        main_widget.setLayout(layout)

        # Header
        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QIcon(plugin_icon_path("Hazmapper.svg")).pixmap(18, 18))
        title = QLabel("<b>Hazmapper</b>")
        title.setTextFormat(Qt.TextFormat.RichText)

        header.addWidget(logo)
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # --- Project Selector Component ---
        self.project_selector = ProjectSelector()
        self.project_selector.load_requested.connect(self.handle_load_request)
        layout.addWidget(self.project_selector)

        # --- Map Status Component (includes status + all metadata) ---
        self.map_status = MapStatus()
        layout.addWidget(self.map_status)

        # --- Selected Feature Component (pick a feature to see it and its links) ---
        self.feature_info = FeatureInfo()
        self.feature_info.pick_button.toggled.connect(self._on_pick_toggled)
        self._pick_tool = None
        self._highlight = None
        layout.addWidget(self.feature_info)

        layout.addStretch()

    def handle_load_request(self, url, remove_previous_map):
        """Handle load request from project selector"""
        try:
            try:
                uuid = url.split("/project-public/")[1].split("/")[0]
            except IndexError:
                QgsMessageLog.logMessage(
                    "Error parsing URL", "Hazmapper", Qgis.Critical
                )
                self.update_status(
                    GeoApiTaskState.FAILED, "Invalid project URL format."
                )
                return

            self.current_project_url = url
            # production, staging or dev, depending on where the map lives
            self.geoapi_url = geoapi_url_for_map(url)

            # Update UI state
            self.project_selector.set_loading_state(True)
            self.map_status.set_running("")

            if remove_previous_map:
                QgsMessageLog.logMessage("Remove previous map", "Hazmapper", Qgis.Info)
                remove_previous_main_group()

            QgsMessageLog.logMessage(
                f"Starting task to load map project: {url}, uuid: {uuid}, "
                f"geoapi: {self.geoapi_url}",
                "Hazmapper",
                Qgis.Info,
            )

            # Create async task to get map project data
            self.active_task = LoadGeoApiProjectTask(
                uuid, base_url=f"{self.geoapi_url}/projects"
            )
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
            self.map_status.set_running(message)
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

    def on_load_data(
        self,
        geoapi_step: GeoApiStep,
        result: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]],
    ):
        # Log incoming data
        QgsMessageLog.logMessage(f"Received {geoapi_step} data", "Hazmapper", Qgis.Info)

        # Store result
        self._step_data[geoapi_step] = result

        # Check if we have all required steps
        required = {GeoApiStep.PROJECT, GeoApiStep.BASEMAP_LAYERS, GeoApiStep.FEATURES}
        if required.issubset(self._step_data.keys()):
            # Process once everything is ready
            QgsMessageLog.logMessage(
                "All data received; processing", "Hazmapper", Qgis.Info
            )
            self._process_all_steps()

    def _process_all_steps(self):
        """Process project, basemaps, and features once all steps have arrived."""
        project = QgsProject.instance()
        canvas = self.iface.mapCanvas()

        canvas.freeze(True)  # or canvas.setRenderFlag(False)
        project.blockSignals(True)

        try:
            project_data = self._step_data.get(GeoApiStep.PROJECT, {})
            basemap_data = self._step_data.get(GeoApiStep.BASEMAP_LAYERS, [])
            feature_data = self._step_data.get(GeoApiStep.FEATURES, [])

            # Clear step data for next load
            self._step_data.clear()

            # Update project metadata + create group
            self.map_status.update_project_data(
                name=project_data.get("name", "–"),
                description=project_data.get("description", "–"),
                url=self.current_project_url,
            )

            self.main_group = create_main_group(
                project_name=project_data.get("name", "Unnamed"),
                project_uuid=project_data.get("uuid", "unknown"),
            )

            QgsMessageLog.logMessage("Created main group", "Hazmapper", Qgis.Info)

            # Process layers directly (with batching for performance)
            self.map_status.set_running("Adding basemap layers...")
            add_basemap_layers(
                self.main_group, basemap_data, self._update_progress, self.geoapi_url
            )

            self.map_status.set_running("Adding feature layers...")
            add_features_layers(
                self.main_group,
                feature_data,
                self._update_progress,
                self._on_features_complete,
            )
            set_map_attribution(self.main_group, self.current_project_url)
            set_layer_source(self.main_group, self.current_project_url, self.geoapi_url)
            self._clear_picked_feature()
        finally:
            project.blockSignals(False)
            canvas.freeze(False)
            canvas.refresh()

    # ---- Selected feature -------------------------------------------------

    def _feature_layers(self) -> list:
        """Visible feature layers of the loaded map, topmost first."""
        try:
            nodes = self.main_group.findLayers() if self.main_group is not None else []
            return [
                node.layer()
                for node in nodes
                if node.isVisible() and isinstance(node.layer(), QgsVectorLayer)
            ]
        except RuntimeError:
            # the group was removed from the layer tree by hand
            return []

    def _on_pick_toggled(self, checked: bool):
        canvas = self.iface.mapCanvas()
        if checked:
            if self._pick_tool is None:
                self._pick_tool = FeaturePickTool(canvas, self._feature_layers)
                self._pick_tool.setButton(self.feature_info.pick_button)
                self._pick_tool.picked.connect(self._on_feature_picked)
                self._pick_tool.missed.connect(self._clear_picked_feature)
            canvas.setMapTool(self._pick_tool)
        elif self._pick_tool is not None:
            canvas.unsetMapTool(self._pick_tool)

    def _on_feature_picked(self, layer, feature):
        self._clear_highlight()
        self.feature_info.show_feature(layer, feature)

        # Mark it on the map without touching the user's own QGIS selection
        canvas = self.iface.mapCanvas()
        if isinstance(canvas, QgsMapCanvas):
            self._highlight = QgsHighlight(canvas, feature.geometry(), layer)
            self._highlight.setColor(QColor(255, 80, 0))
            self._highlight.setFillColor(QColor(255, 80, 0, 60))
            self._highlight.setWidth(3)
            self._highlight.setBuffer(1.0)
            self._highlight.show()

    def _clear_picked_feature(self):
        """Empty the panel and remove the mark on the map (e.g. after clicking nothing)."""
        self._clear_highlight()
        self.feature_info.clear()

    def _clear_highlight(self):
        if self._highlight is not None:
            try:
                self._highlight.hide()
                scene = self._highlight.scene()
                if scene is not None:
                    scene.removeItem(self._highlight)
            except RuntimeError:
                pass  # already deleted along with the canvas
            self._highlight = None

    def _update_progress(self, message: str, progress: int):
        """Update progress bar and status message."""
        self.map_status.set_running_with_progress(message, progress)

    def _on_features_complete(self):
        """Called when all feature layers are loaded."""
        self.map_status.set_success("Hazmapper map loaded successfully.")
        QTimer.singleShot(0, lambda: self._zoom_to_main_group())

    def _zoom_to_main_group(self):
        """Zoom to combined extent of feature layers inside main group (i.e. current map data)"""
        if self.main_group is None:
            return  # nothing to zoom to

        zoom_to_group(self.main_group)

    def on_load_geoapi_project_done(self, status: bool, message: str):
        """Callback triggered when the GeoAPI task finishes successfully."""
        if status:
            self.update_status(
                GeoApiTaskState.DONE, "Hazmapper map loaded successfully."
            )
            self.iface.messageBar().pushMessage(
                "Hazmapper", "Hazmapper map loaded successfully.", level=Qgis.Info
            )
        else:
            self.update_status(GeoApiTaskState.FAILED, message)

    def closeEvent(self, event):
        # Cancel any running tasks
        if self.active_task:
            self.active_task.cancel()

        # Stop picking and remove the mark on the map
        self.feature_info.pick_button.setChecked(False)
        self._clear_highlight()

        self.closingPlugin.emit()
        event.accept()
