# -*- coding: utf-8 -*-
"""
模型分割调试工具

输入：RTSP地址或视频文件路径
输出：绘制有分割掩码结果的实时画面

使用方法：
    # GUI模式（不带参数）
    python detect_debug.py
    
    # 命令行模式（带参数）
    python detect_debug.py --source rtsp://192.168.1.100:554/stream
    python detect_debug.py --source video.mp4
    python detect_debug.py --source 0  # 摄像头
    默认地址rtsp://admin:cei345678@192.168.2.126:8000/stream1
    默认模型D:\\restructure\\liquid_level_line_detection_system\\database\\model\\detection_model\\7\\best.dat
"""

import cv2
import numpy as np
import argparse
import sys
import os
from pathlib import Path
import time
import threading
import queue

# 添加项目根目录到路径
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

# 注意：此调试工具已重构为通过服务端API进行检测
# 不再直接导入服务端检测模块

# 服务端检测功能的客户端代理类
class ServerDetectionProxy:
    """服务端检测功能的客户端代理"""
    
    def __init__(self, model_path=None, device='cuda'):
        self.model_path = model_path
        self.device = device
        self.is_loaded = False
        
    def load_model(self, model_path):
        """通过服务端API加载模型"""
        # 实际实现需要通过WebSocket或HTTP API调用服务端
        print(f"[调试工具] 注意：此功能需要通过服务端API实现")
        return False
        
    def detect(self, frame):
        """通过服务端API执行检测"""
        # 实际实现需要通过WebSocket或HTTP API调用服务端
        print(f"[调试工具] 注意：此功能需要通过服务端API实现")
        return None

# 使用代理类替代直接导入
LiquidDetectionEngine = ServerDetectionProxy

def get_class_color(class_name):
    """获取类别颜色（客户端占位函数）"""
    # 默认颜色映射
    color_map = {
        'liquid': (0, 255, 0),  # 绿色
        'foam': (255, 255, 0),  # 黄色
        'container': (255, 0, 0)  # 红色
    }
    return color_map.get(class_name, (128, 128, 128))

# 导入HK SDK捕获类
try:
    from handlers.videopage.HK_SDK.HKcapture import HKcapture
    HK_AVAILABLE = True
except ImportError:
    HK_AVAILABLE = False
    print("⚠️ 海康SDK不可用，将使用OpenCV")

# 尝试导入Qt库（用于GUI模式）
try:
    from qtpy import QtWidgets, QtCore, QtGui
    from qtpy.QtCore import Qt, Signal, QThread
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    print("⚠️ Qt库未安装，GUI模式不可用。安装方法: pip install qtpy PyQt5")


