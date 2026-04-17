1.每次回复用户之前，阅读此规则文档，先输出好的吴世勋。然后再回复用户。
2.生成任何文件（测试文件除外），必须在开头生成readme简要说明文件用途
3.项目开发环境设置。
    2.1液位检测系统客户端基于pyqt5开发（syetem_pyqt5文件夹是原单机版系统的代码），服务端基于Gin架构开发，服务端的yolo1模型推理基于python语言开发。
    2.2系统的服务端部署ip为192.168.0.121的Linux系统设备，项目文件夹路径/home/lqj/liquid。端口配置Go API服务 (端口8084)Python推理服务 (端口8085)
    测试相机rtsp地址rtsp://admin:cei345678@192.168.0.27:8000/stream1，数据库采用MYSQL，只保存模型的元数据信息，客户端通过API查询模型信息后，推理服务根据file_path加载模型进行推理。
    2.4本项目所有代码都在环境liquid中运行，安装包和扩展资源也在环境liquid中,运行指令前3.不得使用模拟数据进行测试，如有必要，用户同意后才能使用模拟数据测试。
4.服务器在Linux系统使用海康SDK解码rtsp流时，程序启动设置LD_LIBRARY_PATH环境变量指向海康SDK的lib目录。
5.修改原单机版所有与业务功能相关的qt信号连接，改用WebSocket命令处理，只保留ui界面相关的信号连接。
9.生成的任何文件任何内容不得使用emoji符号，所有文本内容保持纯文本格式
10.所有与用户的交流都使用简体中文，外语名词可以正常使用
11.代码中所有路径都基于项目根目录设置动态路径，避免使用硬编码的绝对路径，使用os.path.join()、pathlib或相对路径等方式构建动态路径
12.PowerShell命令规范。Windows PowerShell不支持&&操作符，生成的指令不得包含&&操作符，使用;符号替代&&操作符进行命令连接
文档生成规范
13.用户没有要求的情况下，不得生成说明文档，只有用户明确输入文档生成指令时才生成文档，避免自动创建README.md、使用说明等文档文件
14.测试文件组织规范
- 所有测试脚本、功能脚本都生成到项目根目录的test文件夹中
- 若无test文件夹则自动创建该文件夹
- 所有以test_开头的文件或测试相关的脚本都应放在test/目录下
- 保持项目结构的整洁和规范
15.所有代码都在环境liquid运行，依赖也只安装在liquid中
16不得创建简易版代码代替，保证原版功能不被简化
18.服务器上conda的安装路径和环境配置：
## 服务器环境配置

### 基本信息
- **服务器IP**: 192.168.0.121
- **用户**: lqj 用户密码admin
- **项目路径**: 服务端代码/home/lqj/liquid/server
                api代码/home/lqj/liquid/server/network/api
- **操作系统**: Linux

### Conda环境配置
- **Conda安装路径**: /home/lqj/anaconda3/
- **环境名称**: liquid
- **环境路径**: /home/lqj/anaconda3/envs/liquid/
- **激活命令**: `source ~/anaconda3/bin/activate liquid`

### 开发环境版本
- **Go版本**: go1.26.1 linux/amd64
- **Go路径**: /home/lqj/anaconda3/envs/liquid/bin/go
- **Python版本**: Python 3.11.14
- **Python路径**: /home/lqj/anaconda3/envs/liquid/bin/python

## 服务端口配置

- **Go API服务**: 端口8084 (http://192.168.0.121:8084)
- **Python推理服务**: 端口8085 (ws://192.168.0.121:8085)
19.不生成测试代码测试系统功能，直接运行系统代码测试功能
20.服务端代码只能在服务器上运行，不能在本机运行
21.客户端服务端设置变量属性名要一致
22.为实现同功能生成代码时，不要新建文件在原代码文件上修改
23.此文件用于上传文件到服务器，不得再生成代码用于上传文件
24.所有数据集管理部分全部是离线使用，不需要连接服务器s
F:\liquid_detect\system_client_sever\upload.py
直接发送 `LiquidDetectionEngine.detect()` 的完整返回值
代码中使用的是 liquid
cd /home/lqj/liquid/client/database && python test_config_manager.py
本机器就是服务器，不用上传代码到服务器，直接修改代码
在Python代码中直接配置日志输出到文件
单机模式启动 - 通过subprocess直接启动本地服务

API服务：启动 /home/lqj/liquid/server/network/api/liquid-api
WebSocket服务：启动 /home/lqj/liquid/server/websocket/start_websocket_server.py
分离模式启动 - 通过SSH远程启动服务器上的服务

使用sshpass自动登录远程服务器
在远程服务器上执行启动命令
/home/lqj/liquid/logs，生成log自动覆盖，只有四个log，client.log,server.log,api.log,websocket.log


