# -*- coding: utf-8 -*-

"""
数据采集通道处理器

独立的通道管理系统，专门用于数据采集面板
参考视频监测管理的架构，但完全独立实现
"""

import os
import threading
import queue
import time
import yaml
from qtpy import QtCore
from qtpy import QtWidgets
from qtpy import QtGui

try:
    from widgets.style_manager import DialogManager
except ImportError:
    DialogManager = None


class DataCollectionChannelHandler:
    """
    数据采集通道处理器 (Mixin类)
    
    专门为数据采集面板设计的通道管理系统
    
    架构设计：
    - 捕获线程：从通道抓取画面 -> frame_buffer
    - 显示线程：从frame_buffer读取 -> 显示到UI
    - 保存线程：从frame_buffer读取 -> 保存到文件
    """
    
    # 定义信号（需要在类级别定义）
    class _DCErrorSignal(QtCore.QObject):
        error = QtCore.Signal(str, str)  # title, message
    
    def _initDataCollectionChannelResources(self):
        """初始化数据采集通道相关资源"""
        # 通道捕获对象
        self._dc_channel_capture = None
        
        # frame_buffer（最大容量20帧，用于数据采集）
        self._dc_frame_buffer = queue.Queue(maxsize=20)
        
        # 线程对象
        self._dc_capture_thread = None
        self._dc_display_thread = None
        self._dc_save_thread = None
        
        # 线程控制标志
        self._dc_capture_flag = False
        self._dc_display_flag = False
        self._dc_save_flag = False
        
        # 通道状态
        self._dc_channel_running = False
        self._dc_channel_connected = False
        
        # 创建错误信号对象并连接
        self._dc_error_signal = self._DCErrorSignal()
        self._dc_error_signal.error.connect(self._showDataCollectionChannelErrorUI)
        
        # 保存相关
        self._dc_save_folder = None
        self._dc_save_count = 0
        self._dc_save_interval = 1.0  # 默认每秒保存一帧
        
        # 从配置文件加载帧率设置
        self._loadDataCollectionFrameRateConfig()
        
        pass
    
    def _loadDataCollectionFrameRateConfig(self):
        """从配置文件加载数据采集专用的帧率设置"""
        try:
            config = getattr(self, '_config', {})
            
            # 数据采集专用帧率配置
            self._dc_capture_fps = config.get('datacollection_capture_fps', 25)
            self._dc_display_fps = config.get('datacollection_display_fps', 25)
            self._dc_save_fps = config.get('datacollection_save_fps', 1)  # 默认每秒保存1帧
            
            pass
            # 帧率配置已设置
            
        except Exception as e:
            pass
            # 使用默认帧率
            self._dc_capture_fps = 25
            self._dc_display_fps = 25
            self._dc_save_fps = 1
    
    def startDataCollectionChannel(self, save_folder=None, channel_source=0):
        """
        启动数据采集通道
        
        Args:
            save_folder: 保存文件夹路径
            channel_source: 通道源（默认0为系统默认通道）
        
        Returns:
            bool: 启动是否成功
        """
        try:
            # 检查是否已经在运行
            if self._dc_channel_running:
                return False
            
            # 设置保存文件夹
            self._dc_save_folder = save_folder
            self._dc_save_count = 0
            
            # 标记为正在尝试连接（防止重复点击）
            self._dc_channel_running = True
            
            # 在后台线程中打开通道
            thread = threading.Thread(
                target=self._connectDataCollectionChannelThread,
                args=(channel_source,),
                daemon=True
            )
            thread.start()
            
            return True
            
        except Exception as e:
            self._showDataCollectionChannelError("启动通道失败", str(e))
            self._dc_channel_running = False
            return False
    
    def stopDataCollectionChannel(self):
        """
        停止数据采集通道
        
        Returns:
            bool: 停止是否成功
        """
        try:
            if not self._dc_channel_running:
                return True
            
            # 检查是否正在录制视频
            if hasattr(self, '_dc_video_recording') and self._dc_video_recording:
                # 提示用户必须先停止录制
                self._showDataCollectionChannelError(
                    "无法关闭通道", 
                    "正在录制视频，请先停止录制后再关闭通道"
                )
                # 设置标志位，防止显示第二个提示框
                self._dc_close_blocked_by_recording = True
                return False
            
            # 停止所有线程
            self._stopDataCollectionVideoStream()
            
            # 释放通道资源
            self._releaseDataCollectionChannel()
            
            # 更新状态
            self._dc_channel_running = False
            self._dc_channel_connected = False
            
            # 通知UI更新（线程安全）
            QtCore.QTimer.singleShot(0, self._onDataCollectionChannelDisconnected)
            
            return True
            
        except Exception as e:
            return False
    
    def _connectDataCollectionChannelThread(self, channel_source):
        """在后台线程中连接数据采集通道（使用与实时监测管理相同的方式）"""
        try:
            print(f"[数据采集] 开始连接通道，channel_source={channel_source}, 类型={type(channel_source)}")
            success = False
            error_detail = ""

            # 如果channel_source是数字，尝试从配置中获取通道信息
            if str(channel_source).isdigit():
                print(f"[数据采集] channel_source是数字，尝试从配置获取通道信息")
                channel_config = self._getChannelConfigFromMainConfig(channel_source)
                print(f"[数据采集] 获取到的通道配置: {channel_config}")
                if channel_config:
                    success = self._connectRealChannel(channel_config)
                    if not success:
                        error_detail = f"无法连接到配置的通道 {channel_source}\n请检查：\n相机是否已开机并连接到网络\nIP地址和端口是否正确"
                else:
                    # 如果没有配置，尝试直接连接USB通道
                    success = self._connectUSBChannel(channel_source)
                    if not success:
                        error_detail = f"无法连接到USB通道 {channel_source}\n请检查：\nUSB相机是否已连接\n相机驱动是否已安装\n相机是否被其他程序占用"
            else:
                # 如果是RTSP地址，直接连接
                success = self._connectRTSPChannel(channel_source)
                if not success:
                    error_detail = f"无法连接到RTSP地址\n请检查：\n网络连接是否正常\nRTSP地址格式是否正确\n相机是否支持RTSP协议\n\n地址：{channel_source}"
            
            print(f"[数据采集] 连接结果: success={success}")

            if not success:
                self._showDataCollectionChannelError(
                    "相机连接失败", 
                    error_detail if error_detail else "无法打开通道设备，请检查通道是否连接正常或配置是否正确"
                )
                # 重置状态，确保UI恢复正常
                self._dc_channel_running = False
                self._dc_channel_connected = False
                # 通知UI更新按钮状态（线程安全）
                QtCore.QTimer.singleShot(0, self._onDataCollectionChannelDisconnected)
                return
            
            # 更新状态
            self._dc_channel_connected = True
            self._dc_channel_running = True
            
            # 启动视频流处理
            self._startDataCollectionVideoStream()
            
            # 通知UI更新（线程安全）
            QtCore.QTimer.singleShot(0, self._onDataCollectionChannelConnected)
            
        except Exception as e:
            self._showDataCollectionChannelError(
                "通道连接异常", 
                f"连接过程中发生错误：\n\n{str(e)}\n\n请检查相机设置和网络连接"
            )
            # 重置状态，确保UI恢复正常
            self._dc_channel_running = False
            self._dc_channel_connected = False
            # 通知UI更新按钮状态（线程安全）
            QtCore.QTimer.singleShot(0, self._onDataCollectionChannelDisconnected)
    
    def _startDataCollectionVideoStream(self):
        """启动数据采集视频流处理"""
        print("[数据采集] _startDataCollectionVideoStream 被调用")
        # 清空帧缓存
        while not self._dc_frame_buffer.empty():
            try:
                self._dc_frame_buffer.get_nowait()
            except queue.Empty:
                break

        # 设置线程运行标志
        self._dc_capture_flag = True
        self._dc_display_flag = True
        self._dc_save_flag = True if self._dc_save_folder else False
        print(f"[数据采集] 线程标志已设置: capture={self._dc_capture_flag}, display={self._dc_display_flag}")

        # 启动捕获线程
        print("[数据采集] 准备启动捕获线程")
        self._dc_capture_thread = threading.Thread(
            target=self._dataCollectionCaptureLoop,
            name="DC-Capture",
            daemon=True
        )
        self._dc_capture_thread.start()
        print(f"[数据采集] 捕获线程已启动: {self._dc_capture_thread.is_alive()}")

        # 启动显示线程
        print("[数据采集] 准备启动显示线程")
        self._dc_display_thread = threading.Thread(
            target=self._dataCollectionDisplayLoop,
            name="DC-Display",
            daemon=True
        )
        self._dc_display_thread.start()
        print(f"[数据采集] 显示线程已启动: {self._dc_display_thread.is_alive()}")
        
        # 暂时禁用保存功能（根据用户要求）
        # if self._dc_save_folder:
        #     self._dc_save_thread = threading.Thread(
        #         target=self._dataCollectionSaveLoop,
        #         name="DC-Save",
        #         daemon=True
        #     )
        #     self._dc_save_thread.start()
    
    def _dataCollectionCaptureLoop(self):
        """数据采集捕获线程循环"""
        print("[数据采集] 捕获线程已启动")
        frame_count = 0
        read_attempts = 0
        frame_interval = 1.0 / self._dc_capture_fps if self._dc_capture_fps > 0 else 0.04

        while self._dc_capture_flag:
            try:
                # 读取帧
                ret = False
                frame = None
                read_attempts += 1

                if hasattr(self._dc_channel_capture, 'read_latest'):
                    # HKcapture
                    ret, frame = self._dc_channel_capture.read_latest()
                    if read_attempts % 30 == 1:  # 每30次尝试打印一次
                        print(f"[数据采集] read_latest 尝试 {read_attempts} 次, ret={ret}, frame={'有' if frame is not None else '无'}")
                else:
                    # OpenCV
                    ret, frame = self._dc_channel_capture.read()
                    if read_attempts % 30 == 1:
                        print(f"[数据采集] read 尝试 {read_attempts} 次, ret={ret}, frame={'有' if frame is not None else '无'}")

                if ret and frame is not None:
                    frame_count += 1
                    if frame_count % 30 == 1:  # 每30帧打印一次
                        print(f"[数据采集] 捕获线程已捕获 {frame_count} 帧")
                    
                    # 将帧放入缓存池
                    try:
                        if self._dc_frame_buffer.full():
                            # 队列满了，丢弃最旧的帧
                            try:
                                self._dc_frame_buffer.get_nowait()
                            except queue.Empty:
                                pass
                        
                        # 放入新帧
                        self._dc_frame_buffer.put_nowait(frame.copy())
                            
                    except queue.Full:
                        pass  # 队列满，跳过这一帧
                else:
                    # 没有新帧，等待
                    time.sleep(frame_interval / 4)
                    
            except Exception as e:
                time.sleep(0.1)
    
    def _getChannelConfigFromMainConfig(self, channel_index):
        """从主配置中获取通道配置"""
        try:
            print(f"[数据采集] _getChannelConfigFromMainConfig 被调用，channel_index={channel_index}")
            # 尝试获取channel配置
            channel_key = f"channel{channel_index}"
            print(f"[数据采集] 查找配置key: {channel_key}")

            # 首先尝试从RTSP配置文件获取
            rtsp_config = self._loadRTSPConfig()
            print(f"[数据采集] _loadRTSPConfig 返回: {rtsp_config}")

            if rtsp_config and 'channels' in rtsp_config:
                print(f"[数据采集] rtsp_config包含channels，keys: {list(rtsp_config['channels'].keys())}")
                if channel_key in rtsp_config['channels']:
                    config = rtsp_config['channels'][channel_key]
                    print(f"[数据采集] 从RTSP配置找到通道配置: {config}")
                    return config
                else:
                    print(f"[数据采集] RTSP配置中没有找到 {channel_key}")
            else:
                print(f"[数据采集] rtsp_config为空或不包含channels")

            # 如果RTSP配置没有，尝试从self._config获取
            if hasattr(self, '_config') and channel_key in self._config:
                config = self._config[channel_key]
                print(f"[数据采集] 从self._config找到通道配置: {config}")
                return config
            else:
                print(f"[数据采集] self._config中没有找到 {channel_key}")

            # 如果self._config没有，尝试从父类获取
            if hasattr(self, '_parent') and hasattr(self._parent, '_config'):
                parent_config = self._parent._config
                if channel_key in parent_config:
                    config = parent_config[channel_key]
                    print(f"[数据采集] 从parent._config找到通道配置: {config}")
                    return config
                else:
                    print(f"[数据采集] parent._config中没有找到 {channel_key}")
            else:
                print(f"[数据采集] 没有parent._config")

            # 如果都没有找到，返回None
            print(f"[数据采集] 所有配置源都没有找到 {channel_key}，返回None")
            return None
        except Exception as e:
            print(f"[数据采集] _getChannelConfigFromMainConfig 异常: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _loadRTSPConfig(self):
        """加载RTSP配置（从 default_config.yaml 读取通道地址管理配置）"""
        try:
            import os
            import yaml
            
            #  基于项目根目录动态获取配置文件路径
            # 当前文件是 handlers/datasetpage/datacollection_channel_handler.py
            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
            config_path = os.path.join(project_root, 'database', 'config', 'default_config.yaml')
            
            if not os.path.exists(config_path):
                return None
            
            # 读取配置文件
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if not config:
                return None
            
            # 提取通道地址配置（channel1, channel2, channel3, channel4）
            channels = {}
            for i in range(1, 5):  # channel1 到 channel4
                channel_key = f'channel{i}'
                if channel_key in config:
                    channel_info = config[channel_key]
                    if isinstance(channel_info, dict):
                        # 直接使用原始配置格式
                        channels[channel_key] = channel_info

            if channels:
                return {'channels': channels}
            else:
                return None
            
        except Exception as e:
            return None
    
    def _parseRTSP(self, rtsp_url):
        """解析RTSP URL（复用实时监测管理的方法）"""
        try:
            # RTSP URL格式: rtsp://username:password@ip:port/path
            # 支持密码中包含@符号的情况
            if not rtsp_url.startswith('rtsp://'):
                return None, None, None
            
            url_part = rtsp_url[7:]  # 去掉 "rtsp://"
            
            # 找到最后一个 @ 符号（IP地址前的那个）
            last_at_index = url_part.rfind('@')
            if last_at_index == -1:
                return None, None, None
            
            credentials_part = url_part[:last_at_index]
            host_part = url_part[last_at_index + 1:]
            
            # 分离用户名和密码（第一个:分隔）
            first_colon = credentials_part.find(':')
            if first_colon == -1:
                return None, None, None
            
            username = credentials_part[:first_colon]
            password = credentials_part[first_colon + 1:]
            
            # URL解码密码
            from urllib.parse import unquote
            password = unquote(password)
            
            # 提取IP（到:或/为止）
            ip_end = len(host_part)
            colon_idx = host_part.find(':')
            slash_idx = host_part.find('/')
            if colon_idx != -1:
                ip_end = min(ip_end, colon_idx)
            if slash_idx != -1:
                ip_end = min(ip_end, slash_idx)
            ip = host_part[:ip_end]
            
            return username, password, ip
                
        except Exception as e:
            return None, None, None
    
    def _connectRealChannel(self, channel_config):
        """连接真实通道（使用配置信息）"""
        try:
            # 解析RTSP地址 - 支持多种配置格式
            rtsp_url = channel_config.get('rtsp_url', channel_config.get('address', channel_config.get('rtsp', '')))
            
            if not rtsp_url:
                return False
            
            # 导入HKcapture
            try:
                from videopage.HK_SDK.HKcapture import HKcapture
            except ImportError:
                from handlers.videopage.HK_SDK.HKcapture import HKcapture
            
            # 检查是否是海康威视设备
            device_type = channel_config.get('device_type', '')
            
            if device_type == 'hikvision' and 'ip' in channel_config:
                # 海康威视摄像头（使用SDK）
                ip = channel_config.get('ip')
                username = channel_config.get('username', 'admin')
                password = channel_config.get('password', '')
                port = channel_config.get('port', 8000)
                
                cap = HKcapture(
                    source=ip,
                    username=username,
                    password=password,
                    port=port,
                    channel=1,
                    fps=self._dc_capture_fps
                )
                # 创建海康威视捕获对象
            else:
                # 其他RTSP摄像头或直接使用RTSP URL
                cap = HKcapture(
                    source=rtsp_url,
                    fps=self._dc_capture_fps
                )
            
            # 打开连接
            if not cap.open():
                return False
            
            # 开始捕获
            if not cap.start_capture():
                cap.release()
                return False
            
            # 保存捕获对象
            self._dc_channel_capture = cap
            return True
            
        except Exception as e:
            return False
    
    def _connectUSBChannel(self, channel_index):
        """连接USB通道"""
        try:
            import cv2
            
            cap = cv2.VideoCapture(int(channel_index))
            
            if cap.isOpened():
                # 设置分辨率和帧率
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, self._dc_capture_fps)
                
                self._dc_channel_capture = cap
                return True
            else:
                return False
                
        except Exception as e:
            return False
    
    def _connectRTSPChannel(self, rtsp_url):
        """连接RTSP通道"""
        try:
            try:
                from videopage.HK_SDK.HKcapture import HKcapture
            except ImportError:
                from handlers.videopage.HK_SDK.HKcapture import HKcapture
            
            cap = HKcapture(source=rtsp_url, fps=self._dc_capture_fps)
            
            if cap.open():
                if cap.start_capture():
                    self._dc_channel_capture = cap
                    return True
                else:
                    cap.release()
                    return False
            else:
                return False
                
        except Exception as e:
            return False

    def _dataCollectionDisplayLoop(self):
        """数据采集显示线程循环"""
        print("[数据采集] 显示线程已启动")
        display_count = 0
        frame_interval = 1.0 / self._dc_display_fps if self._dc_display_fps > 0 else 0.033
        last_display_time = time.time()

        while self._dc_display_flag:
            try:
                # 从缓存池获取最新帧
                frame = None
                frames_skipped = 0

                # 清空队列，只保留最新帧
                while not self._dc_frame_buffer.empty():
                    try:
                        frame = self._dc_frame_buffer.get_nowait()
                        frames_skipped += 1
                    except queue.Empty:
                        break

                if frame is None:
                    # 没有帧，等待
                    time.sleep(0.01)
                    continue

                display_count += 1
                if display_count % 30 == 1:  # 每30帧打印一次
                    print(f"[数据采集] 已显示 {display_count} 帧，缓冲区大小: {self._dc_frame_buffer.qsize()}")
                
                # 更新UI显示
                self._updateDataCollectionVideoDisplay(frame)
                
                # 录制视频（如果正在录制）
                self._writeVideoFrame(frame)
                
                # 控制显示帧率
                current_time = time.time()
                elapsed = current_time - last_display_time
                sleep_time = frame_interval - elapsed
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
                last_display_time = time.time()
                
            except Exception as e:
                time.sleep(0.1)
    
    def _dataCollectionSaveLoop(self):
        """数据采集保存线程循环"""
        if not self._dc_save_folder:
            return
        
        save_count = 0
        save_interval = 1.0 / self._dc_save_fps if self._dc_save_fps > 0 else 1.0
        last_save_time = time.time()
        
        # 确保保存目录存在
        os.makedirs(self._dc_save_folder, exist_ok=True)
        
        while self._dc_save_flag:
            try:
                current_time = time.time()
                
                # 检查是否到了保存时间
                if current_time - last_save_time >= save_interval:
                    # 从缓存池获取一帧进行保存
                    frame = None
                    try:
                        # 非阻塞获取，避免保存线程等待
                        frame = self._dc_frame_buffer.get(timeout=0.1)
                    except queue.Empty:
                        time.sleep(0.1)
                        continue
                    
                    if frame is not None:
                        # 生成文件名
                        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
                        filename = f"capture_{timestamp}_{save_count:06d}.jpg"
                        filepath = os.path.join(self._dc_save_folder, filename)
                        
                        # 保存图像
                        try:
                            import cv2
                            success = cv2.imwrite(filepath, frame)
                            
                            if success:
                                save_count += 1
                                self._dc_save_count = save_count
                                
                        except Exception as e:
                            pass
                    
                    last_save_time = current_time
                else:
                    # 还没到保存时间，等待
                    time.sleep(0.1)
                    
            except Exception as e:
                time.sleep(0.1)
    
    def _updateDataCollectionVideoDisplay(self, frame):
        """更新数据采集视频显示（线程安全）"""
        try:
            # 直接调用UI更新方法
            self._updateDataCollectionVideoDisplayUI(frame)
        except Exception as e:
            pass
    
    def _updateDataCollectionVideoDisplayUI(self, frame):
        """在主线程中更新数据采集视频显示"""
        try:
            # 查找数据采集面板的通道预览控件
            if hasattr(self, 'dataCollectionPanel'):
                if hasattr(self.dataCollectionPanel, 'channel_preview'):
                    preview_widget = self.dataCollectionPanel.channel_preview

                    # 转换帧格式并显示
                    self._displayFrameInWidget(frame, preview_widget)
                else:
                    print("[数据采集] dataCollectionPanel没有channel_preview属性")
            else:
                print("[数据采集] 没有dataCollectionPanel属性")

        except Exception as e:
            print(f"[数据采集] 更新显示异常: {e}")
            import traceback
            traceback.print_exc()
    
    def _displayFrameInWidget(self, frame, widget):
        """在指定的QLabel控件中显示帧"""
        try:
            import cv2
            
            # 转换颜色空间 BGR -> RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # 转换为 QImage
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            qt_image = QtGui.QImage(frame_rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
            
            # 缩放到控件大小
            pixmap = QtGui.QPixmap.fromImage(qt_image)
            widget_size = widget.size()
            
            scaled_pixmap = pixmap.scaled(
                widget_size,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            
            # 显示
            widget.setPixmap(scaled_pixmap)
            
        except Exception as e:
            pass
    
    def _stopDataCollectionVideoStream(self):
        """停止数据采集视频流处理"""
        # 设置停止标志
        self._dc_capture_flag = False
        self._dc_display_flag = False
        self._dc_save_flag = False
        
        # 等待捕获线程结束
        if self._dc_capture_thread and self._dc_capture_thread.is_alive():
            self._dc_capture_thread.join(timeout=2.0)
        
        # 等待显示线程结束
        if self._dc_display_thread and self._dc_display_thread.is_alive():
            self._dc_display_thread.join(timeout=2.0)
        
        # 等待保存线程结束
        if self._dc_save_thread and self._dc_save_thread.is_alive():
            self._dc_save_thread.join(timeout=2.0)
        
        # 清空帧缓存
        while not self._dc_frame_buffer.empty():
            try:
                self._dc_frame_buffer.get_nowait()
            except queue.Empty:
                break
    
    def _releaseDataCollectionChannel(self):
        """释放数据采集通道资源"""
        try:
            if self._dc_channel_capture:
                if hasattr(self._dc_channel_capture, 'release'):
                    self._dc_channel_capture.release()
                self._dc_channel_capture = None
        except Exception as e:
            pass
    
    def _onDataCollectionChannelConnected(self):
        """数据采集通道连接成功回调（在主线程中执行）"""
        try:
            # 更新数据采集面板的UI状态
            if hasattr(self, 'dataCollectionPanel'):
                panel = self.dataCollectionPanel
                
                # 更新按钮状态
                if hasattr(panel, 'btn_start_channel'):
                    panel.btn_start_channel.setEnabled(False)
                if hasattr(panel, 'btn_record_video'):
                    panel.btn_record_video.setEnabled(True)  # 启用录制视频按钮
                if hasattr(panel, 'btn_stop_channel'):
                    panel.btn_stop_channel.setEnabled(True)
                
                # 更新状态标签
                if hasattr(panel, 'lbl_channel_status'):
                    panel.lbl_channel_status.setText("通道状态: 运行中")
                    panel.lbl_channel_status.setStyleSheet("color: #2ca02c; padding: 5px; font-weight: bold;")
            
            # 更新状态栏
            if hasattr(self, 'statusBar'):
                self.statusBar().showMessage("数据采集通道已启动")
            
        except Exception as e:
            pass
    
    def _onDataCollectionChannelDisconnected(self):
        """数据采集通道断开回调（在主线程中执行）"""
        try:
            # 更新数据采集面板的UI状态
            if hasattr(self, 'dataCollectionPanel'):
                panel = self.dataCollectionPanel
                
                # 更新按钮状态
                if hasattr(panel, 'btn_start_channel'):
                    panel.btn_start_channel.setEnabled(True)
                if hasattr(panel, 'btn_record_video'):
                    panel.btn_record_video.setEnabled(False)  # 禁用录制视频按钮
                if hasattr(panel, 'btn_stop_channel'):
                    panel.btn_stop_channel.setEnabled(False)
                
                # 更新状态标签
                if hasattr(panel, 'lbl_channel_status'):
                    panel.lbl_channel_status.setText("通道状态: 已停止")
                    panel.lbl_channel_status.setStyleSheet("color: #666; padding: 5px;")
                
                # 清空预览
                if hasattr(panel, 'channel_preview'):
                    panel.channel_preview.clear()
                    panel.channel_preview.setText("通道预览\n点击\"启动通道\"开始预览")
            
            # 更新状态栏
            if hasattr(self, 'statusBar'):
                self.statusBar().showMessage("数据采集通道已停止")
            
        except Exception as e:
            pass
    
    def _showDataCollectionChannelError(self, title, message):
        """显示数据采集通道错误（线程安全）"""
        # 使用信号发射错误信息（线程安全）
        self._dc_error_signal.error.emit(title, message)
    
    def _showDataCollectionChannelErrorUI(self, title, message):
        """在主线程中显示数据采集通道错误"""
        try:
            if DialogManager:
                DialogManager.show_critical(self, title, message)
            else:
                QtWidgets.QMessageBox.critical(self, title, message)
            
            if hasattr(self, 'statusBar'):
                self.statusBar().showMessage(f"错误: {message}")
                
        except Exception as e:
            pass
    
    def getDataCollectionChannelStatus(self):
        """
        获取数据采集通道状态
        
        Returns:
            dict: 通道状态信息
        """
        return {
            'running': self._dc_channel_running,
            'connected': self._dc_channel_connected,
            'save_folder': self._dc_save_folder,
            'save_count': self._dc_save_count,
            'buffer_size': self._dc_frame_buffer.qsize() if hasattr(self, '_dc_frame_buffer') else 0
        }
    
    def setDataCollectionSaveSettings(self, save_fps=None, save_folder=None):
        """
        设置数据采集保存参数
        
        Args:
            save_fps: 保存帧率
            save_folder: 保存文件夹
        """
        if save_fps is not None:
            self._dc_save_fps = save_fps
        
        if save_folder is not None:
            self._dc_save_folder = save_folder
    
    def startDataCollectionVideoRecording(self, video_path):
        """
        开始录制视频
        
        Args:
            video_path: 视频保存路径
            
        Returns:
            bool: 是否成功开始录制
        """
        try:
            # 检查通道是否在运行
            if not self._dc_channel_running:
                return False
            
            # 检查是否已在录制
            if hasattr(self, '_dc_video_recording') and self._dc_video_recording:
                return False
            
            # 初始化视频录制参数
            self._dc_video_path = video_path
            self._dc_video_recording = True
            self._dc_video_writer = None
            self._dc_video_frame_count = 0
            
            return True
            
        except Exception as e:
            return False
    
    def stopDataCollectionVideoRecording(self):
        """
        停止录制视频
        
        Returns:
            bool: 是否成功停止录制
        """
        try:
            # 检查是否在录制
            if not hasattr(self, '_dc_video_recording') or not self._dc_video_recording:
                return True
            
            # 检查是否录制了任何帧
            if not hasattr(self, '_dc_video_writer') or self._dc_video_writer is None:
                # 没有录制到任何帧，清理状态并返回失败
                self._dc_video_recording = False
                return False
            
            # 停止录制
            self._dc_video_recording = False
            
            # 释放视频写入器
            if self._dc_video_writer is not None:
                self._dc_video_writer.release()
                self._dc_video_writer = None
            
            # 等待文件系统完成写入（确保文件完全写入磁盘）
            time.sleep(0.5)
            
            return True
            
        except Exception as e:
            return False
    
    def _writeVideoFrame(self, frame):
        """将帧写入视频文件"""
        try:
            # 检查是否正在录制
            if not hasattr(self, '_dc_video_recording') or not self._dc_video_recording:
                return
            
            # 初始化视频写入器（如果还未初始化）
            if not hasattr(self, '_dc_video_writer') or self._dc_video_writer is None:
                self._initVideoWriter(frame)
            
            # 写入帧
            if hasattr(self, '_dc_video_writer') and self._dc_video_writer is not None:
                self._dc_video_writer.write(frame)
                self._dc_video_frame_count = getattr(self, '_dc_video_frame_count', 0) + 1
                    
        except Exception as e:
            pass
    
    def _initVideoWriter(self, frame):
        """初始化视频写入器"""
        try:
            import cv2
            import os
            
            # 确保保存目录存在
            video_dir = os.path.dirname(self._dc_video_path)
            os.makedirs(video_dir, exist_ok=True)
            
            # 获取帧的尺寸
            height, width = frame.shape[:2]
            
            # 设置视频编码器和参数
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # 使用mp4v编码
            fps = self._dc_display_fps  # 使用显示帧率作为视频帧率
            
            # 创建视频写入器
            self._dc_video_writer = cv2.VideoWriter(
                self._dc_video_path,
                fourcc,
                fps,
                (width, height)
            )
            
            if not self._dc_video_writer.isOpened():
                self._dc_video_writer = None
                
        except Exception as e:
            self._dc_video_writer = None
