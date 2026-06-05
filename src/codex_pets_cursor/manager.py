from __future__ import annotations

import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .autostart import set_autostart
from .browser import BrowserPage
from .config import ConfigStore
from .pets import Pet, PetStore


class ManagerWindow(QWidget):
    active_pet_changed = pyqtSignal(str)
    settings_changed = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self, config_store: ConfigStore, pet_store: PetStore) -> None:
        super().__init__()
        self.config_store = config_store
        self.pet_store = pet_store
        self.setWindowTitle("Codex Pets Cursor")
        self.resize(920, 680)

        tabs = QTabWidget()
        self.browser = BrowserPage()
        self.browser.downloaded.connect(self.import_download)
        tabs.addTab(self.browser, "Browser")
        tabs.addTab(self._collection_tab(), "Collection")
        tabs.addTab(self._settings_tab(), "Settings")

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        self.refresh_pets()

    def import_download(self, path: Path) -> None:
        try:
            pet = self.pet_store.import_zip(path)
        except ValueError as exc:
            QMessageBox.warning(self, "Import failed", str(exc))
            return
        self.config_store.config.active_pet_id = pet.id
        self.config_store.save()
        self.refresh_pets()
        self.active_pet_changed.emit(pet.id)

    def refresh_pets(self) -> None:
        self.pet_list.clear()
        for pet in self.pet_store.list_pets():
            item = QListWidgetItem(pet.display_name)
            item.setData(Qt.ItemDataRole.UserRole, pet.id)
            if pet.id == self.config_store.config.active_pet_id:
                item.setText(f"{pet.display_name} (active)")
            self.pet_list.addItem(item)

    def _collection_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.pet_list = QListWidget()
        self.pet_list.currentItemChanged.connect(self._selected_pet_changed)
        layout.addWidget(self.pet_list)

        self.preview = QLabel("No pet selected")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(180)
        layout.addWidget(self.preview)

        row = QHBoxLayout()
        import_folder = QPushButton("Import Folder")
        import_zip = QPushButton("Import ZIP")
        import_codex = QPushButton("Import Codex Pets")
        activate = QPushButton("Activate")
        remove = QPushButton("Remove")
        open_folder = QPushButton("Open Folder")
        import_folder.clicked.connect(self._import_folder)
        import_zip.clicked.connect(self._import_zip)
        import_codex.clicked.connect(self._import_codex_pets)
        activate.clicked.connect(self._activate_selected)
        remove.clicked.connect(self._remove_selected)
        open_folder.clicked.connect(self._open_selected_folder)
        for button in (import_folder, import_zip, import_codex, activate, remove, open_folder):
            row.addWidget(button)
        layout.addLayout(row)
        return page

    def _settings_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        cfg = self.config_store.config

        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(15, 100)
        self.scale_slider.setValue(int(cfg.scale * 100))
        self.scale_slider.valueChanged.connect(self._save_settings)

        self.offset_x = QSpinBox()
        self.offset_x.setRange(-300, 300)
        self.offset_x.setValue(cfg.offset_x)
        self.offset_x.valueChanged.connect(self._save_settings)

        self.offset_y = QSpinBox()
        self.offset_y.setRange(-300, 300)
        self.offset_y.setValue(cfg.offset_y)
        self.offset_y.valueChanged.connect(self._save_settings)

        self.autostart = QCheckBox()
        self.autostart.setChecked(cfg.autostart)
        self.autostart.toggled.connect(self._save_settings)

        self.keep_open_in_tray = QCheckBox()
        self.keep_open_in_tray.setChecked(cfg.keep_open_in_tray)
        self.keep_open_in_tray.toggled.connect(self._save_settings)

        form.addRow("Scale", self.scale_slider)
        form.addRow("X offset", self.offset_x)
        form.addRow("Y offset", self.offset_y)
        form.addRow("Start in tray at login", self.autostart)
        form.addRow("Keep open in tray", self.keep_open_in_tray)
        close_app = QPushButton("Close App")
        close_app.clicked.connect(self.close_requested.emit)
        form.addRow(close_app)
        return page

    def _save_settings(self) -> None:
        cfg = self.config_store.config
        cfg.scale = self.scale_slider.value() / 100
        cfg.offset_x = self.offset_x.value()
        cfg.offset_y = self.offset_y.value()
        cfg.autostart = self.autostart.isChecked()
        cfg.keep_open_in_tray = self.keep_open_in_tray.isChecked()
        if cfg.autostart and not cfg.keep_open_in_tray:
            cfg.keep_open_in_tray = True
            self.keep_open_in_tray.blockSignals(True)
            self.keep_open_in_tray.setChecked(True)
            self.keep_open_in_tray.blockSignals(False)
        set_autostart(cfg.autostart, background=True)
        self.config_store.save()
        self.settings_changed.emit()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.config_store.config.keep_open_in_tray:
            event.ignore()
            self.hide()
            return
        self.close_requested.emit()
        event.accept()

    def _selected_pet_changed(self) -> None:
        pet = self._selected_pet()
        if not pet:
            self.preview.setText("No pet selected")
            return
        pixmap = QPixmap(str(pet.spritesheet))
        if pixmap.isNull():
            self.preview.setText(pet.description or pet.display_name)
            return
        frame = pixmap.copy(0, 0, pixmap.width() // 8, pixmap.height() // 9)
        self.preview.setPixmap(frame.scaled(160, 180, Qt.AspectRatioMode.KeepAspectRatio))

    def _selected_pet(self) -> Pet | None:
        item = self.pet_list.currentItem()
        if not item:
            return None
        return self.pet_store.get(item.data(Qt.ItemDataRole.UserRole))

    def _activate_selected(self) -> None:
        pet = self._selected_pet()
        if not pet:
            return
        self.config_store.config.active_pet_id = pet.id
        self.config_store.save()
        self.refresh_pets()
        self.active_pet_changed.emit(pet.id)

    def _remove_selected(self) -> None:
        pet = self._selected_pet()
        if not pet:
            return
        self.pet_store.remove(pet.id)
        if self.config_store.config.active_pet_id == pet.id:
            self.config_store.config.active_pet_id = None
            self.config_store.save()
            self.active_pet_changed.emit("")
        self.refresh_pets()

    def _open_selected_folder(self) -> None:
        pet = self._selected_pet()
        if pet:
            subprocess.Popen(["xdg-open", str(pet.directory)])

    def _import_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Import Codex pet folder")
        if folder:
            try:
                pet = self.pet_store.import_directory(Path(folder))
            except ValueError as exc:
                QMessageBox.warning(self, "Import failed", str(exc))
                return
            self.config_store.config.active_pet_id = pet.id
            self.config_store.save()
            self.refresh_pets()
            self.active_pet_changed.emit(pet.id)

    def _import_zip(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Import Codex pet ZIP", "", "ZIP files (*.zip)")
        if filename:
            self.import_download(Path(filename))

    def _import_codex_pets(self) -> None:
        codex_dir = Path.home() / ".codex" / "pets"
        if not codex_dir.exists():
            QMessageBox.information(self, "No Codex pets found", "No ~/.codex/pets folder was found.")
            return
        imported = 0
        last_pet: Pet | None = None
        for pet_json in sorted(codex_dir.glob("*/pet.json")):
            try:
                last_pet = self.pet_store.import_directory(pet_json.parent)
                imported += 1
            except ValueError:
                continue
        if last_pet:
            self.config_store.config.active_pet_id = last_pet.id
            self.config_store.save()
            self.active_pet_changed.emit(last_pet.id)
        self.refresh_pets()
        QMessageBox.information(self, "Import complete", f"Imported {imported} Codex pet package(s).")
