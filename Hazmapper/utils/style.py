from qgis.core import (
    QgsFillSymbol,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsVectorLayer,
    QgsSingleSymbolRenderer,
)


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


# Same blue the Hazmapper web app (Leaflet) uses for plain features
PLAIN_FEATURE_COLOR = "#3388ff"


def apply_plain_feature_style(layer: QgsVectorLayer, family: str) -> None:
    """Style a layer of features that have no asset. `family`: point, line or polygon."""
    if not layer.isValid():
        return

    if family == "point":
        symbol = QgsMarkerSymbol.createSimple(
            {
                "name": "circle",
                "size": "2.4",
                "color": PLAIN_FEATURE_COLOR,
                "outline_color": "#ffffff",
                "outline_width": "0.3",
            }
        )
    elif family == "line":
        symbol = QgsLineSymbol.createSimple(
            {"color": PLAIN_FEATURE_COLOR, "width": "0.8", "line_style": "solid"}
        )
    else:
        symbol = QgsFillSymbol.createSimple(
            {
                "color": "51,136,255,50",
                "outline_color": PLAIN_FEATURE_COLOR,
                "outline_width": "0.66",
            }
        )

    layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    layer.triggerRepaint()
