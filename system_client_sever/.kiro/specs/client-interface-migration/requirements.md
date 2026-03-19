# 需求文档 - VideoPage界面移植

## 简介

本需求文档描述将原单机版PyQt5液位检测系统的VideoPage界面移植到新的客户端-服务器架构的功能需求。系统将保留VideoPage的UI界面和用户交互体验，但将业务逻辑从本地处理改为通过WebSocket与服务器通信。

移植范围：仅移植`syetem_pyqt5/widgets/videopage`目录下的所有UI组件和信号连接方式，其他界面（模型管理、数据集管理等）不在本次移植范围内。

## 术语表

- **Client**: 新的客户端应用程序，基于PyQt5开发，通过WebSocket与服务器通信
- **Legacy_VideoPage**: 原单机版液位检测系统的VideoPage界面，位于syetem_pyqt5/widgets/videopage目录
- **Server**: 服务器端，基于Gin架构（Go）和Python推理服务
- **WebSocket_Connection**: 客户端与服务器之间的WebSocket通信连接
- **Channel_Panel**: 通道面板组件（channelpanel.py），用于显示单个检测通道的视频流和液位线
- **Mission_Panel**: 任务面板组件（missionpanel.py），用于管理和配置检测任务
- **Curve_Panel**: 曲线面板组件（curvepanel.py），用于显示液位高度实时曲线
- **History_Panel**: 历史面板组件（historypanel.py），用于查看历史数据
- **History_Video_Panel**: 历史视频面板组件（historyvideopan
- **Amplify_Window**: 放大窗口组件（amplify_window.py），用于放大显示单个通道
- **Annotation**: 标注组件（annotation.py），用于视频帧标注
- **General_Set**: 常规设置组件（general_set.py），用于通道常规参数设置
- **Logic_Setting_Dialogue**: 逻辑设置对话框（logicsetting_dialogue.py），用于配置检测逻辑
- **Model_Setting_Dialogue**: 模型设置对话框（modelsetting_dialogue.py），用于配置模型参数
- **UI_Component**: 用户界面组件，包括窗口、面板、按钮等PyQt5控件
- **Signal_Connection**: Qt信号槽连接，用于组件间通信
- **Business_Logic**: 业务逻辑，包括视频处理、模型推理、数据存储等功能
- **Liquid_Level_Line**: 液位线，在视频帧上绘制的表示液位高度的可视化线条
- **I用于在视频上叠加显示液位线和检测信息

## 需求

### 需求 1: Channel_Panel组件移植

**用户故事:**el_Panel组件移植到新客户端，以便用户能够查看视频流和液位线。

#### 验收标准

1. THE Client SHALL 包含与Legacy_VideoPage相同的Channel_Panel UI布局和控件
2. THE Client SHALL 保留Channel_Panel的InfoOverlay叠加层机制
3. THE Client SHALL 保留Channel_Panel的UI相关Signal_Connection（如窗口大小调整、控件显示隐藏）
4. THE Client SHALL 移除Channel_Panel中与Business_Logic相关的Signal_Connection
5. WHEN 用户点击通道控制按钮，THE Client SHALL 通过WebSocket发送命令到Server
6. THE Client SHALL 保持与Legacy_VideoPage相同的通道面板视觉样式

### 需求 2: Mission_Panel组件移植

**用户故事:** 作为开发人员，我希望将Legacy_VideoPage的Mission_Panel组件移植到新客户端，以便用户能够管理检测任务。

#### 验收标准

1. THE Client SHALL 包含与Legacy_VideoPage相同的Mission_Panel表格布局
2. THE Client SHALL 保留Mission_Panel的分页功能和UI交互
3. THE Client SHALL 保留Mission_Panel的UI相关Signal_Connection（如表格选择、按钮点击）
4. THE Client SHALL 移除Mission_Panel中与Business_Logic相关的Signal_Connection
5. WHEN 用户创建/修改/删除任务，THE Client SHALL 通过WebSocket发送命令到Server
6. THE Client SHALL 支持16个通道的任务配置界面

### 需求 3: 实时液位线显示

