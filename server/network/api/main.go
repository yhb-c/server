package main

import (
	"log"
	"net/http"

	"github.com/gin-gonic/gin"
	"server/network/api/config"
	"server/network/api/database"
	"server/network/api/routes"
)

func main() {
	// 加载配置
	cfg, err := config.Load()
	if err != nil {
		log.Fatal("配置加载失败:", err)
	}

	// 初始化数据库连接
	dsn := "root:root@tcp(localhost:3306)/liquid_db?charset=utf8mb4&parseTime=True&loc=Local"
	if err := database.InitDB(dsn); err != nil {
		log.Fatal("数据库连接失败:", err)
	}
	defer database.GetDB().Close()

	// 设置Gin模式
	if cfg.Server.Mode == "release" {
		gin.SetMode(gin.ReleaseMode)
	}

	// 创建路由
	router := gin.Default()

	// 设置中间件
	router.Use(gin.Logger())
	router.Use(gin.Recovery())

	// 注册路由
	routes.RegisterRoutes(router)

	// 启动服务器
	log.Printf("API服务启动在端口 %s", cfg.Server.Port)
	if err := http.ListenAndServe(":"+cfg.Server.Port, router); err != nil {
		log.Fatal("服务器启动失败:", err)
	}
}