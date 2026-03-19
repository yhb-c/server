# 实现计划: VideoPage界面移植

## 概述

本实现计划将原单机版PyQt5液位检测系统的VideoPage界面移植到新的客户端-服务器架构。移植包括10个UI组件，将业务逻辑信号连接改为WebSocket处理，保留UI相关信号连接。

实现策略：
1. 先搭建基础架构（WebSocketManager、DataManager、ImageManager）
2. 移植核心显示组件（ChannelPanel、MissionPanel等）
3. 重构信号连接，将业务逻辑改为WebSocket通信
4. 实现配置管理和错误处理
5. 添加日志系统
6. 编写测试验证功能

## 任务

- [x] 1. 搭建项目基础架构
  - 创建项目目录结构（client/、test/、logs/、config/）
  - 创建主配置文件config/client_config.yaml
  - 设置Python虚拟环境liquid的依赖（PyQt5、websocket-client、pyyaml、hypothesis）
  - _需求: 15.1, 15.2_

- [-] 2. 实现WebSocket管理器
  - [x] 2.1 创建WebSocketManager核心类
    - 实现client/websocket_manager.py
    - 定义Qt信号（connected、disconnected、message_received、error_occurred）
    - 实现connect()和disconnect()方法
    - 实现send_message()和send_request()方法
    - _需求: 3.1, 3.2_

  - [x] 2.2 编写WebSocketManager属性测试
    - **属性1: WebSocket连接断开后自动重连**
    - **验证需求: 3.2**

  - [x] 2.3 实现心跳机制
    - 实现start_heartbeat()和stop_heartbeat()方法
    - 每30秒发送心跳消息
    - 60秒心跳超时检测
    - _需求: 3.4, 3.5_

  - [x] 2.4 编写心跳机制属性测试
    - **属性2: 心跳消息定时发送**
    - **属性3: 心跳超时触发断开**
    - **验证需求: 3.4, 3.5**

  - [x] 2.5 实现消息超时处理
    - 实现请求-响应超时机制（默认10秒）
    - 实现ResponseWaiter类
    - _需求: 3.6_

  - [x] 2.6 编写消息超时属性测试
    - **属性4: WebSocket消息超时处理**
    - **验证需求: 3.6**

- [x] 3. 实现数据管理器
  - [x] 3.1 创建DataManager核心类
    - 实现client/data_manager.py
    - 定义通道数据缓存结构
    - 定义任务列表缓存结构
    - 实现update_channel_data()和get_channel_data()方法
    - 实现update_mission_list()和get_mission_list()方法
    - _需求: 13.2_

  - [x] 3.2 编写DataManager单元测试
    - 测试数据缓存和获取功能
    - 测试多通道数据独立性
    - _需求: 13.2, 13.3_

  - [x] 3.3 实现历史数据缓存
    - 实现cache_history_data()和get_history_data()方法
    - _需求: 6.4_

- [x] 4. 实现图像管理器
  - [x] 4.1 创建ImageManager核心类
    - 实现client/image_manager.py
    - 实现帧缓存机制（每通道最多30帧）
    - 实现decode_frame()异步解码方法
    - 实现draw_liquid_line()液位线绘制方法
    - _需求: 4.1, 4.4, 14.5_

  - [x] 4.2 编写图像管理器属性测试
    - **属性26: 视频帧队列超限丢弃旧帧**
    - **验证需求: 14.5**

  - [x] 4.3 编写图像解码单元测试
    - 测试JPEG解码功能
    - 测试Base64解码错误处理
    - _需求: 4.2_

- [x] 5. 实现配置管理器
  - [x] 5.1 创建ConfigManager类
    - 实现client/config_manager.py
    - 实现load_config()从YAML加载配置
    - 实现save_config()保存配置到YAML
    - 实现默认配置创建
    - _需求: 15.1, 15.2, 15.3_

  - [x] 5.2 编写配置管理器属性测试
    - **属性27: 配置文件加载往返一致性**
    - **属性28: 界面设置修改更新配置文件**
    - **验证需求: 15.1, 15.2, 15.3_

- [x] 6. 检查点 - 基础架构验证
  - 确保所有基础组件测试通过，询问用户是否有问题

