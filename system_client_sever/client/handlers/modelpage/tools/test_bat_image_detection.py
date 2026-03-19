"""
使用图片检测.bat文件
"""

import cv2
import numpy as np
import time
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from handlers.videopage.detection.detection import LiquidDetectionEngine


class BatImageDetector:
    """使用.bat文件进行图片检测"""
    
    def __init__(self):
        self.model_loader = LiquidDetectionEngine()
        self.model = None
        
    def load_bat_model(self, model_path: str) -> bool:
        """
        加载.bat模型文件
        
        Args:
            model_path: 模型文件路径
            
        Returns:
            是否加载成功
        """
        print(f" 加载.bat模型: {model_path}")
        
        try:
            # 检查文件是否存在
            if not os.path.exists(model_path):
                print(f"❌ 模型文件不存在: {model_path}")
                return False
            
            # 检查文件大小
            file_size = os.path.getsize(model_path)
            print(f"�� 文件大小: {file_size / (1024*1024):.1f}MB")
            
            # 尝试加载模型
            start_time = time.time()
            self.model = self.model_loader.load_model(model_path)
            load_time = time.time() - start_time
            
            print(f"✅ 模型加载成功!")
            print(f"⏱️ 加载时间: {load_time:.2f}秒")
            print(f"📊 模型类型: {type(self.model)}")
            
            return True
            
        except Exception as e:
            print(f"❌ 模型加载失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def detect_single_image(self, image_path: str, output_path: str = None, conf_threshold: float = 0.5) -> bool:
        """
        检测单张图片
        
        Args:
            image_path: 图片文件路径
            output_path: 输出图片路径
            conf_threshold: 置信度阈值
            
        Returns:
            是否检测成功
        """
        if self.model is None:
            print("❌ 请先加载模型")
            return False
        
        print(f"🖼️ 开始图片检测: {image_path}")
        print(f"🎯 置信度阈值: {conf_threshold}")
        
        try:
            # 读取图片
            image = cv2.imread(image_path)
            if image is None:
                print(f"❌ 无法读取图片: {image_path}")
                return False
            
            print(f"�� 图片尺寸: {image.shape[1]}x{image.shape[0]}")
            
            # 执行检测
            start_time = time.time()
            results = self.model(image, conf=conf_threshold)
            detection_time = time.time() - start_time
            
            # 处理液位高度数据
            detection_count = 0
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    detection_count += len(boxes)
                    
                    # 绘制检测框
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        conf = box.conf[0].cpu().numpy()
                        cls = int(box.cls[0].cpu().numpy())
                        
                        # 绘制边界框
                        cv2.rectangle(image, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                        
                        # 绘制标签
                        label = f"Class {cls}: {conf:.2f}"
                        cv2.putText(image, label, (int(x1), int(y1) - 10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # 保存结果
            if output_path:
                cv2.imwrite(output_path, image)
                print(f"💾 结果已保存到: {output_path}")
            
            # 显示结果
            print(f"\n📈 图片检测完成!")
            print(f"  检测到目标: {detection_count}个")
            print(f"  检测时间: {detection_time:.3f}秒")
            
            # 显示图片
            cv2.imshow('Image Detection Result (.bat)', image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            
            return True
            
        except Exception as e:
            print(f"❌ 图片检测失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def detect_batch_images(self, image_dir: str, output_dir: str = None, conf_threshold: float = 0.5) -> bool:
        """
        批量检测图片
        
        Args:
            image_dir: 图片目录路径
            output_dir: 输出目录路径
            conf_threshold: 置信度阈值
            
        Returns:
            是否检测成功
        """
        if self.model is None:
            print("❌ 请先加载模型")
            return False
        
        print(f"📁 开始批量图片检测: {image_dir}")
        print(f"🎯 置信度阈值: {conf_threshold}")
        
        try:
            # 创建输出目录
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                print(f"📂 输出目录: {output_dir}")
            
            # 支持的图片格式
            image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
            
            # 获取所有图片文件
            image_files = []
            for ext in image_extensions:
                image_files.extend(Path(image_dir).glob(f"*{ext}"))
                image_files.extend(Path(image_dir).glob(f"*{ext.upper()}"))
            
            if not image_files:
                print(f"❌ 在目录 {image_dir} 中未找到图片文件")
                return False
            
            print(f"📊 找到 {len(image_files)} 个图片文件")
            
            # 批量检测
            success_count = 0
            total_detections = 0
            total_time = 0
            
            for i, image_file in enumerate(image_files):
                print(f"\n🔄 处理第 {i+1}/{len(image_files)} 个文件: {image_file.name}")
                
                try:
                    # 读取图片
                    image = cv2.imread(str(image_file))
                    if image is None:
                        print(f"⚠️ 无法读取图片: {image_file}")
                        continue
                    
                    # 执行检测
                    start_time = time.time()
                    results = self.model(image, conf=conf_threshold)
                    detection_time = time.time() - start_time
                    total_time += detection_time
                    
                    # 处理液位高度数据
                    frame_detections = 0
                    for result in results:
                        boxes = result.boxes
                        if boxes is not None:
                            frame_detections += len(boxes)
                            total_detections += len(boxes)
                            
                            # 绘制检测框
                            for box in boxes:
                                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                                conf = box.conf[0].cpu().numpy()
                                cls = int(box.cls[0].cpu().numpy())
                                
                                # 绘制边界框
                                cv2.rectangle(image, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                                
                                # 绘制标签
                                label = f"Class {cls}: {conf:.2f}"
                                cv2.putText(image, label, (int(x1), int(y1) - 10), 
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    
                    # 保存结果
                    if output_dir:
                        output_path = Path(output_dir) / f"detected_{image_file.name}"
                        cv2.imwrite(str(output_path), image)
                    
                    print(f"✅ 检测完成: {frame_detections} 个目标, 耗时 {detection_time:.3f}秒")
                    success_count += 1
                    
                except Exception as e:
                    print(f"❌ 处理失败 {image_file.name}: {e}")
                    continue
            
            # 输出统计信息
            print(f"\n📈 批量检测完成!")
            print(f"  成功处理: {success_count}/{len(image_files)} 个文件")
            print(f"  总检测数: {total_detections} 个目标")
            print(f"  总耗时: {total_time:.2f}秒")
            print(f"  平均耗时: {total_time/success_count:.3f}秒/图片" if success_count > 0 else "  平均耗时: 0秒/图片")
            
            return success_count > 0
            
        except Exception as e:
            print(f"❌ 批量检测失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def cleanup(self):
        """清理资源"""
        self.model_loader.cleanup_temp_files()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="使用图片检测.bat文件")
    parser.add_argument("--model", "-m", type=str, required=True,
                       help=".bat模型文件路径")
    parser.add_argument("--image", "-i", type=str,
                       help="单张图片文件路径")
    parser.add_argument("--dir", "-d", type=str,
                       help="图片目录路径")
    parser.add_argument("--output", "-o", type=str,
                       help="输出文件/目录路径")
    parser.add_argument("--conf", type=float, default=0.5,
                       help="置信度阈值 (默认0.5)")
    parser.add_argument("--mode", type=str, choices=["single", "batch"], default="single",
                       help="检测模式 (single/batch)")
    
    args = parser.parse_args()
    
    # 创建检测器
    detector = BatImageDetector()
    
    try:
        print(" 开始.bat模型图片检测测试")
        print("=" * 50)
        
        # 1. 测试模型加载
        print("\n📦 步骤1: 测试模型加载")
        if not detector.load_bat_model(args.model):
            print("❌ 模型加载失败，测试终止")
            return
        
        # 2. 测试检测功能
        print("\n🎯 步骤2: 测试检测功能")
        success = False
        
        if args.mode == "single":
            if not args.image:
                print("❌ 单张图片模式需要指定 --image 参数")
                return
            success = detector.detect_single_image(args.image, args.output, args.conf)
            
        elif args.mode == "batch":
            if not args.dir:
                print("❌ 批量模式需要指定 --dir 参数")
                return
            success = detector.detect_batch_images(args.dir, args.output, args.conf)
        
        # 3. 输出结果
        print("\n📊 测试结果总结")
        print("=" * 50)
        if success:
            print("✅ .bat模型图片检测测试成功!")
            print("✅ 模型可以正常加载和运行")
            print("✅ 图片检测功能正常工作")
        else:
            print("❌ .bat模型图片检测测试失败!")
            print("❌ 请检查模型文件或检测参数")
        
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        detector.cleanup()


if __name__ == "__main__":
    main() 