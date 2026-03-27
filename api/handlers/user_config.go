package handlers

import (
	"fmt"
	"log"
	"net/http"

	"github.com/gin-gonic/gin"
	"liquid-api/database"
)

// GetUserConfigs 获取用户所有配置
func GetUserConfigs(c *gin.Context) {
	userID := c.Param("user_id")
	configType := c.Query("type")

	db := database.GetDB()
	configs, err := db.GetUserConfigs(userID, configType)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"code":    1,
			"message": err.Error(),
			"data":    nil,
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"code":    0,
		"message": "获取成功",
		"data":    configs,
	})
}

// GetUserConfig 获取用户单个配置
func GetUserConfig(c *gin.Context) {
	userID := c.Param("user_id")
	configKey := c.Param("config_key")

	db := database.GetDB()
	config, err := db.GetUserConfig(userID, configKey)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"code":    1,
			"message": "配置不存在",
			"data":    nil,
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"code":    0,
		"message": "获取成功",
		"data":    config,
	})
}

// SaveUserConfig 保存用户配置
func SaveUserConfig(c *gin.Context) {
	userID := c.Param("user_id")

	var config database.UserConfig
	if err := c.ShouldBindJSON(&config); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"code":    1,
			"message": err.Error(),
			"data":    nil,
		})
		return
	}

	config.UserID = userID

	db := database.GetDB()
	if err := db.SaveUserConfig(&config); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"code":    1,
			"message": err.Error(),
			"data":    nil,
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"code":    0,
		"message": "配置保存成功",
		"data":    nil,
	})
}

// BatchUpdateUserConfigs 批量更新用户配置
func BatchUpdateUserConfigs(c *gin.Context) {
	userID := c.Param("user_id")

	var req struct {
		Configs []database.UserConfig `json:"configs" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"code":    1,
			"message": err.Error(),
			"data":    nil,
		})
		return
	}

	db := database.GetDB()
	successCount := 0
	for _, config := range req.Configs {
		config.UserID = userID
		if err := db.SaveUserConfig(&config); err != nil {
			log.Printf("批量更新配置失败: %v", err)
		} else {
			successCount++
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"code":    0,
		"message": fmt.Sprintf("批量更新完成: 成功 %d/%d", successCount, len(req.Configs)),
		"data":    nil,
	})
}

// DeleteUserConfig 删除用户配置
func DeleteUserConfig(c *gin.Context) {
	userID := c.Param("user_id")
	configKey := c.Param("config_key")

	db := database.GetDB()
	if err := db.DeleteUserConfig(userID, configKey); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"code":    1,
			"message": err.Error(),
			"data":    nil,
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"code":    0,
		"message": "配置删除成功",
		"data":    nil,
	})
}
