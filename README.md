# Hazmapper QGIS Plugin

This QGIS plugin allows users to connect to **Hazmapper**, a geospatial data platform hosted on the DesignSafe cyberinfrastructure. It enables visualization and interaction with datasets managed via the GEOAPI backend.

![demo](https://github.com/user-attachments/assets/1e5d81cc-f69e-494a-9cf7-6bd9120264c0)

## Features

- Browse and load Hazmapper projects directly into QGIS
- Fetch and display GeoJSON datasets served by the GEOAPI backend
- Interact with published project layers in your local QGIS environment

## Requirements

- QGIS 3.10 or newer
- Internet connection to access Hazmapper and backend services

## Development

To just install once, you could clone the repo and copy in to the QGis plugin folder. Using a symbolic link makes things easier
for development and is recommended:


### Step 1: Clone this repository:
    ```bash
    git clone https://github.com/TACC/hazmapper-qgis-plugin.git
    ```

### Step 2: Link the `hazmapper_plugin/` directory into your QGIS plugin folder so changes are reflected live:

**macOS**:
```bash
ln -s /path/to/hazmapper-qgis-plugin/hazmapper_plugin \
  ~/Library/Application\ Support/QGIS/QGIS3/profiles/default/python/plugins/hazmapper_plugin
```

**Linux (UNTESTED)**:
```bash
ln -s /path/to/hazmapper-qgis-plugin/hazmapper_plugin \
  ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/hazmapper_plugin
```

Then restart QGIS and enable the plugin via the Plugin Manager:

* Open QGIS
* Navigate to `Plugins` → `Manage and Install Plugins`
* Locate hazmapper_plugin in the list and check the box to enable it

💡 Use the [Plugin Reloader plugin](https://plugins.qgis.org/plugins/plugin_reloader/) to reload this plugin without restarting QGIS.

Instead if linking, You can also copy hazmapper_plugin/ into your QGIS plugins folder, but this requires re-copying every time you make changes.

## Development notes

If you make changes to icons or update `resources.qrc`, you must recompile the resources file:

```bash
cd hazmapper_plugin
pyrcc5 -o resources_rc.py resources.qrc
```
### Testing

```bash
docker run --rm -v $(pwd):/workspace -w /workspace \
  -e QT_QPA_PLATFORM=offscreen \
  qgis/qgis:release-3_34 \
  python3 -m unittest discover -s hazmapper_plugin/test -p 'test_*.py' -v
```

## Related Projects

- Hazmapper: [https://hazmapper.tacc.utexas.edu/hazmapper/](https://hazmapper.tacc.utexas.edu/hazmapper/)
- GeoApi backend: [https://github.com/TACC-Cloud/geoapi](https://github.com/TACC-Cloud/geoapi)
- DesignSafe portal: [https://www.designsafe-ci.org/](www.designsafe-ci.org/)

