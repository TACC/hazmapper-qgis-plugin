from qgis.core import QgsWkbTypes
from qgis.gui import QgsMapToolIdentify
from qgis.PyQt.QtCore import Qt, pyqtSignal


def _pick_priority(result) -> int:
    """Smaller is better: a point under the cursor beats a line, which beats a polygon."""
    geometry_type = result.mLayer.geometryType()
    if geometry_type == QgsWkbTypes.PointGeometry:
        return 0
    if geometry_type == QgsWkbTypes.LineGeometry:
        return 1
    return 2


class FeaturePickTool(QgsMapToolIdentify):
    """
    Map tool: click a feature of the loaded Hazmapper map to show it in the plugin panel.

    Only looks at the layers returned by `get_layers`. When several features are under
    the cursor (e.g. a photo inside a point cloud's footprint) the smallest kind of
    geometry wins, so points are not hidden by the polygons around them.
    """

    picked = pyqtSignal(object, object)  # layer, feature
    missed = pyqtSignal()  # clicked where there is no feature

    def __init__(self, canvas, get_layers):
        super().__init__(canvas)
        self._get_layers = get_layers
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def pick(self, x: int, y: int):
        """Return (layer, feature) for the best feature at a canvas pixel, or None."""
        layers = self._get_layers()
        if not layers:
            return None

        results = self.identify(
            x, y, layers, QgsMapToolIdentify.IdentifyMode.TopDownAll
        )
        if not results:
            return None
        best = min(results, key=_pick_priority)  # min() keeps the topmost on a tie
        return best.mLayer, best.mFeature

    def canvasReleaseEvent(self, event):
        point = event.pixelPoint()
        found = self.pick(point.x(), point.y())
        if found:
            self.picked.emit(*found)
        else:
            self.missed.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.canvas().unsetMapTool(self)
        else:
            super().keyPressEvent(event)
