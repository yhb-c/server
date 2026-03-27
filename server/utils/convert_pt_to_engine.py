import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "server"))

import torch
from ultralytics import YOLO

def convert_pt_to_engine(pt_path, output_path=None, imgsz=640, device='cuda', half=False):
    """
    将pt格式模型转换为TensorRT engine格式

    Args:
        pt_path: pt模型文件路径
        output_path: 输出engine文件路径，默认与pt文件同目录同名
        imgsz: 输入图像尺寸
        device: 设备类型
        half: 是否使用FP16精度

    Returns:
        bool: 转换是否成功
    """
    pt_path = Path(pt_path)

    if not pt_path.exists():
        print(f"错误: 模型文件不存在 - {pt_path}")
        return False

    if output_path is None:
        output_path = pt_path.with_suffix('.engine')
    else:
        output_path = Path(output_path)

    print("=" * 60)
    print("PT模型转换为TensorRT Engine")
    print("=" * 60)
    print(f"输入模型: {pt_path}")
    print(f"输出模型: {output_path}")
    print(f"图像尺寸: {imgsz}")
    print(f"设备: {device}")
    print(f"半精度: {half}")
    print("=" * 60)

    try:
        if not torch.cuda.is_available() and device == 'cuda':
            print("警告: CUDA不可用，使用CPU")
            device = 'cpu'

        print("\n步骤1: 加载PT模型...")
        model = YOLO(str(pt_path))
        print(f"成功: 模型加载完成")
        print(f"  - 模型类型: {model.task}")

        print("\n步骤2: 导出为TensorRT Engine...")
        print("注意: 此过程可能需要几分钟时间...")

        export_path = model.export(
            format='engine',
            imgsz=imgsz,
            device=device,
            half=half,
            simplify=True,
            workspace=4
        )

        print(f"\n成功: 模型导出完成")
        print(f"  - 导出路径: {export_path}")

        if output_path != Path(export_path):
            print(f"\n步骤3: 移动文件到目标位置...")
            import shutil
            shutil.move(export_path, output_path)
            print(f"成功: 文件已移动到 {output_path}")

        file_size = output_path.stat().st_size / (1024 * 1024)
        print(f"\n转换完成!")
        print(f"  - 文件大小: {file_size:.2f} MB")
        print(f"  - 保存位置: {output_path}")

        return True

    except Exception as e:
        print(f"\n失败: 转换过程出错 - {e}")
        import traceback
        traceback.print_exc()
        return False

def batch_convert_models(model_dir, output_dir=None, imgsz=640, device='cuda', half=False):
    """
    批量转换目录下的所有pt模型

    Args:
        model_dir: 模型目录
        output_dir: 输出目录，默认与输入目录相同
        imgsz: 输入图像尺寸
        device: 设备类型
        half: 是否使用FP16精度
    """
    model_dir = Path(model_dir)

    if not model_dir.exists():
        print(f"错误: 目录不存在 - {model_dir}")
        return

    pt_files = list(model_dir.rglob("*.pt"))

    if not pt_files:
        print(f"警告: 目录中没有找到pt文件 - {model_dir}")
        return

    print(f"\n找到 {len(pt_files)} 个pt模型文件")
    print("=" * 60)

    success_count = 0
    fail_count = 0

    for i, pt_file in enumerate(pt_files, 1):
        print(f"\n[{i}/{len(pt_files)}] 转换: {pt_file.name}")

        if output_dir:
            output_dir_path = Path(output_dir)
            output_dir_path.mkdir(parents=True, exist_ok=True)
            output_path = output_dir_path / pt_file.with_suffix('.engine').name
        else:
            output_path = pt_file.with_suffix('.engine')

        if output_path.exists():
            print(f"跳过: engine文件已存在 - {output_path}")
            continue

        success = convert_pt_to_engine(pt_file, output_path, imgsz, device, half)

        if success:
            success_count += 1
        else:
            fail_count += 1

    print("\n" + "=" * 60)
    print("批量转换完成")
    print("=" * 60)
    print(f"成功: {success_count}")
    print(f"失败: {fail_count}")
    print(f"总计: {len(pt_files)}")

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='将PT模型转换为TensorRT Engine格式')
    parser.add_argument('input', help='输入pt模型文件或目录')
    parser.add_argument('-o', '--output', help='输出engine文件路径或目录')
    parser.add_argument('-s', '--imgsz', type=int, default=640, help='输入图像尺寸 (默认: 640)')
    parser.add_argument('-d', '--device', default='cuda', help='设备类型 (默认: cuda)')
    parser.add_argument('--half', action='store_true', help='使用FP16半精度')
    parser.add_argument('-b', '--batch', action='store_true', help='批量转换目录下所有pt文件')

    args = parser.parse_args()

    input_path = Path(args.input)

    if not input_path.exists():
        print(f"错误: 路径不存在 - {input_path}")
        return 1

    if args.batch or input_path.is_dir():
        batch_convert_models(input_path, args.output, args.imgsz, args.device, args.half)
    else:
        success = convert_pt_to_engine(input_path, args.output, args.imgsz, args.device, args.half)
        return 0 if success else 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
