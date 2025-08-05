from qgis.PyQt.QtCore import QSettings
import uuid


def get_or_create_guest_uuid() -> str:
    settings = QSettings()
    key = "hazmapper/guest_uuid"

    guest_uuid = settings.value(key, None)
    if not guest_uuid:
        guest_uuid = str(uuid.uuid4())
        settings.setValue(key, guest_uuid)

    return guest_uuid
