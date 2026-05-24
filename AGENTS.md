# 小艺桌面宠物

PyQt6 桌面宠物项目，当前使用塔菲喵风格全身 2D PNG 动画资源。

## 项目结构

- `pet_player/` — 核心模块（窗口、渲染、状态机、交互）
- `assets/taffy_fullbody/animations/` — 当前运行时动画帧
- `assets/taffy_fullbody/states/` — 当前确认的站立/趴地状态源图

## 技术要点

- Python 3.11.15
- PyQt6 / Qt 6.11.0
- 显示尺寸: `128x128`
- 源动画帧: `256x256` 透明 PNG
- 无边框透明置顶窗口 + `QAbstractNativeEventFilter` alpha 鼠标穿透
- 禁止 override `QWidget.nativeEvent()`，PyQt6 6.11.0 下可能崩溃
- 状态机: `IDLE -> BREATH -> CLICKED/DRAGGED/SWEAT/SLEEP`
- 拖拽时保持站立图移动，不播放专门拖拽动画

## 环境

- Python: `D:\APP\anaconda2025_12_02\envs\conda_python3.11\python.exe`
