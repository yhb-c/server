package main

import (
	"log"
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"liquid/server/config"
	"liquid/server/database"
)

var db *database.DB

func main() {
	// 加载配置文件
	cfg, err := config.LoadConfig("config/database.yaml")
	if err != nil {
		log.Fatal("加载配置失败:", err)
	}

	// 设置 Gin 模式
	gin.SetMode(cfg.Server.Mode)

	// 初始化数据库连接
	db, err = database.NewDB(cfg.Database.GetDSN())
	if err != nil {
		log.Fatal("数据库连接失败:", err)
	}
	defer db.Close()

	// 创建 Gin 路由
	r := gin.Default()

	// 任务相关接口
	missions := r.Group("/api/missions")
	{
		missions.POST("", createMission)
		missions.GET("", listMissions)
		missions.GET("/:task_id", getMission)
		missions.PUT("/:task_id/status", updateMissionStatus)
		missions.DELETE("/:task_id", deleteMission)
		missions.GET("/:task_id/results", getMissionResults)
		missions.POST("/:task_id/results", createMissionResult)
	}

	// 配置相关接口
	configs := r.Group("/api/configs")
	{
		configs.POST("", saveConfig)
		configs.GET("", listConfigs)
		configs.GET("/:type/:name", getConfig)
		configs.DELETE("/:type/:name", deleteConfig)
	}

	// 启动服务器
	log.Printf("服务器启动在 %s", cfg.Server.GetServerAddr())
	if err := r.Run(cfg.Server.GetServerAddr()); err != nil {
		log.Fatal("服务器启动失败:", err)
	}
}

// createMission 创建任务
func createMission(c *gin.Context) {
	var mission database.Mission
	if err := c.ShouldBindJSON(&mission); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if err := db.CreateMission(&mission); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, gin.H{"message": "任务创建成功"})
}

// listMissions 列出任务
func listMissions(c *gin.Context) {
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "10"))
	offset, _ := strconv.Atoi(c.DefaultQuery("offset", "0"))

	missions, err := db.ListMissions(limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, missions)
}

// getMission 获取任务
func getMission(c *gin.Context) {
	taskID := c.Param("task_id")

	mission, err := db.GetMission(taskID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "任务不存在"})
		return
	}

	c.JSON(http.StatusOK, mission)
}

// updateMissionStatus 更新任务状态
func updateMissionStatus(c *gin.Context) {
	taskID := c.Param("task_id")

	var req struct {
		Status string `json:"status" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if err := db.UpdateMissionStatus(taskID, req.Status); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "状态更新成功"})
}

// deleteMission 删除任务
func deleteMission(c *gin.Context) {
	taskID := c.Param("task_id")

	if err := db.DeleteMission(taskID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "任务删除成功"})
}

// getMissionResults 获取任务结果
func getMissionResults(c *gin.Context) {
	taskID := c.Param("task_id")
	channelName := c.Query("channel")
	regionName := c.Query("region")

	var startTime, endTime time.Time
	if start := c.Query("start_time"); start != "" {
		startTime, _ = time.Parse(time.RFC3339, start)
	}
	if end := c.Query("end_time"); end != "" {
		endTime, _ = time.Parse(time.RFC3339, end)
	}

	results, err := db.GetMissionResults(taskID, channelName, regionName, startTime, endTime)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, results)
}

// createMissionResult 创建任务结果
func createMissionResult(c *gin.Context) {
	taskID := c.Param("task_id")

	// 获取任务 ID
	mission, err := db.GetMission(taskID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "任务不存在"})
		return
	}

	var result database.MissionResult
	if err := c.ShouldBindJSON(&result); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	result.MissionID = mission.ID

	if err := db.CreateMissionResult(&result); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, gin.H{"message": "结果创建成功"})
}

// saveConfig 保存配置
func saveConfig(c *gin.Context) {
	var config database.Config
	if err := c.ShouldBindJSON(&config); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if err := db.SaveConfig(&config); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "配置保存成功"})
}

// getConfig 获取配置
func getConfig(c *gin.Context) {
	configType := c.Param("type")
	configName := c.Param("name")

	config, err := db.GetConfig(configType, configName)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "配置不存在"})
		return
	}

	c.JSON(http.StatusOK, config)
}

// listConfigs 列出配置
func listConfigs(c *gin.Context) {
	configType := c.Query("type")

	configs, err := db.ListConfigs(configType)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, configs)
}

// deleteConfig 删除配置
func deleteConfig(c *gin.Context) {
	configType := c.Param("type")
	configName := c.Param("name")

	if err := db.DeleteConfig(configType, configName); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "配置删除成功"})
}
