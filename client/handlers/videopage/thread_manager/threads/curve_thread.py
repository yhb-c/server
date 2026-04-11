# -*- coding: utf-8 -*-

"""
曲线绘制线程（全局单例版本 - 支持同步模式从内存读取）

职责：
1. 启动时一次性加载本地CSV文件的历史数据
2. 同步模式下：从存储线程的内存缓冲区读取实时数据（无需等待CSV写入）
3. 历史模式下：监控CSV文件变化，增量读取新数据
4. 触发曲线更新回调（支持多通道分发）

数据流（同步模式）：
检测线程 → 存储线程内存缓冲区 → 曲线线程 → UI绘制
                    ↓
              CSV文件（异步写入）

优势：
- 同步模式下实时性更好（直接从内存读取，无需等待磁盘I/O）
- 历史数据从CSV加载，保证数据完整性
- 全局单例，减少线程数量

架构关系：
- curve_thread.py：负责读取数据并触发回调（全局单例）
- storage_thread.py：提供内存缓冲区数据访问接口
- curvepanel_handler.py：接收回调，处理业务逻辑和数据管理
- curvepanel.py（Widget）：只负责UI显示，接收handler调用
"""

import os
import time
import yaml
import csv
from datetime import datetime
from typing import Callable, Optional, Dict, List

# 导入统一的路径管理函数
try:
    from .....config import get_project_root
except ImportError:
    from client.config import get_project_root


