from __future__ import annotations

import shutil

from .paths import AUTOSTART_DIR, AUTOSTART_FILE


def set_autostart(enabled: bool) -> None:
    if enabled:
        AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
        executable = shutil.which("codex-pets-cursor") or "codex-pets-cursor"
        AUTOSTART_FILE.write_text(
            "\n".join(
                [
                    "[Desktop Entry]",
                    "Type=Application",
                    "Name=Codex Pets Cursor",
                    f"Exec={executable} --background",
                    "X-KDE-autostart-after=panel",
                    "X-GNOME-Autostart-enabled=true",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    else:
        AUTOSTART_FILE.unlink(missing_ok=True)
