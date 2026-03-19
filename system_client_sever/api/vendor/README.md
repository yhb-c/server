# Go Vendor依赖包目录

本目录包含Go API服务的所有依赖包，用于支持离线构建和部署。

## 目录说明

vendor目录是通过 `go mod vendor` 命令生成的，包含了项目所需的所有第三方依赖包的源代码副本。

## 主要依赖包

### Web框架
- **github.com/gin-gonic/gin**: Gin Web框架，用于构建REST API
- **github.com/gin-contrib/cors**: CORS中间件支持

### 数据处理
- **gopkg.in/yaml.v2**: YAML配置文件解析
- **github.com/json-iterator/go**: 高性能JSON处理

### 认证和安全
- **github.com/golang-jwt/jwt/v5**: JWT令牌处理
- **golang.org/x/crypto**: 加密算法支持

### 数据库
- **github.com/go-sql-driver/mysql**: MySQL数据库驱动

### 系统和网络
- **golang.org/x/sys**: 系统调用支持
- **golang.org/x/net**: 网络协议支持
- **golang.org/x/text**: 文本处理和国际化

### 协议缓冲区
- **google.golang.org/protobuf**: Protocol Buffers支持

## 使用方法

### 本地开发
```bash
# 更新vendor目录
go mod vendor

# 使用vendor模式构建
go build -mod=vendor -o liquid-api main.go
```

### 远程部署
vendor目录会自动上传到远程服务器，确保在网络受限环境下也能正常构建：

```bash
# 在远程服务器上使用vendor模式构建
cd /home/lqj/liquid/api
source ~/anaconda3/bin/activate liquid
go build -mod=vendor -o liquid-api main.go
```

## 维护说明

### 更新依赖
当需要更新依赖包时：

1. 修改 `go.mod` 文件中的依赖版本
2. 运行 `go mod tidy` 更新依赖
3. 运行 `go mod vendor` 重新生成vendor目录
4. 提交vendor目录到版本控制

### 清理vendor
如果需要清理vendor目录：
```bash
rm -rf vendor/
go mod vendor
```

## 注意事项

1. **版本控制**: vendor目录应该提交到版本控制系统，确保所有开发者使用相同的依赖版本
2. **构建模式**: 在有vendor目录的情况下，优先使用 `-mod=vendor` 参数进行构建
3. **网络依赖**: vendor模式可以在没有网络连接的环境下进行构建
4. **磁盘空间**: vendor目录会占用较多磁盘空间，但提供了构建的可靠性

## 依赖包许可证

所有依赖包都遵循其各自的开源许可证，主要包括：
- MIT License
- Apache License 2.0
- BSD License

使用前请确保遵守相关许可证要求。