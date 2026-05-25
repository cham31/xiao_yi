"""
Pet-side chat UI: a following input bubble plus a speech bubble near XiaoYi.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QEvent, QPoint, QRect, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pet_player.ai_client import request_chat_completion
from pet_player.ai_config import AiApiConfig


CHAT_GAP = 10


class ChatRequestWorker(QObject):
    """Runs one chat request outside the UI thread."""

    finished = pyqtSignal(bool, str)

    def __init__(self, config: AiApiConfig, messages: list[dict[str, str]]):
        super().__init__()
        self._config = config
        self._messages = [dict(item) for item in messages]

    def run(self) -> None:
        ok, message = request_chat_completion(self._config, self._messages)
        self.finished.emit(ok, message)


class PetChatInputBubble(QDialog):
    """A compact input bubble that follows the pet. Enter sends the message."""

    send_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("和小艺说话")
        self._anchor: QWidget | None = None
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(300)

        self._input = QTextEdit()
        self._input.setFixedHeight(82)
        self._input.setPlaceholderText("输入后 Enter 发送")
        self._input.installEventFilter(self)
        self._input.setStyleSheet(
            "QTextEdit {"
            "  background: #fff7fb;"
            "  border: 1px solid #dbcfe2;"
            "  border-radius: 8px;"
            "  color: #2b2430;"
            "  font-size: 13px;"
            "  padding: 9px 11px;"
            "}"
            "QTextEdit:disabled {"
            "  color: #746d7b;"
            "}"
        )

        self._build_layout()

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._input)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._input and event.type() == QEvent.Type.KeyPress:
            key_event = event
            if isinstance(key_event, QKeyEvent) and key_event.key() in (
                Qt.Key.Key_Return,
                Qt.Key.Key_Enter,
            ):
                self._emit_send()
                return True
        return super().eventFilter(watched, event)

    def show_near(self, anchor: QWidget) -> None:
        self._anchor = anchor
        self.adjustSize()
        self.move(self.default_position(anchor))
        self.show()
        self.raise_()
        self.activateWindow()
        self._input.setFocus()

    def set_busy(self, busy: bool) -> None:
        self._input.setEnabled(not busy)
        self._input.setPlaceholderText("小艺思考中..." if busy else "输入后 Enter 发送")
        if not busy:
            self._input.setFocus()

    def restore_text(self, text: str) -> None:
        self._input.setPlainText(text)
        self._input.setFocus()

    def ready_for_next_message(self) -> None:
        self._input.setPlaceholderText("小艺回复啦，可以继续输入")
        self._input.setFocus()

    def _emit_send(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._input.clear()
        self.send_requested.emit(text)

    def move_to(self, pos: QPoint) -> None:
        if self.pos() == pos:
            return
        self.move(pos)

    def default_position(self, anchor: QWidget) -> QPoint:
        self.adjustSize()
        screen = QApplication.screenAt(anchor.geometry().center()) or QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else QRect(0, 0, 1280, 720)

        x = anchor.x() - self.width() - CHAT_GAP
        y = anchor.y() + (anchor.height() - self.height()) // 2
        x = max(available.left(), min(x, available.right() - self.width()))
        y = max(available.top(), min(y, available.bottom() - self.height()))
        return QPoint(x, y)


class SpeechBubbleWindow(QWidget):
    """A lightweight speech bubble that follows the pet window."""

    MAX_TEXT_CHARS = 360

    def __init__(self, anchor: QWidget):
        super().__init__(None)
        self._anchor = anchor
        self._autohide_timer = QTimer(self)
        self._autohide_timer.setSingleShot(True)
        self._autohide_timer.timeout.connect(self.hide)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._label.setMaximumWidth(280)
        self._label.setStyleSheet(
            "QLabel {"
            "  background: #fff7fb;"
            "  border: 1px solid #dbcfe2;"
            "  border-radius: 8px;"
            "  color: #2b2430;"
            "  font-size: 13px;"
            "  line-height: 1.45;"
            "  padding: 10px 12px;"
            "}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._label)

    def show_message(self, text: str, timeout_ms: int | None = None) -> None:
        self._label.setText(self._trim_text(text))
        self.adjustSize()
        self.move(self.default_position())
        self.show()
        self.raise_()

        self._autohide_timer.stop()
        if timeout_ms is None:
            timeout_ms = max(6500, min(18000, len(text) * 90))
        if timeout_ms > 0:
            self._autohide_timer.start(timeout_ms)

    def show_thinking(self) -> None:
        self.show_message("我想想...", timeout_ms=0)

    def reposition(self) -> None:
        self.move(self.default_position())

    def _trim_text(self, text: str) -> str:
        stripped = text.strip()
        if len(stripped) <= self.MAX_TEXT_CHARS:
            return stripped
        return stripped[: self.MAX_TEXT_CHARS - 1].rstrip() + "..."

    def move_to(self, pos: QPoint) -> None:
        if self.pos() == pos:
            return
        self.move(pos)

    def default_position(self) -> QPoint:
        self.adjustSize()
        screen = QApplication.screenAt(self._anchor.geometry().center()) or QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else QRect(0, 0, 1280, 720)

        x = self._anchor.x() - self.width() - CHAT_GAP
        y = self._anchor.y() - self.height() - CHAT_GAP
        x = max(available.left(), min(x, available.right() - self.width()))
        y = max(available.top(), min(y, available.bottom() - self.height()))
        return QPoint(x, y)
