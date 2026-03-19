package handlers

import (
	"encoding/json"
	"io/ioutil"
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"
)

type SystemConfig struct {
	System    SystemSettings    `json:"system"`
	Server    ServerSettings    `json:"server"`
	Detection DetectionSettings `json:"detection"`
	UpdatedAt time.Time         `json:"updated_at"`
}

type SystemSettings struct {
	LogLevel    string `json:"log_level"`
	MaxChannels int    `json:"max_channels"`
	DataPath    string `json:"data_path"`
}

type ServerSettings struct {
	APIPort       string `json:"api_port"`
	WSPort        string `json:"ws_port"`
	InferenceHost string `json:"inference_host"`
	InferencePort string `json:"inference_port"`
}

type DetectionSettings struct {
	ModelPath       string  `json:"model_path"`
	ConfidenceThreshold float64 `json:"confidence_threshold"`
	IOUThreshold    float64 `json:"iou_threshold"`
	MaxDetections   int     `json:"max_detections"`
}

const configFile = "data/system_config.json"

// 读取系统配置
func loadSystemConfig() (*SystemConfig, error) {
	if err := ensureDataDir(); err != nil {
		return nil, err
	}

	if _, err := os.Stat(configFile); os.IsNotExist(err) {
		// 返回默认配置
		return &SystemConfig{
			System: SystemSettings{
				LogLevel:    "INFO",
				MaxChannels: 16,
				DataPath:    "./data",
			},
			Server: ServerSettings{
				APIPort:       "8084",
				WSPort:        "8085",
				InferenceHost: "localhost",
				InferencePort: "8085",
			},
			Detection: DetectionSettings{
				ModelPath:           "./models/detection.pt",
				ConfidenceThreshold: 0.5,
				IOUThreshold:        0.4,
				MaxDetections:       100,
			},
			UpdatedAt: time.Now(),
		}, nil
	}

	data, err := ioutil.ReadFile(configFile)
	if err != nil {
		return nil, err
	}

	var config SystemConfig
	err = json.Unmarshal(data, &config)
	return &config, err
}

// 保存系统配置
func saveSystemConfig(config *SystemConfig) error {
	if err := ensureDataDir(); err != nil {
		return err
	}

	config.UpdatedAt = time.Now()
	data, err := json.MarshalIndent(config, "", "  ")
	if err != nil {
		return err
	}

	return ioutil.WriteFile(configFile, data, 0644)
}

// GetConfig 获取系统配置
func GetConfig(c *gin.Context) {
	config, err := loadSystemConfig()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "读取系统配置失败",
			"message": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"data": config,
	})
}

// UpdateConfig 更新系统配置
func UpdateConfig(c *gin.Context) {
	var updateData SystemConfig
	if err := c.ShouldBindJSON(&updateData); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "请求参数错误",
			"message": err.Error(),
		})
		return
	}

	if err := saveSystemConfig(&updateData); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "保存系统配置失败",
			"message": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"message": "系统配置更新成功",
		"data": updateData,
	})
}