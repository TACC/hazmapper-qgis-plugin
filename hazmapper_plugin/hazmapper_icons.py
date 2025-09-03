import os

PLUGIN_DIR = os.path.dirname(__file__)
ICONS_DIR = os.path.join(PLUGIN_DIR, "icons")


def plugin_icon_path(name: str) -> str:
    """Return filesystem path to an icon shipped with the plugin."""
    return os.path.join(ICONS_DIR, name)
