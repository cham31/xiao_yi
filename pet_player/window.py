"""
窗口层 — 无边框透明置顶 + Alpha 精确鼠标穿透 + 拖拽
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt, QTimer, QAbstractNativeEventFilter, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QPixmap, QImage, QColor, QMouseEvent
from PyQt6.QtWidgets import QWidget, QApplication

from pet_player.interaction import InteractionHandler
from pet_player.renderer import DISPLAY_SIZE

# Windows WM_NCHITTEST
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    HTTRANSPARENT = -1
    WM_NCHITTEST = 0x0084


    class POINT(ctypes.Structure):
        _fields_ = [
            ("x", wintypes.LONG),
            ("y", wintypes.LONG),
        ]


    class MSG(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt", POINT),
        ]


class AlphaPassthroughFilter(QAbstractNativeEventFilter):
    """Windows 鼠标穿透：alpha < threshold 的区域返回 HTTRANSPARENT。

    使用 QAbstractNativeEventFilter 而非覆盖 nativeEvent，
    避免 PyQt6 6.11.0 的 nativeEvent 覆盖导致 segfault 的问题。
    """

    def __init__(self, window: PetWindow, threshold: int = 50):
        super().__init__()
        self._window = window
        self._threshold = threshold
        self._hwnd = int(window.winId())

    def nativeEventFilter(self, eventType, message) -> tuple[bool, int]:
        if sys.platform != "win32":
            return False, 0
        if eventType != b"windows_generic_MSG":
            return False, 0

        ptr = int(message)
        if not ptr:
            return False, 0

        try:
            msg = MSG.from_address(ptr)
            if int(msg.hwnd) != self._hwnd:
                return False, 0

            if msg.message != WM_NCHITTEST:
                return False, 0

            win = self._window
            gp = win.cursor().pos()
            lp = win.mapFromGlobal(gp)
            if win.alpha_at(lp.x(), lp.y()) < self._threshold:
                return True, HTTRANSPARENT
        except Exception:
            pass
        return False, 0


class PetWindow(QWidget):
    """
    桌面宠物窗口
    - 无边框、透明背景、置顶、不在任务栏
    - alpha < 50 区域鼠标穿透（通过 AlphaPassthroughFilter）
    - 不透明区域可拖拽
    """

    ALPHA_THRESHOLD = 50
    moved = pyqtSignal()

    def __init__(self, size: int = DISPLAY_SIZE):
        super().__init__()
        self._size = size
        self._current_pixmap: QPixmap | None = None
        self._alpha_image: QImage | None = None
        self._screen_margins = (0, 0, 0, 0)

        self.interaction = InteractionHandler(self)

        self._setup_window()
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._on_cursor_tick)
        self._cursor_timer.start(33)

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def install_alpha_filter(self, app: QApplication) -> None:
        """在 QApplication 上安装原生事件过滤器（由 App 控制器调用）"""
        self._alpha_filter = AlphaPassthroughFilter(self, self.ALPHA_THRESHOLD)
        app.installNativeEventFilter(self._alpha_filter)

    def set_frame(self, pixmap: QPixmap) -> None:
        self._current_pixmap = pixmap
        self._rebuild_alpha_mask()
        self.update()

    def alpha_at(self, x: int, y: int) -> int:
        if self._alpha_image is None:
            return 0
        if x < 0 or y < 0 or x >= self._alpha_image.width() or y >= self._alpha_image.height():
            return 0
        return QColor(self._alpha_image.pixel(x, y)).alpha()

    def move(self, *args) -> None:
        if len(args) == 1 and isinstance(args[0], QPoint):
            super().move(self._clamped_pos(args[0]))
            return
        if len(args) == 2:
            super().move(self._clamped_pos(QPoint(int(args[0]), int(args[1]))))
            return
        super().move(*args)

    def set_screen_margins(self, left: int = 0, top: int = 0, right: int = 0, bottom: int = 0) -> None:
        """Reserve dynamic space for visible companion widgets without changing screen bounds."""
        self._screen_margins = (
            max(0, left),
            max(0, top),
            max(0, right),
            max(0, bottom),
        )
        self.move(self.pos())

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setFixedSize(self._size, self._size)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.right() - self._size - 40, geo.bottom() - self._size - 80)

    def _clamped_pos(self, pos: QPoint) -> QPoint:
        screen = QApplication.screenAt(pos + QPoint(self.width() // 2, self.height() // 2))
        if screen is None:
            screen = QApplication.screenAt(self.pos() + QPoint(self.width() // 2, self.height() // 2))
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return pos

        geo = screen.availableGeometry()
        left_margin, top_margin, right_margin, bottom_margin = self._screen_margins
        min_x = geo.left() + left_margin
        min_y = geo.top() + top_margin
        max_x = geo.right() - self.width() - right_margin + 1
        max_y = geo.bottom() - self.height() - bottom_margin + 1
        if min_x > max_x:
            min_x = max_x = geo.left() + max(0, (geo.width() - self.width()) // 2)
        if min_y > max_y:
            min_y = max_y = geo.top() + max(0, (geo.height() - self.height()) // 2)
        return QPoint(
            max(min_x, min(pos.x(), max_x)),
            max(min_y, min(pos.y(), max_y)),
        )

    def _rebuild_alpha_mask(self) -> None:
        if self._current_pixmap.isNull():
            self._alpha_image = None
            return
        self._alpha_image = self._current_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)

    # ------------------------------------------------------------------
    # Qt 事件
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if self._current_pixmap and not self._current_pixmap.isNull():
            p.drawPixmap(0, 0, self._current_pixmap)
        p.end()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        self.moved.emit()

    def _on_cursor_tick(self) -> None:
        if not self.interaction.is_dragging:
            local = self.mapFromGlobal(self.cursor().pos())
            inside = 0 <= local.x() < self.width() and 0 <= local.y() < self.height()
            opaque = inside and self.alpha_at(local.x(), local.y()) >= self.ALPHA_THRESHOLD
            self.interaction.on_mouse_move(self.cursor().pos(), hovering=opaque)
            if opaque:
                self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.interaction.show_context_menu(event.globalPosition().toPoint())
            return
        if event.button() == Qt.MouseButton.LeftButton:
            lp = event.position().toPoint()
            if self.interaction.on_mouse_press(
                event.globalPosition().toPoint(), lp.x(), lp.y(), self.alpha_at
            ):
                self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        lp = event.position().toPoint()
        opaque = self.alpha_at(lp.x(), lp.y()) >= self.ALPHA_THRESHOLD
        if self.interaction.is_dragging:
            self.interaction.on_mouse_move(event.globalPosition().toPoint())
        elif opaque:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.interaction.on_mouse_move(event.globalPosition().toPoint(), hovering=True)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.interaction.on_mouse_release()
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def enterEvent(self, event) -> None:
        self.interaction.on_mouse_move(self.cursor().pos(), hovering=True)

    def leaveEvent(self, event) -> None:
        self.interaction.on_mouse_move(self.cursor().pos(), hovering=False)
