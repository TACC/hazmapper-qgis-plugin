from typing import Optional

from qgis.core import (
    QgsColorRampShader,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsRasterBandStats,
    QgsRasterLayer,
    QgsRasterShader,
    QgsSingleBandPseudoColorRenderer,
    QgsStyle,
    QgsVectorLayer,
    QgsSingleSymbolRenderer,
)

# Map geoapi/TiTiler colormap names (uiOptions.renderOptions.colormap_name) to
# the closest built-in QGIS color ramp. geoapi defaults single-band COGs to
# "terrain". Loading a COG natively means QGIS applies its own styling, so this
# is an approximation of the web app's look, not a pixel match.
_COLORMAP_TO_QGIS_RAMP = {
    "terrain": "Spectral",
    "viridis": "Viridis",
    "magma": "Magma",
    "inferno": "Inferno",
    "plasma": "Plasma",
    "cividis": "Cividis",
    "greys": "Greys",
    "gray": "Greys",
    "blues": "Blues",
    "greens": "Greens",
    "reds": "Reds",
}


def apply_cog_colormap(layer: QgsRasterLayer, colormap_name: Optional[str]) -> None:
    """
    Apply an approximate single-band pseudocolor ramp to a COG raster layer,
    matching the geoapi/TiTiler colormap where possible.

    No-op (leaves QGIS default rendering) for invalid layers, multi-band
    rasters, or unknown/absent colormap names.
    """
    if not layer.isValid() or not colormap_name:
        return

    provider = layer.dataProvider()
    if provider.bandCount() != 1:
        return

    ramp_name = _COLORMAP_TO_QGIS_RAMP.get(colormap_name.lower())
    if not ramp_name:
        return

    ramp = QgsStyle.defaultStyle().colorRamp(ramp_name)
    if ramp is None:
        return

    band = 1
    stats = provider.bandStatistics(band, QgsRasterBandStats.All)
    vmin, vmax = stats.minimumValue, stats.maximumValue
    if vmin is None or vmax is None or vmax <= vmin:
        return

    shader_fn = QgsColorRampShader(
        vmin, vmax, ramp, QgsColorRampShader.Interpolated
    )
    # Build evenly spaced ramp stops across the band's value range
    steps = 32
    ramp_items = []
    for i in range(steps + 1):
        frac = i / steps
        value = vmin + frac * (vmax - vmin)
        ramp_items.append(
            QgsColorRampShader.ColorRampItem(
                value, ramp.color(frac), f"{value:.3g}"
            )
        )
    shader_fn.setColorRampItemList(ramp_items)

    shader = QgsRasterShader()
    shader.setRasterShaderFunction(shader_fn)

    renderer = QgsSingleBandPseudoColorRenderer(provider, band, shader)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


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
