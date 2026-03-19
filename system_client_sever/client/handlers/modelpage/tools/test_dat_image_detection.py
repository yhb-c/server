"""
使用图片检测.dat文件（分割模型）
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


class DatImageDetector:
    """使用.dat文件进行图片分割"""
    
    def __init__(self):
        self.model_loader = LiquidDetectionEngine()
        self.model = None
        
    def load_dat_model(self, model_path: str) -> bool:
        """
        加载.dat模型文件
        
        Args:
            model_path: 模型文件路径
            
        Returns:
            是否加载成功
        """
        print(f" 加载.dat模型: {model_path}")
        
        try:
            # 检查文件是否存在
            if not os.path.exists(model_path):
                print(f"❌ 模型文件不存在: {model_path}")
                return False
            
            # 检查文件大小
            file_size = os.path.getsize(model_path)
            print(f" 文件大小: {file_size / (1024*1024):.1f}MB")
            
            # 尝试加载模型
            start_time = time.time()
            self.model = self.model_loader.load_yolo_model(model_path)
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
    
    def segment_single_image(self, image_path: str, output_path: str = None, conf_threshold: float = 0.5) -> bool:
        """
        分割单张图片
        
        Args:
            image_path: 图片文件路径
            output_path: 输出图片路径
            conf_threshold: 置信度阈值
            
        Returns:
            是否分割成功
        """
        if self.model is None:
            print("❌ 请先加载模型")
            return False
        
        print(f"🖼️ 开始图片分割: {image_path}")
        print(f"🎯 置信度阈值: {conf_threshold}")
        
        try:
            # 读取图片
            image = cv2.imread(image_path)
            if image is None:
                print(f"❌ 无法读取图片: {image_path}")
                return False
            
            original_height, original_width = image.shape[:2]
            print(f" 图片尺寸: {original_width}x{original_height}")
            
            # 执行分割
            start_time = time.time()
            results = self.model(image, conf=conf_threshold)
            segmentation_time = time.time() - start_time
            
            # 处理分割结果
            segmentation_count = 0
            for result in results:
                # 获取分割掩码
                if hasattr(result, 'masks') and result.masks is not None:
                    masks = result.masks.data.cpu().numpy()
                    segmentation_count += len(masks)
                    
                    # 为每个分割区域绘制不同颜色
                    for i, mask in enumerate(masks):
                        # 将掩码调整到原图尺寸
                        if mask.shape != (original_height, original_width):
                            mask = cv2.resize(mask, (original_width, original_height), interpolation=cv2.INTER_LINEAR)
                        
                        # 创建彩色掩码
                        colored_mask = np.zeros_like(image)
                        mask_bool = mask > 0.5
                        colored_mask[mask_bool] = [0, 255, 0]  # 绿色
                        
                        # 将掩码叠加到原图上
                        alpha = 0.5
                        image = cv2.addWeighted(image, 1-alpha, colored_mask, alpha, 0)
                        
                        # 绘制边界
                        mask_uint8 = (mask > 0.5).astype(np.uint8) * 255
                        contours, _ = cv2.findContours(
                            mask_uint8, 
                            cv2.RETR_EXTERNAL, 
                            cv2.CHAIN_APPROX_SIMPLE
                        )
                        cv2.drawContours(image, contours, -1, (0, 255, 0), 2)
                
                # 如果有检测框，也绘制出来
                if hasattr(result, 'boxes') and result.boxes is not None:
                    boxes = result.boxes
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        conf = box.conf[0].cpu().numpy()
                        cls = int(box.cls[0].cpu().numpy())
                        
                        # 绘制边界框
                        cv2.rectangle(image, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 2)
                        
                        # 绘制标签
                        label = f"Class {cls}: {conf:.2f}"
                        cv2.putText(image, label, (int(x1), int(y1) - 10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
            
            # 保存结果
            if output_path:
                cv2.imwrite(output_path, image)
                print(f"💾 结果已保存到: {output_path}")
            
            # 显示结果
            print(f"\n📈 图片分割完成!")
            print(f"  分割区域: {segmentation_count}个")
            print(f"  分割时间: {segmentation_time:.3f}秒")
            
            # 显示图片
            cv2.imshow('Image Segmentation Result (.dat)', image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            
            return True
            
        except Exception as e:
            print(f"❌ 图片分割失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def cleanup(self):
        """清理资源"""
        self.model_loader.cleanup_temp_files()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="使用图片分割.dat文件")
    parser.add_argument("--model", "-m", type=str, required=True,
                       help=".dat模型文件路径")
    parser.add_argument("--image", "-i", type=str, required=True,
                       help="图片文件路径")
    parser.add_argument("--output", "-o", type=str,
                       help="输出图片路径")
    parser.add_argument("--conf", type=float, default=0.5,
                       help="置信度阈值 (默认0.5)")
    
    args = parser.parse_args()
    
    # 创建检测器
    detector = DatImageDetector()
    
    try:
        print(" 开始.dat模型图片分割测试")
        print("=" * 50)
        
        # 1. 测试模型加载
        print("\n📦 步骤1: 测试模型加载")
        if not detector.load_dat_model(args.model):
            print("❌ 模型加载失败，测试终止")
            return
        
        # 2. 测试分割功能
        print("\n🎯 步骤2: 测试分割功能")
        success = detector.segment_single_image(args.image, args.output, args.conf)
        
        # 3. 输出结果
        print("\n📊 测试结果总结")
        print("=" * 50)
        if success:
            print("✅ .dat模型图片分割测试成功!")
            print("✅ 模型可以正常加载和运行")
            print("✅ 图片分割功能正常工作")
        else:
            print("❌ .dat模型图片分割测试失败!")
            print("❌ 请检查模型文件或分割参数")
        
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