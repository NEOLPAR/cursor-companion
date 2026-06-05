from __future__ import annotations

import os
from pathlib import Path

APP_ID = "cursor-companion"
DBUS_SERVICE = "io.github.NEOLPAR.CursorCompanion"
DBUS_PATH = "/io/github/NEOLPAR/CursorCompanion"
DBUS_INTERFACE = "io.github.NEOLPAR.CursorCompanion"


def xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def xdg_data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


CONFIG_DIR = xdg_config_home() / APP_ID
CONFIG_FILE = CONFIG_DIR / "config.json"
DATA_DIR = xdg_data_home() / APP_ID
PETS_DIR = DATA_DIR / "pets"
DOWNLOADS_DIR = DATA_DIR / "downloads"
KWIN_SCRIPT_DIR = DATA_DIR / "kwin-script"
AUTOSTART_DIR = xdg_config_home() / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / f"{APP_ID}.desktop"
