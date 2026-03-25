#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终测试：尝试加载和使用TensorRT引擎
"""

import os
import sys
import numpy as np
import time

model_path = "/home/lqj/liquid/server/database/model/detection_model/3/3.engine"

print("=" * 70)
print("TensorRT引擎加载测试")
print("=" * 70)

# 环境信息
print("\n【环境信息】")
try:
    import torch
    print(f"PyTorch: {torch.__version__} (CUDA {torch.version.cuda})")
    print(f"GPU: {torch.cuda.get_device_name(0)}")
except:
    print("❌ PyTorch环境异常")
    exit(1)

try:
    import ultralytics
    print(f"Ultralytics: {ultralytics.__version__}")
except:
    print("❌ Ultralytics未安装")
    exit(1)

# 测试1: 直接加载引擎
print("\n【测试1】直接加载TensorRT引擎")
print(f"模型路径: {model_path}")

try:
    from ultralytics import YOLO

    print("正在加载模型...")
    start_time = time.time()

    # 设置超时
    import signal

    def timeout_handler(signum, frame):
        raise TimeoutError("模型加载超时（30秒）")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(30)  # 30秒超时

    try:
        model = YOLO(model_path, task='segment')
        signal.alarm(0)  # 取消超时

        load_time = time.time() - start_time
        print(f"✅ 模型加载成功！耗时: {load_time:.2f}秒")

        # 测试推理
        print("\n【测试2】执行推理测试")
        test_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)

        print("正在推理...")
        start_time = time.time()

        results = model.predict(
            source=test_image,
            imgsz=640,
            conf=0.5,
            iou=0.5,
            verbose=False,
            device=0
        )

        infer_time = time.time() - start_time
        print(f"✅ 推理成功！耗时: {infer_time*1000:.2f}ms")

        if len(results) > 0:
            result = results[0]
            if result.masks is not None:
                print(f"   检测到 {len(result.masks)} 个mask")
            else:
                print(f"   未检测到mask（正常，测试图像为随机噪声）")

        print("\n" + "=" * 70)
        print("✅✅✅ 测试通过！TensorRT引擎可以在本机正常使用！")
        print("=" * 70)
        print(f"\n性能指标：")
        print(f"  - 模型加载时间: {load_time:.2f}秒")
        print(f"  - 单帧推理时间: {infer_time*1000:.2f}ms")
        print(f"  - 理论FPS: {1/infer_time:.1f}")

        sys.exit(0)

    except TimeoutError as e:
        signal.alarm(0)
        print(f"\n❌ {e}")
        print("\n【原因分析】")
        print("模型加载超时，可能的原因：")
        print("1. TensorRT引擎与当前CUDA/TensorRT版本不兼容")
        print("2. 引擎是在不同GPU架构上构建的")
        print("3. 引擎文件损坏")

except Exception as e:
    print(f"\n❌ 加载失败: {e}")
    import traceback
    traceback.print_exc()

    print("\n【原因分析】")
    print("TensorRT引擎文件(.engine)是平台相关的，必须满足：")
    print("1. 相同的GPU架构")
    print("2. 兼容的CUDA版本")
    print("3. 兼容的TensorRT版本")
    print("4. 相同的操作系统")

    print("\n【解决方案】")
    print("需要在本机重新导出TensorRT引擎。")
    print("\n如果有原始.pt模型文件，可以运行：")
    print("  from ultralytics import YOLO")
    print("  model = YOLO('模型.pt')")
    print("  model.export(format='engine', device=0, half=True)")
    print("\n或者使用更通用的ONNX格式：")
    print("  model.export(format='onnx', dynamic=True)")

    sys.exit(1)
