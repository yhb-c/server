#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的TensorRT模型测试
"""

import os
import numpy as np

model_path = "/home/lqj/liquid/server/database/model/detection_model/3/3.engine"

print("=" * 60)
print("TensorRT模型简单测试")
print("=" * 60)

# 1. 检查模型文件
print(f"\n1. 模型文件: {model_path}")
if not os.path.exists(model_path):
    print(f"❌ 文件不存在")
    exit(1)

file_size = os.path.getsize(model_path) / (1024 * 1024)
print(f"✅ 文件存在，大小: {file_size:.2f} MB")

# 2. 检查ultralytics
print("\n2. 检查ultralytics")
try:
    from ultralytics import YOLO
    print("✅ ultralytics已安装")
except ImportError as e:
    print(f"❌ ultralytics未安装: {e}")
    exit(1)

# 3. 检查CUDA
print("\n3. 检查CUDA")
try:
    import torch
    if torch.cuda.is_available():
        print(f"✅ CUDA可用")
        print(f"   - CUDA版本: {torch.version.cuda}")
        print(f"   - GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("❌ CUDA不可用")
        exit(1)
except Exception as e:
    print(f"❌ 检查CUDA失败: {e}")
    exit(1)

# 4. 加载模型
print("\n4. 加载TensorRT模型")
try:
    model = YOLO(model_path, task='segment')
    print("✅ 模型加载成功")
except Exception as e:
    print(f"❌ 模型加载失败: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# 5. 测试推理
print("\n5. 测试推理")
try:
    test_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
    results = model.predict(
        source=test_image,
        imgsz=640,
        conf=0.5,
        verbose=False
    )
    print("✅ 推理成功")
    print(f"   - 检测结果数量: {len(results)}")
    if len(results) > 0:
        result = results[0]
        if result.masks is not None:
            print(f"   - 检测到的mask数量: {len(result.masks)}")
        else:
            print(f"   - 未检测到mask（正常，因为是随机图像）")

    print("\n" + "=" * 60)
    print("✅ TensorRT模型可以在本机正常使用！")
    print("=" * 60)

except Exception as e:
    print(f"❌ 推理失败: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
