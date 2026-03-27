package routes

import (
	"net/http"
	"github.com/gin-gonic/gin"
	"liquid-api/handlers"
)

func RegisterRoutes(router *gin.Engine) {
	// 健康检查
	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status": "ok",
			"message": "API服务运行正常",
		})
	})

	// API版本组
	v1 := router.Group("/api/v1")
	{
		// 用户认证相关
		auth := v1.Group("/auth")
		{
			auth.POST("/login", handlers.Login)
			auth.POST("/logout", handlers.Logout)
		}

		// 模型管理相关
		models := v1.Group("/models")
		{
			models.GET("/", handlers.GetModels)
			models.GET("/:id", handlers.GetModel)
			models.POST("/", handlers.CreateModel)
			models.PUT("/:id", handlers.UpdateModel)
			models.DELETE("/:id", handlers.DeleteModel)
		}

		// 通道管理相关
		channels := v1.Group("/channels")
		{
			channels.GET("/", handlers.GetChannels)
			channels.GET("/:id", handlers.GetChannel)
			channels.POST("/", handlers.CreateChannel)
			channels.PUT("/:id", handlers.UpdateChannel)
			channels.DELETE("/:id", handlers.DeleteChannel)
		}

		// 配置管理相关
		config := v1.Group("/config")
		{
			config.GET("/", handlers.GetConfig)
			config.PUT("/", handlers.UpdateConfig)
		}
	}

	// 用户配置相关接口
	users := router.Group("/api/users")
	{
		users.GET("/:user_id/configs", handlers.GetUserConfigs)
		users.GET("/:user_id/configs/:config_key", handlers.GetUserConfig)
		users.POST("/:user_id/configs", handlers.SaveUserConfig)
		users.PUT("/:user_id/configs/batch", handlers.BatchUpdateUserConfigs)
		users.DELETE("/:user_id/configs/:config_key", handlers.DeleteUserConfig)
	}
}