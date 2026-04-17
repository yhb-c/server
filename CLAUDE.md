1.每次回复用户之前，阅读此规则文档，先输出好的吴世勋。然后再回复用户。
2.生成的任何文件任何内容不得使用emoji符号，所有文本内容保持纯文本格式
3.所有与用户的交流都使用简体中文，外语名词可以正常使用
4.代码中所有路径都基于项目根目录设置动态路径，避免使用硬编码的绝对路径，使用os.path.join()、pathlib或相对路径等方式构建动态路径
5.PowerShell命令规范。Windows PowerShell不支持&&操作符，生成的指令不得包含&&操作符，使用;符号替代&&操作符进行命令连接
6.得生成说明文档，只有用户明确输入文档生成指令时才生成文档，避免自动创建README.md、使用说明等文档文件
7.所有测试脚本、功能脚本都生成到项目根目录的test文件夹中

15.所有代码都在环境liquid运行，依赖也只安装在liquid中，服务器也在liquid环境中运行
16不得创建简易版代码代替，保证原版功能不被简化

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
系统输入是录像机的延迟流或本地视频文件