- [ ] 7. 移植ChannelPanel组件
  - [x] 7.1 复制并重构ChannelPanel
    - 从syetem_pyqt5/widgets/videopage/channelpanel.py复制到client/widgets/channel_panel.py
    - 保留UI布局和InfoOverlay机制
    - 保留UI相关信号连接（resizeEvent、showEvent等）
    - 移除业务逻辑信号连接
    - _需求: 1.1, 1.2, 1.3, 1.4_

  - [x] 7.2 实现ChannelPanel的WebSocket集成
    - 添加update_frame()方法接收视频帧
    - 添加update_liquid_data()方法接收液位数据
    - 通道控制按钮点击通过WebSocket发送命令
    - _需求: 1.5, 4.1, 4.4_

  - [ ] 7.3 编写ChannelPanel属性测试
    - **属性5: 通道控制按钮触发WebSocket消息**
    - **属性8: 视频帧正确路由到对应通道**
    - **属性9: 液位数据触发液位线绘制**
    - **验证需求: 1.5, 4.1, 4.4, 13.2**

  - [ ] 7.4 实现视频流中断检测
    - 3秒未收到帧显示"视频流中断"提示
    - _需求: 4.6_

  - [ ] 7.5 编写视频流超时属性测试
    - **属性10: 视频帧接收超时显示提示**
    - **验证需求: 4.6**

- [ ] 8. 移植MissionPanel组件
  - [ ] 8.1 复制并重构MissionPanel
    - 从syetem_pyqt5/widgets/videopage/missionpanel.py复制到client/widgets/mission_panel.py
    - 保留表格布局和分页功能
    - 保留UI相关信号连接（表格选择、按钮点击）
    - 移除业务逻辑信号连接
    - _需求: 2.1, 2.2, 2.3, 2.4_

  - [ ] 8.2 实现MissionPanel的WebSocket集成
    - 创建/修改/删除任务通过WebSocket发送
    - 启动/停止任务通过WebSocket发送
    - 从服务器同步任务列表
    - _需求: 2.5_

  - [ ] 8.3 编写MissionPanel属性测试
    - **属性6: 任务操作触发WebSocket消息**
    - **属性33: 分页功能正确显示数据**
    - **验证需求: 2.2, 2.5**

- [ ] 9. 移植CurvePanel组件
  - [ ] 9.1 复制并重构CurvePanel
    - 从syetem_pyqt5/widgets/videopage/curvepanel.py复制到client/widgets/curve_panel.py
    - 保留曲线显示和交互功能
    - 保留UI相关信号连接（曲线缩放、平移）
    - 移除业务逻辑信号连接
    - _需求: 5.1, 5.2, 5.3_

  - [ ] 9.2 实现CurvePanel的数据更新
    - 监听DataManager的channel_data_updated信号
    - 实现append_data_point()方法更新曲线
    - 支持多通道曲线同时显示
    - _需求: 5.4, 5.5_

  - [ ] 9.3 编写CurvePanel属性测试
    - **属性11: 液位数据更新曲线显示**
    - **属性12: 多通道曲线同时显示**
    - **验证需求: 5.4, 5.5**

  - [ ] 9.4 实现曲线数据导出功能
    - 实现export_to_csv()方法
    - _需求: 5.6_

  - [ ] 9.5 编写曲线导出属性测试
    - **属性13: 曲线数据导出往返一致性**
    - **验证需求: 5.6**

- [ ] 10. 移植HistoryPanel组件
  - [ ] 10.1 复制并重构HistoryPanel
    - 从syetem_pyqt5/widgets/videopage/historypanel.py复制到client/widgets/history_panel.py
    - 保留日期选择和数据筛选UI
    - 保留UI相关信号连接
    - 移除业务逻辑信号连接
    - _需求: 6.1, 6.2_

  - [ ] 10.2 实现HistoryPanel的WebSocket集成
    - 查询历史数据通过WebSocket请求
    - 显示历史液位数据和曲线
    - 实现时间范围筛选
    - _需求: 6.3, 6.4, 6.5_

  - [ ] 10.3 编写HistoryPanel属性测试
    - **属性14: 历史数据查询通过WebSocket**
    - **属性15: 历史数据时间范围筛选**
    - **验证需求: 6.3, 6.5**

- [ ] 11. 移植HistoryVideoPanel组件
  - [ ] 11.1 复制并重构HistoryVideoPanel
    - 从syetem_pyqt5/widgets/videopage/historyvideopanel.py复制到client/widgets/history_video_panel.py
    - 保留视频播放控制UI
    - 保留UI相关信号连接（播放控制、进度条）
    - 移除业务逻辑信号连接
    - _需求: 7.1, 7.2_

  - [ ] 11.2 实现HistoryVideoPanel的WebSocket集成
    - 请求历史视频通过WebSocket
    - 实现播放、暂停、快进、快退功能
    - 在历史视频上叠加液位线
    - _需求: 7.3, 7.4, 7.5_

  - [ ] 11.3 编写HistoryVideoPanel属性测试
    - **属性16: 历史视频回放请求通过WebSocket**
    - **属性17: 历史视频播放控制功能**
    - **属性18: 历史视频叠加液位线**
    - **验证需求: 7.3, 7.4, 7.5**

