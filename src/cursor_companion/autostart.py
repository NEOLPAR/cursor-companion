from __future__ import annotations

import shutil

from .paths import AUTOSTART_DIR, AUTOSTART_FILE


def set_autostart(enabled: bool, background: bool = True) -> None:
    if enabled:
        AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
        executable = shutil.which("cursor-companion") or "cursor-companion"
        args = " --background" if background else ""
        AUTOSTART_FILE.write_text(
            "\n".join(
                [
                    "[Desktop Entry]",
                    "Type=Application",
                    "Name=Cursor Companion",
                    f"Exec={executable}{args}",
                    "Icon=cursor-companion",
                    "StartupNotify=false",
                    "X-KDE-autostart-after=panel",
                    "X-GNOME-Autostart-enabled=true",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    else:
        AUTOSTART_FILE.unlink(missing_ok=True)
