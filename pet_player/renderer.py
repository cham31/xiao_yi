"""
渲染层 — 序列帧加载与 AnimationPlayer
"""

from __future__ import annotations

import glob
import os
import re
from typing import Callable

from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt, QObject, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QWidget


DEFAULT_FPS = 12
FADE_MS = 200
DISPLAY_SIZE = 300


def _placeholder(size: int = DISPLAY_SIZE) -> QPixmap:
    """图片缺失时的红色占位方块"""
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    p = QPainter(pix)
    p.fillRect(0, 0, size, size, QColor(220, 50, 50))
    p.setPen(QColor(255, 255, 255))
    p.drawText(pix.rect(), int(Qt.AlignmentFlag.AlignCenter), "MISSING")
    p.end()
    return pix


class AssetLoader:
    """从 assets/ 目录加载序列帧与表情差分"""

    def __init__(self, assets_dir: str, display_size: int = DISPLAY_SIZE):
        self.assets_dir = assets_dir
        self.anim_dir = os.path.join(assets_dir, "animations")
        self.display_size = display_size

    def _scale(self, pix: QPixmap) -> QPixmap:
        if pix.isNull():
            return _placeholder(self.display_size)
        return pix.scaled(
            self.display_size, self.display_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def load_frame(self, path: str) -> QPixmap:
        if not os.path.isfile(path):
            print(f"[AssetLoader] 缺失: {path}")
            return _placeholder(self.display_size)
        pix = QPixmap(path)
        if pix.isNull():
            print(f"[AssetLoader] 无法加载: {path}")
            return _placeholder(self.display_size)
        return self._scale(pix)

    def load_sequence(self, prefix: str) -> list[QPixmap]:
        """加载 prefix_01.png, prefix_02.png … 按序号排序"""
        pattern = os.path.join(self.anim_dir, f"{prefix}_*.png")
        files = glob.glob(pattern)
        if not files:
            print(f"[AssetLoader] 未找到序列: {pattern}")
            return [_placeholder(self.display_size)]

        def sort_key(p: str) -> int:
            m = re.search(r"_(\d+)\.png$", p)
            return int(m.group(1)) if m else 0

        files.sort(key=sort_key)
        return [self.load_frame(f) for f in files]

    def load_expression(self, name: str) -> QPixmap:
        """加载 expr_{name}.png，回退到 assets/{name}.png"""
        paths = [
            os.path.join(self.anim_dir, f"expr_{name}.png"),
            os.path.join(self.assets_dir, f"{name}.png"),
        ]
        for path in paths:
            if os.path.isfile(path):
                return self.load_frame(path)
        print(f"[AssetLoader] 表情缺失: {name}")
        return _placeholder(self.display_size)

    def load_all(self) -> dict:
        return {
            "idle": self.load_sequence("idle"),
            "click": self.load_sequence("click"),
            "drag": self.load_sequence("drag"),
            "expressions": {
                name: self.load_expression(name)
                for name in ("idle", "smile", "grin", "sweat", "angry", "sleep")
            },
        }


class AnimationPlayer(QObject):
    """
    序列帧播放器
    - 循环播放（待机）
    - 单次播放 + 完成回调（互动）
    - 帧率控制（默认 12fps）
  - 淡入淡出（200ms，需绑定 opacity 宿主控件）
    """

    frame_changed = pyqtSignal(QPixmap)
    finished = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._frames: list[QPixmap] = []
        self._index = 0
        self._loop = True
        self._playing = False
        self._fps = DEFAULT_FPS
        self._on_complete: Callable[[], None] | None = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._opacity_effect: QGraphicsOpacityEffect | None = None
        self._fade_anim: QPropertyAnimation | None = None

    def bind_opacity(self, widget: QWidget) -> None:
        """绑定淡入淡出目标控件"""
        self._opacity_effect = QGraphicsOpacityEffect(widget)
        self._opacity_effect.setOpacity(1.0)
        widget.setGraphicsEffect(self._opacity_effect)

    @property
    def current_frame(self) -> QPixmap:
        if not self._frames:
            return _placeholder()
        return self._frames[self._index]

    @property
    def is_playing(self) -> bool:
        return self._playing

    def set_fps(self, fps: int) -> None:
        self._fps = max(1, fps)
        if self._timer.isActive():
            self._timer.setInterval(1000 // self._fps)

    def show_static(self, pixmap: QPixmap) -> None:
        """显示静态帧（表情差分）"""
        self.stop()
        self.frame_changed.emit(pixmap)

    def play_loop(self, frames: list[QPixmap], fps: int | None = None) -> None:
        if fps is not None:
            self.set_fps(fps)
        self._frames = frames or [_placeholder()]
        self._index = 0
        self._loop = True
        self._on_complete = None
        self._start()

    def play_once(
        self,
        frames: list[QPixmap],
        on_complete: Callable[[], None] | None = None,
        fps: int | None = None,
    ) -> None:
        if fps is not None:
            self.set_fps(fps)
        self._frames = frames or [_placeholder()]
        self._index = 0
        self._loop = False
        self._on_complete = on_complete
        self._start()

    def play_subrange_once(
        self,
        frames: list[QPixmap],
        start: int,
        end: int,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        """播放帧子区间 [start, end) 一次"""
        subset = frames[start:end] if frames else [_placeholder()]
        self.play_once(subset, on_complete)

    def stop(self) -> None:
        self._timer.stop()
        self._playing = False

    def fade_to(self, opacity: float, duration_ms: int = FADE_MS) -> None:
        if self._opacity_effect is None:
            return
        if self._fade_anim and self._fade_anim.state() == QPropertyAnimation.State.Running:
            self._fade_anim.stop()
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(duration_ms)
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(opacity)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._fade_anim.start()

    def _start(self) -> None:
        self._playing = True
        self._timer.start(1000 // self._fps)
        self.frame_changed.emit(self.current_frame)

    def _tick(self) -> None:
        if not self._frames:
            return
        self._index += 1
        if self._index >= len(self._frames):
            if self._loop:
                self._index = 0
            else:
                self._index = len(self._frames) - 1
                self._timer.stop()
                self._playing = False
                self.finished.emit()
                if self._on_complete:
                    cb = self._on_complete
                    self._on_complete = None
                    cb()
                return
        self.frame_changed.emit(self.current_frame)
