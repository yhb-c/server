# 液位检测系统 - 项目文件结构

## 项目概述
基于客户端-服务端架构的液位检测系统，客户端使用PyQt5开发，服务端基于Gin框架开发，集成YOLO模型进行液位检测。

## 项目结构

```
liquid_detect/
├── .kiro/                          # Kiro IDE配置文件夹
│   ├── hooks/                      # 钩子配置
│   ├── specs/                      # 规格说明
│   │   └── client-interface-migration/
│   └── steering/                   # 指导规则
│       └── rule.md
├── api/                            # Go API服务
│   ├── config/                     # API配置
│   │   ├── config.go
│   │   └── config.yaml
│   ├── database/                   # 数据库模块
│   ├── handlers/                   # API处理器
│   │   ├── auth.go                 # 认证处理
│   │   ├── channels.go             # 通道处理
│   │   ├── config.go               # 配置处理
│   │   └── models.go               # 模型处理
│   ├── routes/                     # 路由配置
│   │   └── routes.go
│   ├── vendor/                     # Go依赖包
│   │   ├── github.com/
│   │   ├── golang.org/
│   │   ├── google.golang.org/
│   │   ├── gopkg.in/
│   │   ├── modules.txt
│   │   └── README.md
│   ├── build.bat                   # Windows构建脚本
│   ├── build.sh                    # Linux构建脚本
│   ├── go.mod                      # Go模块文件
│   ├── go.sum                      # Go依赖校验
│   ├── liquid-api.exe              # 编译后的可执行文件
│   └── main.go                     # API主程序
├── client/                         # 客户端代码
│   ├── __pycache__/               # Python缓存文件
│   ├── config/                    # 客户端配置
│   │   └── client_config.yaml
│   ├── lib/                       # 客户端库文件
│   │   ├── lib/                   # 子库目录
│   │   ├── focus_control_example.py
│   │   ├── FocusControl.py
│   │   ├── HCNetSDK.py
│   │   ├── HKcapture.py
│   │   ├── ParameterConfigurator.py
│   │   ├── PlayCtrl.py
│   │   ├── README.md
│   │   ├── test_hikcapture.py
│   │   ├── test_main.py
│   │   └── yolov8n.dat
│   ├── logs/                      # 客户端日志
│   │   └── client.log
│   ├── network/                   # 网络模块
│   │   └── __pycache__/
│   ├── resources/                 # 资源文件
│   │   └── icons/                 # 图标资源
│   ├── src/                       # 客户端源代码
│   │   ├── api/                   # API接口模块
│   │   │   ├── __pycache__/
│   │   │   ├── __init__.py
│   │   │   ├── api_manager.py
│   │   │   ├── auth_api.py
│   │   │   ├── base_api.py
│   │   │   ├── channel_api.py
│   │   │   ├── config_api.py
│   │   │   ├── dataset_api.py
│   │   │   ├── mission_api.py
│   │   │   ├── model_api.py
│   │   │   └── video_api.py
│   │   ├── database/              # 数据库模块
│   │   │   ├── __init__.py
│   │   │   └── config.py
│   │   ├── handlers/              # 事件处理器
│   │   │   ├── datasetpage/       # 数据集页面处理器
│   │   │   ├── modelpage/         # 模型页面处理器
│   │   │   ├── videopage/         # 视频页面处理器
│   │   │   │   └── HK_SDK/        # 海康威视SDK
│   │   │   └── [其他处理器文件...]
│   │   ├── main.py                # 客户端主程序
│   │   ├── ui/                    # 用户界面模块
│   │   │   ├── __pycache__/
│   │   │   ├── __init__.py
│   │   │   ├── login.py
│   │   │   ├── main_window.py
│   │   │   └── system_window.py
│   │   ├── utils/                 # 工具模块
│   │   │   ├── __pycache__/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── logger.py
│   │   │   └── ws_client.py
│   │   ├── websocket/             # WebSocket模块
│   │   │   ├── __init__.py
│   │   │   └── ws_client.py
│   │   └── widgets/               # 自定义组件
│   ├── utils/                     # 客户端工具
│   │   └── __pycache__/
│   └── widgets/                   # 客户端组件
├── deploy/                        # 部署脚本
│   ├── check_services.sh          # 服务检查脚本
│   ├── deploy_to_server.ps1       # PowerShell部署脚本
│   ├── deploy_to_server.sh        # Bash部署脚本
│   ├── README.md                  # 部署说明
│   └── stop_services.sh           # 停止服务脚本
├── gin/                           # Gin框架源码
│   ├── .github/                   # GitHub配置
│   │   ├── ISSUE_TEMPLATE/
│   │   └── workflows/
│   ├── binding/                   # 数据绑定
│   ├── codec/                     # 编解码器
│   │   └── json/
│   ├── docs/                      # 文档
│   ├── examples/                  # 示例
│   ├── ginS/                      # Gin简化版
│   ├── internal/                  # 内部模块
│   │   ├── bytesconv/
│   │   └── fs/
│   ├── render/                    # 渲染器
│   ├── testdata/                  # 测试数据
│   │   ├── certificate/
│   │   ├── protoexample/
│   │   └── template/
│   └── [其他Gin框架文件...]
├── gin.demo/                      # Gin框架示例
│   ├── .github/
│   │   └── workflows/
│   ├── ace-template/
│   ├── app-engine/
│   │   ├── go11x/
│   │   └── gophers/
│   ├── assets-in-binary/
│   │   ├── assets/
│   │   └── templates/
│   ├── auto-tls/
│   │   ├── example1/
│   │   ├── example2/
│   │   └── example3/
│   ├── basic/
│   ├── cookie/
│   ├── cors-middleware/
│   ├── custom-validation/
│   ├── file-binding/
│   │   └── public/
│   ├── form-binding/
│   ├── forward-proxy/
│   ├── graceful-shutdown/
│   │   ├── close/
│   │   └── graceful-shutdown/
│   ├── group-routes/
│   │   └── routes/
│   ├── grpc/
│   │   └── example1/
│   ├── http-pusher/
│   │   ├── assets/
│   │   └── testdata/
│   ├── http2/
│   │   └── testdata/
│   ├── multiple-service/
│   ├── new_relic/
│   ├── oidc/
│   │   └── templates/
│   ├── otel/
│   ├── ratelimiter/
│   ├── realtime-advanced/
│   │   └── resources/
│   ├── realtime-chat/
│   ├── reverse-proxy/
│   │   ├── realServer/
│   │   └── reverseServer/
│   ├── secure-web-app/
│   │   └── public/
│   ├── send_chunked_data/
│   ├── server-sent-event/
│   │   └── public/
│   ├── struct-lvl-validations/
│   ├── template/
│   │   └── testdata/
│   ├── upload-file/
│   │   ├── limit-bytes/
│   │   ├── multiple/
│   │   └── single/
│   ├── versioning/
│   └── websocket/
│       ├── client/
│       └── server/
├── logs/                          # 系统日志目录
│   ├── .gitkeep
│   └── main.log
├── sdk/                           # SDK库
│   ├── hikvision/                 # 海康威视SDK
│   │   ├── __pycache__/
│   │   ├── lib/                   # SDK库文件
│   │   └── SdkLog_Python/         # SDK日志
│   └── logs/                      # SDK日志
│       └── SdkLog_1_W.log
├── SdkLog_Python/                 # Python SDK日志
│   └── SdkLog_1_W.log
├── server/                        # 服务端代码
│   ├── __pycache__/              # Python缓存文件
│   ├── config/                   # 服务端配置
│   │   ├── channels.yaml
│   │   ├── main.yaml
│   │   └── README.md
│   ├── database/                 # 数据库模块
│   │   ├── config/
│   │   ├── mission_result/
│   │   └── model/
│   ├── detection/                # 检测模块
│   │   ├── __pycache__/
│   │   ├── __init__.py
│   │   ├── detection.py
│   │   ├── detector.py
│   │   ├── init_error.py
│   │   ├── model_detect.py
│   │   ├── space_logic.py
│   │   └── stabilizer.py
│   ├── lib/                      # 服务端库文件
│   │   ├── lib/                  # 子库目录
│   │   ├── focus_control_example.py
│   │   ├── FocusControl.py
│   │   ├── HCNetSDK.py
│   │   ├── HKcapture.py
│   │   ├── ParameterConfigurator.py
│   │   ├── PlayCtrl.py
│   │   ├── README.md
│   │   ├── test_hikcapture.py
│   │   ├── test_main.py
│   │   └── yolov8n.dat
│   ├── logs/                     # 服务端日志
│   │   ├── .gitkeep
│   │   └── main.log
│   ├── storage/                  # 存储模块
│   │   ├── __pycache__/
│   │   ├── __init__.py
│   │   ├── csv_writer.py
│   │   ├── data_manager.py
│   │   └── video_recorder.py
│   ├── utils/                    # 服务端工具
│   │   ├── __pycache__/
│   │   ├── utils_log/
│   │   ├── __init__.py
│   │   └── camera_position.py
│   ├── video/                    # 视频处理模块
│   │   ├── __pycache__/
│   │   ├── __init__.py
│   │   ├── hik_capture.py
│   │   ├── hik_sdk.py
│   │   ├── rtsp_capture.py
│   │   └── stream_manager.py
│   ├── websocket/                # WebSocket服务
│   │   ├── __pycache__/
│   │   ├── __init__.py
│   │   └── ws_server.py
│   └── temp_start.py             # 临时启动脚本
├── ssh_connect/                   # SSH连接模块
│   ├── __pycache__/
│   ├── check_server_environment.sh
│   ├── database_config.sh
│   ├── README.md
│   ├── ssh_connect.ps1
│   ├── ssh_connection_readme.md
│   ├── ssh_manager.py
│   └── upload_to_server.ps1
├── test/                         # 测试文件目录
│   └── test_ssh_connection.py
├── utils/                        # 通用工具目录
├── 方案/                         # 方案文档
│   └── 记录.md
├── main.py                       # 项目主入口
└── requirements.txt              # 项目依赖
```

