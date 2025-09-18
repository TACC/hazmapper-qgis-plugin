from qgis.core import (
    QgsCoordinateTransform,
    QgsVectorLayer,
    QgsProject,
    QgsLayerTreeGroup,
    QgsCoordinateReferenceSystem,
    QgsMessageLog,
    Qgis,
)
from qgis.utils import iface
from contextlib import contextmanager


def zoom_to_group(group: QgsLayerTreeGroup):
    canvas = iface.mapCanvas()
    QgsMessageLog.logMessage("Starting zoom calculation...", "Hazmapper", Qgis.Info)
    extent = None
    layer_count = 0

    for child in group.children():
        if child.nodeType() == child.NodeLayer:
            layer = child.layer()
            if layer and layer.type() == layer.VectorLayer:
                layer_count += 1
                QgsMessageLog.logMessage(
                    f"Calculating extent for layer: {layer.name()}",
                    "Hazmapper",
                    Qgis.Info,
                )

                # Merge extents
                if extent is None:
                    extent = layer.extent()
                else:
                    extent.combineExtentWith(layer.extent())

    QgsMessageLog.logMessage(
        f"Calculated extents for {layer_count} layers", "Hazmapper", Qgis.Info
    )

    if extent and not extent.isEmpty():
        canvas_crs = canvas.mapSettings().destinationCrs()

        # Assume Hazmapper features are EPSG:4326 (set at creation)
        layer_crs = QgsCoordinateReferenceSystem("EPSG:4326")

        if layer_crs != canvas_crs:
            QgsMessageLog.logMessage(
                "Transforming extent coordinates...", "Hazmapper", Qgis.Info
            )
            xform = QgsCoordinateTransform(layer_crs, canvas_crs, QgsProject.instance())
            extent = xform.transformBoundingBox(extent)

        QgsMessageLog.logMessage("Setting map canvas extent...", "Hazmapper", Qgis.Info)
        canvas.setExtent(extent)
        canvas.refresh()

        QgsMessageLog.logMessage("Zoomed to Hazmapper features", "Hazmapper", Qgis.Info)
    else:
        QgsMessageLog.logMessage(
            "No Hazmapper features to zoom to", "Hazmapper", Qgis.Info
        )


@contextmanager
def quiet_layer(layer, disable_labels: bool = True):
    """
    Temporarily disable signals (and labels) on a QgsVectorLayer.

    Usage:
        with quiet_layer(layer):
            # bulk add features, apply style, etc.
            ...

    After exiting the block, signals and labels are re-enabled and repaint triggered.
    """
    if not layer or not layer.isValid():
        yield
        return

    # Save state
    prev_labels = layer.labelsEnabled()

    try:
        layer.blockSignals(True)
        if disable_labels:
            layer.setLabelsEnabled(False)
        yield
    finally:
        layer.blockSignals(False)
        if disable_labels:
            layer.setLabelsEnabled(prev_labels)
