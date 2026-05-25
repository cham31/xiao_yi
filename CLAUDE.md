# 小艺桌面宠物

PyQt6 桌面宠物项目，当前使用塔菲喵风格全身 2D PNG 动画资源。

## 项目结构

- `pet_player/` — 核心模块（窗口、渲染、状态机、交互）
- `assets/taffy_fullbody/animations/` — 当前运行时动画帧
- `assets/taffy_fullbody/states/` — 当前确认的站立/趴地状态源图
- AI 配置保存在 `%APPDATA%\XiaoYi\ai_config.json`，不要提交 API Key
- 当前聊天功能使用 `PetChatInputBubble` 跟随宠物的输入气泡 + `SpeechBubbleWindow` 回复气泡
- 输入气泡默认在宠物左中，回复气泡默认在宠物左上；气泡贴住屏幕左侧时需动态限制宠物继续左移，避免重叠
- 气泡跟随使用 `PetWindow.moved` / `moveEvent` 事件驱动，不使用轮询定时器
- 宠物贴近上边缘时，输入气泡需要一次性布局到避让后的最终位置，避免闪动

## 技术要点

- Python 3.11.15
- PyQt6 / Qt 6.11.0
- 显示尺寸: `128x128`
- 源动画帧: `256x256` 透明 PNG
- 无边框透明置顶窗口 + `QAbstractNativeEventFilter` alpha 鼠标穿透
- 禁止 override `QWidget.nativeEvent()`，PyQt6 6.11.0 下可能崩溃
- 状态机: `IDLE -> BREATH -> CLICKED/DRAGGED/SWEAT/SLEEP`
- 拖拽时保持站立图移动，不播放专门拖拽动画
- 右键/托盘菜单提供 `和小艺聊天` 与 `AI 设置`
- AI 请求优先适配 DeepSeek OpenAI-compatible API

## 环境

- Python: `D:\APP\anaconda2025_12_02\envs\conda_python3.11\python.exe`