**用户故事:** 作为用户，我希望在客户端实时看到液位线，以便监控液位高度变化。

### 需求 3: WebSocket通信管理
#### 验收标准

1. WHEN Client启动时，THE Client SHALL 自动建立WebSocket_Connection到Server
2. IF Web试重新连接
3. WHEN WebSocket_Connection建立成功，THE Client SHALL 在UI上显示连接状态指示器
4. THE Client SHALL 实现心跳机制，每30秒发送一次心跳消息
5. IF 心跳超时60秒，THEN THE Client SHALL 标记连接为断开状态
6. THE Client SHALL 为所有WebSocket消息实现超时处理机制（默认10秒）

### 需求 5: 视频流接收与显示

**用户故事:** 作为用户，我希望在客户端看到实时视频流，以便监控现场情况。

#### 验收标准

1. WHEN Server推送视频帧数据，THE Client SHALL 在对应Channel_Panel中显示视频帧
2. THE Client SHALL 支持接收JPEG或H.264编码的视频帧
3. THE Client SHALL 在接收到视频帧后的50ms内完成解码和显示
4. WHEN 视频帧包含液位高度数据，THE Client SHALL 同时在InfoOverlay上绘制Liquid_Level_Line
5. THE Client SHALL 维持视频流的帧率不低于15fps
6. IF 视频帧接收超时3秒，THEN THE Client SHALL 在C视频流中断"提示

### 需求 6: Curve_Panel组件移植

**用户故事:** 作为用户，我希望在客户端查看液位高度的实时曲线，以便分析液位变化趋势。
### 需求 4: 视频流接收与显示
#### 验收标准

1. THE Client SHALL 包含与Legacy_VideoPage相同的Curve_Panel布局
2. THE Client SHALL 保留Curve_Panel的UI相关Signal_Connection（如曲线缩放、平移）
3. THE Client SHALL 移除Curve_Panel中与Business_Logic相关的Signal_Connection
4. WHEN Server推送液位高度数据，THE Client SHALL 更新Curve_Panel的实时曲线
5. THE Client SHALL 支持多个通道的曲线同时显示
6. THE Client SHALL 支持曲线数据导出到CSV文件

### 需求 7: History_Panel组件移植

**用户故事:** 作为用户，我希望在客户端查看历史数据，以便回顾过去的检测记录。

### 需求 5: 任务配置同步

1. THE Client SHALL 包含与Legacy_VideoPage相同的History_Panel布局
2. THE Client SHALL 保留History_Panel的UI相关Signal_Connection（如日期选择、数据筛选）
nal_Connection
4. WHEN 用户查询历史数据，THE Client SHALL 通过WebSocket从Server获取历史记录
5. THE Client SHALL 显示历史液位高度数据和曲线
6. THE Client SHALL 支持历史数据的时间范围筛选

### 需求 8: History_Video_Panel组件移植

**用户故事:** 作为用户，我希望在客户端回放历史视频，以便查看过去的检测过程。

#### 验收标准

### 需求 6: 曲线分析功能ALL 包含与Legacy_VideoPage相同的History_Video_Panel布局
2. THE Client SHALL 保留History_Video_Panel的UI相关Signal_Connection（如播放控制、进度条）
3. THE Client SHALL 移除History_Video_Panel中与Business_Logic相关的Signal_Connection
4. WHEN 用户请求回放历史视频，THE Client SHALL 通过WebSocket从Server获取视频数据
5. THE Client SHALL 支持视频播放、暂停、快进、快退功能
L 在历史视频上叠加显示当时的液位线数据

### 需求 9: Amplify_Window组件移植

**用户故事:** 作为用户，我希望能够放大显示单个通道，以便更清晰地查看检测细节。

#### 验收标准

1. THE Client SHALL 包含与Legacy_VideoPage相同的Amplify_Window布局
### 需求 7: 历史记录查看功能L 保留Amplify_Window的UI相关Signal_Connection（如窗口关闭、大小调整）
3. THE Client SHALL 移除Amplify_Window中与Business_Logic相关的Signal_Connection
4. WHEN 用户点击放大按钮，THE Client SHALL 打开Amplify_Window显示对应通道
5. THE Client SHALL 在Amplify_Window中同步显示视频流和液位线
6. THE Client SHALL 保持Amplify_Window与Channel_Panel的数据同步

