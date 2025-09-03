# Scripts

This directory contains utility scripts

## Available Scripts

### designsafe_hazmapper_discovery.py

Discovers all DesignSafe published projects that have associated Hazmapper maps and generates configuration files.

**Usage:**

```bash

# Run short version (100 projects for testing)
python3 designsafe_hazmapper_discovery.py --short

# Run long and save python config to a specific location
python3 designsafe_hazmapper_discovery.py --python_output_location ../hazmapper_plugin/utils/

**Generated Files:**
- `maps_of_published_projects.py` - Python configuration file with project data
- `README_PUBLISHED_MAPS.md` - Markdown table with clickable links to projects and maps
- `projects_with_hazmapper_maps.json` - Raw JSON data for reference