class SegmentationDebugger:
    """分割调试工具类"""
    
    def __init__(self, model_path=None, device='cuda'):
        """
        初始化调试器
        
        Args:
            model_path: 模型文件路径
            device: 计算设备
        """
        self.model_path = model_path
        # 检测GPU是否可用
        self.device = self._validate_device(device)
        self.engine = None
        
        # 显示参数
        self.display_width = 1280
        self.display_height = 720
        self.mask_alpha = 0.6  # 掩码透明度
        
        # 统计信息
        self.frame_count = 0
        self.fps_counter = 0
        self.fps_start_time = time.time()
        self.current_fps = 0
        
        # 线程安全的帧队列
        self.frame_queue = queue.Queue(maxsize=5)
        self.result_queue = queue.Queue(maxsize=5)
        self.running = False
        
        # 颜色映射
        self.class_colors = {
            'liquid': (0, 255, 0),      # 绿色
            'foam': (255, 0, 0),        # 蓝色  
            'air': (0, 0, 255),         # 红色
            'container': (255, 255, 0), # 青色
        }
    
    def _validate_device(self, device):
        """验证并选择可用的设备"""
        try:
            import torch
            
            if device in ['cuda', '0'] or device.startswith('cuda:'):
                if torch.cuda.is_available():
                    print(f"✅ GPU可用，使用设备: {device}")
                    return 'cuda' if device in ['cuda', '0'] else device
                else:
                    print(f"⚠️  未检测到GPU，自动切换到CPU模式")
                    return 'cpu'
            return device
        except Exception as e:
            print(f"⚠️  设备检测异常: {e}，使用CPU模式")
            return 'cpu'
    
    def load_model(self, model_path):
        """加载检测模型"""
        try:
            print(f"🔄 正在加载模型: {model_path}")
            self.engine = LiquidDetectionEngine(device=self.device)
            
            if not self.engine.load_model(model_path):
                print(f"❌ 模型加载失败: {model_path}")
                return False
            
            print(f"✅ 模型加载成功")
            return True
            
        except Exception as e:
            print(f"❌ 模型加载异常: {e}")
            return False
    
    def find_available_model(self):
        """查找可用的模型文件"""
        # 搜索路径列表
        search_paths = [
            project_root / "database" / "model" / "detection_model",
            project_root / "database" / "model",
            Path.cwd(),
        ]
        
        model_extensions = ['.dat', '.pt', '.pth']
        
        for search_dir in search_paths:
            if not search_dir.exists():
                continue
                
            print(f"🔍 搜索模型目录: {search_dir}")
            
            # 递归搜索模型文件
            for ext in model_extensions:
                model_files = list(search_dir.rglob(f"*{ext}"))
                if model_files:
                    # 优先选择包含'best'的文件
                    best_files = [f for f in model_files if 'best' in f.name.lower()]
                    if best_files:
                        return str(best_files[0])
                    return str(model_files[0])
        
        return None
    
    def process_frame_worker(self):
        """处理帧的工作线程"""
        while self.running:
            try:
                # 获取帧
                if self.frame_queue.empty():
                    time.sleep(0.001)
                    continue
                
                frame = self.frame_queue.get(timeout=0.1)
                if frame is None:
                    continue
                
                # 执行检测
                if self.engine and self.engine.model:
                    result = self.detect_and_visualize(frame)
                else:
                    result = frame.copy()
                
                # 放入结果队列
                if not self.result_queue.full():
                    self.result_queue.put(result)
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"⚠️ 处理帧异常: {e}")
                continue
    
    def detect_and_visualize(self, frame):
        """检测并返回结果数据（移除渲染，客户端无GPU）"""
        try:
            # 执行YOLO推理
            results = self.engine.model.predict(
                source=frame,
                imgsz=640,
                conf=0.3,
                iou=0.5,
                device=self.device,
                save=False,
                verbose=False,
                half=True if self.device != 'cpu' else False
            )

            result = results[0]

            # 只返回检测结果数据，不进行渲染
            detection_data = {
                'masks': None,
                'boxes': None,
                'classes': None,
                'confidences': None
            }

            # 提取分割掩码数据
            if result.masks is not None:
                detection_data['masks'] = result.masks.data.cpu().numpy()
                detection_data['classes'] = result.boxes.cls.cpu().numpy().astype(int)
                detection_data['confidences'] = result.boxes.conf.cpu().numpy()
                detection_data['boxes'] = result.boxes.xyxy.cpu().numpy()

            # 提取检测框数据
            elif result.boxes is not None:
                detection_data['boxes'] = result.boxes.xyxy.cpu().numpy()
                detection_data['classes'] = result.boxes.cls.cpu().numpy().astype(int)
                detection_data['confidences'] = result.boxes.conf.cpu().numpy()

            return detection_data

        except Exception as e:
            print(f"⚠️ 检测异常: {e}")
            return None
    
    def run(self, source):
        """运行调试器"""
        # 自动查找模型
        if not self.model_path:
            self.model_path = self.find_available_model()
            if not self.model_path:
                print("❌ 未找到可用的模型文件")
                print("请将模型文件放在以下目录之一：")
                print("  - database/model/detection_model/")
                print("  - database/model/")
                print("  - 当前目录")
                return False
        
        # 加载模型
        if not self.load_model(self.model_path):
            return False
        
        # 打开视频源
        print(f"🔄 正在打开视频源: {source}")
        
        # 判断输入类型
        if source.isdigit():
            source = int(source)
        
        # 优先使用HKcapture
        cap = None
        if HK_AVAILABLE:
            try:
                cap = HKcapture(source)
                if not cap.open():
                    print(f"❌ 无法打开视频源: {source}")
                    return False
                
                # 开始捕获
                if not cap.start_capture():
                    print(f"❌ 无法开始视频捕获: {source}")
                    cap.release()
                    return False
                
                # 等待视频流稳定
                time.sleep(0.5)
                
                # 获取视频信息
                width, height = cap.get_frame_size()
                fps = cap.get_fps()
                
                print(f"✅ 视频源信息: {width}x{height} @ {fps:.1f}fps")
                print(f"✅ 使用HKcapture模式")
                
            except Exception as e:
                print(f"❌ HKcapture初始化失败: {e}")
                return False
        else:
            # 备用：使用OpenCV
            cap = cv2.VideoCapture(source)
            
            if not cap.isOpened():
                print(f"❌ 无法打开视频源: {source}")
                return False
            
            # 设置缓冲区大小（减少延迟）
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # 获取视频信息
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            print(f"✅ 视频源信息: {width}x{height} @ {fps:.1f}fps")
            print(f"✅ 使用OpenCV模式")
        
        # 启动处理线程
        self.running = True
        process_thread = threading.Thread(target=self.process_frame_worker)
        process_thread.daemon = True
        process_thread.start()
        
        print("🎥 开始实时检测，按 'q' 退出")
        
        try:
            while True:
                # 读取帧（兼容HKcapture和OpenCV）
                ret, frame = cap.read()
                
                # HKcapture在没有新帧时返回False，需要继续等待
                if not ret or frame is None:
                    if HK_AVAILABLE and isinstance(cap, HKcapture):
                        time.sleep(0.01)
                        continue
                    else:
                        print("⚠️ 读取帧失败，可能是视频结束")
                        break
                
                self.frame_count += 1
                
                # 调整显示尺寸
                if frame.shape[1] != self.display_width or frame.shape[0] != self.display_height:
                    frame = cv2.resize(frame, (self.display_width, self.display_height))
                
                # 将帧放入处理队列
                if not self.frame_queue.full():
                    self.frame_queue.put(frame.copy())
                
                # 获取处理结果（不再渲染显示）
                detection_data = None
                if not self.result_queue.empty():
                    try:
                        detection_data = self.result_queue.get_nowait()
                    except queue.Empty:
                        pass

                # 处理检测数据（可以在这里添加数据保存或其他处理逻辑）
                if detection_data is not None:
                    # 这里可以添加数据处理逻辑，例如保存到文件或发送到服务器
                    pass
                
                # 处理按键
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('r'):
                    # 重置统计
                    self.frame_count = 0
                    self.fps_counter = 0
                    self.fps_start_time = time.time()
                    print("🔄 统计信息已重置")
        
        except KeyboardInterrupt:
            print("\n⏹️ 用户中断")
        
        finally:
            # 清理资源
            self.running = False
            cap.release()

            # 等待处理线程结束
            if process_thread.is_alive():
                process_thread.join(timeout=1.0)

            print("✅ 调试器已退出")
        
        return True


