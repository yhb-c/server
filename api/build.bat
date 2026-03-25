@echo off
REM Go API服务构建脚本 - Windows版本

echo 开始构建Go API服务...

REM 检查Go环境
where go >nul 2>nul
if %errorlevel% neq 0 (
    echo 错误: Go环境未安装
    exit /b 1
)

REM 进入API目录
cd /d "%~dp0"

REM 下载依赖
echo 下载Go模块依赖...
go mod tidy

REM 构建Windows版本
echo 构建Windows版本...
set GOOS=windows
set GOARCH=amd64
go build -o liquid-api.exe main.go

REM 构建Linux版本
echo 构建Linux版本...
set GOOS=linux
set GOARCH=amd64
go build -o liquid-api main.go

echo 构建完成!
echo Windows版本: liquid-api.exe
echo Linux版本: liquid-api

pause