### 需求 10: Annotation组件移植

**用户故事:** 作为用户，我希望能够在视频帧上进行标注，以便标记关键区域和信息。

#### 验收标准

1. THE Client SHALL 包含与Legacy_VideoPage相同的Annotation工具界面
### 需求 8: 历史视频回放功能L 保留Annotation的UI相关Signal_Connection（如绘制工具选择、颜色选择）
3. THE Client SHALL 保留Annotation的本地绘制和保存功能
4. WHEN 用户保存标注数据，THE Client SHALL 通过WebSocket发送标注信息到Server
5. THE Client SHALL 支持矩形、线条、文本等标注工具
6. THE Client SHALL 支持标注数据的导入和导出

### 需求 11: General_Set组件移植

**用户故事:** 作为用户，我希望能够配置通道的常规参数，以便调整检测设置。

#### 验收标准

1. THE Client SHALL 包含与Legacy_VideoPage相同的General_Set界面布局
### 需求 9: 放大窗口功能LL 保留General_Set的UI相关Signal_Connection（如参数输入、选项选择）
ignal_Connection
4. WHEN 用户修改通道参bSocket发送配置到Server
5. THE Client SHALL 支持通道名称、RTSP地址、分辨率等参数配置
6. THE Client SHALL 在启动时从Server同步通道配置

### 需求 12: Logic_Setting_Dialogue组件移植

**用户故事:** 作为用户，我希望能够配置检测逻辑参数，以便自定义检测规则。

#### 验收标准

1. THE Client SHALL 包含与Legacy_VideoPage相同的Logic_Setting_Dialogue界面
2. THE Client SHALL 保留Logic_Setting_Dialogue的UI相关Signal_Connection（如对话框确认、取消）
### 需求 10: 标注功能HALL 移除Logic_Setting_Dialogue中与Business_Logic相关的Signal_Connection
4. WHEN 用户保存逻辑设置，THE Client SHALL 通过WebSocket发送配置到Server
5. THE Client SHALL 支持阈值、报警条件等逻辑参数配置
6. THE Client SHALL 显示当前生效的逻辑配置

### 需求 13: Model_Setting_Dialogue组件移植

**用户故事:** 作为用户，我希望能够配置模型参数，以便优化检测效果。

#### 验收标准

1. THE Client SHALL 包含与Legacy_VideoPage相同的Model_Setting_Dialogue界面
2. THE Client SHALL 保留Model_Setting_Dialogue的UI相关Signal_Connection（如对话框确认、取消）
### 需求 11: 多通道支持ALL 移除Model_Setting_Dialogue中与Business_Logic相关的Signal_Connection
4. WHEN 用户保存模型设置，THE Client SHALL 通过WebSocket发送配置到Server
5. THE Client SHALL 支持置信度、NMS阈值等模型参数配置
6. THE Client SHALL 从Server获取可用模型列表供用户选择

### 需求 14: 多通道支持

**用户故事:** 作为用户，我希望客户端能够同时显示多个检测通道，以便监控多个液位检测点。

#### 验收标准

1. THE Client SHALL 支持同时显示16个Channel_Panel
2. WHEN Server推送多通道数据，THE Client SHALL 正确路由数据到对应的Channel_Panel
### 需求 12: 性能优化HALL 为每个通道维护独立的WebSocket消息队列
格布局和垂直滚动布局
5. WHEN 用户切换布局模式，THE Client SHALL 保持所有通道的数据显示状态
6. THE Client SHALL 为每个通道显示独立的状态指示器（运行中、已停止、错误）

### 需求 15: 性能优化

**用户故事:** 作为开发人员，我希望客户端能够高效处理多通道视频流和数据，以便提供流畅的用户体验。

#### 验收标准

