# -*- coding: utf-8 -*-
"""
CSV写入器测试脚本
测试16通道并发写入CSV文件
"""

import sys
import time
import random
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from client.storage.detection_result_csv_writer import DetectionResultCSVWriter


class MockMainWindow:
    """模拟主窗口，用于测试"""

    def __init__(self):
        # 模拟通道任务标签
        for i in range(1, 17):
            mission_var_name = f'channel{i}mission'

            # 创建模拟标签对象
            class MockLabel:
                def __init__(self, text):
                    self._text = text

                def text(self):
                    return self._text

            # 前8个通道分配任务1，后8个通道分配任务2
            if i <= 8:
                task_name = "任务1_测试任务"
            else:
                task_name = "任务2_生产任务"

            setattr(self, mission_var_name, MockLabel(task_name))


def test_csv_writer():
    """测试CSV写入器"""
    print("=" * 60)
    print("CSV写入器测试 - 16通道并发写入")
    print("=" * 60)

    # 创建模拟主窗口
    main_window = MockMainWindow()

    # 创建CSV写入器
    csv_writer = DetectionResultCSVWriter(main_window=main_window)

    print(f"\n基础保存目录: {csv_writer.base_save_dir}")
    print("\n开始写入测试数据...")

    # 模拟16个通道同时推送数据
    for round_num in range(1, 4):  # 3轮数据
        print(f"\n--- 第 {round_num} 轮数据 ---")

        for channel_num in range(1, 17):  # 16个通道
            channel_id = f'channel{channel_num}'

            # 生成随机液位高度数据（3-5个液位）
            num_heights = random.randint(3, 5)
            heights = [round(random.uniform(80.0, 150.0), 2) for _ in range(num_heights)]

            # 写入CSV
            csv_writer.write_detection_result(
                channel_id=channel_id,
                heights=heights,
                timestamp=time.time()
            )

            print(f"  {channel_id}: 写入 {len(heights)} 个液位数据")

        # 模拟数据推送间隔
        time.sleep(0.5)

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

    # 显示生成的CSV文件
    print("\n生成的CSV文件:")
    for channel_id, filepath in csv_writer.csv_filepaths.items():
        print(f"  {channel_id}: {filepath}")

    # 关闭所有文件
    print("\n关闭所有CSV文件...")
    csv_writer.close_all()

    print("\n测试结束！")


if __name__ == "__main__":
    test_csv_writer()
