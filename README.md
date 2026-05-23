# 小艺 — 三渲二桌面宠物

> PyQt6 序列帧动画桌面宠物，透明背景 + Alpha 鼠标穿透 + 瞳孔跟随

## 项目结构

```
desk_agent_xiaoyi/
├── main.py                   # 入口
├── requirements.txt          # 依赖 (PyQt6)
├── pet_player/
│   ├── main.py               # 应用控制器 + 系统托盘
│   ├── window.py             # 无边框透明置顶窗口 + Alpha 穿透
│   ├── renderer.py           # 序列帧加载 + 动画播放器
│   ├── interaction.py        # 点击拖拽 + 右键菜单
│   ├── state_machine.py      # 行为状态机
│   └── eye_track.py          # 瞳孔跟随鼠标
└── assets/
    ├── animations/           # 序列帧 (idle_*.png, click_*.png, drag_*.png, expr_*.png)
    └── references/           # 参考图
```

## 快速开始

```bash
# Python 解释器
PY=D:\APP\anaconda2025_12_02\envs\conda_python3.11\python.exe

# 安装依赖
$PY -m pip install PyQt6

# 运行
$PY main.py
```

## 交互

| 操作 | 效果 |
|------|------|
| 鼠标悬停 | 微笑 |
| 点击 | 点击动画 |
| 拖拽 | 拖拽动画 + 惯性滑行 |
| 右键 | 切换表情 / 静音 / 退出 |
| 无操作 60s | 进入睡眠 |
| 瞳孔跟随 | 眼睛跟随鼠标 |

## 添加新动画

在 `assets/animations/` 下放置 `{name}_01.png`, `{name}_02.png` ...，然后在 `pet_player/renderer.py` 的 `load_all()` 中注册序列名即可。
