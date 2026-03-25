-- 用户和配置初始化脚本
-- 当前使用免密公用账户模式
USE liquid_db;

-- 插入公用账户（免密登录）
INSERT INTO users (user_id, username, password, role, status)
VALUES
    ('user', 'user', NULL, 'user', 1)
ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP;

-- 插入默认配置
-- 相机配置
INSERT INTO user_configs (user_id, config_key, config_value, config_type, description)
VALUES
    ('user', 'camera_rtsp', JSON_OBJECT(
        'url', 'rtsp://admin:cei345678@192.168.0.27:8000/stream1',
        'width', 1920,
        'height', 1080,
        'fps', 25
    ), 'camera_config', '相机RTSP流配置'),

    ('user', 'camera_decode', JSON_OBJECT(
        'use_hikvision_sdk', true,
        'decode_threads', 4
    ), 'camera_config', '相机解码配置'),

    ('user', 'model_yolo', JSON_OBJECT(
        'model_path', '/home/lqj/liquid/models/yolo_liquid.pt',
        'confidence', 0.5,
        'iou_threshold', 0.45
    ), 'model_config', 'YOLO模型配置'),

    ('user', 'display_ui', JSON_OBJECT(
        'show_fps', true,
        'show_liquid_line', true,
        'line_color', '#FF0000',
        'line_thickness', 2
    ), 'display_config', '界面显示配置'),

    ('user', 'system_server', JSON_OBJECT(
        'api_host', '192.168.0.121',
        'api_port', 8084,
        'ws_port', 8085,
        'auto_reconnect', true
    ), 'system_config', '服务器连接配置')
ON DUPLICATE KEY UPDATE
    config_value = VALUES(config_value),
    updated_at = CURRENT_TIMESTAMP;
