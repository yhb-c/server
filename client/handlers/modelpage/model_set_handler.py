# -*- coding: utf-8 -*-

import os
import yaml
from pathlib import Path
from qtpy import QtWidgets, QtGui


class ModelSetHandler:
    """
    模型集管理处理器
    
    处理模型集的添加、编辑、删除、加载等功能
    """
    
    def __init__(self, *args, **kwargs):
        """
        初始化模型集管理处理器
        
        在Mixin链中，main_window参数会在后续手动设置
        """
        super().__init__(*args, **kwargs)
        self = None
    
    def _set_main_window(self, main_window):
        """设置主窗口引用"""
        self = main_window
    
    def _onAddModelSet(self):
        """添加模型集 - 显示添加模型对话框"""
        return self._addModelDialog()
    
    def _addModelDialog(self):
        """显示添加模型对话框（实际功能实现）"""
        try:
            # 创建添加模型对话框
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("添加新模型")
            dialog.setModal(True)
            dialog.resize(500, 400)
            
            # 创建布局
            layout = QtWidgets.QVBoxLayout(dialog)
            
            # 模型名称
            name_layout = QtWidgets.QHBoxLayout()
            name_layout.addWidget(QtWidgets.QLabel("模型名称:"))
            name_edit = QtWidgets.QLineEdit()
            name_edit.setPlaceholderText("请输入模型名称")
            name_layout.addWidget(name_edit)
            layout.addLayout(name_layout)
            
            # 模型类型
            type_layout = QtWidgets.QHBoxLayout()
            type_layout.addWidget(QtWidgets.QLabel("模型类型:"))
            type_combo = QtWidgets.QComboBox()

            type_layout.addWidget(type_combo)
            layout.addLayout(type_layout)
            
            # 模型路径
            path_layout = QtWidgets.QHBoxLayout()
            path_layout.addWidget(QtWidgets.QLabel("模型路径:"))
            path_edit = QtWidgets.QLineEdit()
            path_edit.setPlaceholderText("选择模型文件 (.pt, .onnx, .pth, .dat, .engine)")
            browse_btn = QtWidgets.QPushButton("浏览...")
            browse_btn.clicked.connect(lambda: self._browseModelFile(path_edit))
            path_layout.addWidget(path_edit)
            path_layout.addWidget(browse_btn)
            layout.addLayout(path_layout)
            
            # 配置文件路径
            config_layout = QtWidgets.QHBoxLayout()
            config_layout.addWidget(QtWidgets.QLabel("配置文件:"))
            config_edit = QtWidgets.QLineEdit()
            config_edit.setPlaceholderText("选择配置文件 (.yaml, .cfg)")
            config_browse_btn = QtWidgets.QPushButton("浏览...")
            config_browse_btn.clicked.connect(lambda: self._browseConfigFile(config_edit))
            config_layout.addWidget(config_edit)
            config_layout.addWidget(config_browse_btn)
            layout.addLayout(config_layout)
            
            # 模型描述
            desc_layout = QtWidgets.QVBoxLayout()
            desc_layout.addWidget(QtWidgets.QLabel("模型描述:"))
            desc_edit = QtWidgets.QTextEdit()
            desc_edit.setPlaceholderText("请输入模型描述信息")
            desc_edit.setMaximumHeight(80)
            desc_layout.addWidget(desc_edit)
            layout.addLayout(desc_layout)
            
            # 按钮
            button_layout = QtWidgets.QHBoxLayout()
            ok_btn = QtWidgets.QPushButton("确定")
            cancel_btn = QtWidgets.QPushButton("取消")
            button_layout.addWidget(ok_btn)
            button_layout.addWidget(cancel_btn)
            layout.addLayout(button_layout)
            
            # 连接按钮事件
            ok_btn.clicked.connect(dialog.accept)
            cancel_btn.clicked.connect(dialog.reject)
            
            # 显示对话框
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                # 获取输入信息
                model_name = name_edit.text().strip()
                model_type = type_combo.currentText()
                model_path = path_edit.text().strip()
                config_path = config_edit.text().strip()
                description = desc_edit.toPlainText().strip()
                
                # 验证输入
                if not model_name:
                    QtWidgets.QMessageBox.warning(self, "输入错误", "请输入模型名称")
                    return False
                
                if not model_path:
                    QtWidgets.QMessageBox.warning(self, "输入错误", "请选择模型文件")
                    return False
                
                # 检查模型是否已存在
                if hasattr(self, 'modelSetPage'):
                    existing_models = self.modelSetPage.getAllModels()
                    if any(model_name in model for model in existing_models):
                        QtWidgets.QMessageBox.warning(self, "模型已存在", 
                                                     f"模型 '{model_name}' 已存在，请使用不同的名称")
                        return False
                
                # 创建模型参数
                model_params = {
                    'name': model_name,
                    'type': model_type,
                    'path': model_path,
                    'config_path': config_path,
                    'description': description,
                    'size': self._getFileSize(model_path),
                    'classes': 80,  # 默认类别数
                    'input': '640x640',  # 默认输入尺寸
                    'confidence': 0.5,
                    'iou': 0.45,
                    'device': 'CUDA:0 (GPU)',
                    'batch_size': 16,
                    'blur_training': 100,
                    'epochs': 300,
                    'workers': 8
                }
                
                # 添加到模型集页面
                if hasattr(self, 'modelSetPage'):
                    self.modelSetPage._model_params[model_name] = model_params
                    self.modelSetPage.addModelToList(model_name)
                    
                    # 保存新模型到配置文件
                    self._saveNewModelToConfig(model_name, model_params)
                    
                    # 更新测试页面的模型列表
                    if hasattr(self, 'testModelPage'):
                        self.testModelPage.loadModelsFromModelSetPage(self.modelSetPage)
                    
                    QtWidgets.QMessageBox.information(self, "添加成功", 
                                                     f"模型 '{model_name}' 已成功添加")
                    return True
                else:
                    QtWidgets.QMessageBox.warning(self, "错误", "模型集页面未初始化")
                    return False
                    
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"添加模型失败: {e}")
            return False
    
    def _browseModelFile(self, path_edit):
        """浏览模型文件"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "选择模型文件", "",
            "模型文件 (*.pt *.pth *.onnx *.dat *.engine);;TensorRT模型 (*.engine);;所有文件 (*)"
        )
        if file_path:
            path_edit.setText(file_path)
    
    def _browseConfigFile(self, config_edit):
        """浏览配置文件"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "选择配置文件", "",
            "配置文件 (*.yaml *.yml *.cfg *.json);;所有文件 (*)"
        )
        if file_path:
            config_edit.setText(file_path)
    
    def _getFileSize(self, file_path):
        """获取文件大小"""
        try:
            if os.path.exists(file_path):
                size_bytes = os.path.getsize(file_path)
                if size_bytes < 1024:
                    return f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    return f"{size_bytes / 1024:.1f} KB"
                elif size_bytes < 1024 * 1024 * 1024:
                    return f"{size_bytes / (1024 * 1024):.1f} MB"
                else:
                    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
            return "未知"
        except:
            return "未知"
    
    def _saveNewModelToConfig(self, model_name, model_params):
        """保存新模型到配置文件"""
        try:
            # 获取配置文件路径（修复：添加database目录）
            config_path = Path(__file__).parent.parent.parent / "database" / "config" / "default_config.yaml"
            
            # 加载当前配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
            else:
                config = {}
            
            # 查找可用的通道槽位
            available_channel = None
            for i in range(1, 5):
                channel_key = f'channel{i}'
                if channel_key not in config:
                    available_channel = channel_key
                    break
            
            if not available_channel:
                return False
            
            # 创建通道配置
            channel_config = {
                'name': model_name,
                'address': 'rtsp://admin:password@192.168.0.100:8000/stream1',  # 默认地址
                'model_path': model_params.get('path', ''),
                'resolution': '1920x1080',
                'enabled': True,
                'transport': 'TCP',
                'fps': 25
            }
            
            # 添加到配置
            config[available_channel] = channel_config
            
            # 备份原配置文件
            backup_path = config_path.with_suffix('.yaml.backup')
            if config_path.exists():
                import shutil
                shutil.copy2(config_path, backup_path)
            
            # 保存新配置
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
                return True
                
        except Exception as e:
            return False
    
    def _onEditModelSet(self):
        """编辑模型集"""
        try:
            # 直接调用模型集页面的编辑菜单
            if hasattr(self, 'modelSetPage'):
                self.modelSetPage._showEditMenu()
            else:
                QtWidgets.QMessageBox.warning(self, "错误", "模型集页面未初始化")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "错误", f"编辑模型集失败: {e}")
    
    def _onDeleteModelSet(self):
        """删除模型集"""
        try:
            # 检查是否有选中的模型
            if hasattr(self, 'modelSetPage'):
                current_model = self.modelSetPage.getCurrentModel()
                if not current_model:
                    QtWidgets.QMessageBox.warning(self, "警告", "请先选择一个模型")
                    return
                
                # 移除"（默认）"标记获取实际模型名
                model_name = current_model.replace("（默认）", "").strip()
                
                # 显示确认对话框（无图标）
                msg_box = QtWidgets.QMessageBox(self)
                msg_box.setWindowTitle("确认删除")
                msg_box.setText(f"确定要删除模型 '{model_name}' 吗？\n\n此操作不可撤销！")
                msg_box.setIcon(QtWidgets.QMessageBox.NoIcon)
                msg_box.setWindowIcon(QtGui.QIcon())  # 移除窗口图标
                msg_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                msg_box.setDefaultButton(QtWidgets.QMessageBox.No)
                
                # 设置中文按钮文本
                yes_btn = msg_box.button(QtWidgets.QMessageBox.Yes)
                no_btn = msg_box.button(QtWidgets.QMessageBox.No)
                if yes_btn:
                    yes_btn.setText("是")
                if no_btn:
                    no_btn.setText("否")
                
                reply = msg_box.exec_()
                
                if reply == QtWidgets.QMessageBox.Yes:
                    # 调用 ModelSetPage 的删除方法
                    # deleteModel会触发deleteModelDataRequested信号，由deleteModelData处理
                    # deleteModelData会自动刷新训练页面
                    self.modelSetPage.deleteModel(model_name)
            else:
                QtWidgets.QMessageBox.warning(self, "错误", "模型集页面未初始化")
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"删除模型失败: {e}")
    
    def _onLoadModelSet(self):
        """加载模型集（实际功能实现）"""
        try:
            # 检查是否有选中的模型
            if hasattr(self, 'modelSetPage'):
                current_model = self.modelSetPage.getCurrentModel()
                if not current_model:
                    QtWidgets.QMessageBox.warning(self, "警告", "请先选择一个模型")
                    return
                
                # 移除"（默认）"标记获取实际模型名
                model_name = current_model.replace("（默认）", "").strip()
                
                # 获取模型参数
                all_params = self.modelSetPage.getAllModelParams()
                if model_name not in all_params:
                    QtWidgets.QMessageBox.warning(self, "错误", f"未找到模型 '{model_name}' 的参数信息")
                    return
                
                model_params = all_params[model_name]
                model_path = model_params.get('path', '')
                
                if not model_path or not os.path.exists(model_path):
                    QtWidgets.QMessageBox.warning(self, "错误", f"模型文件不存在: {model_path}")
                    return
                
                # 获取加载的模型数量（通过 ModelLoadHandler）
                loaded_count = 0
                if hasattr(self, 'getLoadedModels'):
                    loaded_count = len(self.getLoadedModels())
                
                # 显示加载确认对话框（无图标）
                msg_box = QtWidgets.QMessageBox(self)
                msg_box.setWindowTitle("确认加载模型")
                msg_box.setText(
                    f"确定要加载模型 '{model_name}' 吗？\n\n"
                    f"模型路径: {model_path}\n"
                    f"模型类型: {model_params.get('type', '未知')}\n"
                    f"模型大小: {model_params.get('size', '未知')}\n\n"
                    f"当前已加载模型数量: {loaded_count}\n"
                    f"系统支持加载任意数量的模型"
                )
                msg_box.setIcon(QtWidgets.QMessageBox.NoIcon)
                msg_box.setWindowIcon(QtGui.QIcon())  # 移除窗口图标
                msg_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                msg_box.setDefaultButton(QtWidgets.QMessageBox.Yes)
                
                # 设置中文按钮文本
                yes_btn = msg_box.button(QtWidgets.QMessageBox.Yes)
                no_btn = msg_box.button(QtWidgets.QMessageBox.No)
                if yes_btn:
                    yes_btn.setText("是")
                if no_btn:
                    no_btn.setText("否")
                
                reply = msg_box.exec_()
                
                if reply == QtWidgets.QMessageBox.Yes:
                    # 执行模型加载（通过 ModelLoadHandler，由于是 Mixin，可以直接调用）
                    success = False
                    # 由于 ModelLoadHandler 是 Mixin，self 应该有 _loadModelToSystem 方法
                    if hasattr(self, '_loadModelToSystem'):
                        success = self._loadModelToSystem(model_name, model_params)
                    elif hasattr(self, 'getLoadedModels'):
                        # 如果存在 getLoadedModels，说明 ModelLoadHandler 已混入
                        # 尝试调用加载方法
                        try:
                            success = self._loadModelToSystem(model_name, model_params)
                        except:
                            pass
                    
                    if success:
                        QtWidgets.QMessageBox.information(
                            self, "加载成功", 
                            f"模型 '{model_name}' 已成功加载到系统中！\n\n"
                            f"现在可以在检测任务中使用此模型。"
                        )
                        
                        # 更新状态栏
                        if hasattr(self, 'statusBar'):
                            self.statusBar().showMessage(f" 已加载模型: {model_name}")
                        
                        # 更新模型列表的加载状态显示
                        if hasattr(self, 'modelSetPage'):
                            # 通过 ModelLoadHandler 获取已加载模型
                            loaded_models = {}
                            if hasattr(self, 'getLoadedModels'):
                                loaded_models = self.getLoadedModels()
                            self.modelSetPage.updateModelLoadStatus(loaded_models)
                    else:
                        QtWidgets.QMessageBox.warning(
                            self, "加载失败", 
                            f"模型 '{model_name}' 加载失败，请检查模型文件是否完整。"
                        )
            else:
                QtWidgets.QMessageBox.warning(self, "错误", "模型集页面未初始化")
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"加载模型集失败: {e}")
    
    # ==================== 从 modelset_page.py 转移的业务逻辑 ====================
    
    def loadModelsFromConfig(self):
        """从配置文件和模型目录加载所有模型"""
        try:
            config = self._loadConfigFile()
            if not config:
                return
            
            channel_models = []  # 不加载通道模型
            
            scanned_models = self._scanModelDirectory()
            
            all_models = scanned_models  # 直接使用扫描模型
            
            if len(all_models) > 0:
                all_models[0]['is_default'] = True
            
            self._updateModelList(all_models)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _loadConfigFile(self):
        """加载配置文件"""
        try:
            # 获取配置文件路径
            current_dir = Path(__file__).parent.parent.parent
            config_path = current_dir / "database" / "config" / "default_config.yaml"
            
            if not config_path.exists():
                return None
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config
                
        except Exception as e:
            return None
    
    def _saveConfigFile(self, config):
        """保存配置文件"""
        try:
            # 获取配置文件路径
            current_dir = Path(__file__).parent.parent.parent
            config_path = current_dir / "database" / "config" / "default_config.yaml"
            
            # 备份原配置文件
            backup_path = config_path.with_suffix('.yaml.backup')
            if config_path.exists():
                import shutil
                shutil.copy2(config_path, backup_path)
            
            # 保存新配置
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
                return True
                
        except Exception as e:
            return False
    
    def _extractChannelModels(self, config):
        """从配置文件提取通道模型信息"""
        models = []
        
        # 遍历 channel1-4
        for i in range(1, 5):
            # 尝试多种路径键名
            model_path = None
            channel_name = None
            
            # 1. 尝试从根级别的 channel{i}_model_path 读取
            channel_model_key = f'channel{i}_model_path'
            if channel_model_key in config:
                model_path = config[channel_model_key]
            
            # 2. 尝试从通道配置字典中的 model_path 读取
            channel_key = f'channel{i}'
            if channel_key in config and isinstance(config[channel_key], dict):
                channel_config = config[channel_key]
                if not model_path:
                    model_path = channel_config.get('model_path')
                channel_name = channel_config.get('name', f'通道{i}')
            else:
                channel_name = f'通道{i}'
            
            # 3. 检查模型路径是否存在
            if model_path and os.path.exists(model_path):
                models.append({
                    'name': f"{channel_name}模型",
                    'path': model_path,
                    'channel': channel_key,
                    'channel_name': channel_name,
                    'source': 'config',
                    'is_default': i == 1  # channel1 作为默认
                })
        
        return models
    
    def _scanModelDirectory(self):
        """扫描模型目录获取所有模型文件（增强版：支持config.yaml和按优先级选择模型）"""
        models = []
        
        try:
            # 获取模型目录路径
            current_dir = Path(__file__).parent.parent.parent
            model_dir = current_dir / "database" / "model" / "detection_model"
            
            if not model_dir.exists():
                return models
            
            # 扫描所有子目录（数字和非数字）
            all_subdirs = [d for d in model_dir.iterdir() if d.is_dir()]
            
            # 分离数字目录和非数字目录
            digit_subdirs = [d for d in all_subdirs if d.name.isdigit()]
            non_digit_subdirs = [d for d in all_subdirs if not d.name.isdigit()]
            
            # 数字目录按数字降序排序，非数字目录按字母排序
            sorted_digit_subdirs = sorted(digit_subdirs, key=lambda x: int(x.name), reverse=True)
            sorted_non_digit_subdirs = sorted(non_digit_subdirs, key=lambda x: x.name)
            
            # 合并：数字目录在前，非数字目录在后
            sorted_subdirs = sorted_digit_subdirs + sorted_non_digit_subdirs
            
            for subdir in sorted_subdirs:
                
                # 检查是否有weights子目录（优先检查train/weights，然后weights）
                train_weights_dir = subdir / "train" / "weights"
                weights_dir = subdir / "weights"
                
                if train_weights_dir.exists():
                    search_dir = train_weights_dir
                elif weights_dir.exists():
                    search_dir = weights_dir
                else:
                    search_dir = subdir
                
                # 按优先级查找模型文件：best > last > epoch1
                # 支持的扩展名：.dat, .pt, .template_*, .engine, .onnx, 无扩展名
                selected_model = None
                
                # 优先级1: best模型
                for pattern in ['best.*.dat', 'best.*.pt', 'best.template_*', 'best.*']:
                    if selected_model:
                        break
                    for file in search_dir.iterdir():
                        if file.is_file():
                            # 检查文件名是否匹配模式
                            if file.name.startswith('best.') and not file.name.endswith('.pt'):
                                selected_model = file
                                break
                
                # 优先级2: last模型（如果没有best）
                if not selected_model:
                    for file in search_dir.iterdir():
                        if file.is_file() and file.name.startswith('last.') and not file.name.endswith('.pt'):
                            selected_model = file
                            break
                
                # 优先级3: epoch1模型（如果没有best和last）
                if not selected_model:
                    for file in search_dir.iterdir():
                        if file.is_file() and file.name.startswith('epoch1.') and not file.name.endswith('.pt'):
                            selected_model = file
                            break
                
                # 优先级4: 查找.engine文件（TensorRT模型）
                if not selected_model:
                    for file in search_dir.iterdir():
                        if file.is_file() and file.name.endswith('.engine'):
                            selected_model = file
                            break
                
                # 优先级5: 查找.onnx文件
                if not selected_model:
                    for file in search_dir.iterdir():
                        if file.is_file() and file.name.endswith('.onnx'):
                            selected_model = file
                            break
                
                # 如果都没找到，尝试查找任何非.pt文件
                if not selected_model:
                    for file in search_dir.iterdir():
                        if file.is_file() and not file.name.endswith('.pt') and not file.name.endswith('.txt') and not file.name.endswith('.yaml'):
                            selected_model = file
                            break
                
                # 如果找到了模型文件，添加到列表
                if selected_model:
                    # 使用"文件夹名称/模型文件名"格式
                    model_name = f"{subdir.name}/{selected_model.stem}"
                    description = f"来自目录 {subdir.name}"
                    training_date = ''
                    epochs = ''
                    
                    # 读取模型描述文件（如果存在）
                    description_file = subdir / 'model_description.txt'
                    if description_file.exists():
                        try:
                            with open(description_file, 'r', encoding='utf-8') as f:
                                description_content = f.read()
                                # 提取关键信息（适配新格式）
                                if '训练时间:' in description_content:
                                    training_date = description_content.split('训练时间:')[1].split('\n')[0].strip()
                                if '训练轮数:' in description_content:
                                    epochs = description_content.split('训练轮数:')[1].split('\n')[0].strip()
                                # 使用描述文件的第一行作为简短描述
                                first_line = description_content.split('\n')[0]
                                if first_line:
                                    # 移除可能的前缀
                                    description = first_line.replace('【模型信息】', '').replace('模型', '').strip()
                                    # 如果第一行包含" - "，取后半部分
                                    if ' - ' in description:
                                        description = description.split(' - ', 1)[1]
                        except Exception as e:
                            pass  # 如果读取失败，使用默认描述
                    
                    # 获取文件格式
                    file_ext = selected_model.suffix.lstrip('.')
                    if not file_ext:
                        # 处理无扩展名的情况（如 best.template_6543）
                        if '.' in selected_model.name:
                            file_ext = selected_model.name.split('.')[-1]
                        else:
                            file_ext = 'unknown'
                    
                    model_info = {
                        'name': model_name,
                        'path': str(selected_model),
                        'subdir': subdir.name,
                        'source': 'train_model',
                        'format': file_ext,
                        'description': description,
                        'training_date': training_date,
                        'epochs': epochs,
                        'file_name': selected_model.name,
                        'description_file': str(description_file) if description_file.exists() else None
                    }
                    models.append(model_info)
        
        except Exception as e:
            import traceback
            traceback.print_exc()
        
        return models
    
    def _mergeModelInfo(self, channel_models, scanned_models):
        """合并模型信息，避免重复"""
        all_models = []
        seen_paths = set()
        
        # 优先添加配置文件中的通道模型
        for model in channel_models:
            path = model['path']
            if path not in seen_paths:
                all_models.append(model)
                seen_paths.add(path)
        
        # 再添加扫描到的模型（跳过已存在的）
        for model in scanned_models:
            path = model['path']
            if path not in seen_paths:
                all_models.append(model)
                seen_paths.add(path)
        
        # 确保只有一个默认模型
        default_model_index = -1
        for i, model in enumerate(all_models):
            if model.get('is_default', False):
                if default_model_index == -1:
                    # 第一个默认模型，保留
                    default_model_index = i
                else:
                    # 已经有默认模型了，取消这个模型的默认标记
                    model['is_default'] = False
        
        # 如果没有默认模型，将第一个模型设为默认
        if default_model_index == -1 and len(all_models) > 0:
            all_models[0]['is_default'] = True
        
        return all_models
    
    def _updateModelList(self, all_models):
        """更新UI中的模型列表"""
        try:
            if not hasattr(self, 'modelSetPage') or not self.modelSetPage:
                return
            
            # 清空现有模型参数
            self.modelSetPage._model_params = {}
            
            # 添加所有模型到UI
            for i, model in enumerate(all_models):
                model_name = model['name']
                
                # 创建模型参数
                model_params = self._createModelParams(model, {})
                self.modelSetPage._model_params[model_name] = model_params
                
                # 设置默认模型
                if model.get('is_default', False):
                    self.modelSetPage._current_default_model = model_name
            
            if hasattr(self.modelSetPage, 'refreshModelList'):
                self.modelSetPage.refreshModelList()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _createModelParams(self, model_info, config):
        """为模型创建参数信息"""
        model_path = model_info['path']
        model_name = model_info['name']
        
        # 获取文件大小
        try:
            file_size_bytes = os.path.getsize(model_path)
            file_size_mb = file_size_bytes / (1024 * 1024)
            size_str = f"{file_size_mb:.1f} MB"
        except:
            size_str = "未知"
        
        # 从配置文件获取全局模型参数
        model_config = config.get('model', {})
        
        # 确定模型类型
        if model_path.endswith('.pt'):
            model_type = "PyTorch (YOLOv5/v8)"
        elif model_path.endswith('.dat'):
            model_type = ".dat"
        elif model_path.endswith('.engine'):
            model_type = "TensorRT"
        else:
            model_type = "未知格式"
        
        # 从配置获取设备信息
        performance_config = config.get('performance', {})
        use_gpu = performance_config.get('use_gpu', False)
        gpu_device = performance_config.get('gpu_device', 'cuda:0')
        device_str = f"{gpu_device.upper()} (GPU)" if use_gpu else "CPU"
        
        # 创建参数字典
        params = {
            "name": model_name,
            "type": model_type,
            "size": size_str,
            "classes": model_config.get('max_det', 100),
            "input": f"{model_config.get('input_size', [640, 640])[0]}x{model_config.get('input_size', [640, 640])[1]}",
            "confidence": model_config.get('confidence_threshold', 0.5),
            "iou": model_config.get('iou_threshold', 0.45),
            "device": device_str,
            "batch_size": model_config.get('batch_size', 1),
            "blur_training": 100,
            "epochs": 300,
            "workers": performance_config.get('num_threads', 4),
            "path": model_path,
            "description": self._generateModelDescription(model_info, model_config)
        }
        
        return params
    
    def _generateModelDescription(self, model_info, model_config):
        """生成模型描述"""
        # 优先使用模型描述文件的内容
        description_file_path = model_info.get('description_file')
        if description_file_path:
            try:
                with open(description_file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                pass  # 如果读取失败，使用默认生成的描述
        
        # 如果没有描述文件，生成默认描述
        descriptions = []
        
        # 基本信息
        if model_info.get('source') == 'config':
            descriptions.append(f"【{model_info.get('channel_name', '未命名')}】的检测模型")
            descriptions.append(f"通道: {model_info.get('channel', '未知')}")
        else:
            descriptions.append(f"来自模型库的预训练模型")
            descriptions.append(f"子目录: {model_info.get('subdir', '未知')}")
        
        # 配置信息
        descriptions.append(f"")
        descriptions.append(f"配置信息:")
        descriptions.append(f"- 模型类型: {model_config.get('model_type', 'YOLOv5')}")
        descriptions.append(f"- 输入尺寸: {model_config.get('input_size', [640, 640])}")
        descriptions.append(f"- 置信度阈值: {model_config.get('confidence_threshold', 0.5)}")
        descriptions.append(f"- IOU阈值: {model_config.get('iou_threshold', 0.45)}")
        descriptions.append(f"- 批次大小: {model_config.get('batch_size', 1)}")
        
        # 模型格式说明
        descriptions.append(f"")
        if model_info['path'].endswith('.dat'):
            descriptions.append("这是一个加密的模型文件，需要解密后才能使用。")
        else:
            descriptions.append("这是一个标准的PyTorch模型文件，可直接加载使用。")
        
        return "\n".join(descriptions)
    
    def _removeModelFromConfig(self, model_name):
        """从配置文件中删除模型配置"""
        try:
            # 加载当前配置
            config = self._loadConfigFile()
            if not config:
                return False
            
            # 查找并删除对应的通道配置
            removed = False
            for channel_key in ['channel1', 'channel2', 'channel3', 'channel4']:
                if channel_key in config:
                    channel_config = config[channel_key]
                    # 检查是否是我们要删除的模型
                    if (channel_config.get('name') == model_name or 
                        channel_config.get('model_path', '').endswith(model_name) or
                        model_name in str(channel_config.get('model_path', ''))):
                        
                        # 删除该通道配置
                        del config[channel_key]
                        removed = True
                        break
            
            # 如果找到了对应的配置，保存更新后的配置文件
            if removed:
                success = self._saveConfigFile(config)
                if success:
                    return True
                else:
                    return False
            else:
                return False
                
        except Exception as e:
            return False
    
    def renameModel(self, old_name, new_name):
        """重命名模型（业务逻辑）"""
        try:
            if not new_name.strip() or new_name.strip() == old_name:
                return False
            
            new_name = new_name.strip()
            
            # 检查新名称是否已存在
            if hasattr(self, 'modelSetPage') and self.modelSetPage:
                if new_name in self.modelSetPage._model_params:
                    QtWidgets.QMessageBox.warning(
                        self.modelSetPage, "错误", 
                        f"模型名称 '{new_name}' 已存在"
                    )
                    return False
                
                # 更新模型参数
                if old_name in self.modelSetPage._model_params:
                    self.modelSetPage._model_params[new_name] = self.modelSetPage._model_params.pop(old_name)
                
                # 更新默认模型引用
                if self.modelSetPage._current_default_model == old_name:
                    self.modelSetPage._current_default_model = new_name
                
                return True
            
            return False
            
        except Exception as e:
            return False
    
    def duplicateModel(self, model_name, new_name):
        """复制模型（业务逻辑）"""
        try:
            if not new_name.strip():
                return False
            
            new_name = new_name.strip()
            
            # 检查新名称是否已存在
            if hasattr(self, 'modelSetPage') and self.modelSetPage:
                if new_name in self.modelSetPage._model_params:
                    QtWidgets.QMessageBox.warning(
                        self.modelSetPage, "错误", 
                        f"模型名称 '{new_name}' 已存在"
                    )
                    return False
                
                # 复制模型参数
                if model_name in self.modelSetPage._model_params:
                    model_params = self.modelSetPage._model_params[model_name].copy()
                    model_params['name'] = new_name
                    self.modelSetPage._model_params[new_name] = model_params
                    return True
            
            return False
            
        except Exception as e:
            return False
    
    def deleteModelData(self, model_name):
        """删除模型数据（业务逻辑）"""
        try:
            if hasattr(self, 'modelSetPage') and self.modelSetPage:
                # 如果是默认模型，先取消默认状态
                if self.modelSetPage._current_default_model == model_name:
                    self.modelSetPage._current_default_model = None
                
                # 从参数中删除
                if model_name in self.modelSetPage._model_params:
                    model_params = self.modelSetPage._model_params[model_name]
                    model_path = model_params.get('path', '')
                    
                    # 删除模型文件和所在目录
                    if model_path and os.path.exists(model_path):
                        try:
                            import shutil
                            # 获取模型所在的目录（train_model/{数字ID}/）
                            model_dir = os.path.dirname(model_path)
                            
                            # 检查是否是train_model目录下的子目录
                            if 'train_model' in model_dir:
                                # 删除整个模型目录
                                if os.path.exists(model_dir):
                                    shutil.rmtree(model_dir)
                                    print(f"[删除模型] 已删除模型目录: {model_dir}")
                        except Exception as delete_error:
                            print(f"[删除模型] 删除模型文件失败: {delete_error}")
                    
                    del self.modelSetPage._model_params[model_name]
                
                # 从配置文件中删除模型配置
                self._removeModelFromConfig(model_name)
                
                # 刷新训练页面的模型测试下拉框
                self._refreshTrainingPageModelList()
                
                return True
            
            return False
            
        except Exception as e:
            print(f"[删除模型] 删除失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _refreshTrainingPageModelList(self):
        """刷新训练页面的模型测试下拉框（通过信号机制）"""
        try:
            # 通过ModelSetPage发射全局信号，所有监听的页面都会自动刷新
            if hasattr(self, 'modelSetPage') and self.modelSetPage:
                if hasattr(self.modelSetPage, 'modelListChanged'):
                    self.modelSetPage.modelListChanged.emit()
                    print("[删除模型] 已发射模型列表变化信号")
                else:
                    print("[警告] ModelSetPage没有modelListChanged信号")
            else:
                print("[警告] 未找到ModelSetPage实例")
        except Exception as e:
            print(f"[错误] 发射模型列表变化信号失败: {e}")
    
    def getAllModelParams(self):
        """获取所有模型参数"""
        if hasattr(self, 'modelSetPage') and self.modelSetPage:
            return self.modelSetPage._model_params
        return {}
    
    def getDefaultModel(self):
        """获取默认模型"""
        if hasattr(self, 'modelSetPage') and self.modelSetPage:
            return self.modelSetPage._current_default_model
        return None
