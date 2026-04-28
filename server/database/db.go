package database

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	_ "github.com/go-sql-driver/mysql"
)

// DB 数据库连接
type DB struct {
	conn *sql.DB
}

// Mission 任务结构
type Mission struct {
	ID                      int       `json:"id"`
	TaskID                  string    `json:"task_id"`
	TaskName                string    `json:"task_name"`
	Status                  string    `json:"status"`
	SelectedChannels        []string  `json:"selected_channels"`
	CreatedTime             time.Time `json:"created_time"`
	MissionResultFolderPath string    `json:"mission_result_folder_path"`
	CreatedAt               time.Time `json:"created_at"`
	UpdatedAt               time.Time `json:"updated_at"`
}

// MissionResult 任务结果
type MissionResult struct {
	ID          int64     `json:"id"`
	MissionID   int       `json:"mission_id"`
	ChannelName string    `json:"channel_name"`
	RegionName  string    `json:"region_name"`
	Timestamp   time.Time `json:"timestamp"`
	Value       float64   `json:"value"`
	CreatedAt   time.Time `json:"created_at"`
}

// Config 配置
type Config struct {
	ID         int                    `json:"id"`
	ConfigType string                 `json:"config_type"`
	ConfigName string                 `json:"config_name"`
	ConfigData map[string]interface{} `json:"config_data"`
	CreatedAt  time.Time              `json:"created_at"`
	UpdatedAt  time.Time              `json:"updated_at"`
}

