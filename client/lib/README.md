# 海康SDK动态库目录

此目录用于存放海康SDK的动态库文件。

## Linux系统需要的文件

### 必需库文件
- libhcnetsdk.so - 海康网络SDK核心库
- libHCCore.so - 海康核心库
- libPlayCtrl.so - 播放控制库
- libAudioRender.so - 音频渲染库
- libSuperRender.so - 视频渲染库
- libhpr.so - 海康协议库
- libNPQos.so - 网络QoS库

### 可选库文件（系统可能已有）
- libcrypto.so.1.1 - OpenSSL加密库
- libssl.so.1.1 - OpenSSL SSL/TLS库
- libopenal.so.1 - OpenAL音频库
- libz.so - zlib压缩库

### 目录
- HCNetSDKCom/ - 海康SDK组件目录（包含配置文件和组件）

## 部署说明

### 1. 获取Linux版本的海康SDK

重要: 必须使用Linux版本的SDK库文件（.so文件），Windows的DLL文件无法在Linux上使用。

获取方式:
- 从海康威视官网下载Linux版本的SDK
- 下载地址: https://www.hikvision.com/cn/support/download/sdk/
- 选择 "设备网络SDK" -> "Linux版本"

### 2. 上传SDK文件到服务器

方式1: 使用部署脚本（推荐）
在Windows上: .\deploy_sdk.ps1 -LocalSdkPath "C:\path\to\linux_sdk"
在Linux/Mac上: ./deploy_sdk.sh /path/to/linux_sdk

方式2: 手动上传
使用scp: scp -r /path/to/linux_sdk/* lqj@192.168.0.121:/home/lqj/liquid/server/inference/lib/
使用rsync: rsync -avz /path/to/linux_sdk/ lqj@192.168.0.121:/home/lqj/liquid/server/inference/lib/

### 3. 设置文件权限

登录服务器后执行: chmod 755 *.so; chmod -R 755 HCNetSDKCom/