- [ ] 12. 检查点 - 核心组件验证
  - 确保所有核心显示组件测试通过，询问用户是否有问题

- [ ] 13. 移植AmplifyWindow组件
  - [ ] 13.1 复制并重构AmplifyWindow
    - 从syetem_pyqt5/widgets/videopage/amplify_window.py复制到client/widgets/amplify_window.py
    - 保留放大窗口UI布局
    - 保留UI相关信号连接
    - 移除业务逻辑信号连接
    - _需求: 8.1, 8.2_

  - [ ] 13.2 实现AmplifyWindow的数据同步
    - 打开窗口显示对应通道
    - 与ChannelPanel保持数据同步
    - _需求: 8.3, 8.4, 8.5_

  - [ ] 13.3 编写AmplifyWindow属性测试
    - **属性19: 放大窗口显示对应通道**
    - **属性20: 放大窗口与通道面板数据同步**
    - **验证需求: 8.3, 8.4, 8.5**

- [ ] 14. 移植Annotation组件
  - [ ] 14.1 复制并重构Annotation
    - 从syetem_pyqt5/widgets/videopage/annotation.py复制到client/widgets/annotation.py
    - 保留标注工具UI
    - 保留UI相关信号连接（绘制工具选择、颜色选择）
    - 保留本地绘制和保存功能
    - _需求: 9.1, 9.2, 9.3_

  - [ ] 14.2 实现Annotation的WebSocket集成
    - 保存标注数据通过WebSocket发送到服务器
    - 实现标注数据导入导出
    - _需求: 9.4, 9.6_

  - [ ] 14.3 编写Annotation属性测试
    - **属性21: 标注数据保存触发WebSocket发送**
    - **属性22: 标注数据导入导出往返一致性**
    - **验证需求: 9.4, 9.6**

- [ ] 15. 移植GeneralSet组件
  - [ ] 15.1 复制并重构GeneralSet
    - 从syetem_pyqt5/widgets/videopage/general_set.py复制到client/widgets/general_set.py
    - 保留常规设置UI界面
    - 保留UI相关信号连接
    - 移除业务逻辑信号连接
    - _需求: 10.1, 10.2_

  - [ ] 15.2 实现GeneralSet的WebSocket集成
    - 修改通道参数通过WebSocket发送
    - 启动时从服务器同步通道配置
    - _需求: 10.3, 10.4, 10.5_

  - [ ] 15.3 编写GeneralSet属性测试
    - **属性7: 配置修改触发WebSocket同步**
    - **验证需求: 10.3**

- [ ] 16. 移植LogicSettingDialogue组件
  - [ ] 16.1 复制并重构LogicSettingDialogue
    - 从syetem_pyqt5/widgets/videopage/logicsetting_dialogue.py复制到client/widgets/logic_setting_dialogue.py
    - 保留逻辑设置UI界面
    - 保留UI相关信号连接
    - 移除业务逻辑信号连接
    - _需求: 11.1, 11.2_

  - [ ] 16.2 实现LogicSettingDialogue的WebSocket集成
    - 保存逻辑设置通过WebSocket发送
    - 显示当前生效的逻辑配置
    - _需求: 11.3, 11.4, 11.5_

  - [ ] 16.3 编写LogicSettingDialogue单元测试
    - 测试逻辑配置显示和保存
    - _需求: 11.5_

- [ ] 17. 移植ModelSettingDialogue组件
  - [ ] 17.1 复制并重构ModelSettingDialogue
    - 从syetem_pyqt5/widgets/videopage/modelsetting_dialogue.py复制到client/widgets/model_setting_dialogue.py
    - 保留模型设置UI界面
    - 保留UI相关信号连接
    - 移除业务逻辑信号连接
    - _需求: 12.1, 12.2_

  - [ ] 17.2 实现ModelSettingDialogue的WebSocket集成
    - 保存模型设置通过WebSocket发送
    - 从服务器获取可用模型列表
    - _需求: 12.3, 12.4, 12.5_

  - [ ] 17.3 编写ModelSettingDialogue属性测试
    - **属性36: 模型列表从服务器获取**
    - **验证需求: 12.5**

