from qgis.core import (
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsLayerTreeGroup,
    QgsMapLayer,
    QgsMessageLog,
    Qgis,
)
from qgis.utils import iface
from contextlib import contextmanager

# Set on tile layers that were given a real extent (rather than the whole world)
HAS_KNOWN_EXTENT_PROPERTY = "hazmapper_has_known_extent"

# Set on tile layers drawn from a GeoTIFF that was imported into the Hazmapper map
INTERNAL_COG_PROPERTY = "hazmapper_internal_cog"


def zoom_to_group(group: QgsLayerTreeGroup):
    """Zoom to the combined extent of the map's data layers inside `group`, recursively."""
    canvas = iface.mapCanvas()
    if not canvas or not group:
        return

    canvas_crs = canvas.mapSettings().destinationCrs()
    project = QgsProject.instance()

    def accumulate_extent(node, running_extent=None):
        # Dive into subgroups
        for child in node.children():
            if child.nodeType() == child.NodeGroup:
                running_extent = accumulate_extent(child, running_extent)

            elif child.nodeType() == child.NodeLayer:
                layer = child.layer()
                if not layer or not layer.isValid():
                    continue
                # Vector layers, plus tile layers whose real extent we know (internal
                # COGs). Other tile layers (basemaps) cover the whole world.
                if layer.type() != QgsMapLayer.VectorLayer and not layer.customProperty(
                    HAS_KNOWN_EXTENT_PROPERTY
                ):
                    continue

                lyr_extent = layer.extent()
                if lyr_extent is None or lyr_extent.isEmpty():
                    continue

                # Transform this layer's extent into canvas CRS if needed
                lyr_crs = (
                    layer.crs()
                    if hasattr(layer, "crs")
                    else QgsCoordinateReferenceSystem("EPSG:4326")
                )
                if lyr_crs.isValid() and lyr_crs != canvas_crs:
                    try:
                        xform = QgsCoordinateTransform(lyr_crs, canvas_crs, project)
                        lyr_extent = xform.transformBoundingBox(lyr_extent)
                    except Exception as e:
                        QgsMessageLog.logMessage(
                            f"[Hazmapper] Extent transform failed for {layer.name()}: {e}",
                            "Hazmapper",
                            Qgis.Warning,
                        )
                        continue

                if running_extent is None:
                    running_extent = lyr_extent
                else:
                    running_extent.combineExtentWith(lyr_extent)

        return running_extent

    QgsMessageLog.logMessage(
        "Starting zoom calculation (recursive)…", "Hazmapper", Qgis.Info
    )
    extent = accumulate_extent(group)

    if extent and not extent.isEmpty():
        QgsMessageLog.logMessage("Setting map canvas extent…", "Hazmapper", Qgis.Info)
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
