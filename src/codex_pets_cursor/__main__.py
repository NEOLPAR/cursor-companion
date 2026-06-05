from __future__ import annotations

import os

if os.environ.get("XDG_SESSION_TYPE") == "wayland" and not os.environ.get("CODEX_PETS_CURSOR_NATIVE_WAYLAND"):
    os.environ["QT_QPA_PLATFORM"] = "xcb"

from .app import main

if __name__ == "__main__":
    raise SystemExit(main())
