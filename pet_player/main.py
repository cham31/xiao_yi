"""
三渲二桌面宠物 — 主入口
整合窗口 / 渲染 / 状态机 / 交互 / 系统托盘

注意: 必须先创建 QApplication，再加载 QPixmap / 创建窗口。
"""

from __future__ import annotations

import os
import sys
import traceback

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon

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

        self._hovering = False
        self._forced_expr: str | None = None

    def _setup(self) -> None:
        """在 QApplication 创建之后初始化所有 Qt 资源"""
        self._assets = self._loader.load_all()
        self._window = PetWindow(DISPLAY_SIZE)
        self._window.install_alpha_filter(QApplication.instance())
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
        menu.addSeparator()
        menu.addAction("退出", self._quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(
            lambda r: self._window.setVisible(not self._window.isVisible())
            if r == QSystemTrayIcon.ActivationReason.DoubleClick else None
        )
        self._tray.show()

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
