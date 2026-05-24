# 小艺桌面宠物

基于 PyQt6 的 Windows 桌面宠物。当前版本使用塔菲喵风格的全身 2D PNG 资源，通过透明置顶窗口播放轻量动画，并支持点击、拖拽、悬停、右键菜单和系统托盘。

当前方案已经精简为：

```text
全身塔菲 2D 资源
+ PyQt6 透明置顶窗口
+ alpha 鼠标穿透
+ 状态机切换动画
```

不使用实时 3D，不使用旧的大头/半身序列帧方案。

## 环境

- Python: `D:\APP\anaconda2025_12_02\envs\conda_python3.11\python.exe`
- Python 版本: `3.11.15`
- PyQt6: `6.11.0`
- Qt: `6.11.0`
- 平台: Windows 11 64-bit

注意：PyQt6 6.11.0 下不要重写 `QWidget.nativeEvent()`。项目使用 `QAbstractNativeEventFilter` 处理 Windows `WM_NCHITTEST`，避免 native event 覆盖导致崩溃。

## 目录结构

```text
desk_agent_xiaoyi/
├── main.py
├── requirements.txt
├── pet_player/
│   ├── main.py             # 应用控制器、状态/动画连接、托盘
│   ├── renderer.py         # 资源加载与序列帧播放器
│   ├── window.py           # 透明置顶窗口与 alpha 鼠标穿透
│   ├── interaction.py      # 点击、拖拽、右键菜单、惯性滑动
│   ├── state_machine.py    # IDLE/BREATH/CLICKED/DRAGGED/SWEAT/SLEEP
│   └── __init__.py
└── assets/
    └── taffy_fullbody/
        ├── animations/     # 运行时动画帧
        └── states/         # 当前确认的站立/趴地状态源图
```

## 运行

```powershell
D:\APP\anaconda2025_12_02\envs\conda_python3.11\python.exe main.py
```

安装依赖：

```powershell
D:\APP\anaconda2025_12_02\envs\conda_python3.11\python.exe -m pip install -r requirements.txt
```

语法检查：

```powershell
D:\APP\anaconda2025_12_02\envs\conda_python3.11\python.exe -m compileall -q main.py pet_player
```

## 当前资源

运行时加载目录：

```text
assets/taffy_fullbody/animations/
```

资源规格：

- 源动画帧：`256x256` 透明 PNG
- 运行显示尺寸：`128x128`
- 角色状态：
  - `idle_01..12`: 站立轻微呼吸/摆动
  - `sleep_01..12`: 伏趴待机呼吸
  - `click_01..09`: 点击弹跳反馈
  - `expr_idle/smile/grin/sweat/angry/sleep`: 右键菜单表情

拖拽时不播放专门拖拽动画，目前保持站立图随窗口移动。这样比之前的倾斜拖拽帧更协调。

状态源图保留在：

```text
assets/taffy_fullbody/states/
```

## 已实现功能

- 无边框透明窗口
- 窗口置顶且不占用任务栏
- alpha 低透明区域鼠标穿透
- 站立呼吸动画
- 点击弹跳动画
- 60 秒无交互后切换为伏趴待机动画
- 拖拽移动与释放后的惯性滑动
- 右键切换表情/退出
- 系统托盘显示/隐藏与退出

## 当前行为

- 启动后进入站立 idle 循环。
- 鼠标悬停时显示微笑表情。
- 左键点击触发点击弹跳。
- 左键拖拽时角色保持普通站立图，窗口跟随鼠标移动。
- 长时间无交互后进入伏趴待机循环。
- 右键菜单可切换默认、微笑、大笑、流汗、生气、睡觉。

## 后续可优化

- 点击和拖拽事件仍可进一步拆分：释放且未拖拽时再触发点击，可以避免按下瞬间的点击反馈。
- 可以补一张更自然的拖拽抱起/被拎起姿态，再恢复专门拖拽动画。
- 表情目前主要是静态差分，后续可以改成局部图层或更精细的关键帧。
- 若要继续压缩包体，可以只保留运行时 `animations/`，删除 `states/` 源图。
