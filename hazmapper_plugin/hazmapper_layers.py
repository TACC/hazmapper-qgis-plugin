from PyQt5.QtCore import QVariant, QSettings, QTimer
from qgis.core import (
    QgsMessageLog,
    Qgis,
    QgsProject,
    QgsLayerTreeGroup,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsRaster,
    QgsField,
    QgsFields,
    QgsWkbTypes,
)
import json
import uuid
from .utils.display import get_display_name
from .utils.qgis import quiet_layer

from .utils.style import (
    apply_camera_icon_style,
    apply_point_cloud_style,
    apply_streetview_style,
)
from .utils.geometry import json_to_wkt
from .utils.ui import make_ui_pacer


def remove_previous_main_group() -> None:
    """
    Safely remove Hazmapper project group and all its layers.
    Must be called in GUI thread.
    """
    settings = QSettings()
    internal_uuid = settings.value("HazmapperPlugin/internal_group_uuid", None)

    if not internal_uuid:
        QgsMessageLog.logMessage(
            "[Hazmapper] No internal UUID set; nothing to remove.",
            "Hazmapper",
            Qgis.Info,
        )
        return

    QgsMessageLog.logMessage(
        f"[Hazmapper] Removing group for internal UUID {internal_uuid}",
        "Hazmapper",
        Qgis.Info,
    )

    root = QgsProject.instance().layerTreeRoot()
    if root is None:
        QgsMessageLog.logMessage(
            "No layer tree root available.", "Hazmapper", Qgis.Warning
        )
        return

    for child in list(root.children()):
        if (
            isinstance(child, QgsLayerTreeGroup)
            and child.customProperty("hazmapper_qgis_internal_group_uuid")
            == internal_uuid
        ):
            # Remove all layers first
            for sublayer in child.findLayers():
                layer = sublayer.layer()
                if layer:
                    QgsProject.instance().removeMapLayer(layer.id())

            # Remove group node
            root.removeChildNode(child)
            QgsMessageLog.logMessage(
                f"[Hazmapper] Removed group with internal UUID {internal_uuid}",
                "Hazmapper",
                Qgis.Info,
            )

            # Clear UUID in settings to avoid stale reference
            settings.remove("HazmapperPlugin/internal_group_uuid")
            return

    QgsMessageLog.logMessage(
        f"[Hazmapper] No group found for internal UUID {internal_uuid}",
        "Hazmapper",
        Qgis.Warning,
    )


def create_main_group(project_name: str, project_uuid: str) -> QgsLayerTreeGroup:
    """
    Create new Hazmapper project group at top of layer tree.

    Returns:
        QgsLayerTreeGroup: The newly created group
    """
    try:
        QgsMessageLog.logMessage(
            "[Hazmapper] Creating main group", "Hazmapper", Qgis.Info
        )

        internal_uuid = str(uuid.uuid4())
        group_name = f"{project_name} ({project_uuid[:8]})"

        root = QgsProject.instance().layerTreeRoot()

        # Create new group
        group = QgsLayerTreeGroup(group_name)

        # Store identifiers for map's uuid and our own uuid for the qgis group
        group.setCustomProperty("hazmapper_project_uuid", project_uuid)
        group.setCustomProperty("hazmapper_qgis_internal_group_uuid", internal_uuid)

        root.insertChildNode(0, group)
        QgsMessageLog.logMessage(
            f"[Hazmapper] Created new group: {group_name} with internal UUID: {internal_uuid}",
            "Hazmapper",
            Qgis.Info,
        )
        settings = QSettings()
        settings.setValue("HazmapperPlugin/internal_group_uuid", internal_uuid)

        return group

    except Exception as e:
        QgsMessageLog.logMessage(
            f"[Hazmapper] Error in create_main_group: {str(e)}",
            "Hazmapper",
            Qgis.Critical,
        )
        raise


