package main

import (
	"database/sql"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"gopkg.in/yaml.v2"
)

// Mission 任务结构
type Mission struct {
	TaskID                   string   `yaml:"task_id"`
	TaskName                 string   `yaml:"task_name"`
	Status                   string   `yaml:"status"`
	SelectedChannels         []string `yaml:"selected_channels"`
	CreatedTime              string   `yaml:"created_time"`
	MissionResultFolderPath  string   `yaml:"mission_result_folder_path"`
}

// Config 配置结构
type Config struct {
	Type string
	Name string
	Data map[string]interface{}
}

// DataMigrator 数据迁移器
type DataMigrator struct {
	db *sql.DB
}

// NewDataMigrator 创建迁移器
func NewDataMigrator(dsn string) (*DataMigrator, error) {
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, fmt.Errorf("连接数据库失败: %v", err)
	}

	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("数据库连接测试失败: %v", err)
	}

	return &DataMigrator{db: db}, nil
}

// Close 关闭数据库连接
func (dm *DataMigrator) Close() error {
	return dm.db.Close()
}

// MigrateMissions 迁移任务数据
func (dm *DataMigrator) MigrateMissions(yamlDir string) error {
	files, err := filepath.Glob(filepath.Join(yamlDir, "*.yaml"))
	if err != nil {
		return err
	}

	for _, file := range files {
		data, err := ioutil.ReadFile(file)
		if err != nil {
			log.Printf("读取文件失败 %s: %v", file, err)
			continue
		}

		var mission Mission
		if err := yaml.Unmarshal(data, &mission); err != nil {
			log.Printf("解析 YAML 失败 %s: %v", file, err)
			continue
		}

		if err := dm.insertMission(&mission); err != nil {
			log.Printf("插入任务失败 %s: %v", file, err)
			continue
		}

		log.Printf("成功迁移任务: %s", mission.TaskName)
	}

	return nil
}

// insertMission 插入任务数据
func (dm *DataMigrator) insertMission(mission *Mission) error {
	tx, err := dm.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	// 解析时间
	createdTime, err := time.Parse("2006-01-02 15:04:05", mission.CreatedTime)
	if err != nil {
		return fmt.Errorf("时间解析失败: %v", err)
	}

	// 插入任务
	result, err := tx.Exec(`
		INSERT INTO missions (task_id, task_name, status, created_time, mission_result_folder_path)
		VALUES (?, ?, ?, ?, ?)
		ON DUPLICATE KEY UPDATE
			task_name = VALUES(task_name),
			status = VALUES(status),
			mission_result_folder_path = VALUES(mission_result_folder_path)
	`, mission.TaskID, mission.TaskName, mission.Status, createdTime, mission.MissionResultFolderPath)

	if err != nil {
		return err
	}

	missionID, err := result.LastInsertId()
	if err != nil {
		return err
	}

	// 删除旧的通道关联
	_, err = tx.Exec("DELETE FROM mission_channels WHERE mission_id = ?", missionID)
	if err != nil {
		return err
	}

	// 插入通道关联
	for _, channel := range mission.SelectedChannels {
		_, err = tx.Exec(`
			INSERT INTO mission_channels (mission_id, channel_name)
			VALUES (?, ?)
		`, missionID, channel)
		if err != nil {
			return err
		}
	}

	return tx.Commit()
}

// MigrateCSVResults 迁移 CSV 结果数据
func (dm *DataMigrator) MigrateCSVResults(csvDir string, taskID string) error {
	// 获取任务 ID
	var missionID int
	err := dm.db.QueryRow("SELECT id FROM missions WHERE task_id = ?", taskID).Scan(&missionID)
	if err != nil {
		return fmt.Errorf("任务不存在: %v", err)
	}

	files, err := filepath.Glob(filepath.Join(csvDir, "*.csv"))
	if err != nil {
		return err
	}

	for _, file := range files {
		if err := dm.importCSVFile(file, missionID); err != nil {
			log.Printf("导入 CSV 失败 %s: %v", file, err)
			continue
		}
		log.Printf("成功导入 CSV: %s", filepath.Base(file))
	}

	return nil
}

