package handlers

import (
	"log"
	"net/http"
	"os"
	"path/filepath"
	"github.com/gin-gonic/gin"
)

// Login 用户登录 - 免密码登录模式
func Login(c *gin.Context) {
	var loginData struct {
		Username string `json:"username" binding:"required"`
		Password string `json:"password"`
	}

	if err := c.ShouldBindJSON(&loginData); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "请求参数错误",
			"message": err.Error(),
		})
		return
	}

	// 免密码登录 - 只需要用户名即可登录
	if loginData.Username != "" {
		// 设置LD_LIBRARY_PATH环境变量（如果尚未设置）
		currentLdPath := os.Getenv("LD_LIBRARY_PATH")
		sdkLibPath := "/home/lqj/liquid/server/lib/lib"
		sdkComPath := filepath.Join(sdkLibPath, "HCNetSDKCom")

		// 检查环境变量是否已包含SDK路径
		if currentLdPath == "" || (currentLdPath != "" && !contains(currentLdPath, sdkLibPath)) {
			newLdPath := sdkLibPath + ":" + sdkComPath
			if currentLdPath != "" {
				newLdPath = newLdPath + ":" + currentLdPath
			}
			os.Setenv("LD_LIBRARY_PATH", newLdPath)
			log.Printf("[登录] 用户 %s 登录，已设置LD_LIBRARY_PATH环境变量: %s", loginData.Username, newLdPath)
		} else {
			log.Printf("[登录] 用户 %s 登录，LD_LIBRARY_PATH环境变量已存在，无需设置", loginData.Username)
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "登录成功",
			"token": "mock_token_12345",
			"user": gin.H{
				"id": 1,
				"username": loginData.Username,
				"role": "admin",
			},
		})
	} else {
		c.JSON(http.StatusBadRequest, gin.H{
			"success": false,
			"message": "用户名不能为空",
		})
	}
}

// Logout 用户登出
func Logout(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"message": "登出成功",
	})
}

// contains 检查字符串是否包含子串
func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > len(substr) && (s[:len(substr)] == substr || s[len(s)-len(substr):] == substr || containsMiddle(s, substr)))
}

func containsMiddle(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}