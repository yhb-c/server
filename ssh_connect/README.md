# 自动化脚本说明

本目录包含服务器端自动化配置脚本。

## 脚本列表

### 1. setup_mysql_remote_access.sh

**功能**: 配置MySQL允许局域网远程访问

**用途**:
- 创建liquid_detect数据库
- 配置root用户允许从任何IP连接
- 授予数据库权限

**使用方法**:

**方法1: 使用PowerShell自动上传（Windows推荐）**

```powershell
# 在Windows PowerShell中执行
cd F:\liquid_detect\system_client_sever\autoscript
.\upload_to_server.ps1

# 然后登录服务器执行
ssh lqj@192.168.0.121
cd ~/liquid/autoscript
chmod +x setup_mysql_remote_access.sh
bash setup_mysql_remote_access.sh
```

**方法2: 手动上传和执行**

```bash
# 1. 上传脚本到服务器
scp setup_mysql_remote_access.sh lqj@192.168.0.121:~/liquid/autoscript/

# 2. 登录服务器
ssh lqj@192.168.0.121

# 3. 进入脚本目录
cd ~/liquid/autoscript

# 4. 赋予执行权限
chmod +x setup_mysql_remote_access.sh

# 5. 执行脚本
bash setup_mysql_remote_access.sh
```

**方法3: 使用自动化脚本（Linux/Mac）**

```bash
cd system_client_sever/autoscript
chmod +x upload_and_run.sh
bash upload_and_run.sh
```

**配置参数**:
- 数据库名: liquid_detect
- 用户: root@%
- 密码: cei123456（可在脚本中修改）

**执行后验证**:

```bash
# 在服务器上验证
mysql -u root -p -e "SELECT user, host FROM mysql.user WHERE user='root';"

# 在客户端验证
Test-NetConnection -ComputerName 192.168.0.121 -Port 3306
```

## 注意事项

1. 执行脚本前确保MySQL服务已启动
2. 需要知道MySQL root密码
3. 脚本会提示输入密码
4. 执行完成后可以从局域网任何设备连接MySQL

## 安全建议

1. 修改默认密码为强密码
2. 考虑限制IP范围（使用192.168.0.%代替%）
3. 定期更新MySQL版本
4. 启用SSL连接（生产环境）
