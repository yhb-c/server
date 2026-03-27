package database

import (
	"database/sql"
	"encoding/json"
	"time"

	_ "github.com/go-sql-driver/mysql"
)

// DB 数据库连接
type DB struct {
	conn *sql.DB
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

var dbInstance *DB

// InitDB 初始化数据库连接
func InitDB(dsn string) error {
	conn, err := sql.Open("mysql", dsn)
	if err != nil {
		return err
	}

	if err := conn.Ping(); err != nil {
		return err
	}

	conn.SetMaxOpenConns(100)
	conn.SetMaxIdleConns(10)
	conn.SetConnMaxLifetime(time.Hour)

	dbInstance = &DB{conn: conn}
	return nil
}

// GetDB 获取数据库实例
func GetDB() *DB {
	return dbInstance
}

// Close 关闭数据库连接
func (db *DB) Close() error {
	return db.conn.Close()
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
