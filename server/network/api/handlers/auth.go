package handlers

import (
	"net/http"
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