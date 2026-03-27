import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "server"))

import cv2
import numpy as np
from detection.detector import LiquidDetectionEngine

def test_engine_basic():
    """测试engine基本功能"""
    print("=" * 60)
    print("测试1: LiquidDetectionEngine基本功能")
    print("=" * 60)

    try:
        engine = LiquidDetectionEngine(device='cpu')
        print("成功: Engine初始化成功")
        print(f"  - 设备: {engine.device}")
        print(f"  - 批次大小: {engine.batch_size}")
        print(f"  - 调试模式: {engine.debug}")
        return True
    except Exception as e:
        print(f"失败: Engine初始化失败 - {e}")
        import traceback
        traceback.print_exc()
        return False

def test_engine_configure():
    """测试engine配置功能"""
    print("\n" + "=" * 60)
    print("测试2: Engine配置功能")
    print("=" * 60)

    try:
        engine = LiquidDetectionEngine(device='cpu')

        boxes = [[100, 100, 200, 300]]
        fixed_bottoms = [300]
        fixed_tops = [100]
        actual_heights = [50.0]

        engine.configure(boxes, fixed_bottoms, fixed_tops, actual_heights)

        print("成功: Engine配置成功")
        print(f"  - 目标数量: {len(engine.targets)}")
        print(f"  - 容器底部: {engine.fixed_container_bottoms}")
        print(f"  - 容器顶部: {engine.fixed_container_tops}")
        print(f"  - 实际高度: {engine.actual_heights}")
        return True
    except Exception as e:
        print(f"失败: Engine配置失败 - {e}")
        import traceback
        traceback.print_exc()
        return False

def test_engine_model_load():
    """测试engine模型加载功能"""
    print("\n" + "=" * 60)
    print("测试3: Engine模型加载功能")
    print("=" * 60)

    try:
        engine = LiquidDetectionEngine(device='cpu')

        model_path = project_root / "server" / "models" / "best.pt"

        if not model_path.exists():
            print(f"警告: 模型文件不存在 - {model_path}")
            print("跳过模型加载测试")
            return True

        success = engine.load_model(str(model_path))

        if success:
            print("成功: 模型加载成功")
            print(f"  - 模型路径: {engine.model_path}")
            print(f"  - 模型对象: {type(engine.model)}")
            return True
        else:
            print("失败: 模型加载失败")
            return False

    except Exception as e:
        print(f"失败: 模型加载异常 - {e}")
        import traceback
        traceback.print_exc()
        return False

def test_engine_detect_without_model():
    """测试engine在没有模型时的检测行为"""
    print("\n" + "=" * 60)
    print("测试4: Engine检测功能(无模型)")
    print("=" * 60)

    try:
        engine = LiquidDetectionEngine(device='cpu')

        boxes = [[100, 100, 200, 300]]
        fixed_bottoms = [300]
        fixed_tops = [100]
        actual_heights = [50.0]

        engine.configure(boxes, fixed_bottoms, fixed_tops, actual_heights)

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        result = engine.detect(frame)

        print("成功: Engine检测执行完成")
        print(f"  - 返回类型: {type(result)}")
        print(f"  - 返回内容: {result}")
        return True

    except Exception as e:
        print(f"失败: Engine检测异常 - {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """运行所有测试"""
    print("\n开始测试LiquidDetectionEngine\n")

    results = []

    results.append(("基本初始化", test_engine_basic()))
    results.append(("配置功能", test_engine_configure()))
    results.append(("模型加载", test_engine_model_load()))
    results.append(("检测功能", test_engine_detect_without_model()))

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for name, result in results:
        status = "通过" if result else "失败"
        print(f"{name}: {status}")

    total = len(results)
    passed = sum(1 for _, r in results if r)

    print(f"\n总计: {passed}/{total} 测试通过")

    return all(r for _, r in results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
