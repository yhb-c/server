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

type Channel struct {
	ID          int       `json:"id"`
	Name        string    `json:"name"`
	Description string    `json:"description"`
	RTSPUrl     string    `json:"rtsp_url"`
	Enabled     bool      `json:"enabled"`
	ROI         ROI       `json:"roi"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

type ROI struct {
	X      int `json:"x"`
	Y      int `json:"y"`
	Width  int `json:"width"`
	Height int `json:"height"`
}

const channelsFile = "data/channels.json"

// 读取通道数据
func loadChannels() ([]Channel, error) {
	if err := ensureDataDir(); err != nil {
		return nil, err
	}

	if _, err := os.Stat(channelsFile); os.IsNotExist(err) {
		return []Channel{}, nil
	}

	data, err := ioutil.ReadFile(channelsFile)
	if err != nil {
		return nil, err
	}

	var channels []Channel
	err = json.Unmarshal(data, &channels)
	return channels, err
}

// 保存通道数据
func saveChannels(channels []Channel) error {
	if err := ensureDataDir(); err != nil {
		return err
	}

	data, err := json.MarshalIndent(channels, "", "  ")
	if err != nil {
		return err
	}

	return ioutil.WriteFile(channelsFile, data, 0644)
}

// GetChannels 获取所有通道
func GetChannels(c *gin.Context) {
	channels, err := loadChannels()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "读取通道数据失败",
			"message": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"data": channels,
		"total": len(channels),
	})
}

// GetChannel 获取单个通道
func GetChannel(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "无效的通道ID",
		})
		return
	}

	channels, err := loadChannels()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "读取通道数据失败",
			"message": err.Error(),
		})
		return
	}

	for _, channel := range channels {
		if channel.ID == id {
			c.JSON(http.StatusOK, gin.H{
				"success": true,
				"data": channel,
			})
			return
		}
	}

	c.JSON(http.StatusNotFound, gin.H{
		"error": "通道不存在",
	})
}

// CreateChannel 创建通道
func CreateChannel(c *gin.Context) {
	var newChannel Channel
	if err := c.ShouldBindJSON(&newChannel); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "请求参数错误",
			"message": err.Error(),
		})
		return
	}

	channels, err := loadChannels()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "读取通道数据失败",
			"message": err.Error(),
		})
		return
	}

	// 生成新ID
	maxID := 0
	for _, channel := range channels {
		if channel.ID > maxID {
			maxID = channel.ID
		}
	}
	newChannel.ID = maxID + 1
	newChannel.CreatedAt = time.Now()
	newChannel.UpdatedAt = time.Now()

	channels = append(channels, newChannel)
	if err := saveChannels(channels); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "保存通道数据失败",
			"message": err.Error(),
		})
		return
	}

	c.JSON(http.StatusCreated, gin.H{
		"success": true,
		"message": "通道创建成功",
		"data": newChannel,
	})
}

// UpdateChannel 更新通道
func UpdateChannel(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "无效的通道ID",
		})
		return
	}

	var updateData Channel
	if err := c.ShouldBindJSON(&updateData); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "请求参数错误",
			"message": err.Error(),
		})
		return
	}

	channels, err := loadChannels()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "读取通道数据失败",
			"message": err.Error(),
		})
		return
	}

	for i, channel := range channels {
		if channel.ID == id {
			channels[i].Name = updateData.Name
			channels[i].Description = updateData.Description
			channels[i].RTSPUrl = updateData.RTSPUrl
			channels[i].Enabled = updateData.Enabled
			channels[i].ROI = updateData.ROI
			channels[i].UpdatedAt = time.Now()

			if err := saveChannels(channels); err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{
					"error": "保存通道数据失败",
					"message": err.Error(),
				})
				return
			}

			c.JSON(http.StatusOK, gin.H{
				"success": true,
				"message": "通道更新成功",
				"data": channels[i],
			})
			return
		}
	}

	c.JSON(http.StatusNotFound, gin.H{
		"error": "通道不存在",
	})
}

// DeleteChannel 删除通道
func DeleteChannel(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "无效的通道ID",
		})
		return
	}

	channels, err := loadChannels()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "读取通道数据失败",
			"message": err.Error(),
		})
		return
	}

	for i, channel := range channels {
		if channel.ID == id {
			channels = append(channels[:i], channels[i+1:]...)
			if err := saveChannels(channels); err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{
					"error": "保存通道数据失败",
					"message": err.Error(),
				})
				return
			}

			c.JSON(http.StatusOK, gin.H{
				"success": true,
				"message": "通道删除成功",
			})
			return
		}
	}

	c.JSON(http.StatusNotFound, gin.H{
		"error": "通道不存在",
	})
}