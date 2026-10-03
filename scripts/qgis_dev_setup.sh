#!/usr/bin/env bash
#
# macOS helper for plugin development: finds installed QGIS apps and their user
# profiles, and prints the commands to link this repo's plugin into each profile
# and to launch each QGIS. It only prints; nothing is changed.
#
# Usage: ./scripts/qgis_dev_setup.sh

set -euo pipefail

if [ "$(uname)" != "Darwin" ]; then
  echo "This script only supports macOS." >&2
  exit 1
fi

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_DIR="$REPO_DIR/Hazmapper"
QGIS_SUPPORT="$HOME/Library/Application Support/QGIS"

shopt -s nullglob nocaseglob
apps=(/Applications/*qgis*.app "$HOME"/Applications/*qgis*.app)
shopt -u nocaseglob

if [ ${#apps[@]} -eq 0 ]; then
  echo "No QGIS apps found in /Applications or ~/Applications."
  exit 0
fi

echo "Plugin source: $PLUGIN_DIR"
qgis3_count=0

for app in "${apps[@]}"; do
  version="$(defaults read "$app/Contents/Info" CFBundleShortVersionString 2>/dev/null || echo "?")"
  executable="$(defaults read "$app/Contents/Info" CFBundleExecutable 2>/dev/null || echo "QGIS")"
  major="${version%%.*}"

  echo
  echo "== $(basename "$app") (version $version)"
  echo "   Run:"
  echo "     \"$app/Contents/MacOS/$executable\""

  case "$major" in
    3) qgis3_count=$((qgis3_count + 1)) ;;
    4) ;;
    *)
      echo "   Unknown QGIS major version; skipping profile lookup."
      continue
      ;;
  esac

  profiles_dir="$QGIS_SUPPORT/QGIS$major/profiles"
  profiles=("$profiles_dir"/*/)
  if [ ${#profiles[@]} -eq 0 ]; then
    echo "   No profiles in $profiles_dir yet. Launch this QGIS once, then re-run this script."
    continue
  fi

  for profile in "${profiles[@]}"; do
    profile="${profile%/}"
    link="$profile/python/plugins/Hazmapper"
    echo "   Profile '$(basename "$profile")':"
    if [ -L "$link" ]; then
      echo "     Already linked -> $(readlink "$link")"
    elif [ -e "$link" ]; then
      echo "     $link exists but is not a symlink (an installed copy?). Remove it first to link this repo."
    else
      echo "     mkdir -p \"$profile/python/plugins\""
      echo "     ln -s \"$PLUGIN_DIR\" \"$link\""
    fi
  done

  if [ "$major" = "4" ]; then
    echo "   Note: the plugin still imports PyQt5 directly, so it does not load in QGIS 4 yet."
  fi
done

if [ "$qgis3_count" -gt 1 ]; then
  echo
  echo "Note: QGIS 3.x installs share the QGIS3 profiles. To isolate one, launch it with"
  echo "      --profiles-path <dir> and link the plugin into that profile instead."
fi
