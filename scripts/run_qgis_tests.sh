#!/usr/bin/env bash
# Run QGIS-marked tests inside a QGIS-capable environment
# Usage (inside container): scripts/run_qgis_tests.sh [pytest-args...]
set -euxo pipefail

# Minimal tooling for tests
apt-get update
apt-get install -y --no-install-recommends python3-pip python3-setuptools python3-wheel xvfb

# Newer Debian/Ubuntu images refuse pip installs into the system Python (PEP 668).
# This is a throwaway container, so allow it. Older pip versions ignore the variable.
export PIP_BREAK_SYSTEM_PACKAGES=1

python3 -m pip install pytest

# The plugin is not installed: `python3 -m pytest` puts the repo root on sys.path,
# so tests import the `Hazmapper` package straight from the checkout.

# Sanity: confirm PyQGIS is importable
python3 - <<'PY'
import qgis, sys
print("PyQGIS OK:", qgis.__file__)
sys.exit(0)
PY

# Headless test run; pass through extra pytest args if provided
xvfb-run -s "+extension GLX -screen 0 1280x1024x24" \
  python3 -m pytest -q "$@"

