from qgis.core import (
    QgsFillSymbol,
    QgsLineSymbol,
    QgsSvgMarkerSymbolLayer,
    QgsSingleSymbolRenderer,
    QgsPointClusterRenderer,
    QgsMarkerSymbol,
    QgsVectorLayer,
    QgsSingleSymbolRenderer,
)
from hazmapper_plugin.hazmapper_icons import plugin_icon_path


def apply_camera_icon_style(
    layer: QgsVectorLayer,
) -> None:
    # TODO use camera icon
    simple = QgsMarkerSymbol.createSimple({"name": "circle", "size": "2.4"})
    layer.setRenderer(QgsSingleSymbolRenderer(simple))
    return


def apply_point_cloud_style(layer: QgsVectorLayer) -> None:
    """Apply transparent fill with blue outline for point cloud layers."""
    # Check if layer is valid
    if not layer.isValid():
        return

    symbol = QgsFillSymbol.createSimple(
        {
            "style": "no",
            "color": "0,0,0,0",
            "outline_color": "#3388ff",
            "outline_width": "0.66",
        }
    )

    # Ensure layer has a renderer
    if layer.renderer() is None:
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    else:
        layer.renderer().setSymbol(symbol)

    layer.triggerRepaint()


def apply_streetview_style(layer: QgsVectorLayer, style_name: str = "default") -> None:
    """Apply styled line symbology for streetview layers, with variants."""
    # Check if layer is valid
    if not layer.isValid():
        return
    styles: dict[str, dict[str, str]] = {
        "default": {"color": "#22C7FF", "width": "2.5", "opacity": "0.6"},
        "select": {"color": "#22C7FF", "width": "3", "opacity": "1.0"},
        "hover": {"color": "#22C7FF", "width": "3", "opacity": "0.8"},
    }
    style = styles.get(style_name, styles["default"])

    symbol = QgsLineSymbol.createSimple(
        {
            "color": style["color"],
            "width": style["width"],
            "line_style": "solid",
        }
    )
    symbol.setOpacity(float(style["opacity"]))

    # Ensure layer has a renderer
    if layer.renderer() is None:
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    else:
        layer.renderer().setSymbol(symbol)

    layer.triggerRepaint()
