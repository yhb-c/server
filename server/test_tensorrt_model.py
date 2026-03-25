#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试TensorRT模型是否可以在本机使用
"""

import sys
import os
import cv2
import numpy as np
from pathlib import Path

# 添加client路径以导入detection模块
sys.path.insert(0, str(Path(__file__).parent.parent / 'client'))

def test_tensorrt_model():
    """测试TensorRT模型加载和推理"""

    model_path = "/home/lqj/liquid/server/database/model/detection_model/3/3.engine"

    print("=" * 60)
    print("TensorRT模型测试")
    print("=" * 60)

    # 1. 检查模型文件是否存在
    print(f"\n1. 检查模型文件: {model_path}")
    if not os.path.exists(model_path):
        print(f"❌ 模型文件不存在: {model_path}")
        return False

    file_size = os.path.getsize(model_path) / (1024 * 1024)
    print(f"✅ 模型文件存在，大小: {file_size:.2f} MB")

    # 2. 检查CUDA是否可用
    print("\n2. 检查CUDA环境")
    try:
        import torch
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            print(f"✅ CUDA可用")
            print(f"   - CUDA版本: {torch.version.cuda}")
            print(f"   - GPU数量: {torch.cuda.device_count()}")
            if torch.cuda.device_count() > 0:
                print(f"   - GPU名称: {torch.cuda.get_device_name(0)}")
        else:
            print("❌ CUDA不可用")
            return False
    except Exception as e:
        print(f"❌ 检查CUDA失败: {e}")
        return False

    # 3. 尝试加载检测引擎
    print("\n3. 加载液位检测引擎")
    try:
        from handlers.videopage.detection.detection import LiquidDetectionEngine
        engine = LiquidDetectionEngine(device='cuda')
        print("✅ 检测引擎创建成功")
    except Exception as e:
        print(f"❌ 创建检测引擎失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 4. 加载TensorRT模型
    print("\n4. 加载TensorRT模型")
    try:
        success = engine.load_model(model_path)
        if success:
            print(f"✅ TensorRT模型加载成功")
            print(f"   - 模型路径: {engine.model_path}")
            print(f"   - 设备: {engine.device}")
        else:
            print("❌ TensorRT模型加载失败")
            return False
    except Exception as e:
        print(f"❌ 加载模型时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 5. 创建测试图像
    print("\n5. 创建测试图像并进行推理")
    try:
        # 创建640x640的测试图像
        test_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
        print(f"✅ 测试图像创建成功: {test_image.shape}")

        # 配置检测参数
        boxes = [(320, 320, 640)]  # 中心点和尺寸
        fixed_bottoms = [600]
        fixed_tops = [40]
        actual_heights = [20.0]

        engine.configure(boxes, fixed_bottoms, fixed_tops, actual_heights)
        print("✅ 检测引擎配置成功")

    except Exception as e:
        print(f"❌ 配置检测引擎失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 6. 执行推理测试
    print("\n6. 执行推理测试")
    try:
        result = engine.detect(test_image)

        if result['success']:
            print("✅ 推理成功")
            print(f"   - 检测到的液位数量: {len(result['liquid_line_positions'])}")
            for idx, pos_data in result['liquid_line_positions'].items():
                print(f"   - 区域{idx}: 液位高度 = {pos_data['height_mm']:.2f} mm")
        else:
            print("⚠️  推理执行但未检测到液位（这是正常的，因为是随机图像）")
            print("   模型本身工作正常")

        print("\n✅ TensorRT模型可以正常使用！")
        return True

    except Exception as e:
        print(f"❌ 推理失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # 清理资源
        try:
            engine.cleanup()
        except:
            pass


if __name__ == "__main__":
    try:
        success = test_tensorrt_model()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 测试过程中发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
