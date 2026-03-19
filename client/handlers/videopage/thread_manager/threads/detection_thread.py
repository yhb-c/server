# -*- coding: utf-8 -*-

"""
检测线程

职责：
1. 从frame_buffer读取帧
2. 使用检测引擎进行推理
3. 输出检测结果到检测结果队列
4. 更新最新检测结果（供显示线程和曲线绘制使用）

配置文件：
- 模型配置：从 channel_config.yaml 读取
- 标注数据：从 annotation_result.yaml 读取
"""

import time
import queue
import os
import yaml
import cv2
import numpy as np
from typing import Callable, Optional


class DetectionThread:
    """检测线程类（支持批处理+GPU加速）"""
    
    @staticmethod
    def run(context, frame_rate: float, detection_model=None,
            on_detection_mission_result: Optional[Callable] = None,
            batch_size: int = 4, use_batch: bool = True):
        """检测线程主循环（批处理模式）
        
        Args:
            context: ChannelThreadContext 实例
            frame_rate: 检测帧率（从default_config.detection_frame_rate读取）
            detection_model: 检测模型对象（可选，如果为None则创建）
            on_detection_mission_result: 检测结果回调函数 callback(channel_id, mission_result)
            batch_size: 批处理大小（2-8，推荐4）
            use_batch: 是否启用批处理模式
        """
        channel_id = context.channel_id
        
        # 初始化检测引擎
        detection_engine = DetectionThread._initialize_detection_engine(
            channel_id, detection_model, batch_size=batch_size
        )
        
        if detection_engine is None:
            return
        
        # 决定使用批处理还是单帧处理
        if use_batch:
            print(f"[{channel_id}] 启用批处理模式（批大小={batch_size}）")
            DetectionThread._run_batch_mode(
                context, detection_engine, frame_rate, 
                batch_size, on_detection_mission_result
            )
        else:
            print(f"[{channel_id}] 使用单帧模式")
            DetectionThread._run_single_mode(
                context, detection_engine, frame_rate, on_detection_mission_result
            )

    
    @staticmethod
    def _run_single_mode(context, detection_engine, frame_rate, on_detection_mission_result):
        """单帧检测模式（保留原有逻辑）"""
        channel_id = context.channel_id
        frame_interval = 1.0 / frame_rate if frame_rate > 0 else 0.05
        
        while context.channel_detect_status:
            try:
                frame_start_time = time.time()
                
                # 从frame_buffer读取最新帧（非消费式 - 只取最新帧，丢弃旧帧）
                # 这样检测线程按自己的帧率处理，不会被捕获线程的速度影响
                # 注意：捕获线程放入队列时已复制，这里直接使用无需再复制
                frame = None
                while not context.frame_buffer.empty():
                    try:
                        # 取出帧，如果还有更新的就继续取，最终得到最新帧
                        frame = context.frame_buffer.get_nowait()
                    except queue.Empty:
                        break
                
                if frame is None:
                    # 没有新帧，短暂等待
                    time.sleep(0.01)
                    continue
                
                # 执行检测（传入channel_id用于多通道状态隔离）
                detection_mission_result = detection_engine.detect(frame, channel_id=channel_id)
                
                if detection_mission_result is not None:
                    context.detection_count += 1
                    
                    # 放入检测结果队列（供曲线绘制使用）
                    try:
                        if context.detection_mission_results.full():
                            context.detection_mission_results.get_nowait()  # 丢弃旧结果
                        context.detection_mission_results.put_nowait(detection_mission_result)
                    except:
                        pass
                    
                    #  放入存储数据队列（供存储线程使用，独立队列）
                    #  优化：detection_mission_result每次都是新对象，直接使用无需copy
                    if 'liquid_line_positions' in detection_mission_result:
                        try:
                            if context.storage_data.full():
                                context.storage_data.get_nowait()  # 丢弃旧数据
                            context.storage_data.put_nowait(detection_mission_result)
                        except:
                            pass
                    
                    # 更新最新检测结果（供显示线程使用）
                    with context.detection_lock:
                        context.latest_detection = detection_mission_result
                    
                    # 调用检测结果回调
                    if on_detection_mission_result:
                        try:
                            on_detection_mission_result(channel_id, detection_mission_result)
                        except Exception as e:
                            pass  # 静默处理回调错误
                
                # 外部帧率控制
                elapsed = time.time() - frame_start_time
                sleep_time = max(0, frame_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
            except Exception as e:
                time.sleep(0.1)
    
    @staticmethod
    def _run_batch_mode(context, detection_engine, frame_rate, batch_size, on_detection_mission_result):
        """批处理检测模式（GPU优化）"""
        channel_id = context.channel_id
        frame_interval = 1.0 / frame_rate if frame_rate > 0 else 0.05
        
        # 批处理缓存
        batch_frames = []
        batch_timestamps = []
        last_batch_time = time.time()
        max_wait_time = 0.05  # 最大等待50ms，防止延迟过高
        
        print(f"[{channel_id}] 批处理模式启动")
        print(f"  - 批大小: {batch_size}")
        print(f"  - 目标FPS: {frame_rate}")
        
        while context.channel_detect_status:
            try:
                frame_start_time = time.time()
                
                # 从缓冲区获取最新帧
                frame = None
                while not context.frame_buffer.empty():
                    try:
                        frame = context.frame_buffer.get_nowait()
                    except queue.Empty:
                        break
                
                if frame is not None:
                    batch_frames.append(frame)
                    batch_timestamps.append(frame_start_time)
                
                # 检查是否达到批处理条件
                time_since_last_batch = time.time() - last_batch_time
                should_process = (
                    len(batch_frames) >= batch_size or  # 达到批大小
                    (len(batch_frames) > 0 and time_since_last_batch >= max_wait_time)  # 超时
                )
                
                if should_process:
                    # 批量检测
                    mission_results = DetectionThread._batch_detect(
                        detection_engine, batch_frames, context
                    )
                    
                    # 只使用最后一个结果（最新帧）
                    if mission_results:
                        last_mission_result = mission_results[-1]
                        
                        # 更新上下文
                        context.detection_count += len(mission_results)
                        
                        #  放入显示结果队列（供显示线程使用）
                        if 'liquid_line_positions' in last_mission_result:
                            try:
                                if context.detection_mission_results.full():
                                    context.detection_mission_results.get_nowait()
                                context.detection_mission_results.put_nowait(last_mission_result)
                            except:
                                pass
                        
                        #  放入存储数据队列（供存储线程使用，保存到CSV）
                        if 'liquid_line_positions' in last_mission_result:
                            try:
                                if context.storage_data.full():
                                    context.storage_data.get_nowait()
                                context.storage_data.put_nowait(last_mission_result)
                            except:
                                pass
                        
                        # 更新最新检测结果
                        with context.detection_lock:
                            context.latest_detection = last_mission_result
                        
                        # 回调
                        if on_detection_mission_result:
                            try:
                                on_detection_mission_result(channel_id, last_mission_result)
                            except:
                                pass
                    
                    # 清空批次
                    batch_frames.clear()
                    batch_timestamps.clear()
                    last_batch_time = time.time()
                
                # 帧率控制
                elapsed = time.time() - frame_start_time
                sleep_time = max(0, frame_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except Exception as e:
                print(f"[{channel_id}] 批处理异常: {e}")
                batch_frames.clear()
                batch_timestamps.clear()
                time.sleep(0.1)
    
    @staticmethod
    def _batch_detect(engine, frames, context):
        """批量检测多帧"""
        if not frames:
            return []
        
        channel_id = context.channel_id
        mission_results = []
        try:
            # 对每一帧执行检测（传入channel_id用于多通道状态隔离）
            for frame in frames:
                mission_result = engine.detect(frame, channel_id=channel_id)
                if mission_result:
                    mission_results.append(mission_result)
        except Exception as e:
            print(f"批量检测失败: {e}")
        
        return mission_results
    
    @staticmethod
    def _initialize_detection_engine(channel_id: str, detection_model=None, batch_size: int = 4):
        """初始化检测引擎
        
        Args:
            channel_id: 通道ID（如 'channel1'）
            detection_model: 外部传入的检测模型（可选）
            
        Returns:
            初始化好的检测引擎对象，失败返回None
        """
        try:
            # 如果提供了外部检测模型，直接使用
            if detection_model is not None:
                return detection_model
            
            # 读取配置文件
            model_config = DetectionThread._load_model_config(channel_id)
            annotation_config = DetectionThread._load_annotation_config(channel_id)
            
            if model_config is None:
                return None
            
            # 获取模型路径
            model_path = model_config.get('model_path')
            if not model_path:
                print(f"[{channel_id}] [ERROR] 模型路径为空")
                return None
            
            # 通过SSH在服务端初始化检测引擎
            print(f"[{channel_id}] [INFO] 正在通过SSH在服务端初始化检测引擎...")
            print(f"  - 模型路径: {model_path}")
            print(f"  - 设备: cuda")
            print(f"  - 批处理大小: {batch_size}")
            
            # 导入远程配置管理器
            try:
                from ....utils.config import RemoteConfigManager
            except ImportError:
                try:
                    from utils.config import RemoteConfigManager
                except ImportError:
                    RemoteConfigManager = None
                    
            if not RemoteConfigManager:
                print("[检测线程] 远程配置管理器不可用")
                return None
                
            remote_config = RemoteConfigManager()
            ssh_manager = remote_config._get_ssh_manager()
            
            if not ssh_manager:
                print(f"[{channel_id}] [ERROR] SSH连接不可用")
                return None
            
            # 构建服务端检测引擎初始化命令
            init_cmd = f"""
cd /home/lqj/liquid/server
source ~/anaconda3/bin/activate liquid
python -c "
import sys
sys.path.append('/home/lqj/liquid/server')
try:
    from detection import LiquidDetectionEngine
    engine = LiquidDetectionEngine(
        model_path='{model_path}',
        device='cuda',
        batch_size={batch_size}
    )
    print('SUCCESS: 服务端检测引擎初始化成功')
except Exception as e:
    print(f'ERROR: 服务端检测引擎初始化失败: {{e}}')
    import traceback
    traceback.print_exc()
"
"""
            
            result = ssh_manager.execute_remote_command(init_cmd)
            
            if not result['success'] or 'SUCCESS' not in result['stdout']:
                error_msg = result.get('stderr', result.get('stdout', '未知错误'))
                print(f"[{channel_id}] [ERROR] 服务端检测引擎初始化失败: {error_msg}")
                return None
            
            print(f"[{channel_id}] [OK] 服务端检测引擎初始化成功")
            
            # 返回一个标识对象，表示服务端引擎已准备就绪
            class ServerDetectionEngine:
                def __init__(self, channel_id, model_path):
                    self.channel_id = channel_id
                    self.model_path = model_path
                    self.is_server_engine = True
                    
            engine = ServerDetectionEngine(channel_id, model_path)
            
            # 配置标注数据
            if annotation_config:
                success = DetectionThread._configure_annotation_data(engine, annotation_config)
                if not success:
                    return None
            else:
                return None
            
            return engine
            
        except Exception as e:
            print(f"[{channel_id}] [ERROR] 初始化检测引擎失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def _load_model_config(channel_id: str):
        """从服务端加载模型配置 - 使用远程配置管理器
        
        Args:
            channel_id: 通道ID（如 'channel1'）
            
        Returns:
            模型配置字典，失败返回None
        """
        try:
            # 使用远程配置管理器
            try:
                from .....utils.config import RemoteConfigManager
            except ImportError:
                from utils.config import RemoteConfigManager
            
            remote_config_manager = RemoteConfigManager()
            config = remote_config_manager.load_default_config()
            
            if not config:
                print(f"[{channel_id}] 无法从服务端加载配置")
                return None
            
            # 从 Model Configuration 节读取模型路径
            # 格式：channel1_model_path, channel2_model_path, ...
            model_path_key = f"{channel_id}_model_path"
            model_path = config.get(model_path_key)
            
            if not model_path:
                print(f"[{channel_id}] 服务端配置中没有找到 {model_path_key} 配置")
                return None
            
            # 获取项目根目录（用于解析相对路径）
            try:
                from .....database.config import get_project_root
            except ImportError:
                from database.config import get_project_root
            
            project_root = get_project_root()
            
            # 转换为绝对路径（基于项目根目录）
            if not os.path.isabs(model_path):
                # 先规范化路径分隔符（将 / 替换为系统路径分隔符）
                model_path = model_path.replace('/', os.sep).replace('\\', os.sep)
                model_path = os.path.join(project_root, model_path)
            
            # 规范化路径（解决混用斜杠的问题）
            model_path = os.path.normpath(model_path)
            
            # 注意：不检查本地模型文件是否存在，因为模型在服务端
            print(f"[{channel_id}] 模型路径（服务端）: {model_path}")
            
            # 构造模型配置字典（从全局model配置和通道特定配置合并）
            model_config = config.get('model', {}).copy()  # 获取全局模型配置
            model_config['model_path'] = model_path  # 设置通道特定的模型路径
            
            # 从全局GPU配置中读取device设置
            if 'device' not in model_config:
                if config.get('gpu_enabled', False):
                    model_config['device'] = config.get('default_device', 'cuda')
                else:
                    model_config['device'] = 'cpu'
            
            # 从全局批处理配置中读取batch_size
            if 'batch_size' not in model_config or model_config['batch_size'] == 1:
                if config.get('batch_processing_enabled', False):
                    model_config['batch_size'] = config.get('default_batch_size', 4)
            
            print(f"[{channel_id}] 从服务端加载模型配置:")
            print(f"  - 模型路径: {model_path}")
            print(f"  - 设备: {model_config.get('device', 'cuda')}")
            print(f"  - 批处理大小: {model_config.get('batch_size', 1)}")
            
            return model_config
            
        except Exception as e:
            print(f"[{channel_id}] 加载模型配置失败: {e}")
            import traceback
            traceback.print_exc()
            return None
                
        except Exception as e:
            print(f"[{channel_id}] 加载模型配置失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def _load_annotation_config(channel_id: str):
        """从 annotation_result.yaml 加载标注数据，并从 channel_config.yaml 加载区域高度
        
        Args:
            channel_id: 通道ID（如 'channel1'）
            
        Returns:
            标注配置字典（包含actual_heights），失败返回None
        """
        try:
            # 获取项目根目录（从当前文件向上4级）
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
            
            # 读取标注数据
            annotation_file = os.path.join(project_root, 'database', 'config', 'annotation_result.yaml')
            
            if not os.path.exists(annotation_file):
                print(f"[{channel_id}] annotation_result.yaml 不存在: {annotation_file}")
                return None
            
            with open(annotation_file, 'r', encoding='utf-8') as f:
                annotation_config = yaml.safe_load(f)
            
            if not annotation_config or channel_id not in annotation_config:
                print(f"[{channel_id}] annotation_result.yaml 中没有找到 {channel_id} 的配置")
                return None
            
            annotation_data = annotation_config[channel_id]
            
            # 读取区域高度数据
            channel_config_file = os.path.join(project_root, 'database', 'config', 'channel_config.yaml')
            
            actual_heights = []
            if os.path.exists(channel_config_file):
                with open(channel_config_file, 'r', encoding='utf-8') as f:
                    channel_config = yaml.safe_load(f)
                
                if channel_config and channel_id in channel_config:
                    area_heights = channel_config[channel_id].get('general', {}).get('area_heights', {})
                    num_boxes = len(annotation_data.get('boxes', []))
                    
                    # 提取区域高度
                    print(f"\n [{channel_id}] 加载区域高度配置:")
                    for i in range(num_boxes):
                        area_key = f'area_{i+1}'
                        height_str = area_heights.get(area_key, '20mm')  #  默认20mm
                        print(f"   - {area_key}: 原始字符串='{height_str}'")
                        
                        # 解析高度字符串，提取数字和单位
                        import re
                        height_match = re.search(r'([\d.]+)\s*(mm|cm)?', str(height_str))
                        if height_match:
                            height_value = float(height_match.group(1))
                            unit = height_match.group(2) if height_match.group(2) else 'mm'
                            
                            # 统一转换为毫米
                            if unit == 'cm':
                                height_mm = height_value * 10.0  # cm转mm
                                print(f"     单位转换: {height_value}cm -> {height_mm}mm")
                            else:
                                height_mm = height_value
                                print(f"      使用mm单位: {height_mm}mm")
                            
                            actual_heights.append(height_mm)
                        else:
                            actual_heights.append(20.0)  # 默认20mm
                            print(f"     解析失败，使用默认值: 20mm")
            
            # 如果没有读取到高度数据，使用默认值
            if not actual_heights:
                num_boxes = len(annotation_data.get('boxes', []))
                actual_heights = [20.0] * num_boxes  # 默认20mm
                print(f"[{channel_id}] 未读取到配置，使用默认容器高度: 20mm")
            
            # 添加actual_heights到配置中
            annotation_data['actual_heights'] = actual_heights
            
            return annotation_data
                
        except Exception as e:
            print(f"[{channel_id}] [ERROR] 加载标注配置失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def _configure_annotation_data(engine, annotation_config):
        """配置标注数据到检测引擎
        
        Args:
            engine: LiquidDetectionEngine 实例
            annotation_config: 标注配置字典
        
        Returns:
            bool: 配置是否成功
        """
        try:
            # 提取标注数据
            boxes = annotation_config.get('boxes', [])
            fixed_bottoms = annotation_config.get('fixed_bottoms', [])
            fixed_tops = annotation_config.get('fixed_tops', [])
            actual_heights = annotation_config.get('actual_heights', [])
            
            # 从标注结果读取初始状态（detect_initstatus）
            # areas配置中包含init_status字段：0=默认, 1=满, 2=空
            annotation_initstatus = []
            areas = annotation_config.get('areas', {})
            print(f"[DEBUG] 读取areas配置: {areas}")
            for i in range(len(boxes)):
                area_key = f'area_{i+1}'
                area_info = areas.get(area_key, {})
                init_status = area_info.get('init_status', 0)
                annotation_initstatus.append(init_status)
                print(f"[DEBUG] {area_key}: init_status={init_status}")
            
            print(f"[DEBUG] annotation_initstatus列表: {annotation_initstatus}")
            
            # 如果没有实际高度数据，使用默认值
            if not actual_heights:
                # 使用默认容器高度20mm
                actual_heights = [20.0] * len(boxes)
                print(f"未配置实际高度，使用默认值: 20mm")
            
            # 调用引擎的configure方法（传递annotation_initstatus）
            engine.configure(boxes, fixed_bottoms, fixed_tops, actual_heights, annotation_initstatus)
            
            return True
            
        except Exception as e:
            print(f" 配置标注数据失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
