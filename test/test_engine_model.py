import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "server"))

import cv2
import numpy as np
from detection.detector import LiquidDetectionEngine

def test_engine_model_load():
    """测试.engine格式模型加载"""
    print("=" * 60)
    print("测试1: .engine格式模型加载")
    print("=" * 60)

    engine_files = [
        "/home/lqj/liquid/server/database/model/detection_model/3/3.engine",
        "/home/lqj/liquid/server/database/model/detection_model/4/4.engine",
        "/home/lqj/liquid/server/database/model/detection_model/testmodel/1.engine"
    ]

    for model_path in engine_files:
        if not Path(model_path).exists():
            print(f"跳过: 模型文件不存在 - {model_path}")
            continue

        print(f"\n测试模型: {model_path}")
        try:
            engine = LiquidDetectionEngine(device='cuda')
            success = engine.load_model(model_path)

            if success:
                print(f"  成功: 模型加载成功")
                print(f"  - 实际路径: {engine.model_path}")
                print(f"  - 模型类型: {type(engine.model)}")
                return True, engine, model_path
            else:
                print(f"  失败: 模型加载返回False")
        except Exception as e:
            print(f"  失败: 模型加载异常 - {e}")
            import traceback
            traceback.print_exc()

    return False, None, None

def test_engine_model_inference(engine, model_path):
    """测试.engine格式模型推理"""
    print("\n" + "=" * 60)
    print("测试2: .engine格式模型推理")
    print("=" * 60)

    try:
        boxes = [[100, 100, 400, 400]]
        fixed_bottoms = [400]
        fixed_tops = [100]
        actual_heights = [50.0]

        engine.configure(boxes, fixed_bottoms, fixed_tops, actual_heights)

        frame = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)

        print(f"使用模型: {model_path}")
        print(f"输入帧尺寸: {frame.shape}")

        result = engine.detect(frame)

        print(f"成功: 推理完成")
        print(f"  - 返回类型: {type(result)}")
        print(f"  - 返回键: {result.keys()}")
        print(f"  - success: {result.get('success')}")
        print(f"  - liquid_line_positions: {result.get('liquid_line_positions')}")

        return True

    except Exception as e:
        print(f"失败: 推理异常 - {e}")
        import traceback
        traceback.print_exc()
        return False

def test_engine_model_with_real_image():
    """测试.engine格式模型使用真实图像"""
    print("\n" + "=" * 60)
    print("测试3: .engine格式模型使用真实图像")
    print("=" * 60)

    try:
        model_path = "/home/lqj/liquid/server/database/model/detection_model/testmodel/1.engine"

        if not Path(model_path).exists():
            print(f"跳过: 模型文件不存在")
            return True

        engine = LiquidDetectionEngine(device='cuda')
        success = engine.load_model(model_path)

        if not success:
            print("失败: 模型加载失败")
            return False

        rtsp_url = "rtsp://admin:cei345678@192.168.0.27:8000/stream1"
        cap = cv2.VideoCapture(rtsp_url)

        if not cap.isOpened():
            print(f"警告: 无法打开RTSP流，使用随机图像")
            frame = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
        else:
            ret, frame = cap.read()
            cap.release()

            if not ret:
                print(f"警告: 无法读取帧，使用随机图像")
                frame = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
            else:
                print(f"成功: 从RTSP流获取帧 {frame.shape}")

        boxes = [[100, 100, 500, 500]]
        fixed_bottoms = [500]
        fixed_tops = [100]
        actual_heights = [50.0]

        engine.configure(boxes, fixed_bottoms, fixed_tops, actual_heights)

        result = engine.detect(frame)

        print(f"成功: 推理完成")
        print(f"  - success: {result.get('success')}")
        print(f"  - liquid_line_positions: {result.get('liquid_line_positions')}")

        return True

    except Exception as e:
        print(f"失败: 测试异常 - {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """运行所有测试"""
    print("\n开始测试.engine格式模型\n")

    results = []

    success, engine, model_path = test_engine_model_load()
    results.append(("模型加载", success))

    if success and engine:
        results.append(("模型推理", test_engine_model_inference(engine, model_path)))
    else:
        print("\n跳过推理测试(模型加载失败)")
        results.append(("模型推理", False))

    results.append(("真实图像推理", test_engine_model_with_real_image()))

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
