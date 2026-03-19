# 文件上传工具使用说明

## 功能说明
upload.py用于将本地的api和server文件夹上传到远程服务器192.168.0.121

## 使用方法

### 上传所有文件夹
```bash
python utils/upload.py
```

### 上传指定文件夹
```bash
# 只上传API文件夹
python utils/upload.py --folder api

# 只上传Server文件夹  
python utils/upload.py --folder server
```

## 配置信息
- 服务器IP: 192.168.0.121
- 用户名: lqj
- 密码: admin
- API远程路径: /home/lqj/liquid/api
- Server远程路径: /home/lqj/liquid/server

## 注意事项
1. 需要安装OpenSSH客户端以使用scp命令
2. 确保网络连接正常
3. 首次连接会提示接受服务器密钥