// User 用户
type User struct {
	ID            int       `json:"id"`
	UserID        string    `json:"user_id"`
	Username      string    `json:"username"`
	Password      *string   `json:"password,omitempty"`
	Email         *string   `json:"email,omitempty"`
	Phone         *string   `json:"phone,omitempty"`
	Role          string    `json:"role"`
	Status        int       `json:"status"`
	LastLoginTime *time.Time `json:"last_login_time,omitempty"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}

// UserConfig 用户配置
type UserConfig struct {
	ID          int64                  `json:"id"`
	UserID      string                 `json:"user_id"`
	ConfigKey   string                 `json:"config_key"`
	ConfigValue map[string]interface{} `json:"config_value"`
	ConfigType  string                 `json:"config_type"`
	Description string                 `json:"description"`
	CreatedAt   time.Time              `json:"created_at"`
	UpdatedAt   time.Time              `json:"updated_at"`
}

// NewDB 创建数据库连接
func NewDB(dsn string) (*DB, error) {
	conn, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, err
	}

	if err := conn.Ping(); err != nil {
		return nil, err
	}

	// 设置连接池
	conn.SetMaxOpenConns(100)
	conn.SetMaxIdleConns(10)
	conn.SetConnMaxLifetime(time.Hour)

	return &DB{conn: conn}, nil
}

// Close 关闭数据库连接
func (db *DB) Close() error {
	return db.conn.Close()
}

// CreateMission 创建任务
func (db *DB) CreateMission(mission *Mission) error {
	tx, err := db.conn.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	result, err := tx.Exec(`
		INSERT INTO missions (task_id, task_name, status, created_time, mission_result_folder_path)
		VALUES (?, ?, ?, ?, ?)
	`, mission.TaskID, mission.TaskName, mission.Status, mission.CreatedTime, mission.MissionResultFolderPath)

	if err != nil {
		return err
	}

	missionID, err := result.LastInsertId()
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

// GetMission 获取任务
func (db *DB) GetMission(taskID string) (*Mission, error) {
	mission := &Mission{}
	err := db.conn.QueryRow(`
		SELECT id, task_id, task_name, status, created_time,
		       mission_result_folder_path, created_at, updated_at
		FROM missions WHERE task_id = ?
	`, taskID).Scan(
		&mission.ID, &mission.TaskID, &mission.TaskName, &mission.Status,
		&mission.CreatedTime, &mission.MissionResultFolderPath,
		&mission.CreatedAt, &mission.UpdatedAt,
	)

	if err != nil {
		return nil, err
	}

	// 获取通道列表
	rows, err := db.conn.Query(`
		SELECT channel_name FROM mission_channels WHERE mission_id = ?
	`, mission.ID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	mission.SelectedChannels = []string{}
	for rows.Next() {
		var channel string
		if err := rows.Scan(&channel); err != nil {
			return nil, err
		}
		mission.SelectedChannels = append(mission.SelectedChannels, channel)
	}

	return mission, nil
}

// ListMissions 列出所有任务
func (db *DB) ListMissions(limit, offset int) ([]*Mission, error) {
	rows, err := db.conn.Query(`
		SELECT id, task_id, task_name, status, created_time,
		       mission_result_folder_path, created_at, updated_at
		FROM missions
		ORDER BY created_time DESC
		LIMIT ? OFFSET ?
	`, limit, offset)

	if err != nil {
		return nil, err
	}
	defer rows.Close()

	missions := []*Mission{}
	for rows.Next() {
		mission := &Mission{}
		err := rows.Scan(
			&mission.ID, &mission.TaskID, &mission.TaskName, &mission.Status,
			&mission.CreatedTime, &mission.MissionResultFolderPath,
			&mission.CreatedAt, &mission.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}

		// 获取通道列表
		channelRows, err := db.conn.Query(`
			SELECT channel_name FROM mission_channels WHERE mission_id = ?
		`, mission.ID)
		if err != nil {
			return nil, err
		}

		mission.SelectedChannels = []string{}
		for channelRows.Next() {
			var channel string
			if err := channelRows.Scan(&channel); err != nil {
				channelRows.Close()
				return nil, err
			}
			mission.SelectedChannels = append(mission.SelectedChannels, channel)
		}
		channelRows.Close()

		missions = append(missions, mission)
	}

	return missions, nil
}

// UpdateMissionStatus 更新任务状态
func (db *DB) UpdateMissionStatus(taskID, status string) error {
	_, err := db.conn.Exec(`
		UPDATE missions SET status = ? WHERE task_id = ?
	`, status, taskID)
	return err
}

// DeleteMission 删除任务
func (db *DB) DeleteMission(taskID string) error {
	_, err := db.conn.Exec(`DELETE FROM missions WHERE task_id = ?`, taskID)
	return err
}

// CreateMissionResult 创建任务结果
func (db *DB) CreateMissionResult(result *MissionResult) error {
	_, err := db.conn.Exec(`
		INSERT INTO mission_results (mission_id, channel_name, region_name, timestamp, value)
		VALUES (?, ?, ?, ?, ?)
	`, result.MissionID, result.ChannelName, result.RegionName, result.Timestamp, result.Value)
	return err
}

// GetMissionResults 获取任务结果
func (db *DB) GetMissionResults(taskID, channelName, regionName string, startTime, endTime time.Time) ([]*MissionResult, error) {
	query := `
		SELECT mr.id, mr.mission_id, mr.channel_name, mr.region_name,
		       mr.timestamp, mr.value, mr.created_at
		FROM mission_results mr
		JOIN missions m ON mr.mission_id = m.id
		WHERE m.task_id = ?
	`
	args := []interface{}{taskID}

	if channelName != "" {
		query += " AND mr.channel_name = ?"
		args = append(args, channelName)
	}

	if regionName != "" {
		query += " AND mr.region_name = ?"
		args = append(args, regionName)
	}

	if !startTime.IsZero() {
		query += " AND mr.timestamp >= ?"
		args = append(args, startTime)
	}

	if !endTime.IsZero() {
		query += " AND mr.timestamp <= ?"
		args = append(args, endTime)
	}

	query += " ORDER BY mr.timestamp ASC"

	rows, err := db.conn.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	results := []*MissionResult{}
	for rows.Next() {
		result := &MissionResult{}
		err := rows.Scan(
			&result.ID, &result.MissionID, &result.ChannelName,
			&result.RegionName, &result.Timestamp, &result.Value, &result.CreatedAt,
		)
		if err != nil {
			return nil, err
		}
		results = append(results, result)
	}

	return results, nil
}

// SaveConfig 保存配置
func (db *DB) SaveConfig(config *Config) error {
	jsonData, err := json.Marshal(config.ConfigData)
	if err != nil {
		return err
	}

	_, err = db.conn.Exec(`
		INSERT INTO configs (config_type, config_name, config_data)
		VALUES (?, ?, ?)
		ON DUPLICATE KEY UPDATE config_data = VALUES(config_data)
	`, config.ConfigType, config.ConfigName, jsonData)

	return err
}

// GetConfig 获取配置
func (db *DB) GetConfig(configType, configName string) (*Config, error) {
	config := &Config{}
	var jsonData []byte

	err := db.conn.QueryRow(`
		SELECT id, config_type, config_name, config_data, created_at, updated_at
		FROM configs WHERE config_type = ? AND config_name = ?
	`, configType, configName).Scan(
		&config.ID, &config.ConfigType, &config.ConfigName,
		&jsonData, &config.CreatedAt, &config.UpdatedAt,
	)

	if err != nil {
		return nil, err
	}

	if err := json.Unmarshal(jsonData, &config.ConfigData); err != nil {
		return nil, err
	}

	return config, nil
}

// ListConfigs 列出配置
func (db *DB) ListConfigs(configType string) ([]*Config, error) {
	query := "SELECT id, config_type, config_name, config_data, created_at, updated_at FROM configs"
	args := []interface{}{}

	if configType != "" {
		query += " WHERE config_type = ?"
		args = append(args, configType)
	}

	rows, err := db.conn.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	configs := []*Config{}
	for rows.Next() {
		config := &Config{}
		var jsonData []byte

		err := rows.Scan(
			&config.ID, &config.ConfigType, &config.ConfigName,
			&jsonData, &config.CreatedAt, &config.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}

		if err := json.Unmarshal(jsonData, &config.ConfigData); err != nil {
			return nil, err
		}

		configs = append(configs, config)
	}

	return configs, nil
}

// DeleteConfig 删除配置
func (db *DB) DeleteConfig(configType, configName string) error {
	_, err := db.conn.Exec(`
		DELETE FROM configs WHERE config_type = ? AND config_name = ?
	`, configType, configName)
	return err
}

// GetUserConfigs 获取用户所有配置
func (db *DB) GetUserConfigs(userID string, configType string) ([]*UserConfig, error) {
	query := `
		SELECT id, user_id, config_key, config_value, config_type, description, created_at, updated_at
		FROM user_configs WHERE user_id = ?
	`
	args := []interface{}{userID}

	if configType != "" {
		query += " AND config_type = ?"
		args = append(args, configType)
	}

	query += " ORDER BY updated_at DESC"

	rows, err := db.conn.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	configs := []*UserConfig{}
	for rows.Next() {
		config := &UserConfig{}
		var jsonData []byte

		err := rows.Scan(
			&config.ID, &config.UserID, &config.ConfigKey,
			&jsonData, &config.ConfigType, &config.Description,
			&config.CreatedAt, &config.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}

		if err := json.Unmarshal(jsonData, &config.ConfigValue); err != nil {
			return nil, err
		}

		configs = append(configs, config)
	}

	return configs, nil
}

// GetUserConfig 获取用户单个配置
func (db *DB) GetUserConfig(userID, configKey string) (*UserConfig, error) {
	config := &UserConfig{}
	var jsonData []byte

	err := db.conn.QueryRow(`
		SELECT id, user_id, config_key, config_value, config_type, description, created_at, updated_at
		FROM user_configs WHERE user_id = ? AND config_key = ?
	`, userID, configKey).Scan(
		&config.ID, &config.UserID, &config.ConfigKey,
		&jsonData, &config.ConfigType, &config.Description,
		&config.CreatedAt, &config.UpdatedAt,
	)

	if err != nil {
		return nil, err
	}

	if err := json.Unmarshal(jsonData, &config.ConfigValue); err != nil {
		return nil, err
	}

	return config, nil
}

// SaveUserConfig 保存用户配置
func (db *DB) SaveUserConfig(config *UserConfig) error {
	jsonData, err := json.Marshal(config.ConfigValue)
	if err != nil {
		return err
	}

	_, err = db.conn.Exec(`
		INSERT INTO user_configs (user_id, config_key, config_value, config_type, description)
		VALUES (?, ?, ?, ?, ?)
		ON DUPLICATE KEY UPDATE
			config_value = VALUES(config_value),
			description = VALUES(description),
			updated_at = CURRENT_TIMESTAMP
	`, config.UserID, config.ConfigKey, jsonData, config.ConfigType, config.Description)

	return err
}

// DeleteUserConfig 删除用户配置
func (db *DB) DeleteUserConfig(userID, configKey string) error {
	_, err := db.conn.Exec(`
		DELETE FROM user_configs WHERE user_id = ? AND config_key = ?
	`, userID, configKey)
	return err
}
