-- MySQL 数据库架构设计
-- 创建数据库
CREATE DATABASE IF NOT EXISTS liquid_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE liquid_db;

-- 任务表
CREATE TABLE IF NOT EXISTS missions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(50) NOT NULL UNIQUE,
    task_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT '未启动',
    created_time DATETIME NOT NULL,
    mission_result_folder_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_task_id (task_id),
    INDEX idx_status (status),
    INDEX idx_created_time (created_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 任务通道关联表
CREATE TABLE IF NOT EXISTS mission_channels (
    id INT AUTO_INCREMENT PRIMARY KEY,
    mission_id INT NOT NULL,
    channel_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (mission_id) REFERENCES missions(id) ON DELETE CASCADE,
    INDEX idx_mission_id (mission_id),
    INDEX idx_channel_name (channel_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 任务结果数据表（存储 CSV 数据）
CREATE TABLE IF NOT EXISTS mission_results (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    mission_id INT NOT NULL,
    channel_name VARCHAR(100) NOT NULL,
    region_name VARCHAR(100) NOT NULL,
    timestamp DATETIME NOT NULL,
    value DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (mission_id) REFERENCES missions(id) ON DELETE CASCADE,
    INDEX idx_mission_id (mission_id),
    INDEX idx_channel_region (channel_name, region_name),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 配置表（存储各种 YAML 配置）
CREATE TABLE IF NOT EXISTS configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_type VARCHAR(100) NOT NULL,
    config_name VARCHAR(255) NOT NULL,
    config_data JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_config (config_type, config_name),
    INDEX idx_config_type (config_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
