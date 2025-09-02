from qgis.PyQt.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QVBoxLayout,
    QHBoxLayout,
    QCheckBox,
)
from qgis.PyQt.QtCore import pyqtSignal, QSettings
from ..utils.maps_of_published_projects import predefined_published_maps


class ProjectSelector(QWidget):
    # Signals
    load_requested = pyqtSignal(str, bool)  # url, remove_previous_map

    def __init__(self, parent=None):
        super().__init__(parent)

        self.last_loaded_url = None

        # Main layout
        layout = QVBoxLayout()
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        # --- Project Selection Row ---
        selection_layout = QVBoxLayout()
        selection_layout.setSpacing(2)

        # Checkbox to toggle between dropdown and manual entry
        self.use_predefined = QCheckBox("Use map from published project")
        self.use_predefined.setChecked(True)
        self.use_predefined.toggled.connect(self.toggle_input_mode)
        selection_layout.addWidget(self.use_predefined)

        # Dropdown for predefined projects
        self.project_dropdown = QComboBox()
        self.project_dropdown.addItem("Select a project...", "")  # Default item

        # Add predefined projects
        for project in predefined_published_maps:
            display_name = (
                f"{project['designSafeProjectName']} ({project['designSafeProjectId']})"
            )
            self.project_dropdown.addItem(display_name, project["url"])

        self.project_dropdown.currentTextChanged.connect(self.on_selection_changed)
        selection_layout.addWidget(self.project_dropdown)

        # Manual URL input (initially hidden)
        url_row = QHBoxLayout()
        url_row.setSpacing(4)

        self.label_url = QLabel("URL:")
        self.label_url.setMinimumWidth(30)
        self.label_url.setToolTip(
            "Paste a public Hazmapper project URL here.\n"
            "Example:\n"
            "https://hazmapper.tacc.utexas.edu/hazmapper/project-public/a1e0eb3a-8db7-4b2a-8412-80213841570b"  # noqa: E501
        )

        self.input_url = QLineEdit()
        self.input_url.setPlaceholderText("Enter Hazmapper URL...")
        self.input_url.textChanged.connect(self.on_selection_changed)
        self.input_url.returnPressed.connect(self.load_project)

        url_row.addWidget(self.label_url)
        url_row.addWidget(self.input_url, 1)

        self.url_widget = QWidget()
        self.url_widget.setLayout(url_row)
        self.url_widget.setVisible(False)  # Initially hidden
        selection_layout.addWidget(self.url_widget)

        layout.addLayout(selection_layout)

        # --- Options Row ---
        options_layout = QHBoxLayout()
        options_layout.setSpacing(8)

        # Replace previous checkbox
        self.replace_previous = QCheckBox("Replace previous map")
        self.replace_previous.setChecked(True)
        self.replace_previous.setToolTip(
            "Remove the previous Hazmapper project before loading the new one"
        )
        options_layout.addWidget(self.replace_previous)

        options_layout.addStretch()
        layout.addLayout(options_layout)

        # --- Load Button ---
        self.button_load = QPushButton("Load")
        self.button_load.setToolTip("Fetch data and layers from the Hazmapper project")
        self.button_load.clicked.connect(self.load_project)
        self.button_load.setEnabled(False)
        layout.addWidget(self.button_load)

        # Load saved settings
        self._load_settings()

    def toggle_input_mode(self):
        """Toggle between dropdown and manual URL input"""
        use_dropdown = self.use_predefined.isChecked()
        self.project_dropdown.setVisible(use_dropdown)
        self.url_widget.setVisible(not use_dropdown)
        self.on_selection_changed()

    def on_selection_changed(self):
        """Handle selection change in either dropdown or text input"""
        url = self.get_current_url()

        # Check if it's a valid Hazmapper URL
        is_valid = url and "/project-public/" in url
        self.button_load.setEnabled(is_valid)

        if is_valid:
            # Update button text based on whether this URL was last loaded
            if url == self.last_loaded_url:
                self.button_load.setText("Reload")
            else:
                self.button_load.setText("Load")
        else:
            self.button_load.setText("Load")

    def get_current_url(self):
        """Get the currently selected/entered URL"""
        if self.use_predefined.isChecked():
            return self.project_dropdown.currentData() or ""
        else:
            return self.input_url.text().strip()

    def is_valid_url(self):
        """Check if current URL is valid"""
        url = self.get_current_url()
        return bool(url and "/project-public/" in url)

    def load_project(self):
        """Emit signal to load the current project"""
        if not self.is_valid_url():
            return

        url = self.get_current_url()
        replace = self.replace_previous.isChecked()

        # Update last loaded URL and button text
        self.last_loaded_url = url
        self.button_load.setText("Reload")

        # Save settings
        self._save_settings()

        # Emit signal
        self.load_requested.emit(url, replace)

    def set_loading_state(self, is_loading):
        """Enable/disable controls during loading"""
        self.button_load.setEnabled(not is_loading)
        self.use_predefined.setEnabled(not is_loading)
        self.project_dropdown.setEnabled(not is_loading)
        self.input_url.setEnabled(not is_loading)

    def _save_settings(self):
        """Save current settings to QSettings"""
        settings = QSettings()
        settings.setValue(
            "HazmapperPlugin/use_predefined", self.use_predefined.isChecked()
        )
        settings.setValue("HazmapperPlugin/last_project_url", self.get_current_url())
        settings.setValue(
            "HazmapperPlugin/replace_previous", self.replace_previous.isChecked()
        )

        if self.use_predefined.isChecked():
            settings.setValue(
                "HazmapperPlugin/dropdown_index", self.project_dropdown.currentIndex()
            )
        else:
            settings.setValue("HazmapperPlugin/manual_url", self.input_url.text())

    def _load_settings(self):
        """Load settings from QSettings"""
        settings = QSettings()

        # Restore mode (predefined vs manual)
        use_predefined = settings.value(
            "HazmapperPlugin/use_predefined", True, type=bool
        )
        self.use_predefined.setChecked(use_predefined)

        # Restore replace option
        replace = settings.value("HazmapperPlugin/replace_previous", True, type=bool)
        self.replace_previous.setChecked(replace)

        # Restore last URL
        saved_url = settings.value("HazmapperPlugin/last_project_url", "")

        if use_predefined and saved_url:
            # Try to find in dropdown
            for i in range(self.project_dropdown.count()):
                if self.project_dropdown.itemData(i) == saved_url:
                    self.project_dropdown.setCurrentIndex(i)
                    break
        elif not use_predefined and saved_url:
            # Set manual URL
            self.input_url.setText(saved_url)

        if saved_url:
            self.last_loaded_url = saved_url

        # Apply the mode toggle
        self.toggle_input_mode()
