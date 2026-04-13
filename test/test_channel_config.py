#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试通道配置读取
"""

import sys
import os
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'client'))

from utils.config import RemoteConfigManager

def test_channel_config():
    """测试通道配置读取"""
    print("=" * 60)
    print("测试通道配置读取")
    print("=" * 60)

    # 创建远程配置管理器
    config_manager = RemoteConfigManager()

    # 测试读取channel1配置
    print("\n1. 测试get_channel_info(1):")
    channel1_info = config_manager.get_channel_info(1)
    print(f"   返回结果: {channel1_info}")

    if channel1_info:
        print(f"   - name: {channel1_info.get('name')}")
        print(f"   - address: {channel1_info.get('address')}")
        print(f"   - file_path: {channel1_info.get('file_path')}")

    # 测试读取完整配置
    print("\n2. 测试load_channel_config():")
    full_config = config_manager.load_channel_config()
    print(f"   配置键: {list(full_config.keys())[:10]}")

    if 'channel1' in full_config:
        print(f"   channel1配置: {full_config['channel1']}")

    if 'channels' in full_config and 1 in full_config['channels']:
        print(f"   channels[1]配置: {full_config['channels'][1]}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == '__main__':
    test_channel_config()