def add_basemap_layers(main_group, layers: list[dict], progress_callback):
    # Sort by zIndex (ascending: lower zIndex means lower in stack)
    sorted_layers = sorted(layers, key=lambda x: x["uiOptions"].get("zIndex", 0))
    total_layers = len(sorted_layers)

    update_progress = make_ui_pacer(progress_callback, 0.30)
    update_progress(f"Adding basemap layers", -1, force=True)

    for i, layer_data in enumerate(sorted_layers):
        try:
            name = layer_data["name"]
            url = layer_data["url"]
            layer_type = layer_data["type"]
            opacity = layer_data["uiOptions"].get("opacity", 1.0)

            # QgsMessageLog.logMessage(
            #    f"[Basemap] Name: {name}\n"
            #    f"          Type: {layer_type}\n"
            #    f"          URL: {url}\n"
            #    f"          Tile Options: {layer_data.get('tileOptions')}\n"
            #    f"          UI Options: {layer_data.get('uiOptions')}",
            #    "Hazmapper",
            #    Qgis.Info,
            # )

            # Handle subdomain placeholder (pick 'a' for QGIS)
            if "{s}" in url:
                url = url.replace("{s}", "a")

            if layer_type == "tms" or (layer_type == "arcgis" and "/tiles/" in url):
                # Ensure tile path includes expected XYZ format
                if not url.endswith("/tile/{z}/{y}/{x}") and "{z}/{x}/{y}" not in url:
                    tile_url = url.rstrip("/") + "/tile/{z}/{y}/{x}"
                else:
                    tile_url = url

                # TODO: Later, fetch actual min/max zoom from service metadata
                uri = f"type=xyz&url={tile_url}&zmin=0&zmax=22"
            else:
                QgsMessageLog.logMessage(
                    f"Skipping unsupported layer type: {layer_type}",
                    "Hazmapper",
                    Qgis.Warning,
                )
                continue

            # Note: XYZ tiles are loaded via the 'wms' provider in QGIS.
            # This is a legacy naming convention in QGIS; 'wms' is used
            # for both XYZ and WMS tile layers.
            raster_layer = QgsRasterLayer(uri, name, "wms")

            # Validate layer
            if not raster_layer.isValid():
                # Note: isValid() only checks URI/provider syntax. It does NOT verify that the
                # tile URL responds correctly (e.g., 403/404). Network errors will appear only
                # when tiles are actually requested/rendered.
                QgsMessageLog.logMessage(
                    f"Failed to load basemap layer: {name} (check URL)",
                    "Hazmapper",
                    Qgis.Warning,
                )
                continue

            # Apply opacity
            raster_layer.setOpacity(opacity)

            # Enable magnify/oversampling for smoother zoom beyond max LOD
            if hasattr(raster_layer, "setZoomedInResamplingMethod"):
                # Note: Per-layer magnify/resampling is available in QGIS 3.34+ only.
                # On older versions (like 3.32), resampling must be set globally via QGIS Options.
                raster_layer.resamplingEnabled = True
                raster_layer.setZoomedInResamplingMethod(
                    QgsRaster.ResamplingMethod.Nearest
                )
                raster_layer.setZoomedInMagnificationFactor(4)

            # Add layer to group (on top of stack)
            QgsProject.instance().addMapLayer(raster_layer, False)
            main_group.insertLayer(0, raster_layer)
            update_progress(f"Adding basemap layers", int(i * 100 / total_layers))
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error processing layer '{layer_data.get('name', 'unnamed')}': {str(e)}",
                "Hazmapper",
                Qgis.Critical,
            )


