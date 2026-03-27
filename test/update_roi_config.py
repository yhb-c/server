# -*- coding: utf-8 -*-
"""
批量更新ROI配置为全画面
"""
import yaml
from pathlib import Path

config_path = Path("/home/lqj/liquid/server/database/config/annotation_result.yaml")

# 读取配置
with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# 视频分辨率
width = 1280
height = 848
center_x = width // 2
center_y = height // 2
size = width  # 使用宽度作为size

# 更新所有通道
for channel_id in config.keys():
    channel_config = config[channel_id]
    num_areas = channel_config['annotation_count']

    # 更新boxes为全画面
    channel_config['boxes'] = [[center_x, center_y, size]] * num_areas

    # 更新fixed_bottoms和fixed_tops
    channel_config['fixed_bottoms'] = [height - 24] * num_areas  # 底部留24像素边距
    channel_config['fixed_tops'] = [24] * num_areas  # 顶部留24像素边距

    # 更新init_levels
    channel_config['init_levels'] = [[center_x, height - 24]] * num_areas

    # 更新fixed_init_levels
    channel_config['fixed_init_levels'] = [0.0] * num_areas

    # 更新时间戳
    channel_config['last_updated'] = '2026-03-25 00:00:00'

# 保存配置
with open(config_path, 'w', encoding='utf-8') as f:
    yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

print(f"已更新所有通道的ROI配置为全画面 ({width}x{height})")
print(f"配置文件: {config_path}")