- [ ] 18. 实现多通道支持
  - [ ] 18.1 实现16通道布局管理
    - 创建client/widgets/multi_channel_container.py
    - 实现网格布局和垂直滚动布局
    - 实现布局切换功能
    - _需求: 13.1, 13.4, 13.5_

  - [ ] 18.2 实现通道状态指示器
    - 为每个通道显示状态（运行中、已停止、错误）
    - _需求: 13.6_

  - [ ] 18.3 编写多通道支持属性测试
    - **属性23: 多通道消息队列独立性**
    - **属性24: 布局切换保持数据状态**
    - **属性25: 通道状态指示器正确显示**
    - **验证需求: 13.3, 13.5, 13.6**

- [ ] 19. 检查点 - 所有组件集成验证
  - 确保所有10个组件移植完成并测试通过，询问用户是否有问题

- [ ] 20. 实现错误处理机制
  - [ ] 20.1 实现WebSocket连接错误处理
    - 实现_handle_connection_error()方法
    - 实现指数退避重连策略
    - _需求: 3.2_

  - [ ] 20.2 实现消息超时错误处理
    - 显示"操作超时，请重试"提示
    - _需求: 15.5_

  - [ ] 20.3 实现视频帧解码错误处理
    - 记录错误日志，继续处理下一帧
    - _需求: 4.2_

  - [ ] 20.4 实现数据验证错误处理
    - 创建MessageValidator类验证消息格式
    - _需求: 3.1_

  - [ ] 20.5 编写错误处理单元测试
    - 测试各种错误场景的处理
    - _需求: 3.2, 15.5_

- [ ] 21. 实现日志系统
  - [ ] 21.1 配置日志记录器
    - 创建client/logger.py
    - 配置日志输出到logs/client.log
    - 实现日志级别配置（DEBUG、INFO、WARNING、ERROR）
    - _需求: 16.1, 16.5_

  - [ ] 21.2 添加日志记录点
    - WebSocket连接状态变化日志
    - WebSocket消息收发日志（可配置）
    - UI操作和业务逻辑日志
    - _需求: 16.2, 16.3, 16.4_

  - [ ] 21.3 实现日志文件轮转
    - 单个日志文件不超过10MB
    - _需求: 16.6_

  - [ ] 21.4 编写日志系统属性测试
    - **属性30: 日志记录到指定文件**
    - **属性31: 日志级别配置生效**
    - **属性32: 日志文件轮转机制**
    - **验证需求: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6**

- [ ] 22. 实现主窗口和应用入口
  - [ ] 22.1 创建主窗口
    - 创建client/main_window.py
    - 集成所有组件到主窗口
    - 实现16通道显示
    - _需求: 13.1_

  - [ ] 22.2 创建应用入口
    - 创建client/main.py
    - 初始化配置管理器
    - 初始化WebSocket管理器
    - 启动主窗口
    - _需求: 3.1, 15.1_

  - [ ] 22.3 编写主窗口单元测试
    - 测试主窗口初始化和组件集成
    - _需求: 13.1_

- [ ] 23. 性能优化
  - [ ] 23.1 实现多线程架构
    - WebSocket接收线程
    - 图像解码线程池
    - UI线程分离
    - _需求: 14.1_

  - [ ] 23.2 实现图像缓存机制
    - 减少重复解码开销
    - _需求: 14.2_

  - [ ] 23.3 优化内存使用
    - 限制内存使用不超过2GB
    - _需求: 14.4_

  - [ ] 23.4 编写性能测试
    - 测试16通道同时显示的UI响应时间
    - 测试内存使用限制
    - _需求: 14.3, 14.4_

- [ ] 24. 集成测试
  - [ ] 24.1 编写端到端集成测试
    - 创建test/mock_server.py模拟WebSocket服务器
    - 测试客户端与服务器完整通信流程
    - 测试启动检测、视频流接收、液位线显示
    - _需求: 1.5, 2.5, 4.1, 4.4_

  - [ ] 24.2 编写多通道集成测试
    - 测试16通道同时运行
    - 测试通道间数据独立性
    - _需求: 13.1, 13.2, 13.3_

- [ ] 25. 最终检查点 - 完整系统验证
  - 确保所有测试通过，询问用户是否有问题

## 注意事项

- 标记为`*`的任务是可选的测试任务，可以跳过以加快MVP开发
- 每个任务都引用了具体的需求编号，确保可追溯性
- 检查点任务确保增量验证，及时发现问题
- 属性测试验证通用正确性属性
- 单元测试验证具体示例和边缘情况
- 所有代码路径基于项目根目录设置动态路径
- 测试文件统一放在test/目录下
- 使用简体中文进行交流，代码注释使用中文
