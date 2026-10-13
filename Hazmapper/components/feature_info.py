import html
import os

from qgis.core import NULL, QgsNetworkAccessManager
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.PyQt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..utils.links import asset_url, hazmapper_feature_url
from ..utils.qgis import GEOAPI_URL_PROPERTY, MAP_URL_PROPERTY

# Columns the plugin adds for its own use; shown as title/links, not as feature data
_INTERNAL_FIELDS = {"feature_id", "asset_type", "asset_path", "display_path"}
_MAX_ROWS = 12
_PREVIEW_WIDTH = 240

HINT_IDLE = "Click <i>Pick on map</i>, then a feature of the Hazmapper map."
HINT_PICKING = (
    "Click a feature on the map. Press Esc or click the button again to stop."
)
PICK_LABEL_IDLE = "Pick on map"
PICK_LABEL_ACTIVE = "Picking: click a feature"
# Make it obvious that picking is on (the platform's own "pressed" look is too subtle)
PICK_BUTTON_STYLE = """
QPushButton:checked {
    background-color: #1a73e8;
    color: white;
    border: 1px solid #1558b0;
    border-radius: 4px;
    padding: 3px 10px;
}
"""


class FeatureInfo(QWidget):
    """Shows one feature of the loaded map: what it is, a photo preview, and links."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._wanted_preview = None
        self.has_feature = False

        layout = QVBoxLayout()
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Selected feature</b>"))
        header.addStretch()
        self.pick_button = QPushButton(PICK_LABEL_IDLE)
        self.pick_button.setCheckable(True)
        self.pick_button.setToolTip("Click a feature on the map to show it here")
        self.pick_button.setStyleSheet(PICK_BUTTON_STYLE)
        self.pick_button.toggled.connect(self._on_picking_changed)
        header.addWidget(self.pick_button)
        layout.addLayout(header)

        self.title = QLabel()
        self.preview = QLabel()
        self.details = QLabel()
        self.links = QLabel()
        for label in (self.title, self.details, self.links):
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.LinksAccessibleByMouse
            )
            layout.addWidget(label)
        self.links.setOpenExternalLinks(True)
        layout.insertWidget(2, self.preview)  # under the title

        self.clear()

    def _on_picking_changed(self, picking: bool):
        self.pick_button.setText(PICK_LABEL_ACTIVE if picking else PICK_LABEL_IDLE)
        if not self.has_feature:
            self.clear()  # refresh the hint for the new state

    def clear(self):
        """Show the hint that explains how to pick a feature."""
        self._wanted_preview = None
        self.has_feature = False
        hint = HINT_PICKING if self.pick_button.isChecked() else HINT_IDLE
        self.title.setText(f'<span style="color: gray;">{hint}</span>')
        self.preview.clear()
        self.preview.setVisible(False)
        self.details.setVisible(False)
        self.links.setVisible(False)

    def show_feature(self, layer, feature):
        """Show a feature from one of the layers the plugin created."""
        self.has_feature = True
        attributes = {
            field.name(): value
            for field, value in zip(layer.fields(), feature.attributes())
            if value is not None and value != NULL
        }
        feature_id = attributes.get("feature_id")
        asset_type = attributes.get("asset_type")
        asset_path = attributes.get("asset_path")
        display_path = attributes.get("display_path")
        map_url = layer.customProperty(MAP_URL_PROPERTY)
        geoapi_url = layer.customProperty(GEOAPI_URL_PROPERTY)

        # Title: the file name for a photo/video/point cloud, else the layer name
        name = os.path.basename(str(display_path).rstrip("/")) if display_path else ""
        title = html.escape(name or layer.name())
        subtitle = html.escape(layer.name()) if name and name != layer.name() else ""
        if feature_id is not None:
            subtitle = f"{subtitle} · feature {feature_id}".strip(" ·")
        self.title.setText(
            f'<b>{title}</b><br><span style="color: gray;">{subtitle}</span>'
        )

        # Details: the feature's own data
        rows = [(k, v) for k, v in attributes.items() if k not in _INTERNAL_FIELDS]
        if display_path and str(display_path) != name:
            rows.insert(0, ("Path", display_path))
        shown = rows[:_MAX_ROWS]
        table = "".join(
            f'<tr><td style="color: gray; padding-right: 8px;">{html.escape(str(k))}</td>'
            f"<td>{html.escape(str(v))}</td></tr>"
            for k, v in shown
        )
        if len(rows) > len(shown):
            table += (
                f'<tr><td colspan="2" style="color: gray;">… {len(rows) - len(shown)} '
                "more in the attribute table</td></tr>"
            )
        self.details.setText(f"<table>{table}</table>")
        self.details.setVisible(bool(rows))

        # Link back to this feature in the Hazmapper web map
        has_link = bool(map_url) and feature_id is not None
        if has_link:
            url = hazmapper_feature_url(map_url, feature_id)
            self.links.setText(f'<a href="{html.escape(url)}">View in Hazmapper</a>')
        self.links.setVisible(has_link)

        # Preview (photos only)
        self.preview.clear()
        self.preview.setVisible(False)
        self._wanted_preview = None
        if asset_type == "image" and geoapi_url and asset_path:
            self._load_preview(asset_url(geoapi_url, asset_path))

    def _load_preview(self, url: str):
        self._wanted_preview = url
        reply = QgsNetworkAccessManager.instance().get(QNetworkRequest(QUrl(url)))
        reply.finished.connect(lambda: self._on_preview_loaded(reply, url))

    def _on_preview_loaded(self, reply, url: str):
        try:
            # a different feature may have been picked while this was downloading
            if url != self._wanted_preview:
                return
            pixmap = QPixmap()
            if pixmap.loadFromData(bytes(reply.readAll())):
                self.preview.setPixmap(
                    pixmap.scaledToWidth(
                        min(_PREVIEW_WIDTH, pixmap.width()),
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                self.preview.setVisible(True)
        finally:
            reply.deleteLater()
