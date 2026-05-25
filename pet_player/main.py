"""
三渲二桌面宠物 — 主入口
整合窗口 / 渲染 / 状态机 / 交互 / 系统托盘

注意: 必须先创建 QApplication，再加载 QPixmap / 创建窗口。
"""

from __future__ import annotations

import os
import sys
import traceback

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PyQt6.QtGui import QIcon

from pet_player.ai_config import load_ai_config
from pet_player.ai_settings_dialog import AiSettingsDialog
from pet_player.pet_chat import (
    ChatRequestWorker,
    PetChatInputBubble,
    SpeechBubbleWindow,
)
from pet_player.renderer import AssetLoader, AnimationPlayer, DISPLAY_SIZE
from pet_player.window import PetWindow
from pet_player.state_machine import PetState, PetStateMachine


class PetApplication:
    """桌面宠物应用控制器"""

    def __init__(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._assets_dir = os.path.join(base, "assets")
        self._loader = AssetLoader(self._assets_dir, DISPLAY_SIZE)

        self._assets: dict | None = None
        self._window: PetWindow | None = None
        self._player: AnimationPlayer | None = None
        self._state_machine: PetStateMachine | None = None
        self._tray: QSystemTrayIcon | None = None
        self._ai_chat_dialog: PetChatInputBubble | None = None
        self._ai_dialog: AiSettingsDialog | None = None
        self._speech_bubble: SpeechBubbleWindow | None = None
        self._chat_thread: QThread | None = None
        self._chat_worker: ChatRequestWorker | None = None
        self._chat_messages: list[dict[str, str]] = []
        self._pending_chat_text = ""
        self._updating_chat_bounds = False

        self._hovering = False
        self._forced_expr: str | None = None

    def _setup(self) -> None:
        """在 QApplication 创建之后初始化所有 Qt 资源"""
        self._assets = self._loader.load_all()
        self._window = PetWindow(DISPLAY_SIZE)
        self._window.install_alpha_filter(QApplication.instance())
        self._window.moved.connect(self._on_pet_moved)
        self._player = AnimationPlayer()
        self._player.bind_opacity(self._window)
        self._state_machine = PetStateMachine()
        self._wire_signals()

    def _wire_signals(self) -> None:
        sm = self._state_machine
        player = self._player
        inter = self._window.interaction

        player.frame_changed.connect(self._on_frame)
        player.finished.connect(sm.on_animation_finished)

        sm.request_animation.connect(self._play_for_request)
        inter.clicked.connect(sm.on_mouse_click)
        inter.drag_started.connect(self._on_drag_start)
        inter.drag_ended.connect(self._on_drag_end)
        inter.hover_changed.connect(self._on_hover)
        inter.expression_forced.connect(self._on_force_expression)
        inter.ai_chat_requested.connect(self._show_ai_chat)
        inter.ai_settings_requested.connect(self._show_ai_settings)
        inter.quit_requested.connect(self._quit)

        inter._physics.landed.connect(sm.on_animation_finished)

    def _on_frame(self, pixmap) -> None:
        self._window.set_frame(pixmap)

    def _on_drag_start(self) -> None:
        self._state_machine.on_drag_start()
        self._player.show_static(self._assets["expressions"]["idle"])

    def _on_drag_end(self, throw_distance: float) -> None:
        self._state_machine.on_drag_end(throw_distance)

    def _play_for_request(self, key: str) -> None:
        idle = self._assets["idle"]
        sleep = self._assets.get("sleep") or []
        expr = self._assets["expressions"]

        handlers = {
            "idle_loop": lambda: self._player.play_loop(idle),
            "breath": lambda: self._player.play_subrange_once(
                idle, 0, len(idle), self._state_machine.on_animation_finished
            ),
            "click": lambda: self._player.play_once(
                self._assets["click"], self._state_machine.on_animation_finished
            ),
            "drag": lambda: self._player.show_static(expr.get("idle", idle[0])),
            "sleep": lambda: self._player.play_loop(sleep or [expr.get("sleep", expr["idle"])]),
            "sweat": lambda: self._player.show_static(expr.get("sweat", expr["idle"])),
        }
        if key == "idle_loop":
            self._forced_expr = None
        handler = handlers.get(key)
        if handler:
            handler()

    def _on_hover(self, entered: bool) -> None:
        self._hovering = entered
        self._state_machine.on_hover(entered)
        st = self._state_machine.state
        if st not in (PetState.IDLE, PetState.BREATH):
            return
        if self._forced_expr:
            return
        if entered:
            self._player.show_static(self._assets["expressions"]["smile"])
        else:
            self._play_for_request("idle_loop")

    def _on_force_expression(self, name: str) -> None:
        expr = self._assets["expressions"]
        pix = expr.get(name)
        if not pix:
            return
        self._forced_expr = None if name == "idle" else name
        if name == "sleep":
            self._state_machine.force_expression("sleep")
            return
        if name == "idle":
            self._state_machine.on_animation_finished()
            return
        self._player.show_static(pix)

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("[宠物] 警告: 系统托盘不可用，跳过托盘图标")
            return

        icon_pix = self._assets["expressions"].get("idle")
        self._tray = QSystemTrayIcon(QIcon(icon_pix) if icon_pix else QIcon(), self._window)
        self._tray.setToolTip("小艺 · 桌面宠物")
        menu = QMenu()
        menu.addAction("显示/隐藏", lambda: self._window.setVisible(not self._window.isVisible()))
        menu.addAction("和小艺聊天", self._show_ai_chat)
        menu.addAction("AI 设置", self._show_ai_settings)
        menu.addSeparator()
        menu.addAction("退出", self._quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(
            lambda r: self._window.setVisible(not self._window.isVisible())
            if r == QSystemTrayIcon.ActivationReason.DoubleClick else None
        )
        self._tray.show()

    def _show_ai_chat(self) -> None:
        if self._speech_bubble is None:
            self._speech_bubble = SpeechBubbleWindow(self._window)
        if self._ai_chat_dialog is None:
            self._ai_chat_dialog = PetChatInputBubble()
            self._ai_chat_dialog.send_requested.connect(self._send_ai_chat)
            self._ai_chat_dialog.finished.connect(lambda _: self._on_ai_chat_closed())
        self._ai_chat_dialog.show_near(self._window)
        self._update_chat_bounds()

    def _send_ai_chat(self, text: str) -> None:
        self._pending_chat_text = text
        if self._chat_thread is not None:
            if self._ai_chat_dialog:
                self._ai_chat_dialog.restore_text(text)
            if self._speech_bubble:
                self._speech_bubble.show_message("我还在想上一个问题，等我一下。", timeout_ms=3500)
            return

        cfg = load_ai_config()
        errors = cfg.validate()
        if errors:
            QMessageBox.warning(
                self._ai_chat_dialog,
                "AI 配置不完整",
                "\n".join(errors) + "\n\n请先打开 AI 设置填写 DeepSeek API Key。",
            )
            if self._ai_chat_dialog:
                self._ai_chat_dialog.restore_text(text)
            self._show_ai_settings()
            return

        if self._speech_bubble is None:
            self._speech_bubble = SpeechBubbleWindow(self._window)
        self._speech_bubble.show_thinking()
        self._update_chat_bounds()
        if self._ai_chat_dialog:
            self._ai_chat_dialog.set_busy(True)

        self._chat_messages.append({"role": "user", "content": text})
        self._trim_chat_messages()

        self._chat_thread = QThread(self._window)
        self._chat_worker = ChatRequestWorker(cfg, self._chat_messages)
        self._chat_worker.moveToThread(self._chat_thread)
        self._chat_thread.started.connect(self._chat_worker.run)
        self._chat_worker.finished.connect(self._on_ai_chat_reply)
        self._chat_worker.finished.connect(self._chat_thread.quit)
        self._chat_worker.finished.connect(self._chat_worker.deleteLater)
        self._chat_thread.finished.connect(self._chat_thread.deleteLater)
        self._chat_thread.start()

    def _on_ai_chat_reply(self, ok: bool, message: str) -> None:
        if self._ai_chat_dialog:
            self._ai_chat_dialog.set_busy(False)

        self._chat_thread = None
        self._chat_worker = None

        if ok:
            self._chat_messages.append({"role": "assistant", "content": message})
            self._trim_chat_messages()
            self._speech_bubble.show_message(message)
            self._pending_chat_text = ""
            self._update_chat_bounds()
            if self._ai_chat_dialog:
                self._ai_chat_dialog.ready_for_next_message()
            return

        if self._chat_messages and self._chat_messages[-1].get("role") == "user":
            self._chat_messages.pop()
        self._speech_bubble.show_message(f"发送失败: {message}", timeout_ms=7000)
        self._update_chat_bounds()
        if self._ai_chat_dialog and self._pending_chat_text:
            self._ai_chat_dialog.restore_text(self._pending_chat_text)

    def _trim_chat_messages(self) -> None:
        if len(self._chat_messages) > 24:
            self._chat_messages = self._chat_messages[-24:]

    def _on_ai_chat_closed(self) -> None:
        self._ai_chat_dialog = None
        self._update_chat_bounds()

    def _update_chat_bounds(self) -> None:
        if self._updating_chat_bounds:
            return
        self._updating_chat_bounds = True
        try:
            self._apply_chat_bounds()
        finally:
            self._updating_chat_bounds = False

    def _apply_chat_bounds(self) -> None:
        left_margin = 0
        if self._ai_chat_dialog and self._ai_chat_dialog.isVisible():
            self._ai_chat_dialog.adjustSize()
            left_margin = max(left_margin, self._ai_chat_dialog.width() + 10)
        if self._speech_bubble and self._speech_bubble.isVisible():
            self._speech_bubble.adjustSize()
            left_margin = max(left_margin, self._speech_bubble.width() + 10)

        self._window.set_screen_margins(left=left_margin)
        self._layout_chat_bubbles()

    def _layout_chat_bubbles(self) -> None:
        reply_pos = None
        if self._speech_bubble and self._speech_bubble.isVisible():
            reply_pos = self._speech_bubble.default_position()

        input_pos = None
        if self._ai_chat_dialog and self._ai_chat_dialog.isVisible():
            input_pos = self._ai_chat_dialog.default_position(self._window)
            if reply_pos is not None:
                input_pos = self._avoid_input_reply_overlap(input_pos, reply_pos)

        if self._speech_bubble and self._speech_bubble.isVisible() and reply_pos is not None:
            self._speech_bubble.move_to(reply_pos)
        if self._ai_chat_dialog and self._ai_chat_dialog.isVisible() and input_pos is not None:
            self._ai_chat_dialog.move_to(input_pos)

    def _avoid_input_reply_overlap(self, input_pos, reply_pos):
        input_rect = self._ai_chat_dialog.geometry()
        reply_rect = self._speech_bubble.geometry()
        input_rect.moveTopLeft(input_pos)
        reply_rect.moveTopLeft(reply_pos)
        if not input_rect.intersects(reply_rect):
            return input_pos

        screen = QApplication.screenAt(self._window.geometry().center()) or QApplication.primaryScreen()
        if screen is None:
            return input_pos
        available = screen.availableGeometry()
        target_y = reply_rect.bottom() + 10
        max_y = available.bottom() - input_rect.height() + 1
        input_pos.setY(min(target_y, max_y))
        return input_pos

    def _on_pet_moved(self) -> None:
        if self._ai_chat_dialog or (self._speech_bubble and self._speech_bubble.isVisible()):
            self._update_chat_bounds()

    def _show_ai_settings(self) -> None:
        if self._ai_dialog is None:
            self._ai_dialog = AiSettingsDialog()
            self._ai_dialog.finished.connect(lambda _: setattr(self, "_ai_dialog", None))
        self._ai_dialog.show()
        self._ai_dialog.raise_()
        self._ai_dialog.activateWindow()

    def _quit(self) -> None:
        self._state_machine.stop()
        self._player.stop()
        if self._tray:
            self._tray.hide()
        QApplication.quit()

    def run(self) -> int:
        # ① 必须先创建 QApplication，之后才能使用 QPixmap / QWidget
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        app.setApplicationName("小艺桌面宠物")
        app.setQuitOnLastWindowClosed(False)

        self._setup()
        self._window.show()  # show before sm.start() — avoids init-order crash
        self._setup_tray()
        self._state_machine.start()

        n_idle = len(self._assets["idle"])
        n_click = len(self._assets["click"])
        n_sleep = len(self._assets["sleep"])
        print(f"[宠物] 启动成功 | 站立{n_idle}帧 趴地{n_sleep}帧 点击{n_click}帧")
        print(f"       资源: {self._assets_dir}")

        return app.exec()


def main() -> None:
    try:
        code = PetApplication().run()
        sys.exit(code)
    except Exception:
        traceback.print_exc()
        if sys.stdin.isatty():
            input("按 Enter 键退出…")
        sys.exit(1)


if __name__ == "__main__":
    main()
