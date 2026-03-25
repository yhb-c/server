#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查TensorRT引擎文件的兼容性
"""

import os

model_path = "/home/lqj/liquid/server/database/model/detection_model/3/3.engine"

print("=" * 70)
print("TensorRT引擎兼容性诊断")
print("=" * 70)

# 1. 文件信息
print(f"\n【1】模型文件信息")
if os.path.exists(model_path):
    file_size = os.path.getsize(model_path) / (1024 * 1024)
    print(f"✅ 文件路径: {model_path}")
    print(f"✅ 文件大小: {file_size:.2f} MB")
else:
    print(f"❌ 文件不存在: {model_path}")
    exit(1)

# 2. 系统CUDA版本
print(f"\n【2】系统CUDA环境")
try:
    import subprocess
    result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
    for line in result.stdout.split('\n'):
        if 'CUDA Version' in line:
            print(f"✅ {line.strip()}")
            break
except:
    print("⚠️  无法获取nvidia-smi信息")

# 3. PyTorch CUDA版本
print(f"\n【3】PyTorch环境")
try:
    import torch
    print(f"✅ PyTorch版本: {torch.__version__}")
    print(f"✅ CUDA可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"✅ PyTorch CUDA版本: {torch.version.cuda}")
        print(f"✅ GPU设备: {torch.cuda.get_device_name(0)}")
        print(f"✅ GPU数量: {torch.cuda.device_count()}")
except ImportError:
    print("❌ PyTorch未安装")
    exit(1)

# 4. TensorRT版本
print(f"\n【4】TensorRT环境")
try:
    import tensorrt as trt
    print(f"✅ TensorRT版本: {trt.__version__}")
except ImportError:
    print("⚠️  TensorRT Python包未安装（ultralytics可能使用内置版本）")

# 5. Ultralytics版本
print(f"\n【5】Ultralytics环境")
try:
    import ultralytics
    print(f"✅ Ultralytics版本: {ultralytics.__version__}")
except ImportError:
    print("❌ Ultralytics未安装")
    exit(1)

# 6. 尝试读取引擎文件头部信息
print(f"\n【6】TensorRT引擎文件分析")
try:
    with open(model_path, 'rb') as f:
        header = f.read(100)
        print(f"✅ 文件头部（前100字节）:")
        print(f"   {header[:50].hex()}")

        # 检查是否包含TensorRT标识
        if b'TensorRT' in header or b'NVIDIA' in header:
            print(f"✅ 文件包含TensorRT标识")
        else:
            print(f"⚠️  未在文件头部找到明显的TensorRT标识")
except Exception as e:
    print(f"❌ 读取文件失败: {e}")

# 7. 兼容性总结
print(f"\n" + "=" * 70)
print("【诊断结果】")
print("=" * 70)

print("""
TensorRT引擎文件(.engine)是平台相关的，需要满足以下条件才能使用：

1. ✅ GPU架构匹配（RTX 4070 = Ada Lovelace架构）
2. ⚠️  CUDA版本兼容性：
   - 系统CUDA: 12.2
   - PyTorch CUDA: 11.7
   - 引擎构建时的CUDA版本: 未知

3. ⚠️  TensorRT版本兼容性：
   - 当前环境TensorRT版本: 需要检查
   - 引擎构建时的TensorRT版本: 未知

【建议】：
""")

import torch
if torch.version.cuda:
    pytorch_cuda = torch.version.cuda
    print(f"1. 当前PyTorch使用CUDA {pytorch_cuda}，但系统有CUDA 12.2")
    print(f"   建议：重新导出TensorRT引擎，或升级PyTorch到CUDA 12.x版本")
    print(f"\n2. 如果引擎是在其他机器上构建的，建议在本机重新导出：")
    print(f"   conda run -n liquid python -c \"")
    print(f"   from ultralytics import YOLO")
    print(f"   model = YOLO('原始.pt模型路径')")
    print(f"   model.export(format='engine', device=0, half=True)")
    print(f"   \"")
    print(f"\n3. 或者使用ONNX格式（更通用，但可能稍慢）：")
    print(f"   model.export(format='onnx', dynamic=True)")

print("\n" + "=" * 70)
