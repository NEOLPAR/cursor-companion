from __future__ import annotations

import os
import sys
from pathlib import Path

if os.environ.get("XDG_SESSION_TYPE") == "wayland" and not os.environ.get("CODEX_PETS_CURSOR_NATIVE_WAYLAND"):
    os.environ["QT_QPA_PLATFORM"] = "xcb"

from PyQt6.QtCore import QPoint, QTimer
from PyQt6.QtGui import QAction, QCursor, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .config import ConfigStore
from .kwin_bridge import CursorBridge
from .manager import ManagerWindow
from .overlay import PetOverlay
from .pets import PetStore


class CursorPetApp:
    def __init__(self, show_manager: bool = True) -> None:
        self.qt = QApplication(sys.argv)
        self.qt.setApplicationName("Cursor Companion")
        self.qt.setQuitOnLastWindowClosed(False)

        self.config_store = ConfigStore()
        self.pet_store = PetStore()
        self.overlay = PetOverlay(self.config_store.config)
        self.manager = ManagerWindow(self.config_store, self.pet_store)
        self.manager.active_pet_changed.connect(self.set_active_pet)
        self.manager.settings_changed.connect(self.overlay.apply_config)
        self.manager.settings_changed.connect(self._apply_tray_config)
        self.manager.close_requested.connect(self._quit_app)

        self.bridge = CursorBridge(self.overlay.update_cursor)
        self.dbus_registered = self.bridge.register_dbus()
        self.bridge.install_kwin_script()
        print(
            f"Cursor Companion 0.1.0-dev: tray menu includes 'Quit'; "
            f"dbus_registered={self.dbus_registered}; qt_platform={os.environ.get('QT_QPA_PLATFORM', 'default')}",
            flush=True,
        )

        self.poll_timer = QTimer()
        self.poll_timer.setInterval(33)
        self.poll_timer.timeout.connect(self._poll_cursor)
        self.poll_timer.start()

        self.tray = QSystemTrayIcon(QIcon.fromTheme("input-mouse"), self.qt)
        self.tray.setToolTip("Cursor Companion")
        self.tray.setContextMenu(self._tray_menu())
        self.tray.activated.connect(self._tray_activated)
        self._apply_tray_config()

        first_launch = not self.config_store.config.active_pet_id and not self.pet_store.list_pets()
        if first_launch:
            self._import_existing_cursor_companion()
        self.set_active_pet(self.config_store.config.active_pet_id or "")
        self._poll_cursor()
        if show_manager or first_launch:
            self._show_manager()

    def run(self) -> int:
        result = self.qt.exec()
        if self.bridge:
            self.bridge.unload_kwin_script()
        return result

    def set_active_pet(self, pet_id: str) -> None:
        self.overlay.set_pet(self.pet_store.get(pet_id))
        self._refresh_tray_menu()

    def _tray_menu(self) -> QMenu:
        self.menu = QMenu()
        self.show_manager_action = QAction("Open Manager")
        self.show_manager_action.triggered.connect(self._show_manager)
        self.toggle_action = QAction("Hide Pet")
        self.toggle_action.triggered.connect(self._toggle_pet)
        self.pets_menu = QMenu("Active Pet")
        self.quit_action = QAction("Quit", self.menu)
        self.quit_action.triggered.connect(self._quit_app)
        self.menu.addAction(self.show_manager_action)
        self.menu.addAction(self.toggle_action)
        self.menu.addMenu(self.pets_menu)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)
        return self.menu

    def _refresh_tray_menu(self) -> None:
        self.pets_menu.clear()
        for pet in self.pet_store.list_pets():
            action = QAction(pet.display_name, self.pets_menu)
            action.setCheckable(True)
            action.setChecked(pet.id == self.config_store.config.active_pet_id)
            action.triggered.connect(lambda checked=False, pet_id=pet.id: self._activate_from_tray(pet_id))
            self.pets_menu.addAction(action)
        if not self.pets_menu.actions():
            empty = QAction("No pets imported", self.pets_menu)
            empty.setEnabled(False)
            self.pets_menu.addAction(empty)
        self.toggle_action.setText("Hide Pet" if self.config_store.config.visible else "Show Pet")

    def _activate_from_tray(self, pet_id: str) -> None:
        self.config_store.config.active_pet_id = pet_id
        self.config_store.save()
        self.manager.refresh_pets()
        self.set_active_pet(pet_id)

    def _toggle_pet(self) -> None:
        cfg = self.config_store.config
        cfg.visible = not cfg.visible
        self.config_store.save()
        self.overlay.apply_config()
        self._refresh_tray_menu()

    def _quit_app(self) -> None:
        self.overlay.hide()
        self.tray.hide()
        self.qt.quit()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if self.config_store.config.keep_open_in_tray and reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_manager()

    def _poll_cursor(self) -> None:
        if self.bridge and self.bridge.last_update > 0:
            return
        pos: QPoint = QCursor.pos()
        self.overlay.update_cursor(pos.x(), pos.y())

    def _import_existing_cursor_companion(self) -> None:
        codex_dir = Path.home() / ".codex" / "pets"
        if not codex_dir.exists():
            return
        last_pet_id = None
        for pet_json in sorted(codex_dir.glob("*/pet.json")):
            try:
                pet = self.pet_store.import_directory(pet_json.parent)
            except ValueError:
                continue
            last_pet_id = pet.id
        if last_pet_id:
            self.config_store.config.active_pet_id = last_pet_id
            self.config_store.save()
            self.manager.refresh_pets()

    def _show_manager(self) -> None:
        self.manager.show()
        self.manager.raise_()
        self.manager.activateWindow()

    def _apply_tray_config(self) -> None:
        if self.config_store.config.keep_open_in_tray:
            self.tray.show()
            self.qt.setQuitOnLastWindowClosed(False)
        else:
            self.tray.hide()
            self.qt.setQuitOnLastWindowClosed(True)


def main() -> int:
    app = CursorPetApp(show_manager="--background" not in sys.argv)
    return app.run()
