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

### Step 2: Link the `Hazmapper/` directory into your QGIS plugin folder so changes are reflected live:

**macOS**:

Easiest: run `./scripts/qgis_dev_setup.sh`. It finds the QGIS apps in `/Applications` and
their profiles, and prints the exact link and launch commands for each (it changes nothing).

To do it by hand: QGIS 3.x and QGIS 4.x keep separate settings folders (`QGIS3` and `QGIS4`), so link the
plugin into each version you want to test. Launch each QGIS once first so its folder exists.

```bash
PLUGIN=/path/to/hazmapper-qgis-plugin/Hazmapper
QGIS_SUPPORT=~/Library/Application\ Support/QGIS

# QGIS 3.x
ln -s "$PLUGIN" "$QGIS_SUPPORT/QGIS3/profiles/default/python/plugins/Hazmapper"

# QGIS 4.x
ln -s "$PLUGIN" "$QGIS_SUPPORT/QGIS4/profiles/default/python/plugins/Hazmapper"
```

Because the link points at your checkout, every QGIS loads whichever branch you have checked out.

**Linux (UNTESTED)**:
```bash
ln -s /path/to/hazmapper-qgis-plugin/Hazmapper \
  ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/Hazmapper
```

Then restart QGIS and enable the plugin via the Plugin Manager:

* Open QGIS
* Navigate to `Plugins` → `Manage and Install Plugins`
* Locate Hazmapper in the list and check the box to enable it

💡 Use the [Plugin Reloader plugin](https://plugins.qgis.org/plugins/plugin_reloader/) to reload this plugin without restarting QGIS.

Instead if linking, You can also copy Hazmapper/ into your QGIS plugins folder, but this requires re-copying every time you make changes.

### Running multiple QGIS versions (macOS)

QGIS apps installed in `/Applications` can sit side by side (e.g. `QGIS-3-44-LTR.app` and
`QGIS-final-4_2_1.app`). Start them from a terminal so Python errors from the plugin are
printed there as well as in QGIS's Log Messages panel. The program name inside each app
differs, so run `./scripts/qgis_dev_setup.sh` to print the exact command for each QGIS you
have installed. For example:

```bash
/Applications/QGIS-3-44-LTR.app/Contents/MacOS/QGIS
/Applications/QGIS-final-4_2_1.app/Contents/MacOS/QGIS-final-4_2_1
```

Two 3.x versions share the same `QGIS3` settings folder. To keep one isolated, give it its
own profiles folder (and link the plugin into that profile's `python/plugins/` instead):

```bash
/Applications/QGIS-3-44-LTR.app/Contents/MacOS/QGIS --profiles-path ~/qgis-profiles/3.44
```

In QGIS, `Settings` → `User Profiles` → `Open Active Profile Folder` shows which folder is in use.

Note: QGIS 4 uses Qt6/PyQt6. The plugin currently imports PyQt5 directly in a couple of
places, so it does not load in QGIS 4 yet.

## Development notes

### One-time setup

```
uv venv --python 3.12
uv sync --group dev
```

### Format, Linting and Type Checking

```
# Re-sync after editing pyproject.toml (e.g., adding deps, bumping versions)
uv sync --group dev

# Auto-format the codebase
uv run black .

# Lint
uv run flake8 .

# Type check (within your mypy settings)
uv run mypy .

# Run only fast tests that don't need QGIS
uv run pytest -m no_qgis_required
```

### Testing

```bash
make test-qgis
```


### Building zip

```bash
make zip
```

## Related Projects

- Hazmapper: [https://hazmapper.tacc.utexas.edu/hazmapper/](https://hazmapper.tacc.utexas.edu/hazmapper/)
- GeoApi backend: [https://github.com/TACC-Cloud/geoapi](https://github.com/TACC-Cloud/geoapi)
- DesignSafe portal: [https://www.designsafe-ci.org/](www.designsafe-ci.org/)

