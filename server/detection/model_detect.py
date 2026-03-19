# -*- coding: utf-8 -*-
"""
模型检测函数模块

负责：
    1. 模型加载和验证
    2. 设备管理
    3. .dat 文件解码
"""

import os
import struct
import hashlib
from pathlib import Path

# 导入动态路径获取函数
from database.config import get_temp_models_dir

# 全局调试日志开关
DEBUG_LOG_ENABLED = True


def validate_device(device):
    """
    验证并选择可用的设备
    
    Args:
        device: 计算设备 ('cuda', 'cpu', '0', '1' 等)
    
    Returns:
        str: 可用的设备名称
    """
    try:
        import torch
        
        if device in ['cuda', '0'] or device.startswith('cuda:'):
            if torch.cuda.is_available():
                return 'cuda' if device in ['cuda', '0'] else device
            else:
                return 'cpu'
        return device
    except Exception:
        return 'cpu'


def validate_model_file(model_path):
    """
    验证模型文件的完整性
    
    Args:
        model_path: 模型文件路径
        
    Returns:
        bool: 文件是否有效
    """
    try:
        # 检查文件大小（模型文件不应该太小）
        file_size = os.path.getsize(model_path)
        if file_size < 1024:  # 小于1KB的文件可能无效
            if DEBUG_LOG_ENABLED:
                print(f"⚠️ [检测引擎] 模型文件过小: {file_size} bytes")
            return False
        
        # 检查文件扩展名（支持 .pt, .pth, .engine）
        valid_extensions = ('.pt', '.pth', '.engine')
        if not model_path.endswith(valid_extensions):
            if DEBUG_LOG_ENABLED:
                print(f"⚠️ [检测引擎] 不支持的模型格式: {model_path}")
            return False
        
        # 尝试读取文件头部
        try:
            with open(model_path, 'rb') as f:
                header = f.read(8)
                if len(header) < 8:
                    if DEBUG_LOG_ENABLED:
                        print(f"⚠️ [检测引擎] 模型文件头部不完整")
                    return False
        except Exception as e:
            if DEBUG_LOG_ENABLED:
                print(f"⚠️ [检测引擎] 无法读取模型文件: {e}")
            return False
        
        return True
        
    except Exception as e:
        if DEBUG_LOG_ENABLED:
            print(f"❌ [检测引擎] 模型文件验证异常: {e}")
        return False


def decode_dat_model(dat_path):
    """
    解码 .dat 格式的模型文件
    
    .dat 文件格式：
    - SIGNATURE (14 bytes): b'LDS_MODEL_FILE'
    - VERSION (4 bytes): uint32, 当前为 1
    - FILENAME_LEN (4 bytes): uint32
    - FILENAME (FILENAME_LEN bytes): utf-8 编码的原始文件名
    - DATA_LEN (8 bytes): uint64
    - ENCRYPTED_DATA (DATA_LEN bytes): 加密的模型数据
    
    Args:
        dat_path: .dat 文件路径
    
    Returns:
        str: 解码后的 .pt 文件路径，失败返回 None
    """
    try:
        SIGNATURE = b'LDS_MODEL_FILE'
        VERSION = 1
        ENCRYPTION_KEY = "liquid_detection_system_2024"
        
        key_hash = hashlib.sha256(ENCRYPTION_KEY.encode('utf-8')).digest()
        
        with open(dat_path, 'rb') as f:
            signature = f.read(len(SIGNATURE))
            if signature != SIGNATURE:
                return None
            
            version = struct.unpack('<I', f.read(4))[0]
            if version != VERSION:
                return None
            
            filename_len = struct.unpack('<I', f.read(4))[0]
            original_filename = f.read(filename_len).decode('utf-8')
            
            data_len = struct.unpack('<Q', f.read(8))[0]
            encrypted_data = f.read(data_len)
        
        # XOR 解密
        decrypted_data = bytearray()
        key_len = len(key_hash)
        for i, byte in enumerate(encrypted_data):
            decrypted_data.append(byte ^ key_hash[i % key_len])
        decrypted_data = bytes(decrypted_data)
        
        # 保存到临时目录
        temp_dir = Path(get_temp_models_dir())
        temp_dir.mkdir(exist_ok=True)
        
        path_hash = hashlib.md5(str(dat_path).encode()).hexdigest()[:8]
        temp_model_path = temp_dir / f"temp_{Path(dat_path).stem}_{path_hash}.pt"
        
        with open(temp_model_path, 'wb') as f:
            f.write(decrypted_data)
        
        return str(temp_model_path)
        
    except Exception as e:
        return None


