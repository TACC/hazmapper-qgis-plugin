import time
from typing import Callable, Optional
from PyQt5.QtCore import QEventLoop
from qgis.PyQt.QtWidgets import QApplication


def make_ui_pacer(
    progress_cb: Optional[Callable[[str, int], None]] = None, interval_sec: float = 0.3
):
    """
    Return a function `update_progress_maybe(msg=None, pct=None, force=False)`
    that (a) throttles QApplication.processEvents and (b) coalesces progress updates.
    """
    last = [0.0]

    def update_progress_maybe(
        msg: Optional[str] = None, pct: Optional[int] = None, *, force: bool = False
    ):
        now = time.perf_counter()
        if force or (now - last[0]) >= interval_sec:
            if progress_cb and (msg is not None or pct is not None):
                try:
                    progress_cb(msg or "", 0 if pct is None else int(pct))
                except Exception:
                    pass
            QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
            last[0] = now

    return update_progress_maybe
