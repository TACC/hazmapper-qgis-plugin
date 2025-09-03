#!/usr/bin/env bash
# Run QGIS-marked tests inside a QGIS-capable environment
# Usage (inside container): scripts/run_qgis_tests.sh [pytest-args...]
set -euxo pipefail

# Minimal tooling for tests
apt-get update
apt-get install -y --no-install-recommends python3-pip python3-setuptools python3-wheel xvfb

python3 -m pip install --upgrade pip
python3 -m pip install pytest

# Install your plugin (editable); comment the next line and use PYTHONPATH=.
python3 -m pip install -e .

# Sanity: confirm PyQGIS is importable
python3 - <<'PY'
import qgis, sys
print("PyQGIS OK:", qgis.__file__)
sys.exit(0)
PY

# Headless test run; pass through extra pytest args if provided
xvfb-run -s "+extension GLX -screen 0 1280x1024x24" \
  python3 -m pytest -q "$@"