def _print_gpu_memory(stage=""):
    """打印GPU显存使用情况（包括PyTorch和系统级显存）"""
    try:
        import torch
        if torch.cuda.is_available():
            # PyTorch管理的显存
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            total = torch.cuda.get_device_properties(0).total_memory / 1024**3
            
            # 尝试获取nvidia-smi级别的显存使用（包括TensorRT）
            try:
                import subprocess
                result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    used_mb, total_mb = map(int, result.stdout.strip().split(','))
                    print(f"📊 [显存监控] {stage}: PyTorch分配 {allocated:.2f}GB / 系统实际使用 {used_mb/1024:.2f}GB / 总计 {total:.2f}GB")
                    return
            except:
                pass
            
            print(f"📊 [显存监控] {stage}: PyTorch分配 {allocated:.2f}GB / 预留 {reserved:.2f}GB / 总计 {total:.2f}GB")
    except Exception as e:
        print(f"⚠️ [显存监控] 无法获取显存信息: {e}")


def load_model(model_path, device='cuda'):
    """
    加载YOLO模型
    
    Args:
        model_path: 模型文件路径（支持 .pt 和 .dat 格式）
        device: 计算设备
    
    Returns:
        tuple: (model, actual_model_path) 或 (None, None) 如果失败
    """
    try:
        if not os.path.exists(model_path):
            if DEBUG_LOG_ENABLED:
                print(f"❌ [检测引擎] 模型文件不存在: {model_path}")
            return None, None
        
        # 如果是 .dat 文件，先解码
        if model_path.endswith('.dat'):
            decoded_path = decode_dat_model(model_path)
            if decoded_path is None:
                if DEBUG_LOG_ENABLED:
                    print(f"❌ [检测引擎] .dat 文件解码失败: {model_path}")
                return None, None
            model_path = decoded_path
        
        # TensorRT .engine 文件直接使用，跳过PyTorch格式验证
        is_tensorrt = model_path.endswith('.engine')
        
        # 验证模型文件完整性（.engine文件只检查基本有效性）
        if not validate_model_file(model_path):
            if DEBUG_LOG_ENABLED:
                print(f"❌ [检测引擎] 模型文件验证失败: {model_path}")
            return None, None
        
        # 设置离线模式
        os.environ['YOLO_VERBOSE'] = 'False'
        os.environ['YOLO_OFFLINE'] = '1'
        os.environ['ULTRALYTICS_OFFLINE'] = 'True'
        
        # 🔥 在加载模型前先检查CUDA可用性，避免CUDA初始化崩溃
        actual_device = device
        try:
            import torch
            if device.startswith('cuda') or device == '0':
                if not torch.cuda.is_available():
                    print(f"⚠️ [检测引擎] CUDA不可用，回退到CPU")
                    actual_device = 'cpu'
                else:
                    # 🔥 预先初始化CUDA，捕获可能的崩溃
                    try:
                        torch.cuda.init()
                        # 测试CUDA是否正常工作
                        _ = torch.zeros(1).cuda()
                        print(f"✅ [检测引擎] CUDA初始化成功")
                    except Exception as cuda_err:
                        print(f"⚠️ [检测引擎] CUDA初始化失败: {cuda_err}，回退到CPU")
                        actual_device = 'cpu'
        except ImportError:
            print(f"⚠️ [检测引擎] PyTorch未安装，使用默认设备")
        except Exception as torch_err:
            print(f"⚠️ [检测引擎] PyTorch检查失败: {torch_err}，回退到CPU")
            actual_device = 'cpu'
        
        # 📊 加载前显存监控
        _print_gpu_memory("模型加载前")
        
        # 延迟导入
        if DEBUG_LOG_ENABLED:
            print(f"🔄 [检测引擎] 正在导入ultralytics...")
        from ultralytics import YOLO
        
        if DEBUG_LOG_ENABLED:
            print(f"🔄 [检测引擎] 正在加载模型: {model_path}")
        
        try:
            # TensorRT模型需要明确指定task类型，否则会被当作detect处理
            if is_tensorrt:
                model = YOLO(model_path, task='segment')
                if DEBUG_LOG_ENABLED:
                    print(f"✅ [检测引擎] TensorRT模型以segment任务加载: {model_path}")
            else:
                model = YOLO(model_path)
                if DEBUG_LOG_ENABLED:
                    print(f"✅ [检测引擎] PyTorch模型加载: {model_path}")
        except Exception as load_err:
            print(f"❌ [检测引擎] YOLO模型加载异常: {load_err}")
            import traceback
            traceback.print_exc()
            _print_gpu_memory("YOLO加载失败后")
            return None, None
        
        # 📊 YOLO加载后显存监控
        _print_gpu_memory("YOLO加载后")
        
        # TensorRT模型已绑定GPU，不需要调用.to()
        if is_tensorrt:
            # 🔥 验证TensorRT模型是否正确加载：执行一次warmup推理
            if DEBUG_LOG_ENABLED:
                print(f"🔄 [检测引擎] TensorRT模型warmup测试...")
            try:
                import numpy as np
                # 创建测试图像 (640x640 RGB)
                test_img = np.zeros((640, 640, 3), dtype=np.uint8)
                warmup_results = model.predict(source=test_img, imgsz=640, verbose=False, save=False)
                
                # 检查结果
                if warmup_results and len(warmup_results) > 0:
                    result = warmup_results[0]
                    has_boxes = result.boxes is not None
                    has_masks = result.masks is not None
                    print(f"✅ [检测引擎] TensorRT warmup成功 (boxes={has_boxes}, masks={has_masks})")
                    
                    # 🔥 打印TensorRT模型详细信息
                    print(f"📋 [检测引擎] TensorRT模型信息:")
                    print(f"   - 模型路径: {model_path}")
                    print(f"   - 模型任务: {getattr(model, 'task', 'unknown')}")
                    print(f"   - 模型类型: TensorRT Engine")
                    
                    # 检查模型内部状态
                    if hasattr(model, 'model'):
                        inner_model = model.model
                        print(f"   - 内部模型类型: {type(inner_model).__name__}")
                        if hasattr(inner_model, 'device'):
                            print(f"   - 设备: {inner_model.device}")
                    
                    _print_gpu_memory("TensorRT warmup后")
                else:
                    print(f"⚠️ [检测引擎] TensorRT warmup返回空结果")
            except Exception as warmup_err:
                print(f"❌ [检测引擎] TensorRT warmup失败: {warmup_err}")
                import traceback
                traceback.print_exc()
                # warmup失败可能意味着engine文件有问题
                return None, None
            
            if DEBUG_LOG_ENABLED:
                print(f"✅ [检测引擎] TensorRT模型加载成功: {model_path}")
            _print_gpu_memory("TensorRT模型加载后")
            return model, model_path
        
        if DEBUG_LOG_ENABLED:
            print(f"🔄 [检测引擎] 正在将模型移至设备: {actual_device}")
        
        try:
            model.to(actual_device)
        except RuntimeError as to_err:
            error_msg = str(to_err).lower()
            if 'out of memory' in error_msg or 'cuda' in error_msg:
                print(f"⚠️ [检测引擎] GPU显存不足，尝试使用CPU: {to_err}")
                _print_gpu_memory("显存不足")
                try:
                    # 清理GPU缓存后重试CPU
                    import torch
                    torch.cuda.empty_cache()
                    model.to('cpu')
                    print(f"✅ [检测引擎] 回退到CPU加载成功")
                    return model, model_path
                except Exception as cpu_err:
                    print(f"❌ [检测引擎] CPU回退也失败: {cpu_err}")
                    return None, None
            else:
                raise to_err
        
        # 📊 移至设备后显存监控
        _print_gpu_memory("模型移至设备后")
        
        if DEBUG_LOG_ENABLED:
            print(f"✅ [检测引擎] 模型加载成功: {model_path}")
        
        return model, model_path
        
    except RuntimeError as e:
        # 🔥 捕获CUDA相关的运行时错误
        error_msg = str(e).lower()
        _print_gpu_memory("RuntimeError发生时")
        if 'cuda' in error_msg or 'gpu' in error_msg or 'out of memory' in error_msg:
            print(f"⚠️ [检测引擎] CUDA错误，尝试使用CPU: {e}")
            try:
                import torch
                torch.cuda.empty_cache()  # 清理GPU缓存
                from ultralytics import YOLO
                model = YOLO(model_path)
                model.to('cpu')
                print(f"✅ [检测引擎] 使用CPU加载模型成功")
                return model, model_path
            except Exception as cpu_err:
                print(f"❌ [检测引擎] CPU加载也失败: {cpu_err}")
                import traceback
                traceback.print_exc()
                return None, None
        else:
            if DEBUG_LOG_ENABLED:
                print(f"❌ [检测引擎] 运行时错误: {e}")
            import traceback
            traceback.print_exc()
            return None, None
    except MemoryError as e:
        # 🔥 捕获内存不足错误
        print(f"❌ [检测引擎] 内存不足: {e}")
        _print_gpu_memory("MemoryError发生时")
        import traceback
        traceback.print_exc()
        return None, None
    except Exception as e:
        if DEBUG_LOG_ENABLED:
            print(f"❌ [检测引擎] 模型加载失败: {e}")
        _print_gpu_memory("Exception发生时")
        import traceback
        traceback.print_exc()
        return None, None


def cleanup_temp_models():
    """清理临时模型文件"""
    try:
        temp_dir = Path(get_temp_models_dir())
        if temp_dir.exists():
            for temp_file in temp_dir.glob("temp_*.pt"):
                try:
                    temp_file.unlink()
                except:
                    pass
    except:
        pass


def parse_targets(boxes):
    """
    解析boxes为targets格式
    
    Args:
        boxes: 检测框列表 [[x1, y1, x2, y2], ...] 或 [[cx, cy, size], ...]
    
    Returns:
        list: targets列表 [(cx, cy, size), ...]
    """
    targets = []
    for box in boxes:
        if len(box) == 3:
            targets.append(tuple(box))
        elif len(box) >= 4:
            x1, y1, x2, y2 = box[:4]
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
            size = max(abs(x2 - x1), abs(y2 - y1))
            targets.append((cx, cy, size))
    return targets
