"""
测试.bat模型文件可行性
使用视频输入进行测试
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


class BatModelTester:
    """测试.bat模型文件的可行性"""
    
    def __init__(self):
        self.model_loader = LiquidDetectionEngine()
        self.model = None
        self.video_cap = None
        
    def test_model_loading(self, model_path: str) -> bool:
        """
        测试模型加载
        
        Args:
            model_path: 模型文件路径
            
        Returns:
            是否加载成功
        """
        print(f" 测试模型加载: {model_path}")
        
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
    
    def test_video_detection(self, video_path: str, output_path: str = None) -> bool:
        """
        测试视频检测
        
        Args:
            video_path: 视频文件路径
            output_path: 输出视频路径
            
        Returns:
            是否检测成功
        """
        if self.model is None:
            print("❌ 请先加载模型")
            return False
        
        print(f"🎥 开始视频检测测试: {video_path}")
        
        try:
            # 打开视频文件
            self.video_cap = cv2.VideoCapture(video_path)
            if not self.video_cap.isOpened():
                print(f"❌ 无法打开视频文件: {video_path}")
                return False
            
            # 获取视频信息
            fps = self.video_cap.get(cv2.CAP_PROP_FPS)
            width = int(self.video_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.video_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(self.video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            print(f"📹 视频信息:")
            print(f"  分辨率: {width}x{height}")
            print(f"  帧率: {fps:.1f} FPS")
            print(f"  总帧数: {total_frames}")
            
            # 设置输出视频
            if output_path:
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            else:
                out = None
            
            # 开始检测
            frame_count = 0
            detection_count = 0
            start_time = time.time()
            
            print("🚀 开始检测...")
            
            while True:
                ret, frame = self.video_cap.read()
                if not ret:
                    break
                
                frame_count += 1
                
                # 每10帧显示一次进度
                if frame_count % 10 == 0:
                    progress = (frame_count / total_frames) * 100
                    elapsed_time = time.time() - start_time
                    fps_current = frame_count / elapsed_time if elapsed_time > 0 else 0
                    print(f"�� 进度: {progress:.1f}% ({frame_count}/{total_frames}) - 处理速度: {fps_current:.1f} FPS")
                
                try:
                    # 执行检测
                    results = self.model(frame)
                    
                    # 处理液位高度数据
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
                                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                                
                                # 绘制标签
                                label = f"Class {cls}: {conf:.2f}"
                                cv2.putText(frame, label, (int(x1), int(y1) - 10), 
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    
                    # 保存输出视频
                    if out:
                        out.write(frame)
                    
                except Exception as e:
                    print(f"⚠️ 第{frame_count}帧检测失败: {e}")
                    continue
            
            # 计算统计信息
            total_time = time.time() - start_time
            avg_fps = frame_count / total_time if total_time > 0 else 0
            
            print(f"\n📈 检测完成!")
            print(f"  总帧数: {frame_count}")
            print(f"  检测到目标: {detection_count}个")
            print(f"  总时间: {total_time:.2f}秒")
            print(f"  平均FPS: {avg_fps:.1f}")
            print(f"  检测率: {(detection_count/frame_count)*100:.1f}%")
            
            # 清理资源
            if self.video_cap:
                self.video_cap.release()
            if out:
                out.release()
            
            return True
            
        except Exception as e:
            print(f"❌ 视频检测失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_realtime_detection(self, camera_index: int = 0, duration: int = 30) -> bool:
        """
        测试实时检测
        
        Args:
            camera_index: 摄像头索引
            duration: 测试时长（秒）
            
        Returns:
            是否测试成功
        """
        if self.model is None:
            print("❌ 请先加载模型")
            return False
        
        print(f"📹 开始实时检测测试 (摄像头{camera_index}, 时长{duration}秒)")
        
        try:
            # 打开摄像头
            cap = cv2.VideoCapture(camera_index)
            if not cap.isStarted():
                print(f"❌ 无法打开摄像头: {camera_index}")
                return False
            
            # 设置摄像头参数
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)
            
            start_time = time.time()
            frame_count = 0
            detection_count = 0
            
            print("🚀 开始实时检测...")
            print("按 'q' 键退出")
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("❌ 无法读取摄像头画面")
                    break
                
                frame_count += 1
                current_time = time.time() - start_time
                
                # 检查是否超时
                if current_time > duration:
                    print(f"⏰ 测试时间到 ({duration}秒)")
                    break
                
                try:
                    # 执行检测
                    results = self.model(frame)
                    
                    # 处理液位高度数据
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
                                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                                
                                # 绘制标签
                                label = f"Class {cls}: {conf:.2f}"
                                cv2.putText(frame, label, (int(x1), int(y1) - 10), 
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    
                    # 显示统计信息
                    fps = frame_count / current_time if current_time > 0 else 0
                    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30), 
                              cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    cv2.putText(frame, f"Detections: {detection_count}", (10, 70), 
                              cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    cv2.putText(frame, f"Time: {current_time:.1f}s", (10, 110), 
                              cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    
                    # 显示画面
                    cv2.imshow('Real-time Detection Test', frame)
                    
                    # 检查按键
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        print("👋 用户退出")
                        break
                    
                except Exception as e:
                    print(f"⚠️ 第{frame_count}帧检测失败: {e}")
                    continue
            
            # 计算统计信息
            total_time = time.time() - start_time
            avg_fps = frame_count / total_time if total_time > 0 else 0
            
            print(f"\n📈 实时检测完成!")
            print(f"  总帧数: {frame_count}")
            print(f"  检测到目标: {detection_count}个")
            print(f"  总时间: {total_time:.2f}秒")
            print(f"  平均FPS: {avg_fps:.1f}")
            print(f"  检测率: {(detection_count/frame_count)*100:.1f}%")
            
            # 清理资源
            cap.release()
            cv2.destroyAllWindows()
            
            return True
            
        except Exception as e:
            print(f"❌ 实时检测失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def cleanup(self):
        """清理资源"""
        if self.video_cap:
            self.video_cap.release()
        self.model_loader.cleanup_temp_files()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="测试.bat模型文件可行性")
    parser.add_argument("--model", "-m", type=str, required=True,
                       help="模型文件路径 (.pt 或 .bat)")
    parser.add_argument("--video", "-v", type=str,
                       help="视频文件路径")
    parser.add_argument("--camera", "-c", type=int, default=0,
                       help="摄像头索引 (默认0)")
    parser.add_argument("--output", "-o", type=str,
                       help="输出视频路径")
    parser.add_argument("--duration", "-d", type=int, default=30,
                       help="实时检测时长 (默认30秒)")
    parser.add_argument("--mode", type=str, choices=["video", "realtime"], default="video",
                       help="测试模式 (video/realtime)")
    
    args = parser.parse_args()
    
    # 创建测试器
    tester = BatModelTester()
    
    try:
        print("�� 开始.bat模型文件可行性测试")
        print("=" * 50)
        
        # 1. 测试模型加载
        print("\n📦 步骤1: 测试模型加载")
        if not tester.test_model_loading(args.model):
            print("❌ 模型加载失败，测试终止")
            return
        
        # 2. 测试检测功能
        print("\n🎯 步骤2: 测试检测功能")
        if args.mode == "video":
            if not args.video:
                print("❌ 视频模式需要指定 --video 参数")
                return
            
            success = tester.test_video_detection(args.video, args.output)
        else:  # realtime
            success = tester.test_realtime_detection(args.camera, args.duration)
        
        # 3. 输出结果
        print("\n📊 测试结果总结")
        print("=" * 50)
        if success:
            print("✅ .bat模型文件测试成功!")
            print("✅ 模型可以正常加载和运行")
            print("✅ 检测功能正常工作")
        else:
            print("❌ .bat模型文件测试失败!")
            print("❌ 请检查模型文件或检测参数")
        
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        tester.cleanup()


if __name__ == "__main__":
    main() 