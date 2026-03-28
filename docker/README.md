# Docker部署配置（已归档）

本目录包含Docker容器化部署的配置文件，当前项目不使用Docker部署方式。

## 文件说明

- `docker-compose.yml` - Docker Compose编排配置
- `Dockerfile` - API服务镜像构建配置

## 当前部署方式

项目采用直接部署方式：
- 服务器：192.168.0.121
- 用户：lqj
- 环境：conda环境liquid
- Go API服务：端口8084
- Python推理服务：端口8085

## 如需使用Docker部署

```bash
cd /home/lqj/liquid/docker
docker-compose up -d
```

注意：需要修改端口配置以匹配当前系统（8084/8085）
