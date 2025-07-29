from qgis.PyQt.QtWidgets import (
    QDockWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QWidget, QGridLayout
)
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.core import QgsTask, QgsApplication, QgsMessageLog, Qgis
from qgis.PyQt.QtCore import QSettings, QDateTime
from .geoapi import (LoadGeoApiProjectTask, GeoApiTaskState, GeoApiStep,
                     create_or_replace_main_group, add_basemap_layers, add_features_layers)

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
        main_widget.setLayout(layout)

        # --- URL Input Row ---
        self.label_url = QLabel("Hazmapper Project URL:")
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
        url_row.addWidget(self.label_url)
        url_row.addWidget(self.input_url)
        url_row.addWidget(self.button_refresh)

        layout.addLayout(url_row)

        # React to changes in input
        self.input_url.textChanged.connect(self.update_button_state)
        self.input_url.returnPressed.connect(self.button_refresh.click)

        # --- Status Row ---
        self.label_status_icon = QLabel("🟢")
        self.label_status = QLabel("Ready")

        status_row = QHBoxLayout()
        status_row.addWidget(self.label_status_icon)
        status_row.addWidget(self.label_status)
        status_row.addStretch()

        layout.addLayout(status_row)

        # --- Metadata Table ---
        grid = QGridLayout()
        grid.setSpacing(6)

        self.label_name_title = QLabel("Name:")
        self.label_name = QLabel("–")

        self.label_description_title = QLabel("Description:")
        self.label_description = QLabel("–")

        self.label_map_link_title = QLabel("Map:")
        self.label_map_link = QLabel("–")
        self.label_map_link.setTextFormat(Qt.RichText)
        self.label_map_link.setOpenExternalLinks(True)

        self.label_last_refreshed_title = QLabel("Last Refreshed:")
        self.label_last_refreshed = QLabel("–")

        grid.addWidget(self.label_name_title, 0, 0)
        grid.addWidget(self.label_name, 0, 1)

        grid.addWidget(self.label_description_title, 1, 0)
        grid.addWidget(self.label_description, 1, 1)

        grid.addWidget(self.label_map_link_title, 2, 0)
        grid.addWidget(self.label_map_link, 2, 1)

        grid.addWidget(self.label_last_refreshed_title, 3, 0)
        grid.addWidget(self.label_last_refreshed, 3, 1)

        layout.addSpacing(10)
        layout.addLayout(grid)

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
            self.label_status_icon.setText("🔴")
            self.label_status.setText("Invalid URL — must be a public Hazmapper project.")
            return

        # Enable button
        self.button_refresh.setEnabled(True)

        # Update button label
        if url == self.last_url:
            self.button_refresh.setText("Reload")
        else:
            self.button_refresh.setText("Load")
            self.label_status_icon.setText("🟢")
            self.label_status.setText("Ready")

    def update_status(self, geoapi_state, message):
        self.label_status.setText(message)

        if geoapi_state == GeoApiTaskState.RUNNING:
            self.label_status_icon.setText("🔄")
            self.button_refresh.setEnabled(False)
        elif geoapi_state == GeoApiTaskState.DONE:
            self.label_status_icon.setText("✅")
            self.button_refresh.setEnabled(True)
        elif geoapi_state == GeoApiTaskState.FAILED:
            self.label_status_icon.setText("❌")
            self.button_refresh.setEnabled(True)
        else:
            self.label_status.setText("Unknown state")
            self.label_status_icon.setText("❌")
            self.button_refresh.setEnabled(True)

    def on_progress_data(self, geoapi_step: GeoApiStep,
                         result: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]):
        try:
            QgsMessageLog.logMessage(f"Processing: {str(geoapi_step)}", "Hazmapper", Qgis.Info)

            if geoapi_step == GeoApiStep.PROJECT:
                url = self.last_url
                self.label_name.setText(result.get("name", "–"))
                self.label_description.setText(result.get("description", "–"))
                self.label_map_link.setText(f'<a href="{url}">{url}</a>')
                self.label_last_refreshed.setText(QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm"))

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
