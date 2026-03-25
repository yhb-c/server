#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在本机重新导出TensorRT引擎
"""

import os
import sys
from pathlib import Path

# 源模型路径
source_model = "/home/lqj/liquid/server/database/model/detection_model/testmodel/tensor.pt"
# 输出目录
output_dir = "/home/lqj/liquid/server/database/model/detection_model/testmodel"

print("=" * 70)
print("TensorRT引擎导出工具")
print("=" * 70)

# 1. 检查源模型
print(f"\n【1】检查源模型")
print(f"模型路径: {source_model}")

if not os.path.exists(source_model):
    print(f"❌ 源模型文件不存在")
    sys.exit(1)

file_size = os.path.getsize(source_model) / (1024 * 1024)
print(f"✅ 模型文件存在，大小: {file_size:.2f} MB")

# 2. 检查环境
print(f"\n【2】检查环境")
try:
    import torch
    print(f"✅ PyTorch: {torch.__version__}")
    print(f"✅ CUDA可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"✅ CUDA版本: {torch.version.cuda}")
        print(f"✅ GPU: {torch.cuda.get_device_name(0)}")
except ImportError:
    print("❌ PyTorch未安装")
    sys.exit(1)

try:
    from ultralytics import YOLO
    import ultralytics
    print(f"✅ Ultralytics: {ultralytics.__version__}")
except ImportError:
    print("❌ Ultralytics未安装")
    sys.exit(1)

# 3. 加载模型
print(f"\n【3】加载PyTorch模型")
try:
    model = YOLO(source_model)
    print(f"✅ 模型加载成功")
    print(f"   任务类型: {model.task}")
    print(f"   模型名称: {model.model_name if hasattr(model, 'model_name') else 'N/A'}")
except Exception as e:
    print(f"❌ 模型加载失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. 导出TensorRT引擎
print(f"\n【4】导出TensorRT引擎")
print(f"输出目录: {output_dir}")
print(f"配置:")
print(f"  - 格式: TensorRT (engine)")
print(f"  - 设备: GPU 0")
print(f"  - 精度: FP16 (half=True)")
print(f"  - 图像尺寸: 640")

try:
    print(f"\n开始导出...")
    print(f"⏳ 这可能需要几分钟时间，请耐心等待...")

    # 导出TensorRT引擎
    # imgsz=640: 输入图像尺寸
    # half=True: 使用FP16精度（更快，显存占用更少）
    # device=0: 使用GPU 0
    export_path = model.export(
        format='engine',
        imgsz=640,
        half=True,
        device=0,
        workspace=4,  # TensorRT工作空间大小(GB)
        verbose=True
    )

    print(f"\n✅ 导出成功！")
    print(f"   输出文件: {export_path}")

    # 检查输出文件
    if os.path.exists(export_path):
        output_size = os.path.getsize(export_path) / (1024 * 1024)
        print(f"   文件大小: {output_size:.2f} MB")

    print(f"\n【5】验证导出的引擎")
    print(f"正在加载导出的引擎进行验证...")

    # 加载导出的引擎
    engine_model = YOLO(export_path)
    print(f"✅ 引擎加载成功")

    # 测试推理
    import numpy as np
    test_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)

    print(f"正在测试推理...")
    results = engine_model.predict(
        source=test_image,
        imgsz=640,
        conf=0.5,
        verbose=False
    )

    print(f"✅ 推理测试成功")

    print("\n" + "=" * 70)
    print("✅✅✅ TensorRT引擎导出完成！")
    print("=" * 70)
    print(f"\n导出的引擎文件: {export_path}")
    print(f"\n该引擎已针对当前环境优化：")
    print(f"  - GPU: {torch.cuda.get_device_name(0)}")
    print(f"  - CUDA: {torch.version.cuda}")
    print(f"  - 精度: FP16")
    print(f"\n可以在detection.py中使用此引擎文件。")

except Exception as e:
    print(f"\n❌ 导出失败: {e}")
    import traceback
    traceback.print_exc()

    print(f"\n【故障排除】")
    print(f"如果导出失败，可以尝试：")
    print(f"1. 确保有足够的GPU显存（建议至少4GB空闲）")
    print(f"2. 检查TensorRT是否正确安装")
    print(f"3. 尝试导出ONNX格式作为替代：")
    print(f"   model.export(format='onnx', dynamic=True)")

    sys.exit(1)
