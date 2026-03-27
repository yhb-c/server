# -*- coding: utf-8 -*-

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.config_manager import ConfigManager


def test_config_manager():
    """测试配置管理器功能"""

    print("=" * 60)
    print("客户端配置管理器测试")
    print("=" * 60)

    # 1. 初始化配置管理器
    print("\n1. 初始化配置管理器")
    config_manager = ConfigManager(user_id="user", api_base_url="http://192.168.0.121:8084")

    # 2. 从服务器拉取配置
    print("\n2. 从服务器拉取配置")
    success = config_manager.fetch_all_configs_from_server()
    if success:
        print("拉取成功")
    else:
        print("拉取失败，使用本地缓存")

    # 3. 获取所有配置
    print("\n3. 获取所有配置")
    all_configs = config_manager.get_all_configs()
    print(f"配置总数: {len(all_configs)}")
    for key in all_configs.keys():
        print(f"  - {key}")

    # 4. 获取相机配置
    print("\n4. 获取相机配置")
    camera_configs = config_manager.get_configs_by_type('camera_config')
    print(f"相机配置数量: {len(camera_configs)}")
    for key, value in camera_configs.items():
        print(f"  {key}: {value}")

    # 5. 获取单个配置
    print("\n5. 获取单个配置")
    camera_rtsp = config_manager.get_config('camera_rtsp')
    if camera_rtsp:
        print(f"camera_rtsp配置: {camera_rtsp}")

    # 6. 更新配置
    print("\n6. 更新配置（测试）")
    test_config = {
        'url': 'rtsp://admin:cei345678@192.168.0.27:8000/stream1',
        'width': 1920,
        'height': 1080,
        'fps': 30
    }
    success = config_manager.update_config(
        config_key='camera_rtsp_test',
        config_value=test_config,
        config_type='camera_config',
        description='测试相机配置更新'
    )
    if success:
        print("配置更新成功")
    else:
        print("配置更新失败")

    # 7. 导出配置到YAML
    print("\n7. 导出配置到YAML")
    export_path = project_root / "config" / "cache" / "camera_config_export.yaml"
    success = config_manager.export_to_yaml('camera_config', str(export_path))
    if success:
        print(f"配置已导出到: {export_path}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_config_manager()