# ==================== GUI模式相关类 ====================

if QT_AVAILABLE:
    class VideoThread(QThread):
        """视频处理线程"""
        frame_ready = Signal(np.ndarray)
        fps_update = Signal(float)
        error_occurred = Signal(str)
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self.source = None
            self.running = False

            # FPS统计
            self.fps_counter = 0
            self.fps_start_time = time.time()

            # ROI区域（支持多个）
            self.roi_list = []  # [(x, y, w, h), ...]
            self.use_roi = False

            # 日志记录
            project_root = Path(__file__).parent.parent.parent.parent
            log_dir = project_root / 'logs'
            log_dir.mkdir(parents=True, exist_ok=True)
            self.csv_log_path = str(log_dir / 'detect.csv')
            self.frame_counter = 0
            self.csv_file = None
            self.csv_writer = None

            # WebSocket连接（用于接收服务器检测结果）
            self.ws_client = None

        def set_source(self, source):
            """设置视频源"""
            self.source = source

        def set_model(self, model_path):
            """设置模型路径（客户端不使用，保留接口兼容性）"""
            pass

        def set_roi(self, roi):
            """设置ROI（支持单个或多个）"""
            if roi is None:
                self.roi_list = []
                self.use_roi = False
            elif isinstance(roi, list):
                # 多个ROI
                self.roi_list = roi
                self.use_roi = len(roi) > 0
            else:
                # 单个ROI，转换为列表
                self.roi_list = [roi]
                self.use_roi = True

        def connect_to_server(self):
            """连接到服务器WebSocket（接收检测结果）"""
            try:
                # TODO: 实现WebSocket连接到服务器
                # 示例: ws://192.168.0.121:8085
                print("[VideoThread] 连接到服务器...")
                return True
            except Exception as e:
                self.error_occurred.emit(f"连接服务器失败: {str(e)}")
                return False

        def process_detection_result(self, detection_data):
            """处理从服务器接收的检测结果"""
            try:
                # 解析检测结果
                detection_info = detection_data.get('detection_info', {})

                # 写入CSV日志
                if self.csv_writer and detection_info:
                    for region_name, info in detection_info.items():
                        classes_str = ', '.join(info.get('classes', []))
                        conf_str = ', '.join([f"{c:.2f}" for c in info.get('confidences', [])])
                        pixel_str = ', '.join([str(p) for p in info.get('pixel_counts', [])])
                        self.csv_writer.writerow([
                            self.frame_counter,
                            region_name,
                            info.get('mask_count', 0),
                            classes_str if classes_str else '无',
                            conf_str if conf_str else '无',
                            pixel_str if pixel_str else '无'
                        ])

                    # 每10帧刷新一次文件
                    if self.frame_counter % 10 == 0:
                        self.csv_file.flush()


        def run(self):
            """线程运行函数（客户端只接收服务器数据，不进行检测）"""
            if not self.source:
                self.error_occurred.emit("未设置视频源")
                return

            # 连接到服务器WebSocket
            if not self.connect_to_server():
                return

            self.running = True
            self.fps_start_time = time.time()
            self.frame_counter = 0

            # 初始化CSV日志文件
            try:
                import csv
                self.csv_file = open(self.csv_log_path, 'w', newline='', encoding='utf-8-sig')
                self.csv_writer = csv.writer(self.csv_file)
                # 写入表头
                self.csv_writer.writerow(['帧数', 'ROI', 'Mask数量', '检测类别', '置信度', '像素数量'])
                self.csv_file.flush()
                print(f"✅ 已创建CSV日志文件: {self.csv_log_path}")
            except Exception as e:
                print(f"⚠️  无法创建CSV日志文件: {e}")
                self.csv_file = None
                self.csv_writer = None

            # 主循环：接收服务器的检测结果
            while self.running:
                try:
                    # TODO: 从WebSocket接收检测结果
                    # detection_data = self.ws_client.receive()
                    # self.process_detection_result(detection_data)

                    # 记录帧数
                    self.frame_counter += 1

                    # 更新FPS
                    self.fps_counter += 1
                    current_time = time.time()
                    if current_time - self.fps_start_time >= 1.0:
                        fps = self.fps_counter / (current_time - self.fps_start_time)
                        self.fps_update.emit(fps)
                        self.fps_counter = 0
                        self.fps_start_time = current_time

                    # 短暂休眠
                    self.msleep(10)

                except Exception as e:
                    print(f"⚠️  接收数据异常: {e}")
                    time.sleep(0.1)

            # 关闭CSV文件
            if self.csv_file:
                try:
                    self.csv_file.close()
                    print(f"✅ 已保存CSV日志，共记录 {self.frame_counter} 帧")
                except Exception as e:
                    print(f"⚠️  关闭CSV文件失败: {e}")
        
        def stop(self):
            """停止线程"""
            self.running = False
            self.wait()


    class DebugWindow(QtWidgets.QWidget):
        """调试工具主窗口"""
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self.video_thread = None
            self.current_fps = 0.0
            self._initUI()
        
        def _initUI(self):
            """初始化UI"""
            self.setWindowTitle("模型分割调试工具")
            self.setMinimumSize(800, 700)
            
            # 主布局
            main_layout = QtWidgets.QVBoxLayout(self)
            main_layout.setContentsMargins(20, 20, 20, 20)
            main_layout.setSpacing(15)
            
            # ===== 视频源输入 =====
            rtsp_layout = QtWidgets.QHBoxLayout()
            rtsp_label = QtWidgets.QLabel("视频源")
            rtsp_label.setFixedWidth(100)
            rtsp_label.setStyleSheet("font-size: 14pt; color: #333;")
            
            self.rtsp_input = QtWidgets.QLineEdit()
            self.rtsp_input.setPlaceholderText("输入RTSP地址、视频文件路径或摄像头ID (0,1,2...)")
            # 设置默认RTSP地址
            self.rtsp_input.setText("rtsp://admin:cei345678@192.168.0.127:8000/stream1")
            self.rtsp_input.setStyleSheet("""
                QLineEdit {
                    border: 2px solid #ff6b6b;
                    border-radius: 4px;
                    padding: 8px;
                    font-size: 12pt;
                    background-color: white;
                }
                QLineEdit:focus {
                    border: 2px solid #ff4757;
                }
            """)
            
            # 添加浏览视频按钮
            browse_video_btn = QtWidgets.QPushButton("浏览...")
            browse_video_btn.setFixedWidth(100)
            browse_video_btn.setStyleSheet("""
                QPushButton {
                    background-color: #5f27cd;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px;
                    font-size: 11pt;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #341f97;
                }
                QPushButton:pressed {
                    background-color: #2e1a87;
                }
            """)
            browse_video_btn.clicked.connect(self._browseVideo)
            
            rtsp_layout.addWidget(rtsp_label)
            rtsp_layout.addWidget(self.rtsp_input)
            rtsp_layout.addWidget(browse_video_btn)
            main_layout.addLayout(rtsp_layout)
            
            # ===== 模型路径输入 =====
            model_layout = QtWidgets.QHBoxLayout()
            model_label = QtWidgets.QLabel("模型路径")
            model_label.setFixedWidth(100)
            model_label.setStyleSheet("font-size: 14pt; color: #333;")
            
            self.model_input = QtWidgets.QLineEdit()
            self.model_input.setPlaceholderText("选择模型文件 (.pt 或 .dat)")
            # 设置默认模型路径
            default_model_path = r"C:\Users\123\Desktop\yewei\detection_liquid_system\database\model\detection_model\detect\best.dat"
            if os.path.exists(default_model_path):
                self.model_input.setText(default_model_path)
            self.model_input.setStyleSheet("""
                QLineEdit {
                    border: 2px solid #ff6b6b;
                    border-radius: 4px;
                    padding: 8px;
                    font-size: 12pt;
                    background-color: white;
                }
                QLineEdit:focus {
                    border: 2px solid #ff4757;
                }
            """)
            
            browse_btn = QtWidgets.QPushButton("浏览...")
            browse_btn.setFixedWidth(100)
            browse_btn.setStyleSheet("""
                QPushButton {
                    background-color: #5f27cd;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px;
                    font-size: 11pt;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #341f97;
                }
                QPushButton:pressed {
                    background-color: #2e1a87;
                }
            """)
            browse_btn.clicked.connect(self._browseModel)
            
            model_layout.addWidget(model_label)
            model_layout.addWidget(self.model_input)
            model_layout.addWidget(browse_btn)
            main_layout.addLayout(model_layout)
            
            # ===== 控制按钮 =====
            button_layout = QtWidgets.QHBoxLayout()
            button_layout.setSpacing(10)
            
            self.start_btn = QtWidgets.QPushButton("开始检测")
            self.start_btn.setFixedHeight(40)
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #10ac84;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 10px 20px;
                    font-size: 12pt;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #0d9170;
                }
                QPushButton:pressed {
                    background-color: #0a7d5e;
                }
                QPushButton:disabled {
                    background-color: #c8d6e5;
                    color: #8395a7;
                }
            """)
            self.start_btn.clicked.connect(self._startDetection)
            
            self.stop_btn = QtWidgets.QPushButton("停止检测")
            self.stop_btn.setFixedHeight(40)
            self.stop_btn.setEnabled(False)
            self.stop_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ee5a6f;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 10px 20px;
                    font-size: 12pt;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #d63447;
                }
                QPushButton:pressed {
                    background-color: #c23645;
                }
                QPushButton:disabled {
                    background-color: #c8d6e5;
                    color: #8395a7;
                }
            """)
            self.stop_btn.clicked.connect(self._stopDetection)
            
            self.save_btn = QtWidgets.QPushButton("保存截图")
            self.save_btn.setFixedHeight(40)
            self.save_btn.setEnabled(False)
            self.save_btn.setStyleSheet("""
                QPushButton {
                    background-color: #576574;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 10px 20px;
                    font-size: 12pt;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #485563;
                }
                QPushButton:pressed {
                    background-color: #3d4652;
                }
                QPushButton:disabled {
                    background-color: #c8d6e5;
                    color: #8395a7;
                }
            """)
            self.save_btn.clicked.connect(self._saveScreenshot)
            
            button_layout.addWidget(self.start_btn)
            button_layout.addWidget(self.stop_btn)
            button_layout.addWidget(self.save_btn)
            button_layout.addStretch()
            
            main_layout.addLayout(button_layout)
            
            # ===== 状态栏 =====
            status_layout = QtWidgets.QHBoxLayout()
            
            self.status_label = QtWidgets.QLabel("状态: 就绪")
            self.status_label.setStyleSheet("font-size: 11pt; color: #666;")
            
            self.fps_label = QtWidgets.QLabel("FPS: 0.0")
            self.fps_label.setStyleSheet("font-size: 11pt; color: #666;")
            
            status_layout.addWidget(self.status_label)
            status_layout.addStretch()
            status_layout.addWidget(self.fps_label)
            
            main_layout.addLayout(status_layout)
            
            # ===== 显示区域 =====
            display_container = QtWidgets.QWidget()
            display_container.setStyleSheet("""
                QWidget {
                    border: 3px solid #ff6b6b;
                    border-radius: 8px;
                    background-color: #f8f9fa;
                }
            """)
            display_layout = QtWidgets.QVBoxLayout(display_container)
            display_layout.setContentsMargins(0, 0, 0, 0)
            
            self.display_label = QtWidgets.QLabel("分割掩码结果")
            self.display_label.setAlignment(Qt.AlignCenter)
            self.display_label.setMinimumSize(600, 400)
            self.display_label.setStyleSheet("""
                QLabel {
                    font-size: 18pt;
                    color: #ff6b6b;
                    background-color: white;
                }
            """)
            
            display_layout.addWidget(self.display_label)
            main_layout.addWidget(display_container, 1)
            
            # 设置窗口样式
            self.setStyleSheet("""
                QWidget {
                    background-color: #ffffff;
                    font-family: "Microsoft YaHei", "Arial";
                }
            """)
        
        def _browseModel(self):
            """浏览选择模型文件"""
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "选择模型文件",
                "",
                "模型文件 (*.pt *.dat *.pth);;所有文件 (*.*)"
            )
            
            if file_path:
                self.model_input.setText(file_path)
        
        def _browseVideo(self):
            """浏览选择视频文件"""
            default_video_dir = r"C:\Users\123\Desktop\yewei\video"
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "选择视频文件",
                default_video_dir,
                "视频文件 (*.mp4 *.avi *.mkv *.mov *.flv *.wmv *.m4v *.webm);;所有文件 (*.*)"
            )
            
            if file_path:
                self.rtsp_input.setText(file_path)
        
        def _selectROIWithMouse(self, frame):
            """
            自定义ROI选择，支持多个检测框
            
            Args:
                frame: 视频帧
                
            Returns:
                list: [(x, y, w, h), ...] 或 None
            """
            # ROI选择状态
            roi_data = {
                'drawing': False,
                'ix': -1,
                'iy': -1,
                'x': -1,
                'y': -1,
                'w': 0,
                'h': 0,
            }
            
            # 存储多个ROI
            roi_list = []
            
            def mouse_callback(event, x, y, flags, param):
                if event == cv2.EVENT_LBUTTONDOWN:
                    roi_data['drawing'] = True
                    roi_data['ix'] = x
                    roi_data['iy'] = y
                    
                elif event == cv2.EVENT_MOUSEMOVE:
                    if roi_data['drawing']:
                        roi_data['x'] = min(roi_data['ix'], x)
                        roi_data['y'] = min(roi_data['iy'], y)
                        roi_data['w'] = abs(x - roi_data['ix'])
                        roi_data['h'] = abs(y - roi_data['iy'])
                        
                elif event == cv2.EVENT_LBUTTONUP:
                    roi_data['drawing'] = False
                    roi_data['x'] = min(roi_data['ix'], x)
                    roi_data['y'] = min(roi_data['iy'], y)
                    roi_data['w'] = abs(x - roi_data['ix'])
                    roi_data['h'] = abs(y - roi_data['iy'])
            
            # 创建窗口并设置鼠标回调
            window_name = "选择ROI"
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.setMouseCallback(window_name, mouse_callback)
            
            display_frame = frame.copy()
            
            while True:
                # 绘制当前ROI
                temp_frame = display_frame.copy()
                
                # 绘制已添加的ROI（蓝色）
                for i, roi in enumerate(roi_list):
                    x, y, w, h = roi
                    cv2.rectangle(temp_frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
                    cv2.putText(temp_frame, f"ROI {i+1}", (x, y - 10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
                
                # 绘制当前正在绘制的ROI（绿色）
                if roi_data['w'] > 0 and roi_data['h'] > 0:
                    cv2.rectangle(temp_frame, 
                                (roi_data['x'], roi_data['y']), 
                                (roi_data['x'] + roi_data['w'], roi_data['y'] + roi_data['h']), 
                                (0, 255, 0), 2)
                    
                    # 显示ROI尺寸
                    text = f"ROI: {roi_data['w']}x{roi_data['h']}"
                    cv2.putText(temp_frame, text, (roi_data['x'], roi_data['y'] - 10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                # 显示提示信息
                cv2.putText(temp_frame, f"拖动鼠标框选区域 (已添加{len(roi_list)}个)", (10, 30),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(temp_frame, "按 C 键添加当前ROI | 按 Q 键完成 | 按 ESC 取消", (10, 60),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                cv2.imshow(window_name, temp_frame)
                
                key = cv2.waitKey(10) & 0xFF
                
                if key == ord('c') or key == ord('C'):
                    # 添加当前ROI到列表
                    if roi_data['w'] > 0 and roi_data['h'] > 0:
                        roi_list.append((roi_data['x'], roi_data['y'], roi_data['w'], roi_data['h']))
                        print(f"✅ 已添加ROI {len(roi_list)}: ({roi_data['x']}, {roi_data['y']}, {roi_data['w']}, {roi_data['h']})")
                        # 重置ROI数据，准备选择下一个
                        roi_data.update({'x': -1, 'y': -1, 'w': 0, 'h': 0})
                elif key == ord('q') or key == ord('Q'):
                    # 完成选择
                    if len(roi_list) > 0:
                        break
                elif key == 27:  # ESC键
                    # 取消选择
                    roi_list = []
                    break
            
            cv2.destroyWindow(window_name)
            
            # 返回ROI列表
            if len(roi_list) > 0:
                print(f"✅ 总共选择了 {len(roi_list)} 个检测框")
                return roi_list
            else:
                return None
        
        def _selectROI(self, source):
            """
            获取视频帧并让用户选择ROI
            
            Returns:
                tuple: (x, y, w, h) ROI坐标，或None表示全图，或False表示取消
            """
            try:
                # 判断输入类型
                if source.isdigit():
                    source = int(source)
                
                # 临时打开视频源获取一帧
                temp_cap = None
                if HK_AVAILABLE:
                    try:
                        temp_cap = HKcapture(source)
                        if not temp_cap.open():
                            QtWidgets.QMessageBox.warning(self, "错误", "无法打开视频源")
                            return False
                        
                        if not temp_cap.start_capture():
                            temp_cap.release()
                            QtWidgets.QMessageBox.warning(self, "错误", "无法开始视频捕获")
                            return False
                        
                        # 等待获取帧
                        time.sleep(1.0)
                        
                        # 读取帧
                        for _ in range(10):  # 尝试10次
                            ret, frame = temp_cap.read()
                            if ret and frame is not None:
                                break
                            time.sleep(0.1)
                        else:
                            temp_cap.release()
                            QtWidgets.QMessageBox.warning(self, "错误", "无法获取视频帧")
                            return False
                    except Exception as e:
                        if temp_cap:
                            temp_cap.release()
                        QtWidgets.QMessageBox.warning(self, "错误", f"HKcapture错误: {str(e)}")
                        return False
                else:
                    temp_cap = cv2.VideoCapture(source)
                    if not temp_cap.isOpened():
                        QtWidgets.QMessageBox.warning(self, "错误", "无法打开视频源")
                        return False
                    
                    ret, frame = temp_cap.read()
                    if not ret:
                        temp_cap.release()
                        QtWidgets.QMessageBox.warning(self, "错误", "无法获取视频帧")
                        return False
                
                # 让用户选择ROI
                reply = QtWidgets.QMessageBox.question(
                    self, 
                    "选择ROI",
                    "是否要选择特定的ROI？\n\n"
                    "点击 Yes 选择区域\n"
                    "点击 No 使用全图检测\n"
                    "点击 Cancel 取消检测",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel,
                    QtWidgets.QMessageBox.Yes
                )
                
                if reply == QtWidgets.QMessageBox.Cancel:
                    if temp_cap:
                        temp_cap.release()
                    return False
                elif reply == QtWidgets.QMessageBox.No:
                    if temp_cap:
                        temp_cap.release()
                    return None  # 全图检测
                
                # 使用自定义ROI选择（支持多个ROI）
                roi = self._selectROIWithMouse(frame)
                
                # 释放临时捕获对象
                if temp_cap:
                    temp_cap.release()
                
                # 检查是否选择了有效区域
                # roi现在是一个列表: [(x, y, w, h), ...]
                if roi:
                    # 验证所有ROI都是有效的
                    valid_rois = [r for r in roi if len(r) == 4 and r[2] > 0 and r[3] > 0]
                    if valid_rois:
                        return valid_rois
                
                # 没有有效ROI，使用全图
                return None
                    
            except Exception as e:
                if temp_cap:
                    try:
                        temp_cap.release()
                    except:
                        pass
                QtWidgets.QMessageBox.warning(self, "错误", f"ROI选择失败: {str(e)}")
                return False
        
        def _startDetection(self):
            """开始检测"""
            rtsp = self.rtsp_input.text().strip()
            model_path = self.model_input.text().strip()
            
            if not rtsp:
                QtWidgets.QMessageBox.warning(self, "警告", "请输入RTSP地址或视频源")
                return
            
            if not model_path:
                QtWidgets.QMessageBox.warning(self, "警告", "请选择模型文件")
                return
            
            if not os.path.exists(model_path):
                QtWidgets.QMessageBox.warning(self, "警告", "模型文件不存在")
                return
            
            # 更新UI状态
            self.status_label.setText("状态: 正在获取视频帧...")
            QtWidgets.QApplication.processEvents()
            
            # 获取一帧用于ROI选择
            roi = self._selectROI(rtsp)
            
            if roi is False:  # 用户取消
                self.status_label.setText("状态: 已取消")
                return
            
            # 更新UI状态
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.save_btn.setEnabled(True)
            self.rtsp_input.setEnabled(False)
            self.model_input.setEnabled(False)
            self.status_label.setText("状态: 正在启动...")
            
            # 创建并启动视频线程
            self.video_thread = VideoThread()
            self.video_thread.set_source(rtsp)
            self.video_thread.set_model(model_path)
            self.video_thread.set_roi(roi)  # 设置ROI
            # 不再连接frame_ready信号（客户端无GPU，不渲染）
            # self.video_thread.frame_ready.connect(self._updateFrame)
            self.video_thread.fps_update.connect(self._updateFPS)
            self.video_thread.error_occurred.connect(self._handleError)
            self.video_thread.start()
            
            if roi:
                if isinstance(roi, list):
                    self.status_label.setText(f"状态: 检测中 ({len(roi)}个ROI区域)")
                else:
                    self.status_label.setText(f"状态: 检测中 (ROI: {roi[2]}x{roi[3]})")
            else:
                self.status_label.setText("状态: 检测中 (全图)")
        
        def _stopDetection(self):
            """停止检测"""
            if self.video_thread:
                self.video_thread.stop()
                self.video_thread = None
            
            # 更新UI状态
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.save_btn.setEnabled(False)
            self.rtsp_input.setEnabled(True)
            self.model_input.setEnabled(True)
            self.status_label.setText("状态: 已停止")
            self.fps_label.setText("FPS: 0.0")
            
            # 清空显示
            self.display_label.setText("分割掩码结果")
            self.display_label.setPixmap(QtGui.QPixmap())
        
        def _updateFrame(self, frame):
            """更新显示帧"""
            try:
                # 转换BGR到RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # 转换为QImage
                h, w, ch = frame_rgb.shape
                bytes_per_line = ch * w
                q_image = QtGui.QImage(frame_rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
                
                # 缩放到显示区域
                pixmap = QtGui.QPixmap.fromImage(q_image)
                scaled_pixmap = pixmap.scaled(
                    self.display_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                
                self.display_label.setPixmap(scaled_pixmap)
                
                # 保存当前帧用于截图
                self.current_frame = frame
                
            except Exception as e:
                print(f"更新帧失败: {e}")
        
        def _updateFPS(self, fps):
            """更新FPS显示"""
            self.current_fps = fps
            self.fps_label.setText(f"FPS: {fps:.1f}")
        
        def _handleError(self, error_msg):
            """处理错误"""
            self.status_label.setText(f"状态: 错误 - {error_msg}")
            QtWidgets.QMessageBox.critical(self, "错误", error_msg)
            self._stopDetection()
        
        def _saveScreenshot(self):
            """保存截图"""
            if not hasattr(self, 'current_frame'):
                QtWidgets.QMessageBox.warning(self, "警告", "没有可保存的图像")
                return
            
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"debug_screenshot_{timestamp}.jpg"
            
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "保存截图",
                filename,
                "JPEG图像 (*.jpg);;PNG图像 (*.png);;所有文件 (*.*)"
            )
            
            if file_path:
                cv2.imwrite(file_path, self.current_frame)
                self.status_label.setText(f"状态: 截图已保存 - {Path(file_path).name}")
                QtWidgets.QMessageBox.information(self, "成功", f"截图已保存:\n{file_path}")
        
        def closeEvent(self, event):
            """窗口关闭事件"""
            if self.video_thread and self.video_thread.isRunning():
                self._stopDetection()
            event.accept()


def main():
    """主函数 - 自动选择GUI或命令行模式"""
    # 检查是否有命令行参数（除了脚本名称）
    if len(sys.argv) > 1:
        # 命令行模式
        parser = argparse.ArgumentParser(description='模型分割调试工具 (命令行模式)')
        parser.add_argument('--source', '-s', type=str, required=True,
                           help='视频源：RTSP地址、视频文件路径或摄像头ID(0,1,2...)')
        parser.add_argument('--model', '-m', type=str, default=None,
                           help='模型文件路径（.pt或.dat格式）')
        parser.add_argument('--device', '-d', type=str, default='cuda',
                           choices=['cuda', 'cpu', '0', '1', '2', '3'],
                           help='计算设备')
        parser.add_argument('--width', '-w', type=int, default=1280,
                           help='显示宽度')
        parser.add_argument('--height', type=int, default=720,
                           help='显示高度')
        parser.add_argument('--alpha', '-a', type=float, default=0.6,
                           help='掩码透明度 (0.0-1.0)')
        
        args = parser.parse_args()
        
        # 创建调试器（命令行模式）
        print("[CLI] 使用命令行模式")
        debugger = SegmentationDebugger(model_path=args.model, device=args.device)
        debugger.display_width = args.width
        debugger.display_height = args.height
        debugger.mask_alpha = args.alpha
        
        # 运行调试器
        success = debugger.run(args.source)
        
        return 0 if success else 1
    
    else:
        # GUI模式
        if not QT_AVAILABLE:
            print("[ERROR] GUI模式需要Qt库支持")
            print("安装方法: pip install qtpy PyQt5")
            print("\n或使用命令行模式:")
            print("  python detect_debug.py --source <视频源> --model <模型路径>")
            return 1
        
        print("[GUI] 使用GUI模式")
        app = QtWidgets.QApplication(sys.argv)
        app.setStyle("Fusion")
        
        window = DebugWindow()
        window.show()
        
        return app.exec_()


if __name__ == "__main__":
    sys.exit(main())