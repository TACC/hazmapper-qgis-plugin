from qgis.PyQt.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QProgressBar,
    QFormLayout,
    QSizePolicy,
)
from qgis.PyQt.QtCore import Qt, QDateTime

from ..utils.maps_of_published_projects import predefined_published_maps


class MapStatus(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Main layout
        layout = QVBoxLayout()
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        # --- Status Row ---
        status_layout = QHBoxLayout()
        status_layout.setSpacing(4)

        self.status_icon = QLabel("🟢")
        self.status_message = QLabel("Ready")

        status_layout.addWidget(self.status_icon)
        status_layout.addWidget(self.status_message)
        status_layout.addStretch()

        layout.addLayout(status_layout)

        # --- Progress Bar ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # --- Metadata Form (labels left, values right) ---
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignTop | Qt.AlignRight)
        form.setFormAlignment(Qt.AlignTop)

        # Name
        self.name_title = QLabel("Name:")
        self.name_value = QLabel("–")
        self.name_value.setWordWrap(
            True
        )  # allow wrapping (or set False + elide if you prefer)
        self.name_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.name_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        form.addRow(self.name_title, self.name_value)

        # Description
        self.description_title = QLabel("Description:")
        self.description_value = QLabel("–")
        self.description_value.setWordWrap(True)
        self.description_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.description_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        form.addRow(self.description_title, self.description_value)

        # Hazmapper Map
        self.map_title = QLabel("Hazmapper Map:")
        self.map_value = QLabel("–")
        self.map_value.setTextFormat(Qt.RichText)
        self.map_value.setOpenExternalLinks(True)
        self.map_value.setWordWrap(True)
        self.map_value.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
        )
        self.map_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        form.addRow(self.map_title, self.map_value)

        # DesignSafe (hidden until matched)
        self.ds_title = QLabel("DesignSafe:")
        self.ds_value = QLabel("–")
        self.ds_value.setTextFormat(Qt.RichText)
        self.ds_value.setOpenExternalLinks(True)
        self.ds_value.setWordWrap(True)
        self.ds_value.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
        )
        self.ds_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.ds_title.setVisible(False)
        self.ds_value.setVisible(False)
        form.addRow(self.ds_title, self.ds_value)

        # Last Refreshed
        self.refreshed_title = QLabel("Last Refreshed:")
        self.refreshed_value = QLabel("–")
        self.refreshed_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.refreshed_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        form.addRow(self.refreshed_title, self.refreshed_value)

        layout.addLayout(form)
        layout.addStretch()

    # Status update methods
    def update_status(self, icon, message):
        """Update the status display with new icon and message."""
        self.status_icon.setText(icon)
        self.status_message.setText(message)

    def set_ready(self):
        """Set status to ready state."""
        self.update_status("🟢", "Ready")

    def set_running(self, message):
        """Set status to running state."""
        self.update_status("🔄", message)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

    def set_running_with_progress(self, message: str, progress: int) -> None:
        """Set status to running state with progress bar.

        If `progress` is -1, then we show busy mode
        """
        self.update_status("🔄", message)
        self.progress_bar.setVisible(True)

        if progress == -1:
            self.progress_bar.setRange(0, 0)  # busy mode
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(progress)

    def set_success(self, message="Success"):
        """Set status to success state."""
        self.update_status("✅", message)
        self.progress_bar.setVisible(False)

    def set_error(self, message="Error"):
        """Set status to error state."""
        self.update_status("❌", message)
        self.progress_bar.setVisible(False)

    def set_invalid_url(self):
        """Set status for invalid URL."""
        self.update_status("🔴", "Invalid URL — must be a public Hazmapper project.")

    # Project metadata update methods
    def update_project_data(self, name=None, description=None, url=None):
        """Update project metadata."""
        if name is not None:
            self.name_value.setText(name)

        if description is not None:
            self.description_value.setText(description)

        if url is not None:
            self.map_value.setText(f'<a href="{url}">{url}</a>')
            self._update_designsafe_from_map_url(url)
        else:
            self._hide_designsafe_row()

        # Update refresh time
        self.refreshed_value.setText(
            QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm")
        )

    def clear_project_data(self):
        """Clear all project metadata."""
        self.name_value.setText("–")
        self.description_value.setText("–")
        self.map_value.setText("–")
        self.refreshed_value.setText("–")
        self._hide_designsafe_row()

    def set_name(self, name):
        """Set project name."""
        self.name_value.setText(name)

    def set_description(self, description):
        """Set project description."""
        self.description_value.setText(description)

    def set_map_url(self, url):
        """Set project map URL."""
        self.map_value.setText(f'<a href="{url}">{url}</a>')
        self._update_designsafe_from_map_url(url)

    def set_last_refreshed(self, datetime_str=None):
        """Set last refreshed time. If None, uses current time."""
        if datetime_str is None:
            datetime_str = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm")
        self.refreshed_value.setText(datetime_str)

    def _normalize_url(self, u: str) -> str:
        return (u or "").strip().rstrip("/").lower()

    def _lookup_ds_by_map_url(self, map_url: str):
        """Return the matching DS dict from index if map_url matches, else None."""
        norm = self._normalize_url(map_url)
        for item in predefined_published_maps:
            if self._normalize_url(item.get("url", "")) == norm:
                return item
        return None

    def _update_designsafe_from_map_url(self, map_url: str):
        # TODO this should come from DesignSafe eventually but right now
        # we are using our predefined_published_maps list
        # See https://github.com/TACC/hazmapper-qgis-plugin/issues/8
        item = self._lookup_ds_by_map_url(map_url)
        if not item:
            self._hide_designsafe_row()
            return

        prj = item.get("designSafeProjectId")
        name = item.get("designSafeProjectName")
        if not prj or not name:
            self._hide_designsafe_row()
            return

        ds_href = (
            f"https://www.designsafe-ci.org/"
            f"data/browser/public/designsafe.storage.published/{prj}"
        )
        link_text = f"{prj} | {name}"
        self.ds_value.setText(f'<a href="{ds_href}">{link_text}</a>')
        self.ds_title.setVisible(True)
        self.ds_value.setVisible(True)

    def _hide_designsafe_row(self):
        self.ds_title.setVisible(False)
        self.ds_value.setVisible(False)
        self.ds_value.setText("–")
