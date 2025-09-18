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