// importCSVFile 导入单个 CSV 文件
func (dm *DataMigrator) importCSVFile(filePath string, missionID int) error {
	// 从文件名解析通道和区域信息
	fileName := filepath.Base(filePath)
	fileName = strings.TrimSuffix(fileName, ".csv")
	parts := strings.Split(fileName, "_")
	if len(parts) != 2 {
		return fmt.Errorf("文件名格式错误: %s", fileName)
	}
	channelName := parts[0]
	regionName := parts[1]

	file, err := os.Open(filePath)
	if err != nil {
		return err
	}
	defer file.Close()

	reader := csv.NewReader(file)
	records, err := reader.ReadAll()
	if err != nil {
		return err
	}

	tx, err := dm.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	stmt, err := tx.Prepare(`
		INSERT INTO mission_results (mission_id, channel_name, region_name, timestamp, value)
		VALUES (?, ?, ?, ?, ?)
	`)
	if err != nil {
		return err
	}
	defer stmt.Close()

	for _, record := range records {
		if len(record) != 2 {
			continue
		}

		timestamp, err := time.Parse("2006-01-02-15:04:05.000", record[0])
		if err != nil {
			log.Printf("时间解析失败 %s: %v", record[0], err)
			continue
		}

		_, err = stmt.Exec(missionID, channelName, regionName, timestamp, record[1])
		if err != nil {
			log.Printf("插入数据失败: %v", err)
			continue
		}
	}

	return tx.Commit()
}

// MigrateConfigs 迁移配置文件
func (dm *DataMigrator) MigrateConfigs(configDir string, configType string) error {
	files, err := filepath.Glob(filepath.Join(configDir, "*.yaml"))
	if err != nil {
		return err
	}

	for _, file := range files {
		data, err := ioutil.ReadFile(file)
		if err != nil {
			log.Printf("读取配置文件失败 %s: %v", file, err)
			continue
		}

		var config map[string]interface{}
		if err := yaml.Unmarshal(data, &config); err != nil {
			log.Printf("解析配置失败 %s: %v", file, err)
			continue
		}

		configName := strings.TrimSuffix(filepath.Base(file), ".yaml")
		if err := dm.insertConfig(configType, configName, config); err != nil {
			log.Printf("插入配置失败 %s: %v", file, err)
			continue
		}

		log.Printf("成功迁移配置: %s/%s", configType, configName)
	}

	return nil
}

// insertConfig 插入配置数据
func (dm *DataMigrator) insertConfig(configType, configName string, data map[string]interface{}) error {
	jsonData, err := json.Marshal(data)
	if err != nil {
		return err
	}

	_, err = dm.db.Exec(`
		INSERT INTO configs (config_type, config_name, config_data)
		VALUES (?, ?, ?)
		ON DUPLICATE KEY UPDATE config_data = VALUES(config_data)
	`, configType, configName, jsonData)

	return err
}

func main() {
	// 数据库连接配置
	dsn := "username:password@tcp(localhost:3306)/liquid_db?parseTime=true&charset=utf8mb4"

	migrator, err := NewDataMigrator(dsn)
	if err != nil {
		log.Fatal(err)
	}
	defer migrator.Close()

	// 迁移任务数据
	log.Println("开始迁移任务数据...")
	if err := migrator.MigrateMissions("/home/lqj/liquid/server/database/config/mission"); err != nil {
		log.Printf("任务迁移失败: %v", err)
	}

	// 迁移 CSV 结果数据
	log.Println("开始迁移 CSV 结果数据...")
	if err := migrator.MigrateCSVResults("/home/lqj/liquid/server/database/mission_result/1_1", "1"); err != nil {
		log.Printf("CSV 迁移失败: %v", err)
	}

	// 迁移配置数据
	log.Println("开始迁移配置数据...")
	if err := migrator.MigrateConfigs("/home/lqj/liquid/server/database/config", "system"); err != nil {
		log.Printf("配置迁移失败: %v", err)
	}

	log.Println("数据迁移完成！")
}
