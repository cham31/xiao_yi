"""
交互层 — 悬停、点击拖拽、扔出去物理、右键菜单
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer, QPoint, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu


class DragPhysics(QObject):
    """简单抛掷物理：释放时根据速度衰减滑动"""

    landed = pyqtSignal()

    FRICTION = 0.92
    MIN_SPEED = 0.5

    def __init__(self, move_callback, parent: QObject | None = None):
        super().__init__(parent)
        self._move = move_callback
        self._velocity = QPoint(0, 0)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._active = False

    @property
    def velocity(self) -> QPoint:
        return self._velocity

    def add_sample(self, delta: QPoint) -> None:
        """拖拽过程中采样位移，估算速度"""
        self._velocity = delta

    def release(self, throw_scale: float = 1.5) -> float:
        """
        启动惯性滑动，返回预估抛掷距离（像素）
        """
        self._velocity = QPoint(
            int(self._velocity.x() * throw_scale),
            int(self._velocity.y() * throw_scale),
        )
        distance = (self._velocity.x() ** 2 + self._velocity.y() ** 2) ** 0.5
        if distance > self.MIN_SPEED:
            self._active = True
            self._timer.start(16)
        return distance

    def stop(self) -> None:
        self._active = False
        self._timer.stop()
        self._velocity = QPoint(0, 0)

    def _tick(self) -> None:
        if not self._active:
            return
        self._move(self._velocity)
        self._velocity = QPoint(
            int(self._velocity.x() * self.FRICTION),
            int(self._velocity.y() * self.FRICTION),
        )
        speed = (self._velocity.x() ** 2 + self._velocity.y() ** 2) ** 0.5
        if speed < DragPhysics.MIN_SPEED:
            self.stop()
            self.landed.emit()


class InteractionHandler(QObject):
    """鼠标交互与右键菜单"""

    clicked = pyqtSignal()
    drag_started = pyqtSignal()
    drag_ended = pyqtSignal(float)  # throw distance
    hover_changed = pyqtSignal(bool)
    expression_forced = pyqtSignal(str)
    ai_chat_requested = pyqtSignal()
    ai_settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, parent_widget, parent: QObject | None = None):
        super().__init__(parent)
        self._widget = parent_widget
        self._dragging = False
        self._drag_started_emitted = False
        self._drag_start = QPoint()
        self._window_start = QPoint()
        self._last_pos = QPoint()
        self._hovering = False

        self._physics = DragPhysics(self._apply_velocity, self)

    @property
    def is_dragging(self) -> bool:
        return self._dragging

    def hit_opaque(self, local_x: int, local_y: int, alpha_at) -> bool:
        """alpha_at(x,y) -> 0-255；不透明才响应"""
        return alpha_at(local_x, local_y) >= 50

    def on_mouse_press(self, global_pos: QPoint, local_x: int, local_y: int, alpha_at) -> bool:
        if not self.hit_opaque(local_x, local_y, alpha_at):
            return False
        self._physics.stop()
        self._dragging = True
        self._drag_started_emitted = False
        self._drag_start = global_pos
        self._window_start = self._widget.pos()
        self._last_pos = global_pos
        self.clicked.emit()
        return True

    def on_mouse_move(self, global_pos: QPoint, hovering: bool = False) -> None:
        if self._dragging:
            if not self._drag_started_emitted:
                moved = (global_pos - self._drag_start).manhattanLength()
                if moved > 4:
                    self._drag_started_emitted = True
                    self.drag_started.emit()
            delta = global_pos - self._last_pos
            self._last_pos = global_pos
            prev = self._widget.pos()
            self._widget.move(self._window_start + (global_pos - self._drag_start))
            moved = self._widget.pos() - prev
            self._physics.add_sample(moved)
        if hovering != self._hovering:
            self._hovering = hovering
            self.hover_changed.emit(hovering)

    def on_mouse_release(self) -> None:
        if not self._dragging:
            return
        self._dragging = False
        throw_dist = self._physics.release()
        self.drag_ended.emit(throw_dist)

    def _apply_velocity(self, velocity: QPoint) -> None:
        self._widget.move(self._widget.pos() + velocity)

    def show_context_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self._widget)
        menu.setStyleSheet(
            "QMenu { background: #2a2030; color: #fff; border: 1px solid #554; }"
            "QMenu::item:selected { background: #6a5080; }"
        )

        expr_menu = menu.addMenu("切换表情")
        for label, key in [
            ("默认", "idle"), ("微笑", "smile"), ("大笑", "grin"),
            ("流汗", "sweat"), ("生气", "angry"), ("睡觉", "sleep"),
        ]:
            act = expr_menu.addAction(label)
            act.triggered.connect(lambda _, k=key: self.expression_forced.emit(k))

        menu.addSeparator()
        menu.addAction("和小艺聊天", self.ai_chat_requested.emit)
        menu.addAction("AI 设置", self.ai_settings_requested.emit)

        menu.addSeparator()
        menu.addAction("退出", self.quit_requested.emit)
        menu.exec(global_pos)
