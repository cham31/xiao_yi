# 小艺桌面宠物

三渲二桌面精灵，基于 PyQt6 的序列帧动画桌面宠物。

## 项目结构
- `pet_player/` — 核心模块（窗口/渲染/状态机/交互）
- `assets/animations/` — 序列帧资源（idle/click/drag）
- `assets/` — 表情差分（expr_*.png）

## 技术要点
- PyQt6 6.11.0，64-bit Windows 11
- 无边框透明置顶窗口 + WM_NCHITTEST alpha 穿透（AlphaPassthroughFilter）
- **禁止** override QWidget.nativeEvent() — PyQt6 6.11.0 会 segfault
- 序列帧播放器：循环/单次/子区间 + 帧率控制
- 状态机：IDLE → BREATH(4s) → CLICKED/DRAGGED → SLEEP(60s)
- 交互：拖拽抛掷物理(DragPhysics) + 右键表情菜单 + 悬停差分

## 环境
- Python: `D:\APP\anaconda2025_12_02\envs\conda_python3.11\python.exe`
- 配置文件: `D:/StudyMaterials/HM_Personal_Study/hmStudy_Project/Python/desk_agent_xiaoyi/.claude/`