class CurveThread:
    """曲线绘制线程类（全局单例版本 - 支持同步模式从内存读取）
    
    同步模式：从存储线程内存缓冲区读取实时数据
    历史模式：从CSV文件读取历史数据
    """
    
    # 全局单例线程运行标志
    _global_running_flag = False
    
    # 全局统一的回调函数
    _global_callback: Optional[Callable] = None
    
    # 进度回调函数（用于显示进度条）
    _progress_callback: Optional[Callable] = None
    
    # 同步模式标志（True=从内存读取实时数据，False=仅从CSV读取）
    _sync_mode = False
    
    # 已发送数据的索引（用于增量发送内存数据）
    # {area_name: last_sent_index}
    _memory_data_indices: Dict[str, int] = {}
    
    @staticmethod
    def run(current_mission_path: str = None, callback: Optional[Callable] = None):
        """曲线绘制线程主循环（全局单例版本）
        
        数据流：
        1. 启动时：加载本地CSV文件的历史数据
        2. 同步模式：从存储线程内存缓冲区读取实时数据
        3. 历史模式：监控CSV文件变化，增量读取
        
        Args:
            current_mission_path: 当前任务路径
            callback: 回调函数 callback(csv_filepath, area_name, area_idx, curve_points)
        """
        # 设置全局运行标志
        CurveThread._global_running_flag = True
        CurveThread._memory_data_indices = {}  # 重置内存数据索引
        
        # 设置统一的回调函数
        if callback:
            CurveThread._global_callback = callback
        
        curve_path = current_mission_path
        
        # 从配置文件读取曲线帧率
        curve_frame_rate = CurveThread._get_curve_frame_rate()
        check_interval = 1.0 / curve_frame_rate
        
        # 如果curve_path为None或为"0000"，曲线线程优雅退出
        if not curve_path or curve_path == "0000":
            CurveThread._global_running_flag = False
            return
        
        # ==================== 阶段1：加载本地CSV历史数据 ====================
        available_csv_files = CurveThread._list_csv_files(curve_path)
        file_states = {}
        area_index_map = {}
        next_area_idx = 0
        
        def _ensure_file_state(csv_filepath: str):
            """确保为指定CSV文件创建读取状态"""
            nonlocal next_area_idx
            if csv_filepath in file_states:
                return
            
            area_name = os.path.splitext(os.path.basename(csv_filepath))[0]
            
            if csv_filepath in area_index_map:
                area_idx = area_index_map[csv_filepath]
            else:
                area_idx = next_area_idx
                area_index_map[csv_filepath] = area_idx
                next_area_idx += 1
            
            initial_size = 0
            cached_data = []
            
            try:
                if os.path.exists(csv_filepath):
                    initial_size = os.path.getsize(csv_filepath)
                    cached_data = CurveThread._load_csv_to_memory(csv_filepath)
            except Exception:
                pass
            
            file_states[csv_filepath] = {
                'area_idx': area_idx,
                'area_name': area_name,
                'last_size': initial_size,
                'cached_data': cached_data,
            }
            
            # 初始化内存数据索引
            CurveThread._memory_data_indices[area_name] = 0
        
        # 初次建立文件状态
        for csv_filepath in available_csv_files:
            _ensure_file_state(csv_filepath)
        
        # 发送所有文件的历史数据
        total_files = len(available_csv_files)
        
        for idx, csv_filepath in enumerate(available_csv_files):
            state = file_states.get(csv_filepath)
            if state and state['cached_data']:
                if CurveThread._progress_callback:
                    try:
                        progress_value = int((idx + 1) / total_files * 100)
                        progress_text = f"正在加载曲线数据... ({idx + 1}/{total_files})"
                        CurveThread._progress_callback(progress_value, progress_text)
                    except Exception:
                        pass
                
                if CurveThread._global_callback:
                    try:
                        CurveThread._global_callback(
                            csv_filepath,
                            state['area_name'],
                            state['area_idx'],
                            state['cached_data']
                        )
                    except Exception:
                        import traceback
                        traceback.print_exc()
        
        if CurveThread._progress_callback:
            try:
                CurveThread._progress_callback(100, "加载完成")
            except Exception:
                pass
        
        # ==================== 阶段2：主循环 - 实时数据读取 ====================
        scan_counter = 0
        scan_interval = 10
        
        while CurveThread._global_running_flag:
            try:
                # 同步模式：从存储线程内存缓冲区读取实时数据
                if CurveThread._sync_mode:
                    CurveThread._read_from_memory_buffer(file_states)
                
                # 定期重新扫描文件夹，发现新的CSV文件
                scan_counter += 1
                if scan_counter >= scan_interval:
                    scan_counter = 0
                    current_csv_files = CurveThread._list_csv_files(curve_path)
                    
                    new_files = set(current_csv_files) - set(available_csv_files)
                    if new_files:
                        for new_file in new_files:
                            _ensure_file_state(new_file)
                            state = file_states.get(new_file)
                            if state and state['cached_data']:
                                if CurveThread._global_callback:
                                    try:
                                        CurveThread._global_callback(
                                            new_file,
                                            state['area_name'],
                                            state['area_idx'],
                                            state['cached_data']
                                        )
                                    except Exception:
                                        pass
                        available_csv_files = current_csv_files
                
                # 非同步模式：从CSV文件增量读取（历史回放模式）
                if not CurveThread._sync_mode:
                    for csv_filepath in available_csv_files:
                        state = file_states.get(csv_filepath)
                        if not state:
                            continue
                        
                        try:
                            current_size = os.path.getsize(csv_filepath)
                        except Exception:
                            continue
                        
                        last_size = state['last_size']
                        
                        if current_size > last_size:
                            new_data = CurveThread._read_csv_incremental(
                                csv_filepath, last_size, current_size
                            )
                            
                            if new_data:
                                new_points = []
                                for line in new_data:
                                    line = line.strip()
                                    if not line:
                                        continue
                                    
                                    parts = line.split()
                                    if len(parts) >= 2:
                                        try:
                                            timestamp = datetime.strptime(
                                                parts[0], "%Y-%m-%d-%H:%M:%S.%f"
                                            ).timestamp()
                                            height_mm = float(parts[1])
                                            
                                            point = {
                                                'timestamp': timestamp,
                                                'height_mm': height_mm,
                                                'area_idx': state['area_idx'],
                                                'area_name': state['area_name'],
                                            }
                                            new_points.append(point)
                                            state['cached_data'].append(point)
                                        except ValueError:
                                            pass
                                
                                state['last_size'] = current_size
                                
                                if new_points and CurveThread._global_callback:
                                    try:
                                        CurveThread._global_callback(
                                            csv_filepath,
                                            state['area_name'],
                                            state['area_idx'],
                                            new_points
                                        )
                                    except Exception:
                                        pass
                        
                        elif current_size < last_size:
                            state['cached_data'] = CurveThread._load_csv_to_memory(csv_filepath)
                            state['last_size'] = current_size
                
                time.sleep(check_interval)
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                time.sleep(1.0)
        
        CurveThread._global_running_flag = False
    
    @staticmethod
    def _read_from_memory_buffer(file_states: dict):
        """从存储线程的内存缓冲区读取实时数据
        
        Args:
            file_states: 文件状态字典，用于获取area_name和area_idx的映射
        """
        try:
            from .storage_thread import StorageThread
            
            # 遍历存储线程的内存缓冲区
            for channel_id, channel_buffers in StorageThread._memory_buffers.items():
                area_names_map = StorageThread._area_names.get(channel_id, {})
                
                for area_idx, buffer in channel_buffers.items():
                    area_name = area_names_map.get(area_idx, f'区域{area_idx}')
                    
                    # 获取上次发送的索引
                    last_index = CurveThread._memory_data_indices.get(area_name, 0)
                    current_length = len(buffer)
                    
                    # 关键修复：检测缓冲区是否被重置（写入磁盘后清空）
                    # 如果当前缓冲区长度小于上次索引，说明缓冲区被清空了，需要重置索引
                    if current_length < last_index:
                        last_index = 0
                        CurveThread._memory_data_indices[area_name] = 0
                    
                    # 如果有新数据
                    if current_length > last_index:
                        # 获取新增的数据
                        new_data = buffer[last_index:current_length]
                        
                        # 转换为曲线数据点格式
                        new_points = []
                        for time_str, height_mm in new_data:
                            try:
                                timestamp = datetime.strptime(
                                    time_str, "%Y-%m-%d-%H:%M:%S.%f"
                                ).timestamp()
                                
                                point = {
                                    'timestamp': timestamp,
                                    'height_mm': height_mm,
                                    'area_idx': area_idx,
                                    'area_name': area_name,
                                }
                                new_points.append(point)
                            except ValueError:
                                pass
                        
                        # 更新索引
                        CurveThread._memory_data_indices[area_name] = current_length
                        
                        # 触发回调
                        if new_points and CurveThread._global_callback:
                            try:
                                # 构造虚拟的csv_filepath（用于兼容回调接口）
                                csv_filepath = f"memory://{channel_id}/{area_name}"
                                
                                CurveThread._global_callback(
                                    csv_filepath,
                                    area_name,
                                    area_idx,
                                    new_points
                                )
                            except Exception:
                                import traceback
                                traceback.print_exc()
        
        except ImportError:
            pass
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    @staticmethod
    def _load_csv_to_memory(csv_filepath: str) -> List[dict]:
        """启动时一次性加载CSV文件到内存
        
        Args:
            csv_filepath: CSV文件路径
            
        Returns:
            list: 数据点列表 [{'timestamp': float, 'height_mm': float, ...}, ...]
        """
        data_points = []
        
        try:
            with open(csv_filepath, 'r', encoding='utf-8') as f:
                line_count = 0
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    parts = line.split()
                    if len(parts) >= 2:
                        timestamp_str = parts[0]
                        height_str = parts[1]
                        
                        try:
                            timestamp = datetime.strptime(
                                timestamp_str, "%Y-%m-%d-%H:%M:%S.%f"
                            ).timestamp()
                            
                            height_mm = float(height_str)
                            
                            point = {
                                'timestamp': timestamp,
                                'height_mm': height_mm
                            }
                            
                            data_points.append(point)
                            line_count += 1
                            
                        except ValueError as ve:
                            pass
            
            return data_points
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return []
    
    @staticmethod
    def _read_csv_incremental(csv_filepath: str, start_pos: int, end_pos: int) -> List[str]:
        """读取CSV文件的增量部分（基于字节位置）
        
        Args:
            csv_filepath: CSV文件路径
            start_pos: 起始字节位置
            end_pos: 结束字节位置
            
        Returns:
            list: 新增的行列表
        """
        new_lines = []
        
        try:
            with open(csv_filepath, 'r', encoding='utf-8') as f:
                # 移动到起始位置
                f.seek(start_pos)
                
                # 如果不在行首，跳过当前行（可能是部分行）
                if start_pos > 0:
                    # 向前查找最近的换行符
                    f.seek(max(0, start_pos - 1))
                    if f.read(1) != '\n':
                        # 不在行首，读取并丢弃当前行
                        f.readline()
                
                # 读取新增部分
                while f.tell() < end_pos:
                    line = f.readline()
                    if not line:
                        break
                    new_lines.append(line)
            
            return new_lines
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return []
    
    @staticmethod
    def _list_csv_files(directory: str):
        """列出目标目录下的全部CSV文件（启动时只调用一次）
        
        Args:
            directory: 目录路径
            
        Returns:
            list: CSV文件路径列表
        """
        if not directory or not os.path.isdir(directory):
            return []
        
        try:
            files = []
            for name in os.listdir(directory):
                if name.lower().endswith('.csv'):
                    files.append(os.path.join(directory, name))
            return files
        except Exception as e:
            import traceback
            traceback.print_exc()
            return []
    
    @staticmethod
    def _load_channel_config(channel_id: str):
        """加载通道配置（使用统一的路径管理）"""
        try:
            # 使用统一的项目根目录获取配置文件路径
            project_root = get_project_root()
            config_file = os.path.join(project_root, 'database', 'config', 'default_config.yaml')
            
            if not os.path.exists(config_file):
                return None
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if config and channel_id in config:
                return config[channel_id]
            
            return None
        except Exception as e:
            return None
    
    @staticmethod
    def _get_channel_name(channel_id: str, channel_config: dict):
        """获取通道名称"""
        if channel_config:
            task_name = channel_config.get('general', {}).get('task_name', '')
            if task_name:
                return task_name
        
        # 从 default_config.yaml 读取（使用统一的路径管理）
        try:
            project_root = get_project_root()
            default_config_file = os.path.join(project_root, 'database', 'config', 'default_config.yaml')
            
            if os.path.exists(default_config_file):
                with open(default_config_file, 'r', encoding='utf-8') as f:
                    default_config = yaml.safe_load(f)
                
                if default_config and channel_id in default_config:
                    name = default_config[channel_id].get('name', '')
                    if name:
                        return name
        except:
            pass
        
        return channel_id.replace('channel', '通道')
    
    @staticmethod
    def _get_curve_frame_rate():
        """
        从配置文件读取曲线帧率
        
        Returns:
            int: 曲线帧率（Hz），默认为2
        """
        try:
            # 基于项目根目录动态获取配置文件路径（使用统一的路径管理）
            project_root = get_project_root()
            default_config_file = os.path.join(project_root, 'database', 'config', 'default_config.yaml')
            
            if os.path.exists(default_config_file):
                with open(default_config_file, 'r', encoding='utf-8') as f:
                    default_config = yaml.safe_load(f)
                
                if default_config:
                    curve_frame_rate = default_config.get('curve_frame_rate', 2)
                    # 限制帧率在合理范围内（1-25 Hz）
                    curve_frame_rate = max(1, min(25, curve_frame_rate))
                    return curve_frame_rate
        except Exception as e:
            import traceback
            traceback.print_exc()
        
        # 默认返回2 Hz
        return 2
    
    @staticmethod
    def stop():
        """停止全局曲线线程"""
        CurveThread._global_running_flag = False
    
    @staticmethod
    def is_running():
        """检查全局曲线线程是否运行"""
        return CurveThread._global_running_flag
    
    @staticmethod
    def set_callback(callback: Optional[Callable]):
        """设置统一的回调函数
        
        Args:
            callback: 回调函数 callback(csv_filepath, area_name, area_idx, curve_points)
                     曲线线程读取到新数据后，直接调用此函数
                     参数说明：
                     - csv_filepath: CSV文件的完整路径
                     - area_name: CSV文件名（不含扩展名），如 "侧门液位检测_区域1"
                     - area_idx: 区域索引（0, 1, 2...）
                     - curve_points: 数据点列表
                     回调函数内部根据csv_filepath或area_name来处理不同通道的数据
        """
        CurveThread._global_callback = callback
    
    @staticmethod
    def clear_callback():
        """清除回调函数"""
        CurveThread._global_callback = None
    
    @staticmethod
    def set_progress_callback(callback: Optional[Callable]):
        """设置进度回调函数
        
        Args:
            callback: 进度回调函数 callback(value, text)
                     - value: 进度值 (0-100)
                     - text: 进度文本描述
        """
        CurveThread._progress_callback = callback
    
    @staticmethod
    def clear_progress_callback():
        """清除进度回调函数"""
        CurveThread._progress_callback = None
    
    @staticmethod
    def set_sync_mode(enabled: bool):
        """设置同步模式
        
        Args:
            enabled: True=从内存读取实时数据，False=仅从CSV读取
        """
        CurveThread._sync_mode = enabled
        
        print(f"[曲线线程] 同步模式: {'开启' if enabled else '关闭'}")
    
    @staticmethod
    def is_sync_mode() -> bool:
        """检查是否为同步模式"""
        return CurveThread._sync_mode
    
    @staticmethod
    def reset_memory_indices():
        """重置内存数据索引（切换任务时调用）"""
        CurveThread._memory_data_indices.clear()