## 核心模块说明

### API服务 (api/)
- **handlers/**: API处理器，包含认证、通道、配置、模型等处理逻辑
- **config/**: API服务配置文件
- **routes/**: 路由配置
- **vendor/**: Go依赖包管理

### 客户端 (client/)
- **src/api/**: API接口管理，包含认证、通道、配置、数据集、任务、模型、视频等API
- **src/handlers/**: 事件处理器，分为数据集页面、模型页面、视频页面处理器
- **src/ui/**: 用户界面模块，包含登录界面、主窗口、系统窗口
- **src/websocket/**: WebSocket客户端通信模块
- **lib/**: 客户端库文件，包含海康威视SDK相关功能
- **resources/icons/**: 界面图标资源

### 服务端 (server/)
- **detection/**: YOLO模型检测模块，包含检测器、模型检测、空间逻辑等
- **video/**: 视频处理模块，支持海康威视SDK和RTSP流处理
- **websocket/**: WebSocket服务端通信模块
- **storage/**: 数据存储模块，包含CSV写入、数据管理、视频录制
- **database/**: 数据库模块，包含配置、任务结果、模型管理
- **lib/**: 服务端库文件，包含海康威视SDK相关功能
- **config/**: 服务端配置文件

### 部署模块 (deploy/)
- 自动化部署脚本，支持Windows PowerShell和Linux Bash
- 服务检查和停止脚本
- 部署说明文档

### SSH连接模块 (ssh_connect/)
- SSH连接管理器
- 服务器环境检查脚本
- 数据库配置脚本
- 文件上传脚本

### SDK库 (sdk/)
- **hikvision/**: 海康威视SDK库文件，用于RTSP流解码

## 技术栈
- **API服务**: Go语言, Gin框架
- **客户端**: PyQt5, Python
- **服务端**: Python推理服务
- **深度学习**: YOLO模型
- **通信**: WebSocket, RTSP, HTTP API
- **数据库**: MySQL
- **SDK**: 海康威视SDK

## 部署信息
- **服务端IP**: 192.168.0.121
- **Go API服务端口**: 8084
- **Python推理服务端口**: 8085
- **测试相机RTSP地址**: rtsp://admin:cei345678@192.168.0.27:8000/stream1
- **运行环境**: liquid虚拟环境

## 主要功能
1. 实时液位检测和显示
2. RTSP视频流处理
3. ROI区域配置和检测
4. 模型训练和管理
5. 数据采集和预处理
6. WebSocket实时通信
7. 历史数据查询和分析
8. 自动化部署和服务管理
9. SSH远程连接和文件传输

## 开发环境
- 所有代码运行在liquid虚拟环境中
- 使用简体中文进行交流和文档编写
- 遵循项目开发规范和代码质量标准