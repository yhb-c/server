package handlers

import (
	"encoding/json"
	"io/ioutil"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
)

type Model struct {
	ID          int       `json:"id"`
	Name        string    `json:"name"`
	Description string    `json:"description"`
	FilePath    string    `json:"file_path"`
	Version     string    `json:"version"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

const modelsFile = "data/models.json"

// 确保数据目录存在
func ensureDataDir() error {
	return os.MkdirAll("data", 0755)
}

// 读取模型数据
func loadModels() ([]Model, error) {
	if err := ensureDataDir(); err != nil {
		return nil, err
	}

	if _, err := os.Stat(modelsFile); os.IsNotExist(err) {
		return []Model{}, nil
	}

	data, err := ioutil.ReadFile(modelsFile)
	if err != nil {
		return nil, err
	}

	var models []Model
	err = json.Unmarshal(data, &models)
	return models, err
}

// 保存模型数据
func saveModels(models []Model) error {
	if err := ensureDataDir(); err != nil {
		return err
	}

	data, err := json.MarshalIndent(models, "", "  ")
	if err != nil {
		return err
	}

	return ioutil.WriteFile(modelsFile, data, 0644)
}

// GetModels 获取所有模型
func GetModels(c *gin.Context) {
	models, err := loadModels()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "读取模型数据失败",
			"message": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"data": models,
		"total": len(models),
	})
}

// GetModel 获取单个模型
func GetModel(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "无效的模型ID",
		})
		return
	}

	models, err := loadModels()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "读取模型数据失败",
			"message": err.Error(),
		})
		return
	}

	for _, model := range models {
		if model.ID == id {
			c.JSON(http.StatusOK, gin.H{
				"success": true,
				"data": model,
			})
			return
		}
	}

	c.JSON(http.StatusNotFound, gin.H{
		"error": "模型不存在",
	})
}

// CreateModel 创建模型
func CreateModel(c *gin.Context) {
	var newModel Model
	if err := c.ShouldBindJSON(&newModel); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "请求参数错误",
			"message": err.Error(),
		})
		return
	}

	models, err := loadModels()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "读取模型数据失败",
			"message": err.Error(),
		})
		return
	}

	// 生成新ID
	maxID := 0
	for _, model := range models {
		if model.ID > maxID {
			maxID = model.ID
		}
	}
	newModel.ID = maxID + 1
	newModel.CreatedAt = time.Now()
	newModel.UpdatedAt = time.Now()

	// 检查文件路径是否存在
	if newModel.FilePath != "" {
		if _, err := os.Stat(newModel.FilePath); os.IsNotExist(err) {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "模型文件不存在",
				"path": newModel.FilePath,
			})
			return
		}
	}

	models = append(models, newModel)
	if err := saveModels(models); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "保存模型数据失败",
			"message": err.Error(),
		})
		return
	}

	c.JSON(http.StatusCreated, gin.H{
		"success": true,
		"message": "模型创建成功",
		"data": newModel,
	})
}

// UpdateModel 更新模型
func UpdateModel(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "无效的模型ID",
		})
		return
	}

	var updateData Model
	if err := c.ShouldBindJSON(&updateData); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "请求参数错误",
			"message": err.Error(),
		})
		return
	}

	models, err := loadModels()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "读取模型数据失败",
			"message": err.Error(),
		})
		return
	}

	for i, model := range models {
		if model.ID == id {
			// 检查文件路径是否存在
			if updateData.FilePath != "" {
				if _, err := os.Stat(updateData.FilePath); os.IsNotExist(err) {
					c.JSON(http.StatusBadRequest, gin.H{
						"error": "模型文件不存在",
						"path": updateData.FilePath,
					})
					return
				}
			}

			models[i].Name = updateData.Name
			models[i].Description = updateData.Description
			models[i].FilePath = updateData.FilePath
			models[i].Version = updateData.Version
			models[i].UpdatedAt = time.Now()

			if err := saveModels(models); err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{
					"error": "保存模型数据失败",
					"message": err.Error(),
				})
				return
			}

			c.JSON(http.StatusOK, gin.H{
				"success": true,
				"message": "模型更新成功",
				"data": models[i],
			})
			return
		}
	}

	c.JSON(http.StatusNotFound, gin.H{
		"error": "模型不存在",
	})
}

// DeleteModel 删除模型
func DeleteModel(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "无效的模型ID",
		})
		return
	}

	models, err := loadModels()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "读取模型数据失败",
			"message": err.Error(),
		})
		return
	}

	for i, model := range models {
		if model.ID == id {
			models = append(models[:i], models[i+1:]...)
			if err := saveModels(models); err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{
					"error": "保存模型数据失败",
					"message": err.Error(),
				})
				return
			}

			c.JSON(http.StatusOK, gin.H{
				"success": true,
				"message": "模型删除成功",
			})
			return
		}
	}

	c.JSON(http.StatusNotFound, gin.H{
		"error": "模型不存在",
	})
}