1. THE Client SHALL 使用多线程处理WebSocket消息接收和UI更新
2. THE Client SHALL 使用图像缓存机制减少重复解码开销
3. WHEN 同时显示16个通道时，THE Client SHALL 保持UI响应时间低于100ms
### 需求 13: 日志记录HALL 限制内存使用不超过2GB
5. THE Client SHALL 在视频帧队列超过30帧时丢弃旧帧
6. THE Client SHALL 使用异步方式处理所有网络请求

### 需求 16: 配置文件管理

**用户故事:** 作为开发人员，我希望客户端能够管理本地配置文件，以便保存用户偏好和系统设置。

#### 验收标准

1. THE Client SHALL 从本地YAML配置文件加载客户端配置
2. THE Client SHALL 保存服务器连接配置（IP地址、端口号）到配置文件
3. WHEN 用户修改界面设置，THE Client SHALL 更新配置文件
### 需求 14: 兼容性保持中断"提示
5. WHEN 操作超时，THE Client SHALL 显示"操作超时，请重试"提示
6. THE Client SHALL 为所有用户操作提供视觉反馈（加载动画、进度条等）

### 需求 18: 日志记录

**用户故事:** 作为开发人员，我希望客户端能够记录详细的运行日志，以便排查问题和分析系统行为。

#### 验收标准

1. THE Client SHALL 将所有日志记录到logs/client.log文件
2. THE Client SHALL 记录WebSocket连接状态变化日志
3. THE Client SHALL 记录所有发送和接收的WebSocket消息（可配置）
4. THE Client SHALL 记录UI操作和业务逻辑执行日志
5. THE Client SHALL 支持通过配置文件设置日志级别（DEBUG、INFO、WARNING、ERROR）
6. THE Client SHALL 实现日志文件轮转，单个日志文件不超过10MB


---

## 附录：VideoPage组件清单

以下是需要移植的VideoPage组件列表：
"channel1",
  "start_time": 1234567890,
  "end_time": 1234567900
}
```
e64_encoded_jpeg_data",
  "timestamp": 1234567890,
  "frame_id": 12345,
  "width": 1920,
  "height": 1080
}
```

### 任务状态更新
```json
{
  "type": "mission_status",
  "mission_name": "任务1",
  "status": "running",
  "message": "检测进行中"
}
```

### 通道配置同步
```json
{
  "type": "channel_config",
  "channel": "channel1",
  "config": {
    "name": "通道1",
    "rtsp_url": "rtsp://admin:cei345678@192.168.0.27:8000/stream1",
    "resolution": "1920x1080"
  }
}
```

### 历史数据查询
```json
{
  "type": "query_history",
  "channel":  "start_detection",
  "mission_name": "任务1",
  "channels": ["channel1", "channel2"],
  "model_id": "model_123"
}
```

### 液位高度数据推送
```json
{
  "type": "liquid_level_data",
  "channel": "channel1",
  "height": 85.5,
  "timestamp": 1234567890,
  "frame_id": 12345,
  "liquid_positions": {
    "0": {
      "left": 100,
      "right": 200,
      "y": 150,
      "height_mm": 85.5,
      "valid": true
    }
  }
}
```

### 视频帧推送
```json
{
  "type": "video_frame",
  "channel": "channel1",
  "frame_data": "bas逻辑设置对话框，配置检测逻辑
10. **modelsetting_dialogue.py** - 模型设置对话框，配置模型参数

---

## 附录：WebSocket消息协议示例

以下是主要业务功能的WebSocket消息协议示例：

### 启动检测任务
```json
{
  "type":
### 核心显示组件
1. **channelpanel.py** - 通道面板，显示视频流和液位线
2. **missionpanel.py** - 任务管理面板，管理检测任务
3. **curvepanel.py** - 曲线面板，显示实时液位曲线
4. **historypanel.py** - 历史面板，查看历史数据
5. **historyvideopanel.py** - 历史视频面板，回放历史视频

### 辅助功能组件
6. **amplify_window.py** - 放大窗口，放大显示单个通道
7. **annotation.py** - 标注工具，视频帧标注功能

### 配置对话框组件
8. **general_set.py** - 常规设置，配置通道基本参数
9. **logicsetting_dialogue.py** - 