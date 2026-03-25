#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库客户端简单示例（无 GUI）
演示基本的数据库操作
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.db_client import DatabaseClient


def main():
    """主函数"""
    # 创建数据库客户端
    client = DatabaseClient(base_url="http://localhost:8080")

    print("=" * 60)
    print("数据库客户端测试")
    print("=" * 60)

    # 1. 测试连接
    print("\n1. 测试连接...")
    if client.test_connection():
        print("✓ 连接成功")
    else:
        print("✗ 连接失败，请确保服务器正在运行")
        return

    # 2. 创建任务
    print("\n2. 创建测试任务...")
    task_id = f"test_{int(datetime.now().timestamp())}"
    result = client.create_mission({
        "task_id": task_id,
        "task_name": "Python 测试任务",
        "status": "未启动",
        "selected_channels": ["通道1", "通道2", "通道3"],
        "created_time": datetime.now().isoformat(),
        "mission_result_folder_path": "/tmp/test"
    })

    if "error" in result:
        print(f"✗ 创建失败: {result['error']}")
    else:
        print(f"✓ 创建成功: {task_id}")

    # 3. 获取任务列表
    print("\n3. 获取任务列表...")
    missions = client.get_missions(limit=5)
    print(f"找到 {len(missions)} 个任务:")
    for mission in missions:
        print(f"  - {mission['task_id']}: {mission['task_name']} ({mission['status']})")

    # 4. 获取单个任务
    print(f"\n4. 获取任务详情: {task_id}")
    mission = client.get_mission(task_id)
    if mission:
        print(f"  任务名称: {mission['task_name']}")
        print(f"  状态: {mission['status']}")
        print(f"  通道数: {len(mission['selected_channels'])}")
        print(f"  创建时间: {mission['created_time']}")

    # 5. 更新任务状态
    print(f"\n5. 更新任务状态...")
    result = client.update_mission_status(task_id, "进行中")
    if "error" in result:
        print(f"✗ 更新失败: {result['error']}")
    else:
        print(f"✓ 状态已更新为: 进行中")

    # 6. 添加结果数据
    print(f"\n6. 添加结果数据...")
    for i in range(5):
        result = client.create_mission_result(
            task_id=task_id,
            channel_name="通道1",
            region_name="区域1",
            timestamp=datetime.now(),
            value=1.0 + i * 0.5
        )
        if "error" not in result:
            print(f"  ✓ 添加数据点 {i+1}: {1.0 + i * 0.5}")

    # 7. 获取结果数据
    print(f"\n7. 获取结果数据...")
    mission = client.get_mission(task_id)
    if mission:
        mission_id = mission['id']
        results = client.get_mission_results(
            task_id=task_id,
            channel="通道1",
            region="区域1"
        )
        print(f"找到 {len(results)} 条结果:")
        for result in results[:5]:
            print(f"  - {result['timestamp']}: {result['value']}")

    # 8. 保存配置
    print(f"\n8. 保存配置...")
    config_result = client.save_config(
        config_type="test",
        config_name="example",
        config_data={
            "setting1": "value1",
            "setting2": 123,
            "setting3": ["a", "b", "c"]
        }
    )
    if "error" in config_result:
        print(f"✗ 保存失败: {config_result['error']}")
    else:
        print(f"✓ 配置已保存")

    # 9. 获取配置
    print(f"\n9. 获取配置...")
    config = client.get_config("test", "example")
    if config:
        print(f"  配置类型: {config['config_type']}")
        print(f"  配置名称: {config['config_name']}")
        print(f"  配置数据: {config['config_data']}")

    # 10. 批量添加结果
    print(f"\n10. 批量添加结果...")
    batch_results = []
    for i in range(10):
        batch_results.append({
            "channel_name": "通道2",
            "region_name": "区域2",
            "timestamp": datetime.now().isoformat(),
            "value": 2.0 + i * 0.1
        })

    batch_result = client.batch_create_results(task_id, batch_results)
    print(f"  成功: {batch_result['success']}")
    print(f"  失败: {batch_result['error']}")
    print(f"  总计: {batch_result['total']}")

    # 11. 清理（可选）
    print(f"\n11. 清理测试数据...")
    choice = input("是否删除测试任务？(y/n): ")
    if choice.lower() == 'y':
        result = client.delete_mission(task_id)
        if "error" in result:
            print(f"✗ 删除失败: {result['error']}")
        else:
            print(f"✓ 任务已删除")

        result = client.delete_config("test", "example")
        if "error" in result:
            print(f"✗ 删除配置失败: {result['error']}")
        else:
            print(f"✓ 配置已删除")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

    # 关闭连接
    client.close()


if __name__ == "__main__":
    main()
