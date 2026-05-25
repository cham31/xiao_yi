# 小艺桌面宠物

基于 PyQt6 的 Windows 桌面宠物。当前版本使用塔菲喵风格的全身 2D PNG 资源，通过透明置顶窗口播放轻量动画，并支持点击、拖拽、悬停、右键菜单、系统托盘和宠物旁气泡聊天。

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
│   ├── ai_config.py        # 大模型 API 配置存储与连通性测试
│   ├── ai_client.py        # OpenAI-compatible 聊天请求客户端
│   ├── pet_chat.py         # 跟随宠物的输入气泡、回复气泡、请求线程
│   ├── ai_settings_dialog.py # AI API 设置窗口
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
- 右键或托盘打开 `和小艺聊天`
- 右键或托盘打开 AI API 设置
- DeepSeek 优先的大模型 API 配置与测试
- 系统托盘显示/隐藏与退出

## AI 聊天

右键桌宠，选择 `和小艺聊天`，或从系统托盘菜单选择 `和小艺聊天`。

当前聊天功能已切换到方案 B：使用跟随宠物的输入气泡收集用户问题，回复显示在宠物旁边的置顶气泡中。这样既避免把输入控件塞进透明宠物窗口导致焦点和鼠标穿透冲突，又能让小艺像是在桌面上直接说话。

聊天行为：

- 输入气泡没有发送/取消按钮，`Enter` 直接发送
- 输入气泡固定跟随在宠物左侧中部
- 发送请求时输入气泡显示“小艺思考中...”，避免重复发送
- 回复完成后输入气泡保持打开并重新聚焦，可继续连续聊天
- 发送后宠物旁边显示“我想想...”气泡，回复完成后替换为模型回答
- 失败时气泡显示错误，输入气泡保留原问题便于重试
- 回复气泡固定跟随在宠物左上方
- 输入/回复气泡通过宠物窗口 `moveEvent` 事件即时重定位，不再依赖定时器追随
- 宠物本体可以贴合上/右/下边缘移动；聊天气泡贴住屏幕左侧时，会按当前气泡宽度限制宠物继续左移，避免宠物和气泡重叠
- 宠物贴近上边缘时，输入气泡会一次性计算到避让后的最终位置，避免和回复气泡重叠或闪动
- 请求在后台 `QThread` 中执行，不阻塞桌宠动画
- 未配置 API Key 时提示先打开 `AI 设置`
- 请求接口为 `{Base URL}/chat/completions`，使用 OpenAI-compatible 非流式响应

聊天历史当前仅保存在应用内存中，关闭程序后不会落盘。

## AI API 设置

右键桌宠，选择 `AI 设置`，或从系统托盘菜单选择 `AI 设置`。

当前默认适配 DeepSeek OpenAI-compatible API：

```text
Provider: deepseek
Base URL: https://api.deepseek.com
Model: deepseek-v4-flash
```

可在窗口里配置：

- 提供商：`deepseek` / `custom`
- Base URL
- 模型名称
- API Key
- 请求超时

点击 `测试连接` 会向 `{Base URL}/chat/completions` 发送一次极小请求，用于确认 Key、模型和网络是否可用。

配置文件保存在用户目录，不进入仓库：

```text
%APPDATA%\XiaoYi\ai_config.json
```

当前阶段 API Key 以明文保存在该用户配置文件中，仅适合本机个人开发使用。不要把这个文件复制进项目目录或提交到 Git。

如果没有配置文件，程序会优先读取环境变量：

```text
DEEPSEEK_API_KEY
OPENAI_API_KEY
```

## 当前行为

- 启动后进入站立 idle 循环。
- 鼠标悬停时显示微笑表情。
- 左键点击触发点击弹跳。
- 左键拖拽时角色保持普通站立图，窗口跟随鼠标移动。
- 长时间无交互后进入伏趴待机循环。
- 右键菜单可切换默认、微笑、大笑、流汗、生气、睡觉，也可打开聊天窗口和 AI 设置。

## 后续可优化

- 点击和拖拽事件仍可进一步拆分：释放且未拖拽时再触发点击，可以避免按下瞬间的点击反馈。
- 可以补一张更自然的拖拽抱起/被拎起姿态，再恢复专门拖拽动画。
- 表情目前主要是静态差分，后续可以改成局部图层或更精细的关键帧。
- 若要继续压缩包体，可以只保留运行时 `animations/`，删除 `states/` 源图。
- AI API Key 当前为用户目录明文保存，后续可升级为 Windows Credential Manager 或 DPAPI 加密存储。
- 聊天功能后续可继续补流式输出、会话持久化、气泡手动关闭和更细的角色设定。
