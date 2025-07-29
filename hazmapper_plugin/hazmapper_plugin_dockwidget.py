from qgis.PyQt.QtWidgets import (
    QDockWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QWidget
)
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.core import QgsTask, QgsApplication, QgsMessageLog, Qgis
from qgis.PyQt.QtCore import QSettings
from .geoapi import (LoadGeoApiProjectTask, GeoApiTaskState, GeoApiStep,
                     create_or_replace_main_group, add_basemap_layers, add_features_layers)
from .components.map_status import MapStatus

from typing import Dict, Any, List, Optional, Union
import traceback


class HazmapperPluginDockWidget(QDockWidget):
    closingPlugin = pyqtSignal()

    def __init__(self, iface, plugin_dir, parent=None):
        super().__init__(parent)

        self.active_task = None

        self.iface = iface
        self.plugin_dir = plugin_dir

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

        # --- URL Input Row ---
        self.label_url = QLabel("URL:")
        self.label_url.setMinimumWidth(30)  # Fixed small width
        self.label_url.setToolTip(
            "Paste a public Hazmapper project URL here.\nExample:\nhttps://hazmapper.tacc.utexas.edu/hazmapper/project-public/a1e0eb3a-8db7-4b2a-8412-80213841570b"
        )

        self.input_url = QLineEdit()
        self.input_url.setPlaceholderText("Enter Hazmapper URL...")

        self.button_refresh = QPushButton("Load")
        self.button_refresh.setToolTip("Fetch data and layers from the Hazmapper project URL")

        self.last_url = None

        # URL row layout
        url_row = QHBoxLayout()
        url_row.setSpacing(4)  # Tighter spacing
        url_row.addWidget(self.label_url)
        url_row.addWidget(self.input_url, 1)  # Give input most space
        url_row.addWidget(self.button_refresh)

        layout.addLayout(url_row)

        # React to changes in input
        self.input_url.textChanged.connect(self.update_button_state)
        self.input_url.returnPressed.connect(self.button_refresh.click)

        # --- Map Status Component (includes status + all metadata) ---
        self.map_status = MapStatus()
        layout.addWidget(self.map_status)

        # --- Connect Logic ---
        self.button_refresh.clicked.connect(self.handle_refresh)

        # Update from stored settings
        saved_url = QSettings().value("HazmapperPlugin/last_project_url", "")
        if saved_url:
            self.input_url.setText(saved_url)
            self.last_url = saved_url
            self.update_button_state()

    def update_button_state(self):
        url = self.input_url.text().strip()

        # Check if it's a public Hazmapper URL
        if not url or "/project-public/" not in url:
            self.button_refresh.setEnabled(False)
            self.map_status.set_invalid_url()
            return

        # Enable button
        self.button_refresh.setEnabled(True)

        # Update button label
        if url == self.last_url:
            self.button_refresh.setText("Reload")
        else:
            self.button_refresh.setText("Load")
            self.map_status.set_ready()

    def update_status(self, geoapi_state, message):
        if geoapi_state == GeoApiTaskState.RUNNING:
            self.map_status.set_running()
            self.button_refresh.setEnabled(False)
        elif geoapi_state == GeoApiTaskState.DONE:
            self.map_status.set_success("Hazmapper map loaded successfully.")
            self.button_refresh.setEnabled(True)
        elif geoapi_state == GeoApiTaskState.FAILED:
            self.map_status.set_error(message)
            self.button_refresh.setEnabled(True)
        else:
            self.map_status.set_error("Unknown state")
            self.button_refresh.setEnabled(True)

    def on_progress_data(self, geoapi_step: GeoApiStep,
                         result: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]):
        try:
            QgsMessageLog.logMessage(f"Processing: {str(geoapi_step)}", "Hazmapper", Qgis.Info)

            if geoapi_step == GeoApiStep.PROJECT:
                # Update all project metadata at once
                self.map_status.update_project_data(
                    name=result.get("name", "–"),
                    description=result.get("description", "–"),
                    url=self.last_url
                )

                # TODO should refactor this as assuming PROJECT is first thing
                self.main_group = create_or_replace_main_group(
                    project_name=result.get("name", "Unnamed"),
                    project_uuid=result.get("uuid", "unknown")
                )
            elif geoapi_step == GeoApiStep.BASEMAP_LAYERS:
                if self.main_group:
                    add_basemap_layers(self.main_group, result)
            elif geoapi_step == GeoApiStep.FEATURES:
                if self.main_group:
                    add_features_layers(self.main_group, result)
        except Exception as e:
            QgsMessageLog.logMessage(traceback.format_exc(), "Hazmapper", Qgis.Warning)
            self.update_status(GeoApiTaskState.FAILED, f"Unknown processing error during processing of {geoapi_step}")

    def on_done(self):
        """Callback triggered when the GeoAPI task finishes successfully."""
        self.update_status(GeoApiTaskState.DONE, "Hazmapper map loaded successfully.")
        self.iface.messageBar().pushMessage("Hazmapper", "Hazmapper map loaded successfully.", level=Qgis.Info)

    def handle_refresh(self):
        try:
            # url is ready for parsing and validated in `update_button_state`
            url = self.input_url.text().strip()
            QgsMessageLog.logMessage(f"Loading map project: {url}", "Hazmapper", Qgis.Info)
            try:
                uuid = url.split("/project-public/")[1].split("/")[0]
            except IndexError:
                QgsMessageLog.logMessage("Error parsing url", "Hazmapper", Qgis.Critical)
                self.update_status(GeoApiTaskState.FAILED, "Invalid project URL format.")
                return

            QSettings().setValue("HazmapperPlugin/last_project_url", url)
            self.last_url = url

            QgsMessageLog.logMessage(f"Starting task to load map project: {url}, uuid:{uuid}", "Hazmapper", Qgis.Info)

            # Kick off async task to get project
            self.active_task = LoadGeoApiProjectTask(uuid,
                                                     on_finished=self.on_done,
                                                     update_status=self.update_status,
                                                     on_progress_data=self.on_progress_data)
            added = QgsApplication.taskManager().addTask(self.active_task)
            QgsMessageLog.logMessage(f"Task added #{added}", "Hazmapper", Qgis.Info)
        except Exception:
            QgsMessageLog.logMessage(traceback.format_exc(), "Hazmapper", Qgis.Critical)
            self.update_status(GeoApiTaskState.FAILED, "Error starting task")

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()