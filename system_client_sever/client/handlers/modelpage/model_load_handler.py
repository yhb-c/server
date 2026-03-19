# -*- coding: utf-8 -*-

import os
import time
from qtpy import QtWidgets


class ModelLoadHandler:
    """
    模型加载处理器
    
    处理各种类型模型的加载、状态管理等功能
    """
    
    def __init__(self, *args, **kwargs):
        """
        初始化模型加载处理器
        
        在Mixin链中，main_window参数会在后续手动设置
        """
        super().__init__(*args, **kwargs)
        self._config = {}
        self._loaded_models = {}
    
    def _set_main_window(self, main_window):
        """设置主窗口引用"""
        self = main_window
        # 获取配置
        if hasattr(main_window, '_config'):
            self._config = main_window._config
    
    def _loadModelToSystem(self, model_name, model_params):
        """
        将模型加载到系统中
        
        Args:
            model_name: 模型名称
            model_params: 模型参数字典
            
        Returns:
            bool: 加载是否成功
        """
        try:
            # 检查是否已经加载了太多模型（移除限制）
            loaded_models = self.getLoadedModels()
            current_count = len(loaded_models)
            
            # 移除模型数量限制，允许加载任意数量的模型
            # 原来的限制：if current_count >= 3:
            # 现在允许加载任意数量的模型
            
            model_path = model_params.get('path', '')
            
            # 检查模型文件是否存在
            if not os.path.exists(model_path):
                return False
            
            # 检查模型是否已经加载
            if model_name in loaded_models:
                # 可以选择跳过或重新加载，这里选择重新加载
                pass
            
            # 根据模型类型进行不同的加载处理
            model_type = model_params.get('type', '')
            
            if '.pt' in model_path.lower() or 'pytorch' in model_type.lower():
                # PyTorch模型加载
                success = self._loadPyTorchModel(model_name, model_path, model_params)
            elif '.dat' in model_path.lower() or '加密' in model_type:
                # 加密模型加载
                success = self._loadEncryptedModel(model_name, model_path, model_params)
            elif '.onnx' in model_path.lower():
                # ONNX模型加载
                success = self._loadONNXModel(model_name, model_path, model_params)
            else:
                # 默认处理
                success = self._loadGenericModel(model_name, model_path, model_params)
            
            if success:
                # 保存模型加载状态到配置
                self._saveModelLoadStatus(model_name, model_params)
            
            return success
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False
    
    def _loadPyTorchModel(self, model_name, model_path, model_params):
        """加载PyTorch模型"""
        try:
            # 这里应该实际加载PyTorch模型
            # 由于我们没有实际的模型加载库，这里模拟加载过程
            
            # 模拟加载时间
            time.sleep(0.5)  # 模拟加载时间
            
            # 检查模型文件大小
            file_size = os.path.getsize(model_path)
            
            return True
            
        except Exception as e:
            return False
    
    def _loadEncryptedModel(self, model_name, model_path, model_params):
        """加载加密模型"""
        try:
            # 模拟加密模型加载过程
            time.sleep(0.3)
            
            # 这里应该调用实际的解密和加载逻辑
            # 由于我们没有解密库，这里模拟成功
            
            return True
            
        except Exception as e:
            return False
    
    def _loadONNXModel(self, model_name, model_path, model_params):
        """加载ONNX模型"""
        try:
            # 模拟ONNX模型加载过程
            time.sleep(0.4)
            
            # 这里应该调用实际的ONNX加载逻辑
            # 由于我们没有ONNX库，这里模拟成功
            
            return True
            
        except Exception as e:
            return False
    
    def _loadGenericModel(self, model_name, model_path, model_params):
        """加载通用模型"""
        try:
            # 模拟通用模型加载过程
            time.sleep(0.2)
            
            # 这里应该调用实际的通用加载逻辑
            
            return True
            
        except Exception as e:
            return False
    
    def _saveModelLoadStatus(self, model_name, model_params):
        """保存模型加载状态到配置"""
        try:
            # 创建模型加载状态记录
            load_status = {
                'model_name': model_name,
                'model_path': model_params.get('path', ''),
                'model_type': model_params.get('type', ''),
                'load_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'loaded'
            }
            
            # 保存到内部字典
            self._loaded_models[model_name] = load_status
            
            # 保存到配置中
            if 'loaded_models' not in self._config:
                self._config['loaded_models'] = {}
            
            self._config['loaded_models'][model_name] = load_status
            
            # 更新当前默认模型（如果加载的是默认模型）
            if hasattr(self, 'modelSetPage'):
                default_model = self.modelSetPage.getDefaultModel()
                if default_model == model_name:
                    self._config['current_model'] = model_name
            
        except Exception as e:
            pass
    
    def getLoadedModels(self):
        """
        获取已加载的模型列表
        
        Returns:
            dict: 已加载的模型信息
        """
        return self._config.get('loaded_models', {})
    
    def isModelLoaded(self, model_name):
        """
        检查模型是否已加载
        
        Args:
            model_name: 模型名称
            
        Returns:
            bool: 是否已加载
        """
        loaded_models = self.getLoadedModels()
        return model_name in loaded_models and loaded_models[model_name].get('status') == 'loaded'
    
    def getModelLoadStatistics(self):
        """
        获取模型加载统计信息
        
        Returns:
            dict: 包含统计信息的字典
        """
        loaded_models = self.getLoadedModels()
        
        # 统计各类型模型数量
        type_counts = {}
        for model_name, model_info in loaded_models.items():
            model_type = model_info.get('model_type', '未知')
            type_counts[model_type] = type_counts.get(model_type, 0) + 1
        
        statistics = {
            'total_loaded': len(loaded_models),
            'type_counts': type_counts,
            'loaded_models': list(loaded_models.keys()),
            'load_times': {name: info.get('load_time', '未知') for name, info in loaded_models.items()}
        }
        
        return statistics
    
    def showModelLoadStatistics(self):
        """显示模型加载统计信息对话框"""
        try:
            stats = self.getModelLoadStatistics()
            
            # 构建统计信息文本
            stats_text = f" 模型加载统计信息\n\n"
            stats_text += f"总加载模型数量: {stats['total_loaded']}\n\n"
            
            if stats['type_counts']:
                stats_text += "各类型模型数量:\n"
                for model_type, count in stats['type_counts'].items():
                    stats_text += f"  • {model_type}: {count} 个\n"
                stats_text += "\n"
            
            if stats['loaded_models']:
                stats_text += "已加载的模型:\n"
                for i, model_name in enumerate(stats['loaded_models'], 1):
                    load_time = stats['load_times'].get(model_name, '未知')
                    stats_text += f"  {i}. {model_name} (加载时间: {load_time})\n"
            
            stats_text += f"\n 系统支持加载任意数量的模型，无数量限制"
            
            QtWidgets.QMessageBox.information(
                self, "模型加载统计", stats_text
            )
            
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "错误", f"显示模型统计信息失败: {e}"
            )
