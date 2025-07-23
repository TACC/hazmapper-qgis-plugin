from qgis.core import (
    QgsFillSymbol,
    QgsLineSymbol,
    QgsSvgMarkerSymbolLayer,
    QgsMarkerSymbol,
    QgsVectorLayer
)


def apply_camera_icon_style(layer: QgsVectorLayer) -> None:
    """Apply a camera SVG icon for point layers (e.g., images)."""
    # TODO refactor to make portable
    svg_path = "/Applications/QGIS.app/Contents/Resources/svg/gpsicons/camera.svg"
    svg_layer = QgsSvgMarkerSymbolLayer(svg_path, 6.0, 0)

    symbol = QgsMarkerSymbol()
    symbol.changeSymbolLayer(0, svg_layer)
    layer.renderer().setSymbol(symbol)
    layer.triggerRepaint()


def apply_point_cloud_style(layer: QgsVectorLayer) -> None:
    """Apply transparent fill with blue outline for point cloud layers."""
    symbol = QgsFillSymbol.createSimple({
        'style': 'no',
        'color': '0,0,0,0',
        'outline_color': '#3388ff',
        'outline_width': '0.66'
    })
    layer.renderer().setSymbol(symbol)
    layer.triggerRepaint()


def apply_streetview_style(layer: QgsVectorLayer, style_name: str = 'default') -> None:
    """Apply styled line symbology for streetview layers, with variants."""
    styles: dict[str, dict[str, str]] = {
        'default': {'color': '#22C7FF', 'width': '2.5', 'opacity': '0.6'},
        'select': {'color': '#22C7FF', 'width': '3', 'opacity': '1.0'},
        'hover': {'color': '#22C7FF', 'width': '3', 'opacity': '0.8'},
    }
    style = styles.get(style_name, styles['default'])

    symbol = QgsLineSymbol.createSimple({
        'color': style['color'],
        'width': style['width'],
        'line_style': 'solid',
    })
    symbol.setOpacity(float(style['opacity']))
    layer.renderer().setSymbol(symbol)
    layer.triggerRepaint()
