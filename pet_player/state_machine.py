"""
状态机 — 宠物行为状态与转换规则
"""

from __future__ import annotations

from enum import Enum, auto

from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class PetState(Enum):
    IDLE = auto()
    BREATH = auto()
    CLICKED = auto()
    DRAGGED = auto()
    SWEAT = auto()
    SLEEP = auto()


class PetStateMachine(QObject):
    """
    状态转换规则:
    - IDLE → 每 4 秒 BREATH
    - 任意 → 鼠标点击 → CLICKED
    - 任意 → 拖拽 → DRAGGED
    - 无交互 60 秒 → SLEEP
    - 动画结束 → IDLE
    """

    request_animation = pyqtSignal(str)  # "idle_loop" | "breath" | "click" | "drag" | "sleep" | "sweat"

    IDLE_SUBTIMER_MS = 4000
    SLEEP_TIMEOUT_MS = 60_000

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._state = PetState.IDLE
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._on_idle_tick)

        self._sleep_timer = QTimer(self)
        self._sleep_timer.setSingleShot(True)
        self._sleep_timer.timeout.connect(self._enter_sleep)

        self.reset_activity()

    @property
    def state(self) -> PetState:
        return self._state

    def reset_activity(self) -> None:
        """重置无交互计时（鼠标活动时调用）"""
        self._sleep_timer.stop()
        if self._state == PetState.SLEEP:
            self._transition(PetState.IDLE)
        self._sleep_timer.start(self.SLEEP_TIMEOUT_MS)

    def start(self) -> None:
        self._transition(PetState.IDLE)
        self._idle_timer.start(self.IDLE_SUBTIMER_MS)

    def stop(self) -> None:
        self._idle_timer.stop()
        self._sleep_timer.stop()

    def on_animation_finished(self) -> None:
        """单次动画播放完毕 → 回到 IDLE"""
        if self._state in (PetState.CLICKED, PetState.DRAGGED, PetState.BREATH, PetState.SWEAT):
            self._transition(PetState.IDLE)

    def on_mouse_click(self) -> None:
        self.reset_activity()
        if self._state != PetState.CLICKED:
            self._transition(PetState.CLICKED)

    def on_drag_start(self) -> None:
        self.reset_activity()
        if self._state != PetState.DRAGGED:
            self._transition(PetState.DRAGGED)

    def on_drag_end(self, throw_distance: float) -> None:
        self.reset_activity()
        if throw_distance > 80 and self._state == PetState.DRAGGED:
            self._transition(PetState.SWEAT)
        else:
            self.on_animation_finished()

    def on_hover(self, entered: bool) -> None:
        """悬停时不改状态机，由交互层切换 smile 差分"""
        if entered:
            self.reset_activity()

    def force_expression(self, name: str) -> None:
        """右键菜单强制切换表情"""
        self.reset_activity()
        mapping = {
            "idle": PetState.IDLE,
            "sleep": PetState.SLEEP,
            "sweat": PetState.SWEAT,
        }
        if name in mapping:
            self._transition(mapping[name])

    def _on_idle_tick(self) -> None:
        if self._state != PetState.IDLE:
            return
        self._transition(PetState.BREATH)

    def _enter_sleep(self) -> None:
        if self._state not in (PetState.DRAGGED, PetState.CLICKED):
            self._transition(PetState.SLEEP)

    def _transition(self, new: PetState) -> None:
        old = self._state
        if old == new and new != PetState.BREATH:
            return
        self._state = new
        self._emit_animation_request(new)

    def _emit_animation_request(self, state: PetState) -> None:
        mapping = {
            PetState.IDLE: "idle_loop",
            PetState.BREATH: "breath",
            PetState.CLICKED: "click",
            PetState.DRAGGED: "drag",
            PetState.SWEAT: "sweat",
            PetState.SLEEP: "sleep",
        }
        self.request_animation.emit(mapping.get(state, "idle_loop"))
