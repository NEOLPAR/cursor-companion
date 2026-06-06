from __future__ import annotations

import time
import random
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import QPoint, QPointF, QRect, QSize, Qt, QTimer
from PyQt6.QtGui import QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QWidget

from .config import AppConfig
from .pets import Pet


class Motion(Enum):
    IDLE = 0
    RIGHT = 1
    LEFT = 2
    UP = 4


@dataclass(frozen=True)
class WanderSpec:
    row: int
    min_seconds: float
    max_seconds: float
    dx: float
    dy: float


class PetOverlay(QWidget):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.pet: Pet | None = None
        self.sheet = QImage()
        self.motion = Motion.IDLE
        self.current_row = Motion.IDLE.value
        self.frame = 0
        self.last_pos: QPoint | None = None
        self.last_frame_time = time.monotonic()
        self.last_cursor_time = 0.0
        self.target_pos = QPoint(0, 0)
        self.cursor_target_pos = QPoint(0, 0)
        self.companion_pos = QPointF(0, 0)
        self.has_cursor_position = False
        self.wandering = False
        self.returning_to_cursor = False
        self.wander_action: WanderSpec | None = None
        self.wander_action_started = 0.0
        self.wander_action_duration = 0.0
        self.last_wander_row: int | None = None
        self.pending_wander_pause = False
        self.cell_width = 192
        self.cell_height = 208
        self.frame_counts: dict[Motion, int] = {motion: 1 for motion in Motion}
        self.row_frame_counts: dict[int, int] = {row: 1 for row in range(9)}

        self.setWindowTitle("Cursor Companion Overlay")
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
            self.row_frame_counts = self._detect_row_frame_counts()
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
        self.cursor_target_pos = QPoint(x + self.config.offset_x, y + self.config.offset_y)
        self.has_cursor_position = True
        if moved:
            self.last_cursor_time = time.monotonic()
            if self.wandering:
                self.wandering = False
                self.returning_to_cursor = True
                self.pending_wander_pause = False
            elif not self.returning_to_cursor:
                self.companion_pos = QPointF(self.cursor_target_pos)
                self.target_pos = QPoint(self.cursor_target_pos)
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
        row = self.current_row
        frame = self.frame % self.row_frame_counts.get(row, 1)
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
        now = time.monotonic()
        if self.returning_to_cursor:
            self._return_to_cursor()
        elif self.last_cursor_time and now - self.last_cursor_time > 0.14:
            idle_elapsed_ms = (now - self.last_cursor_time) * 1000
            if self.config.wander_when_idle and idle_elapsed_ms >= self.config.wander_idle_delay_ms:
                self._tick_wander(now)
            elif not self.wandering:
                self._set_motion(Motion.IDLE)
        self.frame = (self.frame + 1) % self.row_frame_counts.get(self.current_row, 1)
        self.move(self.target_pos)
        self.update()

    def _set_motion(self, motion: Motion) -> None:
        if motion != self.motion or self.current_row != motion.value:
            was_idle = self.motion == Motion.IDLE
            self.motion = motion
            self.current_row = motion.value
            if was_idle or motion == Motion.IDLE:
                self.frame = 0
            else:
                self.frame %= self.row_frame_counts.get(self.current_row, 1)

    def _tick_wander(self, now: float) -> None:
        if not self.wandering:
            self.wandering = True
            self.companion_pos = QPointF(self.target_pos)
            self._start_wander_action(now)
        elif now - self.wander_action_started >= self.wander_action_duration:
            self._start_wander_action(now)
        if not self.wander_action:
            return
        next_pos = QPointF(
            self.companion_pos.x() + self.wander_action.dx,
            self.companion_pos.y() + self.wander_action.dy,
        )
        clamped = self._clamp_to_desktop(next_pos)
        if clamped != next_pos:
            self._start_wander_action(now)
            if not self.wander_action:
                return
            next_pos = self._clamp_to_desktop(
                QPointF(
                    self.companion_pos.x() + self.wander_action.dx,
                    self.companion_pos.y() + self.wander_action.dy,
                )
            )
        self.companion_pos = next_pos
        self.target_pos = QPoint(round(next_pos.x()), round(next_pos.y()))
        self._set_row(self.wander_action.row)

    def _start_wander_action(self, now: float) -> None:
        if not self.pending_wander_pause and self.wander_action is not None:
            self.pending_wander_pause = True
            self.wander_action = WanderSpec(0, 2, 2, 0, 0)
            self.wander_action_started = now
            self.wander_action_duration = 2.0
            self._set_motion(Motion.IDLE)
            return
        self.pending_wander_pause = False
        specs = [
            WanderSpec(1, 3, 15, 5.0, 0),
            WanderSpec(2, 3, 15, -5.0, 0),
            WanderSpec(3, 2, 5, 0, 0),
            WanderSpec(4, 2, 5, 0, random.choice([-3.4, 3.4])),
            WanderSpec(5, 3, 8, 0, 0),
            WanderSpec(6, 3, 5, 0, 0),
            WanderSpec(7, 3, 5, 0, 0),
            WanderSpec(8, 3, 5, 0, 0),
        ]
        choices = [spec for spec in specs if spec.row != self.last_wander_row] or specs
        self.wander_action = random.choice(choices)
        self.last_wander_row = self.wander_action.row
        self.wander_action_started = now
        self.wander_action_duration = random.uniform(
            self.wander_action.min_seconds,
            self.wander_action.max_seconds,
        )
        self._set_row(self.wander_action.row)

    def _return_to_cursor(self) -> None:
        current = QPointF(self.target_pos)
        target = QPointF(self.cursor_target_pos)
        dx = target.x() - current.x()
        dy = target.y() - current.y()
        distance = (dx * dx + dy * dy) ** 0.5
        if distance <= 6:
            self.returning_to_cursor = False
            self.companion_pos = QPointF(target)
            self.target_pos = QPoint(round(target.x()), round(target.y()))
            self._set_motion(Motion.IDLE)
            return
        step = min(4.0, distance)
        nx = current.x() + dx / distance * step
        ny = current.y() + dy / distance * step
        self.companion_pos = QPointF(nx, ny)
        self.target_pos = QPoint(round(nx), round(ny))
        if abs(dy) >= abs(dx) * 0.5:
            self._set_motion(Motion.UP)
        elif dx < 0:
            self._set_motion(Motion.LEFT)
        else:
            self._set_motion(Motion.RIGHT)

    def _set_row(self, row: int) -> None:
        row = max(0, min(8, row))
        old_row = self.current_row
        self.current_row = row
        if row in {motion.value for motion in Motion}:
            self.motion = Motion(row)
        if row != old_row:
            self.frame %= self.row_frame_counts.get(row, 1)

    def _desktop_geometry(self) -> QRect:
        screen = self.screen()
        virtual = screen.virtualGeometry() if screen else None
        return virtual if virtual else QRect(0, 0, 1920, 1080)

    def _clamp_to_desktop(self, pos: QPointF) -> QPointF:
        geometry = self._desktop_geometry()
        min_x = geometry.left()
        min_y = geometry.top()
        max_x = max(min_x, geometry.right() - self.width())
        max_y = max(min_y, geometry.bottom() - self.height())
        return QPointF(
            max(min_x, min(max_x, pos.x())),
            max(min_y, min(max_y, pos.y())),
        )

    def _resize_to_config(self) -> None:
        width = max(24, int(self.cell_width * self.config.scale))
        height = max(24, int(self.cell_height * self.config.scale))
        self.resize(QSize(width, height))

    def _detect_frame_counts(self) -> dict[Motion, int]:
        return {motion: max(1, self._non_empty_frames_for_row(motion.value)) for motion in Motion}

    def _detect_row_frame_counts(self) -> dict[int, int]:
        return {row: max(1, self._non_empty_frames_for_row(row)) for row in range(9)}

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
