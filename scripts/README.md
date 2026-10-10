# Scripts

This directory contains utility scripts

## Available Scripts

### designsafe_hazmapper_discovery.py

Discovers all DesignSafe published projects that have associated Hazmapper maps and generates configuration files.

**Requirements:** [uv](https://docs.astral.sh/uv/). The script declares its own
dependencies (`requests`) inline (PEP 723), so `uv run` installs them into a
throwaway environment; nothing needs to be added to the project.

**Usage** (run from this `scripts/` directory):

```bash
# Run short version (100 projects for testing)
uv run designsafe_hazmapper_discovery.py --short

# Run full discovery and update the plugin's list of published maps
uv run designsafe_hazmapper_discovery.py --python_output_location ../Hazmapper/utils/
```

Without uv, install `requests` yourself (e.g. `pip install requests`) and run with `python3`.

**Generated Files:**
- `maps_of_published_projects.py` - Python configuration file with project data
- `README_PUBLISHED_MAPS.md` - Markdown table with clickable links to projects and maps
- `projects_with_hazmapper_maps.json` - Raw JSON data for reference


### qgis_dev_setup.sh

macOS only. Finds installed QGIS apps (`/Applications/*qgis*.app`) and their QGIS3/QGIS4 user
profiles, then prints the commands to link this repo's `Hazmapper/` plugin into each profile and
to launch each QGIS. It only prints; nothing is changed.

```bash
./scripts/qgis_dev_setup.sh
```
