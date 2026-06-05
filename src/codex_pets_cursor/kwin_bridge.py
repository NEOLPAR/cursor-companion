from __future__ import annotations

import subprocess
import time
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtDBus import QDBusConnection

from .paths import DBUS_PATH, DBUS_SERVICE, KWIN_SCRIPT_DIR


SCRIPT = f"""
var service = "{DBUS_SERVICE}";
var path = "{DBUS_PATH}";
var iface = "local.CursorBridge";

function publishCursor() {{
    var p = workspace.cursorPos;
    var x = typeof p.x === "function" ? p.x() : p.x;
    var y = typeof p.y === "function" ? p.y() : p.y;
    callDBus(service, path, iface, "UpdateCursor", Math.round(x), Math.round(y), Date.now() / 1000.0);
}}

workspace.cursorPosChanged.connect(publishCursor);
publishCursor();
"""


class CursorBridge(QObject):
    def __init__(self, callback) -> None:
        super().__init__()
        self.callback = callback
        self.script_id: int | None = None
        self.last_update = 0.0

    @pyqtSlot(int, int, float)
    def UpdateCursor(self, x: int, y: int, timestamp: float) -> None:  # noqa: N802, ARG002
        self.last_update = time.monotonic()
        self.callback(x, y)

    def register_dbus(self) -> bool:
        bus = QDBusConnection.sessionBus()
        ok = bus.registerService(DBUS_SERVICE)
        object_ok = bus.registerObject(
            DBUS_PATH,
            self,
            QDBusConnection.RegisterOption.ExportScriptableSlots
            | QDBusConnection.RegisterOption.ExportNonScriptableSlots,
        )
        return ok and object_ok

    def install_kwin_script(self) -> None:
        KWIN_SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
        script_path = KWIN_SCRIPT_DIR / "cursor-bridge.js"
        script_path.write_text(SCRIPT, encoding="utf-8")
        try:
            self.unload_kwin_script()
            result = subprocess.run(
                [
                    "qdbus6",
                    "org.kde.KWin",
                    "/Scripting",
                    "org.kde.kwin.Scripting.loadScript",
                    str(script_path),
                    "codex-pets-cursor-bridge",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.stdout.strip().isdigit():
                self.script_id = int(result.stdout.strip())
            subprocess.run(
                ["qdbus6", "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.start"],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            pass

    def unload_kwin_script(self) -> None:
        try:
            subprocess.run(
                [
                    "qdbus6",
                    "org.kde.KWin",
                    "/Scripting",
                    "org.kde.kwin.Scripting.unloadScript",
                    "codex-pets-cursor-bridge",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            pass