def add_features_layers(
    main_group: QgsLayerTreeGroup,
    features: dict,
    progress_callback=None,
    completion_callback=None,
):
    """Add feature layers with batching."""

    update_progress = make_ui_pacer(progress_callback, 0.30)
    update_progress(f"Preparing feature layers)", -1, force=True)

    #  first group by asset_type
    feature_groups: dict[str, list[tuple[dict, dict]]] = {}
    total_items = 0
    for feat in features.get("features", []):
        assets = feat.get("assets") or []
        if not assets:
            continue
        asset = assets[0]
        atype = asset.get("asset_type")
        feature_groups.setdefault(atype, []).append((feat, asset))
        total_items += 1

    processed = 0

    #  Work through each type of assets
    for asset_type, items in feature_groups.items():
        if not items:
            continue

        update_progress(f"Processing {asset_type})", -1, force=True)

        # ======== IMAGES / STREETVIEW / VIDEO : just a single memory layer =========
        if asset_type in ("video", "image", "streetview"):
            layer_name = get_display_name(asset_type)
            layer = QgsVectorLayer("MultiPoint?crs=EPSG:4326", layer_name, "memory")
            if not layer.isValid():
                QgsMessageLog.logMessage(
                    f"[Hazmapper] Failed to create memory layer for {asset_type}",
                    "Hazmapper",
                    Qgis.Critical,
                )
                continue

            with quiet_layer(layer):
                prov = layer.dataProvider()

                fields = QgsFields()
                fields.append(QgsField("asset_type", QVariant.String))
                fields.append(QgsField("display_path", QVariant.String))
                prov.addAttributes(fields)
                layer.updateFields()

                total = len(items)
                BATCH = 200  # bigger batches are faster for memory provider
                for i in range(0, total, BATCH):
                    feats = []
                    for feat, asset in items[i : i + BATCH]:
                        try:
                            g = QgsGeometry.fromWkt(
                                json_to_wkt(json.dumps(feat["geometry"]))
                            )
                            if not g or g.isEmpty():
                                continue

                            if QgsWkbTypes.geometryType(
                                g.wkbType()
                            ) == QgsWkbTypes.PointGeometry and QgsWkbTypes.isSingleType(
                                g.wkbType()
                            ):
                                g.convertToMultiType()

                            f = QgsFeature()
                            f.setGeometry(g)
                            f.setAttributes(
                                [
                                    asset.get("asset_type", ""),
                                    asset.get("display_path", ""),
                                ]
                            )
                            feats.append(f)
                        except Exception as e:
                            # Skip bad geometry but keep loading things
                            QgsMessageLog.logMessage(
                                f"[Hazmapper] Skipping bad geometry in {asset_type}: {e}",
                                "Hazmapper",
                                Qgis.Warning,
                            )
                    if feats:
                        prov.addFeatures(feats)

                    done = min(i + BATCH, total)
                    pct = int(done * 100 / max(total, 1))
                    update_progress(
                        f"Processing {asset_type} features... ({done}/{total})", pct
                    )

                # finalize, style, insert
                layer.updateExtents()
                _set_feature_metadata(layer, items[0][0], items[0][1])
                _apply_style_for_asset_type(layer, asset_type)

            QgsProject.instance().addMapLayer(layer, False)
            main_group.insertLayer(0, layer)
            processed += len(items)
            update_progress(f"Completed {asset_type} layer insertion", 100, force=True)

        # ======== POINT CLOUDS / OTHERS: many layers, batch project ops =========
        else:
            subgroup_name = get_display_name(asset_type)
            subgroup = QgsLayerTreeGroup(subgroup_name)
            main_group.insertChildNode(0, subgroup)

            batch_layers, BATCH = [], 50
            root = QgsProject.instance().layerTreeRoot()
            # Reduce layer-tree chatter while we stuff the subgroup
            root.blockSignals(True)
            subgroup.blockSignals(True)
            try:
                total = len(items)
                for i, (feat, asset) in enumerate(items, 1):
                    name = asset.get("display_path", f"Unnamed {asset_type}")
                    vl = _create_memory_layer(feat, name)
                    if vl:
                        _set_feature_metadata(vl, feat, asset)
                        _apply_style_for_asset_type(vl, asset_type)
                        batch_layers.append(vl)

                    # Bulk-add every BATCH to cutregistry bridge updates
                    if len(batch_layers) >= BATCH or i == total:
                        QgsProject.instance().addMapLayers(batch_layers, False)
                        for l in batch_layers:
                            subgroup.insertLayer(0, l)
                        batch_layers.clear()

                    processed += 1
                    pct = int(processed * 100 / max(total_items, 1))
                    update_progress(f"Processing {asset_type}… ({i}/{total})", pct)
            finally:
                subgroup.blockSignals(False)
                root.blockSignals(False)
            update_progress(f"Completed {asset_type} layers", 100, force=True)

    if completion_callback:
        completion_callback()


def _create_memory_layer(feature: dict, name: str) -> QgsVectorLayer:
    geom_type = feature["geometry"]["type"]
    layer = QgsVectorLayer(f"{geom_type}?crs=EPSG:4326", name, "memory")
    provider = layer.dataProvider()

    # Define fields
    fields = QgsFields()
    fields.append(QgsField("asset_type", QVariant.String))
    fields.append(QgsField("display_path", QVariant.String))
    provider.addAttributes(fields)
    layer.updateFields()

    # Build feature
    f = QgsFeature()
    f.setGeometry(QgsGeometry.fromWkt(json_to_wkt(json.dumps(feature["geometry"]))))

    asset = feature.get("assets", [{}])[0] or {}
    f.setAttributes([asset.get("asset_type", ""), asset.get("display_path", "")])

    provider.addFeature(f)
    return layer


def _create_memory_layer_collection(features: list, name: str) -> QgsVectorLayer:
    first_geom_type = features[0]["geometry"]["type"]
    layer = QgsVectorLayer(f"{first_geom_type}?crs=EPSG:4326", name, "memory")
    provider = layer.dataProvider()

    # Define fields
    fields = QgsFields()
    fields.append(QgsField("asset_type", QVariant.String))
    fields.append(QgsField("display_path", QVariant.String))
    provider.addAttributes(fields)
    layer.updateFields()

    features_to_add = []
    for i, feature in enumerate(features):
        asset = feature.get("assets", [{}])[0] or {}

        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromWkt(json_to_wkt(json.dumps(feature["geometry"]))))

        # Set attributes
        f.setAttributes([asset.get("asset_type", ""), asset.get("display_path", "")])
        features_to_add.append(f)

    provider.addFeatures(features_to_add)
    layer.updateExtents()
    return layer


def _apply_style_for_asset_type(layer: QgsVectorLayer, asset_type: str):
    """Apply appropriate styling based on asset type."""
    if asset_type == "point_cloud":
        apply_point_cloud_style(layer)
    elif asset_type == "image":
        apply_camera_icon_style(layer)
    elif asset_type == "streetview":
        apply_streetview_style(layer)


def _set_feature_metadata(feature_or_layer, feature, asset):
    # Set metadata on QgsFeature or layer depending on type
    for k, v in asset.items():
        feature_or_layer.setCustomProperty(f"asset_{k}", v)
