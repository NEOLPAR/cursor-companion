from __future__ import annotations

import time
from enum import Enum

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PyQt6.QtGui import QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QWidget

from .config import AppConfig
from .pets import Pet


class Motion(Enum):
    IDLE = 0
    RIGHT = 1
    LEFT = 2
    UP = 4


class PetOverlay(QWidget):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.pet: Pet | None = None
        self.sheet = QImage()
        self.motion = Motion.IDLE
        self.frame = 0
        self.last_pos: QPoint | None = None
        self.last_frame_time = time.monotonic()
        self.last_cursor_time = 0.0
        self.target_pos = QPoint(0, 0)
        self.has_cursor_position = False
        self.cell_width = 192
        self.cell_height = 208
        self.frame_counts: dict[Motion, int] = {motion: 1 for motion in Motion}

        self.setWindowTitle("Codex Pets Cursor Overlay")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop)

        self.timer = QTimer(self)
        self.timer.setInterval(90)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def set_pet(self, pet: Pet | None) -> None:
        self.pet = pet
        self.sheet = QImage(str(pet.spritesheet)) if pet else QImage()
        if not self.sheet.isNull():
            self.cell_width = max(1, self.sheet.width() // 8)
            self.cell_height = max(1, self.sheet.height() // 9)
            self.frame_counts = self._detect_frame_counts()
            self.frame = 0
            self._resize_to_config()
            if self.config.visible and self.has_cursor_position:
                self.show()
        else:
            self.hide()
        self.update()

    def apply_config(self) -> None:
        self._resize_to_config()
        if not self.config.visible:
            self.hide()
        elif self.pet and not self.sheet.isNull() and self.has_cursor_position:
            self.show()

    def update_cursor(self, x: int, y: int) -> QPoint:
        pos = QPoint(x, y)
        moved = self.last_pos is None or pos != self.last_pos
        self.target_pos = QPoint(x + self.config.offset_x, y + self.config.offset_y)
        self.has_cursor_position = True
        if moved:
            self.last_cursor_time = time.monotonic()
            self._set_motion(self._motion_for(pos))
        self.last_pos = pos
        self._resize_to_config()
        self.move(self.target_pos)
        if self.config.visible and self.pet and not self.sheet.isNull() and not self.isVisible():
            self.show()
        return QPoint(self.target_pos)

    def paintEvent(self, event) -> None:  # noqa: N802
        if self.sheet.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        row = self.motion.value
        frame = self.frame % self.frame_counts.get(self.motion, 1)
        source = QRect(frame * self.cell_width, row * self.cell_height, self.cell_width, self.cell_height)
        pixmap = QPixmap.fromImage(self.sheet.copy(source))
        painter.drawPixmap(self.rect(), pixmap)

    def _motion_for(self, pos: QPoint) -> Motion:
        if self.last_pos is None:
            return Motion.IDLE
        dx = pos.x() - self.last_pos.x()
        dy = pos.y() - self.last_pos.y()
        if dx == 0 and dy == 0:
            return Motion.IDLE
        if dy != 0 and abs(dy) >= max(1, abs(dx) * 0.5):
            return Motion.UP
        if dx < 0:
            return Motion.LEFT
        if dx > 0:
            return Motion.RIGHT
        return Motion.IDLE

    def _tick(self) -> None:
        if self.sheet.isNull():
            return
        if self.last_cursor_time and time.monotonic() - self.last_cursor_time > 0.14:
            self._set_motion(Motion.IDLE)
        self.frame = (self.frame + 1) % self.frame_counts.get(self.motion, 1)
        self.move(self.target_pos)
        self.update()

    def _set_motion(self, motion: Motion) -> None:
        if motion != self.motion:
            was_idle = self.motion == Motion.IDLE
            self.motion = motion
            if was_idle or motion == Motion.IDLE:
                self.frame = 0
            else:
                self.frame %= self.frame_counts.get(motion, 1)

    def _resize_to_config(self) -> None:
        width = max(24, int(self.cell_width * self.config.scale))
        height = max(24, int(self.cell_height * self.config.scale))
        self.resize(QSize(width, height))

    def _detect_frame_counts(self) -> dict[Motion, int]:
        return {motion: max(1, self._non_empty_frames_for_row(motion.value)) for motion in Motion}

    def _non_empty_frames_for_row(self, row: int) -> int:
        count = 0
        for frame in range(8):
            if self._frame_has_visible_pixels(frame, row):
                count = frame + 1
        return count

    def _frame_has_visible_pixels(self, frame: int, row: int) -> bool:
        x0 = frame * self.cell_width
        y0 = row * self.cell_height
        step = max(1, min(self.cell_width, self.cell_height) // 24)
        for y in range(y0, y0 + self.cell_height, step):
            for x in range(x0, x0 + self.cell_width, step):
                if self.sheet.pixelColor(x, y).alpha() > 8:
                    return True
        return False
