#!/usr/bin/env bash
# Run the blocking checks plugins.qgis.org runs on an upload, on the built plugin ZIP.
# The ZIP is scanned rather than the repo because that is what the site sees.
# See https://plugins.qgis.org/docs/security-scanning
# Usage: scripts/scan_plugin_zip.sh Hazmapper.<version>.zip
set -euo pipefail

ZIP="$1"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCAN_DIR="$(mktemp -d)"
trap 'rm -rf "$SCAN_DIR"' EXIT
unzip -q "$ZIP" -d "$SCAN_DIR/plugin"

echo "--- Suspicious file types (FILE_SUSPICIOUS, can't be skipped on upload)"
SUSPICIOUS="$(find "$SCAN_DIR/plugin" -type f \( \
  -name '*.sh' -o -name '*.bat' -o -name '*.cmd' \
  -o -name '*.exe' -o -name '*.dll' -o -name '*.so' \))"
if [ -n "$SUSPICIOUS" ]; then
  echo "Found file types that plugins.qgis.org blocks:"
  echo "$SUSPICIOUS"
  exit 1
fi

echo "--- Bandit"
uv run bandit -r "$SCAN_DIR/plugin" -q

echo "--- detect-secrets"
# Run from inside the folder: detect-secrets silently skips paths outside the cwd
(cd "$SCAN_DIR/plugin" && uv run --project "$REPO_ROOT" detect-secrets scan --all-files .) \
  > "$SCAN_DIR/secrets.json"
uv run python - "$SCAN_DIR/secrets.json" <<'PY'
import json
import sys

with open(sys.argv[1]) as f:
    results = json.load(f)["results"]
for path, secrets in results.items():
    for secret in secrets:
        print(f"{path}:{secret['line_number']}: {secret['type']}")
sys.exit(1 if results else 0)
PY

echo "Plugin ZIP passed the scan"
