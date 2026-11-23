def get_display_name(asset_type: str) -> str:
    """Get display name for asset type."""
    display_names = {
        "point_cloud": "Point Clouds",
        "image": "Images",
        "streetview": "StreetView",
        "video": "Videos",
        "questionnaire": "Questionnaires",
        "no_asset_vector": "Vector Features",
    }

    return display_names.get(asset_type, asset_type.replace("_", " ").title())


def shorten(text: str, limit: int = 110) -> str:
    """
    Cut text to about `limit` characters at a word boundary.

    Returns the text unchanged if it already fits; otherwise the cut text, without a
    trailing ellipsis (the caller adds its own "more" marker).
    """
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(" ,.;:-")
