# Page0 视频监控页面 UI 结构说明

## 文件信息
- **文件路径**: `client/ui/page0_video.ui`
- **UI版本**: 4.0
- **主类名**: VideoPage
- **窗口尺寸**: 1920x1080

---

## UI 结构树

```
VideoPage (QWidget) [1920x1080]
│
└─ mainLayout (QVBoxLayout) [无边距, 无间距]
   │
   └─ videoLayoutStack (QStackedWidget) [当前索引: 0]
      │
      ├─ [索引0] defaultLayoutPage (默认布局模式)
      │  │
      │  └─ defaultLayout (QHBoxLayout) [边距10, 间距10]
      │     │
      │     ├─ missionTableContainer (任务表格容器)
      │     │  │  - 尺寸策略: Preferred/Preferred (水平拉伸=1)
      │     │  │
      │     │  └─ missionLayout (QVBoxLayout) [无边距, 无间距]
      │     │     │
      │     │     └─ missionTable (QWidget)
      │     │        └─ objectName: "MissionPanel"
      │     │           用途: 任务管理表格，显示任务列表和通道分配
      │     │
      │     └─ defaultScrollArea (QScrollArea)
      │        │  - 最小宽度: 1310px
      │        │  - 水平滚动条: 始终关闭
      │        │  - 垂直滚动条: 按需显示
      │        │  - 尺寸策略: Preferred/Preferred (水平拉伸=1)
      │        │
      │        └─ defaultChannelContainer (QWidget) [1320x3880]
      │           └─ 用途: 容纳16个通道面板 (2列 x 8行)
      │              - 每个通道面板: 620x465 像素
      │              - 列间距: 20px
      │              - 行间距: 20px
      │              - 布局位置:
      │                第1列: x=30, 第2列: x=670
      │                第1行: y=10, 第2行: y=495, 第3行: y=980...
      │
      └─ [索引1] curveLayoutPage (曲线模式布局)
         │
         └─ curveLayout (QHBoxLayout) [边距10, 间距10]
            │
            ├─ curveLayoutStack (QStackedWidget) [固定宽度660px]
            │  │  - 最小/最大宽度: 660px
            │  │  - 当前索引: 0
            │  │
            │  ├─ [子索引0] realtimeCurveSubLayout (实时检测曲线布局)
            │  │  │
            │  │  └─ realtimeLayout (QVBoxLayout) [无边距, 无间距]
            │  │     │
            │  │     └─ curveScrollArea (QScrollArea)
            │  │        │  - 水平滚动条: 始终关闭
            │  │        │  - 垂直滚动条: 按需显示
            │  │        │
            │  │        └─ curveChannelContainer (QWidget) [640x1600]
            │  │           └─ 用途: 垂直排列的通道面板列表
            │  │
            │  └─ [子索引1] historyCurveSubLayout (历史回放曲线布局)
            │     │
            │     └─ historyLayout (QVBoxLayout) [无边距, 无间距]
            │        │
            │        └─ historyVideoContainer (QWidget)
            │           └─ 用途: 历史视频面板容器
            │
            └─ curvePanelContainer (曲线面板容器)
               │  - 尺寸策略: Expanding/Preferred (水平拉伸=1)
               │
               └─ curvePanelLayout (QVBoxLayout) [无边距, 无间距]
                  │
                  └─ curvePanel (QWidget)
                     └─ objectName: "CurvePanel"
                        用途: 显示液位曲线图表
```

---

## 两种显示模式详解

### 模式1: 默认布局 (索引0)
**布局方式**: 水平分割 (左右结构)

**左侧区域** - 任务表格面板
- 组件: MissionPanel
- 功能:
  - 显示任务列表 (任务编号、任务名称、状态)
  - 显示16个通道的分配情况 (列1-16)
  - 曲线按钮列
  - 支持添加/删除/编辑任务
  - 支持通道管理

**右侧区域** - 通道面板网格
- 布局: 2列 x 8行 = 16个通道
- 每个通道面板尺寸: 620x465 (4:3比例)
- 容器总尺寸: 1320x3880
- 带垂直滚动条，可滚动查看所有通道
- 功能:
  - 实时视频显示
  - 液位线叠加显示
  - 通道信息显示 (通道名、任务名、FPS、分辨率)

### 模式2: 曲线模式布局 (索引1)
**布局方式**: 水平分割 (左右结构)

**左侧区域** - 子布局栈 (固定宽度660px)
包含两个子布局，可切换:

- **子布局0: 实时检测曲线布局**
  - 垂直排列的通道面板列表
  - 带滚动条，可查看所有通道
  - 用于实时监控模式

- **子布局1: 历史回放曲线布局**
  - 历史视频面板容器
  - 用于历史数据回放模式

**右侧区域** - 曲线面板 (共用)
- 组件: CurvePanel
- 功能:
  - 显示液位高度随时间变化的曲线
  - 支持多通道曲线对比
  - 支持任务选择下拉框
  - 支持时间范围选择
  - 支持曲线缩放和平移

---

## 模式切换方法

在Python代码中通过以下方式切换:

```python
# 切换到默认布局模式
self.videoLayoutStack.setCurrentIndex(0)

# 切换到曲线模式布局
self.videoLayoutStack.setCurrentIndex(1)

# 在曲线模式下切换子布局
self.curveLayoutStack.setCurrentIndex(0)  # 实时检测
self.curveLayoutStack.setCurrentIndex(1)  # 历史回放
```

---

## 动态内容创建

以下内容需要在Python代码中动态创建:

1. **16个通道面板** (ChannelPanel)
   - 位置: defaultChannelContainer
   - 通过循环创建并设置位置

2. **任务表格内容** (MissionPanel)
   - 位置: missionTable
   - 实例化MissionPanel类

3. **曲线面板内容** (CurvePanel)
   - 位置: curvePanel
   - 实例化CurvePanel类

4. **垂直通道列表**
   - 位置: curveChannelContainer
   - 根据任务配置动态创建

5. **历史视频面板**
   - 位置: historyVideoContainer
   - 根据需要动态创建

---

## 尺寸规格总结

| 组件 | 宽度 | 高度 | 说明 |
|------|------|------|------|
| 主窗口 | 1920 | 1080 | 全屏尺寸 |
| 通道面板 | 620 | 465 | 4:3比例 |
| 通道容器 | 1320 | 3880 | 2列x8行 |
| 滚动区域 | 1310+ | 自适应 | 最小宽度 |
| 曲线左侧栈 | 660 | 自适应 | 固定宽度 |
| 曲线通道容器 | 640 | 1600 | 垂直列表 |

---

## 使用说明

此UI文件定义了page0的基本框架结构，实际使用时:

1. 通过 `uic.loadUi()` 加载UI文件
2. 查找各个容器组件 (通过objectName)
3. 在容器中动态创建实际的业务组件
4. 连接信号和槽函数
5. 通过切换索引实现不同模式的显示

UI文件只负责布局框架，具体的业务逻辑和组件内容由Python代码实现。
