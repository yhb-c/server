# -*- coding: utf-8 -*-

"""
模型测试处理器

处理模型测试相关的所有功能，从 model_training_handler.py 中分离出来
"""

import os
import yaml
import json
import cv2
import numpy as np
import tempfile
from pathlib import Path
from datetime import datetime
from qtpy import QtCore, QtWidgets, QtGui

# 尝试导入 pyqtSignal 和 QThread
try:
    from PyQt5.QtCore import pyqtSignal, QThread
except ImportError:
    try:
        from PyQt6.QtCore import pyqtSignal, QThread
    except ImportError:
        from qtpy.QtCore import Signal as pyqtSignal, QThread

# 先定义后备类（确保一定有定义）
def newIcon(icon):
    from qtpy.QtGui import QIcon
    return QIcon()

class FontManager:
    FONT_SIZE_SMALL = 10
    @staticmethod
    def applyToWidget(widget, size=None, weight=None, italic=False, underline=False):
        pass

class DialogManager:
    @staticmethod
    def show_warning(parent, title, message, text_alignment=None):
        QtWidgets.QMessageBox.warning(parent, title, message)

# 尝试导入样式管理器（如果成功则覆盖上面的定义）
try:
    from widgets.style_manager import newIcon, FontManager, DialogManager
except ImportError as e:
    try:
        from ...widgets.style_manager import newIcon, FontManager, DialogManager
    except (ImportError, ValueError) as e2:
        pass

# 导入统一的路径管理函数
try:
    from ...config import get_project_root, get_temp_models_dir, get_train_dir
except (ImportError, ValueError):
    try:
        from client.config import get_project_root, get_temp_models_dir, get_train_dir
    except ImportError:
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))
        from client.config import get_project_root, get_temp_models_dir, get_train_dir


class ModelTestThread(QThread):
    """模型测试后台线程"""
    
    # 信号定义
    progress_updated = pyqtSignal(int, str)  # (进度值, 提示文本)
    test_finished = pyqtSignal(bool, str)  # (是否成功, 结果消息)
    error_occurred = pyqtSignal(str, str)  # (错误类型, 错误消息)
    
    def __init__(self, test_params):
        """
        初始化测试线程
        
        Args:
            test_params: 测试参数字典，包含：
                - model_path: 模型路径
                - test_file_path: 测试文件路径
                - annotation_file: 标注文件路径
                - is_video: 是否为视频文件
                - handler: ModelTestHandler实例引用
        """
        super().__init__()
        self.test_params = test_params
        self.is_running = True
        self._detection_result = None
    
    def run(self):
        """线程执行函数"""
        try:
            model_path = self.test_params['model_path']
            test_file_path = self.test_params['test_file_path']
            annotation_file = self.test_params['annotation_file']
            is_video = self.test_params['is_video']
            handler = self.test_params['handler']
            
            if is_video:
                # 视频文件检测
                self.progress_updated.emit(20, "正在加载视频文件...")
                self._performVideoDetection(handler, model_path, test_file_path, annotation_file)
            else:
                # 图片文件检测
                self.progress_updated.emit(20, "正在加载测试图像...")
                test_frame = handler._loadTestFrame(test_file_path)
                
                if test_frame is None:
                    self.error_occurred.emit("文件读取失败", f"无法读取测试文件: {test_file_path}")
                    return
                
                self.progress_updated.emit(30, "正在执行液位检测...")
                self._performImageDetection(handler, model_path, test_frame, annotation_file)
            
            if self.is_running:
                self.test_finished.emit(True, "测试完成")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error_occurred.emit(type(e).__name__, str(e))
    
    def _performImageDetection(self, handler, model_path, test_frame, annotation_file):
        """通过服务端API执行图片检测"""
        try:
            # 连接服务端
            self.progress_updated.emit(40, "正在连接服务端...")
            
            # 导入远程配置管理器
            from client.utils.config import RemoteConfigManager
            remote_config = RemoteConfigManager()
            ssh_manager = remote_config._get_ssh_manager()
            
            if not ssh_manager:
                raise RuntimeError("SSH连接不可用")
            
            # 读取标注数据
            self.progress_updated.emit(45, "正在读取标注数据...")
            
            import yaml
            with open(annotation_file, 'r', encoding='utf-8') as f:
                try:
                    annotation_data = yaml.safe_load(f)
                except yaml.constructor.ConstructorError as e:
                    if 'python/tuple' in str(e):
                        f.seek(0)
                        annotation_data = yaml.unsafe_load(f)
                    else:
                        raise
            
            self.progress_updated.emit(50, "正在服务端创建检测引擎...")
            
            # 提取标注数据
            test_model_data = annotation_data.get('test_model', {})
            boxes = test_model_data.get('boxes', [])
            bottoms = test_model_data.get('bottoms', [])
            tops = test_model_data.get('tops', [])
            init_levels = test_model_data.get('init_levels', [])
            
            # 提取Y坐标
            fixed_bottoms = [bottom[1] if isinstance(bottom, (tuple, list)) else bottom for bottom in bottoms]
            fixed_tops = [top[1] if isinstance(top, (tuple, list)) else top for top in tops]
            fixed_init_levels = [level[1] if isinstance(level, (tuple, list)) else level for level in init_levels]
            
            # 提取实际高度
            actual_heights = test_model_data.get('actual_heights', [20.0] * len(boxes))
            
            self.progress_updated.emit(60, "正在服务端加载模型...")
            
            # 将图像保存到临时文件并上传到服务端
            import cv2
            import tempfile
            import os
            import json
            import base64
            
            # 编码图像为base64
            _, buffer = cv2.imencode('.jpg', test_frame)
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            
            # 构建服务端检测命令
            detection_cmd = f"""
cd /home/lqj/liquid/server
source ~/anaconda3/bin/activate liquid
python -c "
import sys
sys.path.append('/home/lqj/liquid/server')
import cv2
import numpy as np
import base64
import json

try:
    from detection import LiquidDetectionEngine
    
    # 解码图像
    frame_data = base64.b64decode('{frame_base64}')
    frame_array = np.frombuffer(frame_data, np.uint8)
    frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
    
    # 创建检测引擎
    engine = LiquidDetectionEngine(model_path='{model_path}')
    
    # 配置检测引擎
    boxes = {boxes}
    fixed_bottoms = {fixed_bottoms}
    fixed_tops = {fixed_tops}
    actual_heights = {actual_heights}
    fixed_init_levels = {fixed_init_levels}
    
    engine.configure(boxes, fixed_bottoms, fixed_tops, actual_heights, fixed_init_levels)
    
    # 执行检测
    detection_result = engine.detect(frame)
    
    if detection_result and detection_result.get('success'):
        print('SUCCESS:' + json.dumps(detection_result))
    else:
        print('ERROR: 检测失败或结果为空')
        
except Exception as e:
    print(f'ERROR: {{e}}')
    import traceback
    traceback.print_exc()
"
"""
            
            self.progress_updated.emit(70, "正在服务端执行检测...")
            
            result = ssh_manager.execute_remote_command(detection_cmd)
            
            if not result['success'] or 'SUCCESS:' not in result['stdout']:
                error_msg = result.get('stderr', result.get('stdout', '未知错误'))
                raise RuntimeError(f"服务端检测失败: {error_msg}")
            
            # 解析检测结果
            success_line = [line for line in result['stdout'].split('\n') if line.startswith('SUCCESS:')][0]
            result_json = success_line.replace('SUCCESS:', '')
            detection_result = json.loads(result_json)
            
            self.progress_updated.emit(80, "正在处理检测结果...")
            
            # 转换检测结果格式以兼容现有代码
            converted_result = self._convertDetectionResult(detection_result)
            self._detection_result = converted_result
            
            self.progress_updated.emit(90, "正在保存测试结果...")
            # 通过handler调用保存方法
            handler = self.test_params['handler']
            handler._saveImageTestResults(model_path, test_frame, converted_result, annotation_file)
            
        except Exception as e:
            raise
    
    def _performVideoDetection(self, handler, model_path, video_path, annotation_file):
        """执行视频检测"""
        try:
            # 视频检测需要在主线程中执行（涉及UI更新）
            # 所以这里只是标记，实际检测由主线程的原有方法处理
            # 发送进度信号
            self.progress_updated.emit(30, "正在准备视频检测...")
            
            # 注意：视频检测由于涉及实时播放器等UI组件
            # 暂时保持在主线程执行，这里只做标记
            pass
            
        except Exception as e:
            raise
    
    def stop(self):
        """停止线程"""
        self.is_running = False
    
    def get_detection_result(self):
        """获取检测结果"""
        return self._detection_result
    
    def _convertDetectionResult(self, detection_result):
        """
        转换检测结果格式以兼容现有代码
        
        Args:
            detection_result: detect方法返回的结果格式
            {
                'liquid_line_positions': {
                    0: {'y': y坐标, 'height_mm': 高度毫米, 'height_px': 高度像素},
                    1: {...},
                    ...
                },
                'success': bool
            }
        
        Returns:
            dict: 转换后的结果格式，包含 liquid_level_mm 字段
        """
        try:
            if not detection_result or not detection_result.get('success', False):
                return {'liquid_level_mm': 0.0, 'success': False}
            
            liquid_positions = detection_result.get('liquid_line_positions', {})
            
            if not liquid_positions:
                return {'liquid_level_mm': 0.0, 'success': False}
            
            # 取第一个ROI的液位高度
            first_position = next(iter(liquid_positions.values()))
            liquid_level_mm = first_position.get('height_mm', 0.0)
            
            # 构建兼容格式的结果
            converted_result = {
                'liquid_level_mm': liquid_level_mm,
                'success': True,
                'areas': {}
            }
            
            # 转换所有区域的数据
            for idx, position_data in liquid_positions.items():
                area_name = f'区域{idx + 1}'
                converted_result['areas'][area_name] = {
                    'liquid_height': position_data.get('height_mm', 0.0),
                    'y_position': position_data.get('y', 0),
                    'height_px': position_data.get('height_px', 0)
                }
            
            return converted_result
            
        except Exception as e:
            print(f"[结果转换] 转换检测结果失败: {e}")
            return {'liquid_level_mm': 0.0, 'success': False}


class ModelTestHandler:
    """
    模型测试处理器
    
    负责处理所有模型测试相关的功能：
    - 测试文件加载
    - 标注数据管理
    - 液位检测执行
    - 视频逐帧检测
    - 结果显示
    """
    
    def __init__(self, *args, **kwargs):
        """
        初始化模型测试处理器
        
        在Mixin链中，main_window参数会在后续手动设置
        """
        super().__init__(*args, **kwargs)
        self.main_window = None
        self.training_panel = None  # 训练面板引用
        self.annotation_engine = None  # 标注引擎
        self.annotation_widget = None  # 标注界面组件
        self.test_detection_window = None  # 测试检测窗口
        self._detection_stopped = False  # 检测停止标志
        self._realtime_frame_label = None  # 实时帧显示标签
        self._realtime_container = None  # 实时容器
        self._realtime_video_path = None  # 实时视频路径
        self._draw_debug_count = 0  # 液位线绘制调试计数
        self._yellow_line_warning_shown = False  # 黄色液位线警告标志
        self._realtime_frame_buffer = []  # 帧缓冲区
        self._realtime_frame_index = 0  # 帧索引
        self._draw_debug_count = 0  # 绘制调试计数
        self._yellow_line_warning_shown = False  # 黄线警告显示标志
        self._test_thread = None  # 测试后台线程
        self._test_progress_dialog = None  # 测试进度对话框
    
    def connectTestButtons(self, training_panel):
        """连接测试相关按钮"""
        # 连接开始标注按钮
        if hasattr(training_panel, 'start_annotation_btn'):
            training_panel.start_annotation_btn.clicked.connect(self._handleStartAnnotation)
        
        # 连接开始测试按钮
        if hasattr(training_panel, 'start_test_btn'):
            training_panel.start_test_btn.clicked.connect(self._handleStartTest)
    
    def _handleStartTest(self):
        """处理开始/停止测试按钮点击 - 支持状态切换"""
        # 检查当前状态
        if self.training_panel.isTestingInProgress():
            # 当前正在测试中，执行停止操作
            self._handleStopTest()
            return
        
        # 当前未测试，执行开始测试操作
        self._handleStartTestExecution()
    
    def _handleStopTest(self):
        """停止测试并释放资源"""
        try:
            self._detection_stopped = True
            
            # 恢复按钮状态
            self.training_panel.setTestButtonState(False)
            
            # 显示停止信息
            if hasattr(self.training_panel, 'display_panel'):
                stop_html = """
                <div style="padding: 15px; background: #000000; border: 1px solid #dee2e6; border-radius: 5px; color: #ffffff;">
                    <h3 style="margin-top: 0; color: #ffffff;">测试已停止</h3>
                    <p style="color: #ffffff;">用户手动停止了测试过程</p>
                    <p style="margin-bottom: 0; font-size: 12px; color: #ffffff;">资源已释放，可以重新开始测试</p>
                </div>
                """
                self.training_panel.display_panel.setHtml(stop_html)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _handleStartTestExecution(self):
        """执行开始测试操作 - 液位检测测试功能"""
        try:
            # 🔥 清空曲线数据，准备新的测试
            self._clearCurve()
            
            # 禁用查看曲线按钮
            if hasattr(self.training_panel, 'disableViewCurveButton'):
                self.training_panel.disableViewCurveButton()
            
            # 切换按钮状态为“停止测试”
            self.training_panel.setTestButtonState(True)
            
            # 获取选择的测试模型和测试文件
            test_model_display = self.training_panel.test_model_combo.currentText()
            test_model_path_raw = self.training_panel.test_model_combo.currentData()
            # 从QLineEdit获取测试文件路径（浏览选择的文件）
            test_file_path_raw = self.training_panel.test_file_input.text().strip()
            test_file_display = os.path.basename(test_file_path_raw) if test_file_path_raw else ""
            
            # 关键修复：路径规范化处理，确保相对路径转换为绝对路径
            project_root = get_project_root()
            
            # 处理模型路径
            if test_model_path_raw and not os.path.isabs(test_model_path_raw):
                # 相对路径，转换为绝对路径
                test_model_path = os.path.join(project_root, test_model_path_raw)
                pass
            else:
                test_model_path = test_model_path_raw
            
            # 处理测试文件路径
            if test_file_path_raw and not os.path.isabs(test_file_path_raw):
                # 相对路径，转换为绝对路径
                test_file_path = os.path.join(project_root, test_file_path_raw)
                print(f"[模型测试] 相对路径转换: {test_file_path_raw} -> {test_file_path}")
            else:
                test_file_path = test_file_path_raw
            
            # 规范化路径（统一使用正斜杠）
            test_model_path = os.path.normpath(test_model_path) if test_model_path else None
            test_file_path = os.path.normpath(test_file_path) if test_file_path else None
            
            print(f"[模型测试] 最终模型路径: {test_model_path}")
            print(f"[模型测试] 最终文件路径: {test_file_path}")
            
            # 验证参数
            if not test_model_path or not test_file_path:
                error_msg = "参数验证失败：\n"
                if not test_model_path:
                    error_msg += f"- 未选择测试模型（原始路径: {test_model_path_raw}\n"
                if not test_file_path:
                    error_msg += f"- 未选择测试文件（原始路径: {test_file_path_raw}\n"
                print(f"[模型测试] 错误: {error_msg}")
                
                # 在显示面板中显示详细错误信息
                if hasattr(self.training_panel, 'display_panel'):
                    error_html = f"""
                    <div style="padding: 15px; background: #000000; border: 1px solid #dee2e6; border-radius: 5px; color: #ffffff;">
                        <h3 style="margin-top: 0; color: #ffffff;">参数验证失败</h3>
                        <p style="color: #ffffff;"><strong>错误原因:</strong></p>
                        <ul style="color: #ffffff;">
                            {f'<li>未选择测试模型（原始路径: {test_model_path_raw}）</li>' if not test_model_path else ''}
                            {f'<li>未选择测试文件（原始路径: {test_file_path_raw}）</li>' if not test_file_path else ''}
                        </ul>
                        <div style="margin-top: 15px; padding: 10px; border-left: 4px solid #dee2e6;">
                            <p style="margin: 0; font-size: 12px; color: #ffffff;"><strong>解决方法:</strong></p>
                            <ul style="margin: 5px 0; padding-left: 20px; font-size: 12px; color: #ffffff;">
                                <li>请在上方下拉框中选择测试模型</li>
                                <li>请点击"浏览..."按钮选择测试图片或视频文件</li>
                                <li>确保选择的文件存在且可访问</li>
                            </ul>
                        </div>
                    </div>
                    """
                    self.training_panel.display_panel.setHtml(error_html)
                
                DialogManager.show_warning(
                    self.training_panel,
                    "参数缺失",
                    error_msg + '请在上方下拉框中选择测试模型，并点击"浏览..."按钮选择测试文件'
                )
                return
            
            # 检查模型文件是否存在
            if not os.path.exists(test_model_path):
                error_msg = f"模型文件不存在: {test_model_path}"
                print(f"[模型测试] 错误: {error_msg}")
                DialogManager.show_warning(
                    self.training_panel,
                    "模型文件缺失",
                    error_msg
                )
                return
            
            # 检查测试文件是否存在
            if not os.path.exists(test_file_path):
                error_msg = f"测试文件不存在: {test_file_path}"
                print(f"[模型测试] 错误: {error_msg}")
                DialogManager.show_warning(
                    self.training_panel,
                    "测试文件缺失",
                    error_msg
                )
                return
            
            print(f"[模型测试] 文件验证通过")
            
            # 关键修复：先定义 annotation_file 变量，再在HTML中使用
            project_root = get_project_root()
            annotation_file = os.path.join(project_root, 'database', 'config', 'model_test_annotation_result.yaml')
            
            print(f"[模型测试] 标注文件路径: {annotation_file}")
            print(f"[模型测试] 标注文件存在: {os.path.exists(annotation_file)}")
            
            # 显示测试开始提示
            if hasattr(self.training_panel, 'display_panel'):
                start_html = f"""
                <div style="padding: 15px; background: #000000; border: 1px solid #dee2e6; border-radius: 5px; color: #ffffff;">
                    <h3 style="margin-top: 0; color: #ffffff;">正在执行模型测试...</h3>
                    <p style="color: #ffffff;"><strong>测试模型:</strong> {test_model_display}</p>
                    <p style="color: #ffffff;"><strong>模型路径:</strong> {test_model_path}</p>
                    <p style="color: #ffffff;"><strong>测试文件:</strong> {test_file_display}</p>
                    <p style="color: #ffffff;"><strong>文件路径:</strong> {test_file_path}</p>
                    <p style="color: #ffffff;"><strong>标注文件:</strong> {annotation_file}</p>
                    <p style="color: #ffffff;"><strong>标注文件存在:</strong> {'是' if os.path.exists(annotation_file) else '否'}</p>
                    <div style="margin-top: 15px; padding: 10px; border-left: 4px solid #dee2e6;">
                        <p style="margin: 0; font-size: 12px; color: #ffffff;">正在执行液位检测测试，请稍候...</p>
                    </div>
                </div>
                """
                self.training_panel.display_panel.setHtml(start_html)
            
            # 创建进度对话框（使用模块级别的DialogManager）
            progress_dialog = DialogManager.create_progress_dialog(
                parent=self.training_panel,
                title="模型测试进度",
                label_text="正在准备测试...",
                icon_name="model",
                cancelable=True
            )
            
            # 应用全局进度条样式管理器到进度对话框中的进度条
            try:
                progress_bar = progress_dialog.findChild(QtWidgets.QProgressBar)
                if progress_bar:
                    ProgressBarStyleManager.applyToProgressBar(progress_bar)
            except Exception:
                pass
            
            progress_dialog.setValue(0)
            QtWidgets.QApplication.processEvents()
            
            # 检查标注结果文件是否存在
            progress_dialog.setLabelText("正在检查标注文件...")
            progress_dialog.setValue(10)
            QtWidgets.QApplication.processEvents()
            
            if not os.path.exists(annotation_file):
                progress_dialog.close()
                error_msg = f"标注数据文件不存在: {annotation_file}"
                print(f"[模型测试] 错误: {error_msg}")
                DialogManager.show_warning(
                    self.training_panel,
                    "标注数据缺失",
                    "请先点击【开始标注】按钮完成标注操作\n\n" + error_msg
                )
                return
            
            # 检查是否为视频文件
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
            is_video = os.path.isfile(test_file_path) and any(test_file_path.lower().endswith(ext) for ext in video_extensions)
            
            print(f"[模型测试] 测试文件类型: {'视频' if is_video else '图片/文件夹'}")
            
            if is_video:
                # 视频文件：由于涉及实时播放器UI，保持在主线程执行
                print(f"[模型测试] 视频检测将在主线程执行（涉及UI播放器）")
                progress_dialog.setLabelText("正在加载视频文件...")
                progress_dialog.setValue(20)
                QtWidgets.QApplication.processEvents()
                
                try:
                    self._performVideoFrameDetection(test_model_path, test_file_path, annotation_file, progress_dialog)
                    print(f"[模型测试] 视频检测完成")
                except Exception as detection_error:
                    progress_dialog.close()
                    error_msg = f"[模型测试] 视频检测失败: {detection_error}"
                    print(error_msg)
                    import traceback
                    traceback.print_exc()
                    QtWidgets.QMessageBox.critical(
                        self.training_panel,
                        "视频检测失败",
                        f"视频逐帧检测失败：\n{str(detection_error)}"
                    )
                    return
            else:
                # 图片文件：使用后台线程执行，避免阻塞UI
                print(f"[模型测试] 图片检测将在后台线程执行")
                
                # 保存进度对话框引用
                self._test_progress_dialog = progress_dialog
                
                # 创建测试参数
                test_params = {
                    'model_path': test_model_path,
                    'test_file_path': test_file_path,
                    'annotation_file': annotation_file,
                    'is_video': is_video,
                    'handler': self
                }
                
                # 创建并启动后台测试线程
                print(f"[模型测试] 创建后台测试线程...")
                self._test_thread = ModelTestThread(test_params)
                
                # 连接信号
                self._test_thread.progress_updated.connect(self._onTestProgressUpdated)
                self._test_thread.test_finished.connect(self._onTestFinished)
                self._test_thread.error_occurred.connect(self._onTestError)
                
                # 启动线程
                print(f"[模型测试] 启动后台测试线程...")
                self._test_thread.start()
                
                print(f"[模型测试] 测试线程已启动，UI主线程不会被阻塞")
            
        except Exception as e:
            print(f"[模型测试] 启动测试失败: {e}")
            import traceback
            traceback.print_exc()
            if self._test_progress_dialog:
                self._test_progress_dialog.close()
            
            # 将常见的英文错误信息翻译为中文
            error_msg = str(e)
            if "cannot access local variable" in error_msg and "DialogManager" in error_msg:
                error_msg = "对话框管理器未正确初始化\n请重启应用程序或联系技术支持"
            elif "DialogManager" in error_msg:
                error_msg = f"对话框管理器错误\n原始错误: {error_msg}"
            elif "not associated with a value" in error_msg:
                error_msg = "变量未正确初始化\n请重启应用程序"
            
            QtWidgets.QMessageBox.critical(
                self.training_panel,
                "测试启动失败",
                f"无法启动模型测试：\n{error_msg}"
            )
    
    def _onTestProgressUpdated(self, value, text):
        """测试进度更新回调"""
        if self._test_progress_dialog and not self._test_progress_dialog.wasCanceled():
            try:
                self._test_progress_dialog.setValue(value)
                self._test_progress_dialog.setLabelText(text)
                QtWidgets.QApplication.processEvents()
            except (AttributeError, RuntimeError) as e:
                # 进度对话框可能已被关闭
                print(f"[模型测试] 进度更新失败（对话框可能已关闭）: {e}")
    
    def _onTestFinished(self, success, message):
        """测试完成回调"""
        print(f"[模型测试] 测试完成: success={success}, message={message}")
        
        if self._test_progress_dialog:
            self._test_progress_dialog.setValue(100)
            self._test_progress_dialog.close()
            self._test_progress_dialog = None
        
        if success and self._test_thread:
            # 获取检测结果
            detection_result = self._test_thread.get_detection_result()
            
            if detection_result:
                # 显示检测结果
                self._showDetectionResult(detection_result)
                
                # 🔥 添加曲线数据点
                if 'liquid_line_positions' in detection_result:
                    liquid_positions = detection_result['liquid_line_positions']
                    if liquid_positions and 0 in liquid_positions:
                        # 获取第一个区域的液位高度
                        liquid_level = liquid_positions[0]['height_mm']
                        # 图片测试只有一个数据点，帧序号为0
                        self._addCurveDataPoint(0, liquid_level)
                        
                        # 启用查看曲线按钮（不自动显示曲线面板）
                        if hasattr(self.training_panel, 'enableViewCurveButton'):
                            self.training_panel.enableViewCurveButton()
            
            QtWidgets.QMessageBox.information(
                self.training_panel,
                "测试完成",
                "模型测试已成功完成！可查看曲线分析结果。"
            )
        
        # 恢复按钮状态
        if hasattr(self.training_panel, 'setTestButtonState'):
            self.training_panel.setTestButtonState(False)
        
        # 清理线程
        if self._test_thread:
            self._test_thread.wait()
            self._test_thread = None
    
    def _onTestError(self, error_type, error_message):
        """测试错误回调"""
        print(f"[模型测试] 测试错误: {error_type} - {error_message}")
        
        if self._test_progress_dialog:
            self._test_progress_dialog.close()
            self._test_progress_dialog = None
        
        # 显示错误信息
        QtWidgets.QMessageBox.critical(
            self.training_panel,
            f"测试失败 - {error_type}",
            f"模型测试过程中发生错误：\n\n{error_message}\n\n"
            f"请检查：\n"
            f"1. 模型文件是否完整\n"
            f"2. 标注数据是否正确\n"
            f"3. 测试文件是否可访问"
        )
        
        # 恢复按钮状态
        if hasattr(self.training_panel, 'setTestButtonState'):
            self.training_panel.setTestButtonState(False)
        
        # 清理线程
        if self._test_thread:
            self._test_thread.wait()
            self._test_thread = None
    
    def _addCurveDataPoint(self, frame_index, height_mm):
        """添加曲线数据点
        
        Args:
            frame_index: 帧序号
            height_mm: 液位高度（毫米）
        """
        try:
            if hasattr(self.training_panel, 'addCurvePoint'):
                self.training_panel.addCurvePoint(frame_index, height_mm)
                print(f"[曲线] 添加数据点: 帧{frame_index}, 液位{height_mm:.1f}mm")
        except Exception as e:
            print(f"[曲线] 添加数据点失败: {e}")
    
    def _clearCurve(self):
        """清空曲线数据"""
        try:
            if hasattr(self.training_panel, '_clearCurve'):
                self.training_panel._clearCurve()
                print(f"[曲线] 已清空曲线")
        except Exception as e:
            print(f"[曲线] 清空曲线失败: {e}")
    
    def _showDetectionResult(self, detection_result):
        """显示检测结果"""
        try:
            print(f"[模型测试] 显示检测结果...")
            # 这里可以添加结果显示逻辑
            # 例如在display_panel中显示检测结果
            if hasattr(self.training_panel, 'display_panel') and detection_result:
                # 提取液位高度
                liquid_level = 0
                if 'liquid_line_positions' in detection_result:
                    liquid_positions = detection_result['liquid_line_positions']
                    if liquid_positions and 0 in liquid_positions:
                        liquid_level = liquid_positions[0]['height_mm']
                
                result_html = f"""
                <div style="padding: 15px; background: #000000; border: 1px solid #28a745; border-radius: 5px; color: #ffffff;">
                    <h3 style="margin-top: 0; color: #28a745;">液位检测测试成功</h3>
                    <p style="color: #ffffff;"><strong>检测结果:</strong> 已完成液位检测</p>
                    <p style="color: #ffffff;"><strong>液位高度:</strong> {liquid_level:.1f} mm</p>
                    <div style="margin-top: 15px; padding: 10px; background: #1a1a1a; border-radius: 3px;">
                        <p style="margin: 0; font-size: 12px; color: #ffffff;">检测结果已完成，点击“查看曲线”按钮可查看详细分析。</p>
                    </div>
                </div>
                """
                self.training_panel.display_panel.setHtml(result_html)
        except Exception as e:
            print(f"[模型测试] 显示检测结果失败: {e}")
    
    def _loadTestFrame(self, test_file_path):
        """加载测试帧（增强版，包含详细调试信息）"""
        try:
            from PIL import Image
            
            print(f"[测试帧加载] 开始加载: {test_file_path}")
            
            test_path = Path(test_file_path)
            print(f"[测试帧加载] 路径存在: {test_path.exists()}")
            print(f"[测试帧加载] 是文件: {test_path.is_file()}")
            print(f"[测试帧加载] 是文件夹: {test_path.is_dir()}")
            
            if not test_path.exists():
                print(f"[测试帧加载] 错误: 路径不存在")
                return None
            
            if test_path.is_file():
                print(f"[测试帧加载] 处理文件: {test_path.name}")
                # 视频格式
                video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
                image_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
                
                file_ext = test_path.suffix.lower()
                print(f"[测试帧加载] 文件扩展名: {file_ext}")
                
                if file_ext in video_extensions:
                    print(f"[测试帧加载] 识别为视频文件，读取第10帧")
                    # 读取视频的第10帧
                    cap = cv2.VideoCapture(str(test_path))
                    if cap.isOpened():
                        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        print(f"[测试帧加载] 视频总帧数: {total_frames}")
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 9)
                        ret, frame = cap.read()
                        cap.release()
                        if ret:
                            print(f"[测试帧加载] 视频帧读取成功，尺寸: {frame.shape}")
                            return frame
                        else:
                            print(f"[测试帧加载] 视频帧读取失败")
                    else:
                        print(f"[测试帧加载] 视频文件打开失败")
                elif file_ext in image_formats:
                    print(f"[测试帧加载] 识别为图片文件")
                    # 修复：处理中文路径问题
                    # cv2.imread()不支持中文路径，使用numpy+PIL作为备选方案
                    try:
                        frame = cv2.imread(str(test_path))
                        if frame is not None:
                            print(f"[测试帧加载] 图片读取成功，尺寸: {frame.shape}")
                            return frame
                        else:
                            print(f"[测试帧加载] cv2.imread失败，尝试使用PIL读取...")
                            # 备选方案：使用PIL读取
                            try:
                                pil_image = Image.open(test_file_path)
                                frame = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                                print(f"[测试帧加载] PIL读取成功，尺寸: {frame.shape}")
                                return frame
                            except Exception as pil_e:
                                print(f"[测试帧加载] PIL读取也失败: {pil_e}")
                    except Exception as cv2_e:
                        print(f"[测试帧加载] cv2读取异常: {cv2_e}")
                        # 再次尝试PIL
                        try:
                            pil_image = Image.open(test_file_path)
                            frame = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                            print(f"[测试帧加载] PIL读取成功，尺寸: {frame.shape}")
                            return frame
                        except Exception as pil_e:
                            print(f"[测试帧加载] PIL读取也失败: {pil_e}")
                else:
                    print(f"[测试帧加载] 不支持的文件格式: {file_ext}")
                    
            elif test_path.is_dir():
                print(f"[测试帧加载] 处理文件夹: {test_path.name}")
                # 读取文件夹内第一张图片
                image_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
                
                try:
                    files_in_dir = os.listdir(test_file_path)
                    print(f"[测试帧加载] 文件夹内容: {files_in_dir}")
                    
                    if not files_in_dir:
                        print(f"[测试帧加载] 错误: 文件夹为空")
                        return None
                    
                    image_files = []
                    for file in files_in_dir:
                        if any(file.lower().endswith(fmt) for fmt in image_formats):
                            image_files.append(file)
                    
                    print(f"[测试帧加载] 找到图片文件: {image_files}")
                    
                    if not image_files:
                        print(f"[测试帧加载] 错误: 文件夹中没有图片文件")
                        return None
                    
                    # 尝试读取第一张图片
                    first_image = image_files[0]
                    first_image_path = os.path.join(test_file_path, first_image)
                    print(f"[测试帧加载] 尝试读取: {first_image_path}")
                    
                    # 修复：处理中文路径问题
                    try:
                        frame = cv2.imread(first_image_path)
                        if frame is not None:
                            print(f"[测试帧加载] 文件夹图片读取成功，尺寸: {frame.shape}")
                            return frame
                        else:
                            print(f"[测试帧加载] cv2.imread失败，尝试使用PIL读取...")
                            # 备选方案：使用PIL读取
                            try:
                                from PIL import Image
                                pil_image = Image.open(first_image_path)
                                frame = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                                print(f"[测试帧加载] PIL读取成功，尺寸: {frame.shape}")
                                return frame
                            except Exception as pil_e:
                                print(f"[测试帧加载] PIL读取也失败: {pil_e}")
                    except Exception as cv2_e:
                        print(f"[测试帧加载] cv2读取异常: {cv2_e}")
                        # 再次尝试PIL
                        try:
                            from PIL import Image
                            pil_image = Image.open(first_image_path)
                            frame = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                            print(f"[测试帧加载] PIL读取成功，尺寸: {frame.shape}")
                            return frame
                        except Exception as pil_e:
                            print(f"[测试帧加载] PIL读取也失败: {pil_e}")
                        
                except Exception as dir_error:
                    print(f"[测试帧加载] 文件夹处理异常: {dir_error}")
            else:
                print(f"[测试帧加载] 错误: 路径不是文件也不是文件夹")
            
            print(f"[测试帧加载] 最终结果: 加载失败")
            return None
            
        except Exception as e:
            print(f"[测试帧加载] 异常: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _performTestDetection(self, model_path, test_frame, annotation_file, progress_dialog=None):
        """通过服务端API执行液位检测测试"""
        try:
            print(f"\n[液位检测] ========== 开始液位检测测试 ==========")
            print(f"[液位检测] 模型路径: {model_path}")
            print(f"[液位检测] 测试帧尺寸: {test_frame.shape}")
            print(f"[液位检测] 标注文件: {annotation_file}")
            
            # 连接服务端
            if progress_dialog:
                progress_dialog.setLabelText("正在连接服务端...")
                progress_dialog.setValue(40)
                QtWidgets.QApplication.processEvents()
            
            print(f"[液位检测] 正在连接服务端...")
            
            # 导入远程配置管理器
            from client.utils.config import RemoteConfigManager
            remote_config = RemoteConfigManager()
            ssh_manager = remote_config._get_ssh_manager()
            
            if not ssh_manager:
                raise RuntimeError("SSH连接不可用")
            
            print(f"[液位检测] 服务端连接成功")
            
            # 读取标注数据
            print(f"[液位检测] 开始读取标注文件: {annotation_file}")
            
            try:
                with open(annotation_file, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                    print(f"[液位检测] 文件内容预览: {file_content[:200]}...")
                
                # 关键修复：处理Python tuple标签问题
                print(f"[液位检测] 开始解析YAML文件...")
                
                # 首先尝试safe_load
                try:
                    with open(annotation_file, 'r', encoding='utf-8') as f:
                        annotation_data = yaml.safe_load(f)
                    print(f"[液位检测] 使用safe_load解析成功")
                except yaml.constructor.ConstructorError as constructor_error:
                    if 'python/tuple' in str(constructor_error):
                        print(f"[液位检测] 检测到Python tuple标签，使用unsafe_load解析...")
                        with open(annotation_file, 'r', encoding='utf-8') as f:
                            annotation_data = yaml.unsafe_load(f)
                        print(f"[液位检测] 使用unsafe_load解析成功")
                    else:
                        print(f"[液位检测] YAML构造器错误: {constructor_error}")
                        raise
                except yaml.YAMLError as yaml_error:
                    print(f"[液位检测] YAML解析错误: {yaml_error}")
                    try:
                        print(f"[液位检测] 尝试使用unsafe_load作为备选方案...")
                        with open(annotation_file, 'r', encoding='utf-8') as f:
                            annotation_data = yaml.unsafe_load(f)
                        print(f"[液位检测] unsafe_load备选方案成功")
                    except Exception as e2:
                        print(f"[液位检测] unsafe_load备选方案也失败: {e2}")
                        raise yaml_error
                
                print(f"[液位检测] YAML解析成功")
                print(f"[液位检测] 加载标注数据: {annotation_data}")
                
            except Exception as e:
                print(f"[液位检测] 读取标注文件失败: {e}")
                import traceback
                traceback.print_exc()
                raise
            
            # 创建检测引擎
            if progress_dialog:
                progress_dialog.setLabelText("正在创建检测引擎...")
                progress_dialog.setValue(50)
                QtWidgets.QApplication.processEvents()
            
            print(f"[液位检测] 正在创建检测引擎...")
            try:
                detection_engine = LiquidDetectionEngine(model_path=model_path)
                print(f"[液位检测] 检测引擎创建成功")
                
                if progress_dialog:
                    progress_dialog.setLabelText("正在加载模型权重...")
                    progress_dialog.setValue(60)
                    QtWidgets.QApplication.processEvents()
                
                print(f"[液位检测] 正在加载模型权重...")
                if not detection_engine.load_model(model_path):
                    raise RuntimeError(f"模型加载失败: {model_path}")
                print(f"[液位检测] 模型权重加载成功")
                
            except Exception as engine_error:
                print(f"[液位检测] 检测引擎创建或加载失败: {engine_error}")
                import traceback
                traceback.print_exc()
                raise
            
            # 配置标注数据
            if progress_dialog:
                progress_dialog.setLabelText("正在解析标注数据...")
                progress_dialog.setValue(70)
                QtWidgets.QApplication.processEvents()
            
            print(f"[测试检测] 开始解析标注数据...")
            test_data = annotation_data['test_model']
            print(f"[测试检测] test_data keys: {test_data.keys()}")
            
            boxes = test_data.get('boxes', [])
            bottoms = test_data.get('bottoms', [])
            tops = test_data.get('tops', [])
            init_levels = test_data.get('init_levels', [])
            
            print(f"[测试检测] 原始数据:")
            print(f"  - boxes: {boxes} (类型: {type(boxes)})")
            print(f"  - bottoms: {bottoms} (类型: {type(bottoms)})")
            print(f"  - tops: {tops} (类型: {type(tops)})")
            print(f"  - init_levels: {init_levels} (类型: {type(init_levels)})")
            
            # 关键修复：确保数据格式正确并进行详细验证
            print(f"[液位检测] 开始验证和转换数据格式...")
            try:
                # 验证boxes数据
                if not boxes:
                    raise ValueError("boxes数据为空，请检查标注配置")
                
                # 转换为正确的格式
                boxes_converted = []
                for i, box in enumerate(boxes):
                    if isinstance(box, (tuple, list)) and len(box) >= 3:
                        converted_box = tuple(box[:3])
                        boxes_converted.append(converted_box)
                        print(f"[液位检测] Box {i+1}: {converted_box}")
                    else:
                        error_msg = f"无效的box数据 {i+1}: {box} (类型: {type(box)}, 长度: {len(box) if hasattr(box, '__len__') else 'N/A'})"
                        print(f"[液位检测] 错误: {error_msg}")
                        raise ValueError(error_msg)
                        
                # 验证bottoms数据
                if not bottoms:
                    raise ValueError("bottoms数据为空，请检查标注配置")
                    
                bottoms_converted = []
                for i, bottom in enumerate(bottoms):
                    if isinstance(bottom, (tuple, list)) and len(bottom) >= 2:
                        converted_bottom = tuple(bottom[:2])
                        bottoms_converted.append(converted_bottom)
                        print(f"[液位检测] Bottom {i+1}: {converted_bottom}")
                    else:
                        error_msg = f"无效的bottom数据 {i+1}: {bottom} (类型: {type(bottom)}, 长度: {len(bottom) if hasattr(bottom, '__len__') else 'N/A'})"
                        print(f"[液位检测] 错误: {error_msg}")
                        raise ValueError(error_msg)
                        
                # 验证tops数据
                if not tops:
                    raise ValueError("tops数据为空，请检查标注配置")
                    
                tops_converted = []
                for i, top in enumerate(tops):
                    if isinstance(top, (tuple, list)) and len(top) >= 2:
                        converted_top = tuple(top[:2])
                        tops_converted.append(converted_top)
                        print(f"[液位检测] Top {i+1}: {converted_top}")
                    else:
                        error_msg = f"无效的top数据 {i+1}: {top} (类型: {type(top)}, 长度: {len(top) if hasattr(top, '__len__') else 'N/A'})"
                        print(f"[液位检测] 错误: {error_msg}")
                        raise ValueError(error_msg)
                
                # 验证数据数量一致性
                if not (len(boxes_converted) == len(bottoms_converted) == len(tops_converted)):
                    error_msg = f"数据数量不一致: boxes={len(boxes_converted)}, bottoms={len(bottoms_converted)}, tops={len(tops_converted)}"
                    print(f"[液位检测] 错误: {error_msg}")
                    raise ValueError(error_msg)
                
                boxes = boxes_converted
                bottoms = bottoms_converted
                tops = tops_converted
                
                print(f"[液位检测] 数据验证和转换成功:")
                print(f"  - ROI数量: {len(boxes)}")
                print(f"  - boxes: {boxes}")
                print(f"  - bottoms: {bottoms}")
                print(f"  - tops: {tops}")
                
            except Exception as e:
                print(f"[液位检测] 数据验证和转换失败: {e}")
                import traceback
                traceback.print_exc()
                raise ValueError(f"标注数据格式错误: {e}")
            
            # 提取实际高度配置
            print(f"[液位检测] 开始提取区域高度配置...")
            actual_heights = []
            areas = test_data.get('areas', {})
            print(f"[液位检测] areas配置: {areas}")
            
            if not areas:
                print(f"[液位检测] 警告: 未找到areas配置，将使用默认高度")
            
            for i, box in enumerate(boxes):
                area_key = f'area_{i+1}'
                print(f"[液位检测] 处理区域 {i+1} (key: {area_key})...")
                
                if area_key in areas:
                    area_config = areas[area_key]
                    print(f"[液位检测] 区域 {i+1} 配置: {area_config}")
                    
                    height_str = area_config.get('height', '20mm')
                    area_name = area_config.get('name', f'区域{i+1}')
                    
                    try:
                        if isinstance(height_str, (int, float)):
                            height_value = float(height_str)
                        else:
                            height_clean = str(height_str).replace('mm', '').replace('cm', '').replace('m', '').strip()
                            height_value = float(height_clean)
                        
                        actual_heights.append(height_value)
                        print(f"[液位检测] 区域 {i+1} ({area_name}): {height_value}mm")
                    except (ValueError, TypeError) as e:
                        print(f"[液位检测] 警告: 区域 {i+1} 高度解析失败 ({height_str}): {e}，使用默认值")
                        actual_heights.append(20.0)
                else:
                    actual_heights.append(20.0)
                    print(f"[液位检测] 区域 {i+1} 未找到配置，使用默认高度: 20.0mm")
            
            # 验证高度数量
            if len(actual_heights) != len(boxes):
                error_msg = f"高度配置数量 ({len(actual_heights)}) 与ROI数量 ({len(boxes)}) 不匹配"
                print(f"[液位检测] 错误: {error_msg}")
                raise ValueError(error_msg)
            
            # 提取初始液位线y坐标
            fixed_init_levels = []
            for level in init_levels:
                if isinstance(level, (tuple, list)) and len(level) >= 2:
                    fixed_init_levels.append(level[1])
                elif isinstance(level, (int, float)):
                    fixed_init_levels.append(level)
            
            print(f"[液位检测] 最终配置数据:")
            print(f"  - ROI数量: {len(boxes)}")
            print(f"  - boxes: {boxes}")
            print(f"  - bottoms: {bottoms}")
            print(f"  - tops: {tops}")
            print(f"  - actual_heights: {actual_heights}")
            print(f"  - fixed_init_levels: {fixed_init_levels}")
            
            # 配置检测引擎
            print(f"[液位检测] 开始配置检测引擎...")
            try:
                detection_engine.configure(boxes, bottoms, tops, actual_heights, fixed_init_levels)
                print(f"[液位检测] 检测引擎配置完成")
            except Exception as config_error:
                print(f"[液位检测] 检测引擎配置失败: {config_error}")
                import traceback
                traceback.print_exc()
                raise ValueError(f"检测引擎配置失败: {config_error}")
            
            print(f"[液位检测] 准备执行液位检测...")
            print(f"[液位检测] 测试帧信息: 尺寸={test_frame.shape}, 类型={test_frame.dtype}")
            
            # 执行检测
            if progress_dialog:
                progress_dialog.setLabelText("正在执行液位检测...")
                progress_dialog.setValue(80)
                QtWidgets.QApplication.processEvents()
            
            print(f"[液位检测] 开始执行液位检测...")
            try:
                detection_result = detection_engine.detect(test_frame)
                print(f"[液位检测] 检测执行完成")
                
                if progress_dialog:
                    progress_dialog.setLabelText("正在生成检测结果...")
                    progress_dialog.setValue(90)
                    QtWidgets.QApplication.processEvents()
                
                # 增强调试：详细分析检测结果
                print(f"[液位检测] 检测结果类型: {type(detection_result)}")
                print(f"[液位检测] 检测结果是否为None: {detection_result is None}")
                print(f"[液位检测] 检测结果详情: {detection_result}")
                
                # 检查检测结果的有效性
                is_valid_result = False
                if detection_result:
                    if isinstance(detection_result, dict) and 'areas' in detection_result:
                        areas_data = detection_result['areas']
                        if areas_data and len(areas_data) > 0:
                            is_valid_result = True
                            print(f"[液位检测] 检测到有效结果: {len(areas_data)} 个区域")
                        else:
                            print(f"[液位检测] areas字段为空: {areas_data}")
                    else:
                        print(f"[液位检测] 检测结果格式异常: 缺少areas字段或不是字典")
                else:
                    print(f"[液位检测] 检测结果为空或None")
                
                if is_valid_result:
                    print(f"[液位检测] 检测成功！")
                    
                    if 'areas' in detection_result:
                        print(f"[液位检测] 检测到 {len(detection_result['areas'])} 个区域的液位")
                        for area_name, area_data in detection_result['areas'].items():
                            if 'liquid_height' in area_data:
                                height = area_data['liquid_height']
                                print(f"[液位检测] {area_name}: {height}mm")
                    
                    self._showTestDetectionResult(test_frame, detection_result, boxes, bottoms, tops, actual_heights)
                    print(f"[液位检测] 检测结果已显示在右侧面板中")
                    
                else:
                    print(f"[液位检测] 检测失败：未获得有效结果")
                    print(f"[液位检测] 可能原因:")
                    print(f"  1. 模型无法检测到目标物体（置信度过低）")
                    print(f"  2. ROI设置不正确（位置偏移）")
                    print(f"  3. 图像质量或光照条件不佳")
                    
                    self._showTestDetectionResult(test_frame, None, boxes, bottoms, tops, actual_heights)
                    print(f"[液位检测] 原始图像和标注信息已显示在右侧面板中")
                    
                    
            except Exception as detect_error:
                print(f"[液位检测] 检测执行异常: {detect_error}")
                import traceback
                traceback.print_exc()
                
                try:
                    self._showTestDetectionResult(test_frame, None, boxes, bottoms, tops, actual_heights)
                    print(f"[液位检测] 原始图像已显示（检测失败）")
                except Exception as show_error:
                    print(f"[液位检测] 显示原始图像也失败: {show_error}")
                
                raise
                
        except Exception as e:
            print(f"[液位检测] 液位检测测试失败: {e}")
            import traceback
            traceback.print_exc()
            
            error_details = [
                f"错误类型: {type(e).__name__}",
                f"错误信息: {str(e)}",
                f"模型路径: {model_path}",
                f"标注文件: {annotation_file}",
            ]
            
            error_report = "\n".join(error_details)
            print(f"[液位检测] 错误详情:\n{error_report}")
            
            QtWidgets.QMessageBox.critical(
                self.training_panel,
                "液位检测执行失败",
                f"执行液位检测时发生错误：\n\n{str(e)}\n\n"
                f"详细信息：\n{error_report}\n\n"
                f"建议检查：\n"
                f"1. 检测引擎模块是否正确安装\n"
                f"2. 模型文件格式是否正确\n"
                f"3. 标注数据格式是否有效\n"
                f"4. 系统依赖库是否完整"
            )
    
    def _performVideoFrameDetection(self, model_path, video_path, annotation_file, progress_dialog=None):
        """执行视频逐帧液位检测测试"""
        try:
            import tempfile
            from datetime import datetime
            
            print(f"\n[视频检测] 开始视频逐帧液位检测")
            print(f"[视频检测] 视频路径: {video_path}")
            print(f"[视频检测] 模型路径: {model_path}")
            
            # 打开视频文件
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise RuntimeError(f"无法打开视频文件: {video_path}")
            
            # 获取视频信息
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            original_fps = cap.get(cv2.CAP_PROP_FPS)  # 原始视频帧率（仅供参考）
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            print(f"[视频检测] 视频信息: {total_frames}帧, 原始帧率{original_fps}fps, {width}x{height}")
            print(f"[视频检测] 将根据实际检测速度自适应计算输出帧率")
            
            # 导入检测引擎
            try:
                from ...handlers.videopage.detection.detection import LiquidDetectionEngine
            except ImportError:
                from handlers.videopage.detection.detection import LiquidDetectionEngine
            
            # 读取标注数据
            try:
                with open(annotation_file, 'r', encoding='utf-8') as f:
                    annotation_data = yaml.safe_load(f)
            except yaml.constructor.ConstructorError:
                with open(annotation_file, 'r', encoding='utf-8') as f:
                    annotation_data = yaml.unsafe_load(f)
            
            # 获取标注信息
            test_model_key = 'test_model'
            if test_model_key not in annotation_data:
                raise ValueError(f"标注文件中没有 {test_model_key} 数据")
            
            boxes = annotation_data[test_model_key].get('boxes', [])
            bottoms = annotation_data[test_model_key].get('bottoms', [])
            tops = annotation_data[test_model_key].get('tops', [])
            init_levels = annotation_data[test_model_key].get('init_levels', [])
            
            print(f"[视频检测] 标注信息: {len(boxes)}个区域")
            
            # 提取Y坐标
            fixed_bottoms = [bottom[1] if isinstance(bottom, (tuple, list)) else bottom for bottom in bottoms]
            fixed_tops = [top[1] if isinstance(top, (tuple, list)) else top for top in tops]
            fixed_init_levels = [level[1] if isinstance(level, (tuple, list)) else level for level in init_levels]
            
            # 🔥 调试：打印标注数据
            print(f"\n{'='*60}")
            print(f"[标注数据验证] 检查容器标注坐标")
            print(f"{'='*60}")
            for i in range(len(boxes)):
                if i < len(fixed_bottoms) and i < len(fixed_tops):
                    print(f"区域{i}:")
                    print(f"  - top (容器顶部) Y坐标: {fixed_tops[i]}")
                    print(f"  - bottom (容器底部) Y坐标: {fixed_bottoms[i]}")
                    container_height_px = fixed_bottoms[i] - fixed_tops[i]
                    print(f"  - 容器像素高度: {container_height_px}px")
                    if container_height_px < 0:
                        print(f"  [警告] 容器高度为负数！top 和 bottom 可能标反了！")
            print(f"{'='*60}\n")
            
            # 初始化检测引擎
            detection_engine = LiquidDetectionEngine(model_path)
            detection_engine.load_model(model_path)
            
            # 配置标注数据
            actual_heights = annotation_data[test_model_key].get('actual_heights', [20.0] * len(boxes))
            print(f"[标注数据验证] 容器实际高度: {actual_heights}")
            print(f"[标注数据验证] 初始液位线: {fixed_init_levels}")
            detection_engine.configure(boxes, fixed_bottoms, fixed_tops, actual_heights, fixed_init_levels)
            
            # 暂不创建输出视频，先进行检测以计算实际帧率
            temp_dir = tempfile.gettempdir()
            output_video_path = os.path.join(temp_dir, "detection_result.mp4")
            out = None  # 稍后根据实际检测速度创建
            
            print(f"[视频检测] 输出视频路径: {output_video_path}")
            
            # 暂不创建实时播放器，等计算出实际帧率后再创建
            actual_fps = None
            
            # 存储检测结果统计
            frame_results = {}
            last_detection_result = None
            detection_count = 0
            success_count = 0
            fail_count = 0
            
            # 🔥 清空曲线数据，准备添加新的视频检测曲线
            self._clearCurve()
            
            # 关闭进度对话框
            if progress_dialog:
                progress_dialog.setLabelText("正在检测中...")
                progress_dialog.setValue(100)
                QtWidgets.QApplication.processEvents()
                import time
                time.sleep(0.3)
                progress_dialog.close()
                print(f"[视频检测] 进度对话框已关闭")
            
            # 逐帧处理
            frame_index = 0
            detection_interval = 3  # 每3帧检测一次
            
            # 初始化停止标志
            self._detection_stopped = False
            
            # 用于计算实际检测速度
            import time
            detection_start_time = time.time()
            warmup_frames = 30  # 预热帧数，用于计算稳定的检测速度
            
            print(f"[视频检测] 开始逐帧处理，检测间隔: 每{detection_interval}帧")
            print(f"[视频检测] 将在处理{warmup_frames}帧后计算实际检测帧率")
            
            while True:
                # 检查停止标志
                if self._detection_stopped:
                    print(f"[视频检测] 检测被停止，当前帧: {frame_index}")
                    break
                
                # 每10帧处理一次UI事件
                if frame_index % 10 == 0:
                    QtWidgets.QApplication.processEvents()
                
                ret, frame = cap.read()
                if not ret:
                    print(f"[视频检测] 视频读取完成，总帧数: {frame_index}")
                    break
                
                # 每detection_interval帧进行一次检测
                if frame_index % detection_interval == 0:
                    try:
                        detection_result = detection_engine.detect(frame)
                        frame_results[frame_index] = detection_result
                        last_detection_result = detection_result
                        detection_count += 1
                        success_count += 1
                        
                        # 🔥 添加曲线数据点（取第一个区域的液位高度）
                        if detection_result and 'liquid_line_positions' in detection_result:
                            liquid_positions = detection_result['liquid_line_positions']
                            if liquid_positions and 0 in liquid_positions:
                                # 获取第一个区域的液位高度
                                liquid_level = liquid_positions[0]['height_mm']
                                self._addCurveDataPoint(frame_index, liquid_level)
                    except Exception as e:
                        print(f"[视频检测] 第 {frame_index} 帧检测失败: {e}")
                        fail_count += 1
                        if last_detection_result:
                            frame_results[frame_index] = last_detection_result
                else:
                    # 使用最后一次的检测结果
                    if last_detection_result:
                        frame_results[frame_index] = last_detection_result
                
                # 获取当前帧的检测结果
                current_detection = frame_results.get(frame_index)
                
                # 绘制液位线
                result_frame = self._drawLiquidLinesOnFrame(frame, current_detection, boxes, bottoms, tops)
                
                # 在预热阶段后，根据实际检测速度创建输出视频
                if frame_index == warmup_frames and out is None:
                    elapsed_time = time.time() - detection_start_time
                    actual_fps = warmup_frames / elapsed_time if elapsed_time > 0 else original_fps
                    # 限制帧率在合理范围内
                    actual_fps = min(actual_fps, original_fps)  # 不超过原始帧率
                    actual_fps = max(actual_fps, 5.0)  # 最低5fps
                    
                    print(f"[视频检测] 实际检测速度: {actual_fps:.1f} FPS（预热{warmup_frames}帧，耗时{elapsed_time:.2f}秒）")
                    print(f"[视频检测] 使用自适应帧率创建输出视频: {actual_fps:.1f} FPS")
                    
                    # 创建输出视频
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    out = cv2.VideoWriter(output_video_path, fourcc, actual_fps, (width, height))
                    
                    if not out.isOpened():
                        raise RuntimeError(f"无法创建输出视频: {output_video_path}")
                    
                    # 创建实时视频播放器界面
                    print(f"[视频检测] 创建实时播放器（帧率: {actual_fps:.1f} FPS）...")
                    self._createRealtimeVideoPlayer(output_video_path, total_frames, actual_fps)
                
                # 写入输出视频
                if out is not None:
                    out.write(result_frame)
                
                # 实时显示检测结果
                if hasattr(self, '_realtime_frame_label'):
                    try:
                        self._updateRealtimeFrame(result_frame)
                        
                        # 每30帧更新一次统计信息
                        if frame_index % 30 == 0:
                            QtWidgets.QApplication.processEvents()
                    except Exception as e:
                        print(f"[视频检测] 实时显示更新失败: {e}")
                
                frame_index += 1
            
            cap.release()
            out.release()
            
            print(f"[视频检测] 检测完成")
            print(f"[视频检测] 处理帧数: {frame_index}")
            print(f"[视频检测] 检测统计: 总检测次数={detection_count}, 成功={success_count}, 失败={fail_count}")
            
            # 保存测试结果到模型目录
            if not self._detection_stopped:
                print(f"[视频检测] 保存测试结果...")
                self._saveVideoTestResults(model_path, video_path, output_video_path, 
                                         frame_index, detection_count, success_count, fail_count, annotation_file)
            
            # 显示检测结果视频
            if not self._detection_stopped:
                print(f"[视频检测] 显示检测结果视频...")
                self._showDetectionVideo(output_video_path, frame_index, detection_count, success_count, fail_count)
                
                # 启用查看曲线按钮（不自动显示曲线面板）
                if hasattr(self.training_panel, 'enableViewCurveButton'):
                    self.training_panel.enableViewCurveButton()
                    print(f"[曲线] 已启用查看曲线按钮，共{len(self.training_panel.curve_data_x if hasattr(self.training_panel, 'curve_data_x') else [])}个数据点")
            else:
                print(f"[视频检测] 检测被用户停止")
            
            # 恢复按钮状态
            if hasattr(self, 'training_panel') and hasattr(self.training_panel, 'setTestButtonState'):
                self.training_panel.setTestButtonState(False)
                print(f"[视频检测] 按钮状态已恢复")
            
        except Exception as e:
            print(f"[视频检测] 检测失败: {e}")
            import traceback
            traceback.print_exc()
            
            # 清理资源
            try:
                if 'cap' in locals() and cap is not None:
                    cap.release()
                if 'out' in locals() and out is not None:
                    out.release()
            except:
                pass
            
            raise
        finally:
            if hasattr(self, '_detection_stopped'):
                print(f"[视频检测] 最终停止标志: {self._detection_stopped}")
    
    def _showTestDetectionResult(self, original_frame, detection_result, boxes, bottoms, tops, actual_heights=None):
        """在显示面板中显示检测结果（带液位线的图像）
        
        Args:
            original_frame: 原始图像帧
            detection_result: 检测结果
            boxes: 检测框列表
            bottoms: 底部线条列表
            tops: 顶部线条列表
            actual_heights: 实际容器高度列表（毫米），如果为None则使用默认值20mm
        """
        try:
            from datetime import datetime
            
            print(f"[检测结果显示] 开始显示检测结果...")
            print(f"[检测结果显示] 原始帧尺寸: {original_frame.shape}")
            print(f"[检测结果显示] ROI数量: {len(boxes)}")
            print(f"[检测结果显示] 检测结果: {detection_result}")
            print(f"[检测结果显示] 容器实际高度: {actual_heights}")
            
            # 如果没有提供actual_heights，使用默认值
            if actual_heights is None:
                actual_heights = [20.0] * len(boxes)
                print(f"[检测结果显示] 未提供容器高度，使用默认值: {actual_heights}")
            
            # 复制原始帧
            result_frame = original_frame.copy()
            
            # 绘制液位线 - 默认为0mm
            for i in range(len(boxes)):
                if i < len(bottoms) and i < len(tops):
                    cx, cy, size = boxes[i]
                    half = size // 2
                    left = cx - half
                    right = cx + half
                    bottom_y = bottoms[i][1]
                    top_y = tops[i][1]
                    
                    # 获取该区域的实际容器高度
                    actual_height = actual_heights[i] if i < len(actual_heights) else 20.0
                    
                    # 提取液位高度（默认为0）
                    liquid_height = 0.0
                    
                    if detection_result and 'areas' in detection_result:
                        area_items = list(detection_result['areas'].items())
                        if i < len(area_items):
                            area_name, area_data = area_items[i]
                            if 'liquid_height' in area_data:
                                liquid_height = area_data['liquid_height']
                                print(f"[检测结果显示] 区域{i+1}: 检测到液位 {liquid_height}mm (容器高度: {actual_height}mm)")
                            else:
                                print(f"[检测结果显示] 区域{i+1}: 未检测到液位，使用默认值 0mm")
                        else:
                            print(f"[检测结果显示] 区域{i+1}: 检测结果中没有对应数据，使用默认值 0mm")
                    else:
                        print(f"[检测结果显示] 区域{i+1}: 无检测结果，使用默认值 0mm")
                    
                    # 计算液位线的Y坐标 - 使用实际容器高度
                    container_height_px = bottom_y - top_y
                    liquid_ratio = min(1.0, max(0.0, liquid_height / actual_height))
                    liquid_y = int(bottom_y - container_height_px * liquid_ratio)
                    
                    # 绘制液位线（红色）
                    cv2.line(result_frame, (left, liquid_y), (right, liquid_y), (0, 0, 255), 3)
                    
                    # 绘制液位高度标签
                    cv2.putText(result_frame, f"{liquid_height:.1f}mm", 
                               (right + 5, liquid_y), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    
                    print(f"[检测结果显示] 区域{i+1}: 绘制液位线 (y={liquid_y}, 高度={liquid_height}mm)")
            
            print(f"[检测结果显示] 液位线绘制完成")
            
            # 转换为RGB格式
            rgb_frame = cv2.cvtColor(result_frame, cv2.COLOR_BGR2RGB)
            
            # 缩放图像
            target_width = 600
            h, w = rgb_frame.shape[:2]
            scale = target_width / w
            new_w = int(w * scale)
            new_h = int(h * scale)
            
            if new_h > 400:
                scale = 400 / new_h
                new_w = int(new_w * scale)
                new_h = int(new_h * scale)
            
            print(f"[检测结果显示] 图像缩放: {w}x{h}, 缩放后: {new_w}x{new_h}")
            
            rgb_frame_resized = cv2.resize(rgb_frame, (new_w, new_h))
            
            # 转换为QImage
            h, w, ch = rgb_frame_resized.shape
            bytes_per_line = ch * w
            qt_image = QtGui.QImage(rgb_frame_resized.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
            
            # 保存到临时文件
            temp_dir = tempfile.gettempdir()
            preview_image_path = os.path.join(temp_dir, "test_detection_result.png")
            qt_image.save(preview_image_path)
            
            # 在显示面板中显示结果
            if hasattr(self.training_panel, 'display_panel'):
                current_time = datetime.now().strftime("%H:%M:%S")
                
                # 切换到显示面板
                if hasattr(self.training_panel, 'display_layout'):
                    self.training_panel.display_layout.setCurrentIndex(1)
                    print(f"[检测结果显示] 已切换到显示面板")
                
                # 生成HTML内容
                html_content = f"""
                <div style="font-family: Arial, sans-serif; padding: 10px;">
                    <div style="margin-bottom: 15px; padding: 10px; background: #d1ecf1; border: 1px solid #bee5eb; border-radius: 5px; color: #0c5460;">
                        <h3 style="margin: 0 0 10px 0; color: #0c5460;">检测完成 ({current_time}) - {len(boxes)}个区域</h3>
                    </div>
                    
                    <div style="text-align: center; margin-bottom: 15px;">
                        <img src="file:///{preview_image_path.replace(chr(92), '/')}" style="max-width: 100%; max-height: 500px; border: 2px solid #dee2e6; border-radius: 4px;">
                    </div>
                    
                    <div style="padding: 10px; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px;">
                        <h4 style="margin-top: 0; color: #495057;">液位检测结果</h4>
                """
                
                # 添加检测结果
                if detection_result and 'areas' in detection_result:
                    html_content += '<p style="color: #28a745; font-weight: bold;">[成功] 液位检测成功</p>'
                    for area_name, area_data in detection_result['areas'].items():
                        if 'liquid_height' in area_data:
                            liquid_height = area_data['liquid_height']
                            html_content += f'<p style="margin: 5px 0;"><strong>{area_name}:</strong> {liquid_height:.1f}mm</p>'
                else:
                    html_content += '<p style="color: #dc3545;">[失败] 液位检测未返回有效结果</p>'
                    for i in range(len(boxes)):
                        html_content += f'<p style="margin: 5px 0;"><strong>区域{i+1}:</strong> 0.0mm</p>'
                
                html_content += """
                    </div>
                </div>
                """
                
                # 设置HTML内容
                if isinstance(self.training_panel.display_panel, QtWidgets.QTextEdit):
                    self.training_panel.display_panel.setHtml(html_content)
                    print(f"[检测结果显示] HTML显示完成")
                else:
                    print(f"[检测结果显示] 警告: display_panel不是QTextEdit类型")
            else:
                print(f"[检测结果显示] 错误: 找不到display_panel")
                
        except Exception as e:
            print(f"[检测结果显示] 显示检测结果失败: {e}")
            import traceback
            traceback.print_exc()
    
    
    def _drawLiquidLinesOnFrame(self, frame, detection_result, boxes, bottoms, tops):
        """在帧上绘制液位线"""
        try:
            # 复制帧
            result_frame = frame.copy()
            h, w = result_frame.shape[:2]
            
            # 标记是否已绘制液位线
            has_drawn_lines = False
            
            # 如果有检测结果，绘制液位线
            if detection_result is not None and 'liquid_line_positions' in detection_result:
                liquid_line_positions = detection_result['liquid_line_positions']
                
                # 绘制每个区域的液位线
                if len(liquid_line_positions) > 0:
                    line_count = 0
                    for idx, position_data in liquid_line_positions.items():
                        if idx < len(boxes) and idx < len(bottoms) and idx < len(tops):
                            # 获取液位线位置信息
                            liquid_y = int(position_data.get('y', 0))
                            height_mm = position_data.get('height_mm', 0.0)
                            
                            # 从boxes计算left和right
                            box = boxes[idx]
                            if len(box) == 3:  # (center_x, center_y, size)
                                cx, cy, size = box
                                half = size // 2
                                left = cx - half
                                right = cx + half
                            else:  # (x, y, w, h)
                                x, y, w, h = box
                                left = x
                                right = x + w
                            
                            # 验证坐标有效性 - 防止越界
                            if left >= 0 and right > left and liquid_y >= 0 and liquid_y < h:
                                # 绘制液位线（红色）
                                cv2.line(result_frame, (int(left), int(liquid_y)), (int(right), int(liquid_y)), (0, 0, 255), 3)
                                
                                # 绘制液位高度标签
                                cv2.putText(result_frame, f"{height_mm:.1f}mm", 
                                        (int(right) + 5, int(liquid_y)), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                                
                                line_count += 1
                                has_drawn_lines = True
                                
                                # 打印调试信息（仅前几帧）
                                if self._draw_debug_count < 5:
                                    print(f"[液位线绘制] 区域{idx}: y={liquid_y}, height={height_mm:.1f}mm")
                                    self._draw_debug_count += 1
            
            # 如果没有检测结果，绘制默认的0mm液位线
            if not has_drawn_lines and len(bottoms) > 0:
                for idx in range(len(boxes)):
                    if idx < len(bottoms):
                        # 在底部绘制0mm液位线
                        bottom_x, bottom_y = bottoms[idx]
                        
                        # 计算液位线的左右边界
                        if idx < len(boxes):
                            cx, cy, size = boxes[idx]
                            half = size // 2
                            left = cx - half
                            right = cx + half
                            
                            # 绘制0mm液位线（黄色）
                            cv2.line(result_frame, (int(left), int(bottom_y)), (int(right), int(bottom_y)), (0, 255, 255), 3)
                            
                            # 绘制0mm标签
                            cv2.putText(result_frame, "0.0mm", 
                                    (int(right) + 5, int(bottom_y)), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                
                # 只显示一次警告
                if not self._yellow_line_warning_shown:
                    print(f"[液位线绘制] 未检测到液位，绘制默认0mm液位线（共{len(bottoms)}个区域）")
                    self._yellow_line_warning_shown = True
            
            return result_frame
            
        except Exception as e:
            print(f"[液位线绘制] 绘制失败: {e}")
            import traceback
            traceback.print_exc()
            return frame
    
    def _createRealtimeVideoPlayer(self, video_path, total_frames, fps=25.0):
        """创建实时视频播放器界面"""
        try:
            from PyQt5.QtGui import QPixmap
            
            print(f"[实时播放器] 创建实时播放器")
            print(f"[实时播放器] 视频路径: {video_path}")
            print(f"[实时播放器] 总帧数: {total_frames}")
            print(f"[实时播放器] 帧率: {fps} fps")
            
            # 检查display_layout是否存在
            if not hasattr(self.training_panel, 'display_layout'):
                print(f"[实时播放器] 错误: 找不到display_layout")
                return
            
            # 创建视频容器
            video_container = QtWidgets.QWidget()
            container_layout = QtWidgets.QVBoxLayout(video_container)
            container_layout.setContentsMargins(15, 15, 15, 15)
            container_layout.setSpacing(10)
            
            # 帧显示区域（使用QLabel）
            frame_label = QtWidgets.QLabel()
            frame_label.setMinimumHeight(400)
            frame_label.setAlignment(QtCore.Qt.AlignCenter)
            frame_label.setStyleSheet("background: black; border: 2px solid #dee2e6; border-radius: 4px;")
            frame_label.setScaledContents(False)
            container_layout.addWidget(frame_label)
            
            # 提示信息
            hint_label = QtWidgets.QLabel(f"实时显示检测结果，帧率 {fps:.1f} fps")
            hint_label.setStyleSheet("color: #666; padding: 5px; font-style: italic;")
            FontManager.applyToWidget(hint_label, size=FontManager.FONT_SIZE_SMALL)
            hint_label.setWordWrap(True)
            container_layout.addWidget(hint_label)
            
            # 保存引用
            self._realtime_frame_label = frame_label
            self._realtime_container = video_container
            self._realtime_video_path = video_path
            self._realtime_frame_buffer = []
            self._realtime_frame_index = 0
            
            print(f"[实时播放器] 界面组件已创建")
            
            # 添加到display_layout
            if hasattr(self.training_panel, '_video_container_index'):
                old_index = self.training_panel._video_container_index
                old_widget = self.training_panel.display_layout.widget(old_index)
                if old_widget:
                    print(f"[实时播放器] 移除旧的视频容器")
                    self.training_panel.display_layout.removeWidget(old_widget)
                    old_widget.deleteLater()
            
            video_index = self.training_panel.display_layout.addWidget(video_container)
            self.training_panel._video_container_index = video_index
            self.training_panel.display_layout.setCurrentIndex(video_index)
            
            print(f"[实时播放器] 视频容器已添加到布局（索引{video_index}）")
            
        except Exception as e:
            print(f"[实时播放器] 创建失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _updateRealtimeFrame(self, result_frame):
        """更新实时显示帧"""
        try:
            if hasattr(self, '_realtime_frame_label') and result_frame is not None:
                from PyQt5.QtGui import QImage, QPixmap
                from PyQt5 import QtCore
                
                # 转换为RGB格式
                rgb_frame = cv2.cvtColor(result_frame, cv2.COLOR_BGR2RGB)
                
                # 获取标签尺寸
                label_width = self._realtime_frame_label.width()
                label_height = self._realtime_frame_label.height()
                
                # 计算缩放比例
                h, w = rgb_frame.shape[:2]
                scale_w = label_width / w
                scale_h = label_height / h
                scale = min(scale_w, scale_h, 1.0)  # 不放大，只缩小
                
                # 缩放图像
                new_w = int(w * scale)
                new_h = int(h * scale)
                rgb_frame_resized = cv2.resize(rgb_frame, (new_w, new_h))
                
                # 转换为QImage
                h, w, ch = rgb_frame_resized.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgb_frame_resized.data, w, h, bytes_per_line, QImage.Format_RGB888)
                
                # 转换为QPixmap并显示
                pixmap = QPixmap.fromImage(qt_image)
                self._realtime_frame_label.setPixmap(pixmap)
                self._realtime_frame_label.setAlignment(QtCore.Qt.AlignCenter)
                
                # 处理事件以更新UI
                QtWidgets.QApplication.processEvents()
        except Exception as e:
            print(f"[实时帧更新] 更新失败: {e}")
    
    def _showDetectionVideo(self, video_path, total_frames, detection_count, success_count, fail_count):
        """在视频面板中显示检测结果视频"""
        try:
            print(f"[显示视频] 开始在界面中显示检测结果视频")
            
            # 检查视频面板是否存在
            if not hasattr(self.training_panel, 'video_panel'):
                print(f"[显示视频] 视频面板不存在，尝试使用显示面板")
                if hasattr(self.training_panel, 'display_panel'):
                    video_panel = self.training_panel.display_panel
                else:
                    print(f"[显示视频] 显示面板也不存在")
                    return
            else:
                video_panel = self.training_panel.video_panel
            
            # 转换为正斜杠路径
            video_path_formatted = video_path.replace('\\', '/')
            
            success_rate = (success_count / detection_count * 100) if detection_count > 0 else 0
            
            # 创建HTML内容，包含视频播放器和统计信息（统一使用白色背景）
            html_content = f"""
            <div style="font-family: 'Microsoft YaHei', 'SimHei', Arial, sans-serif; padding: 20px; background-color: #ffffff; height: 100%; overflow-y: auto; color: #333333;">
                <div style="margin-bottom: 20px; padding: 0; background-color: #ffffff;">
                    <h3 style="margin: 0 0 15px 0; color: #333333; font-size: 18px; font-weight: 600; background-color: transparent;">视频逐帧检测完成</h3>
                </div>
                
                <div style="margin-bottom: 20px; background-color: #ffffff;">
                    <h4 style="margin: 0 0 10px 0; color: #333333; font-size: 16px; font-weight: 500; background-color: transparent;">检测结果视频</h4>
                    <video width="100%" height="auto" controls style="border: none; border-radius: 6px; max-height: 400px; background-color: #f8f9fa;">
                        <source src="file:///{video_path_formatted}" type="video/mp4">
                    </video>
                </div>
                
                <div style="margin-bottom: 20px; background-color: #ffffff;">
                    <h4 style="margin: 0 0 15px 0; color: #333333; font-size: 16px; font-weight: 500; background-color: transparent;">检测统计</h4>
                    <table style="width: 100%; border-collapse: collapse; font-size: 14px; font-family: 'Microsoft YaHei', 'SimHei', Arial, sans-serif; background-color: #ffffff;">
                        <tr style="border-bottom: 1px solid #e9ecef; background-color: #ffffff;">
                            <td style="padding: 12px 8px; color: #333333; font-weight: 500; background-color: #ffffff;">总帧数</td>
                            <td style="padding: 12px 8px; color: #333333; font-weight: 400; background-color: #ffffff;">{total_frames}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #e9ecef; background-color: #ffffff;">
                            <td style="padding: 12px 8px; color: #333333; font-weight: 500; background-color: #ffffff;">检测次数</td>
                            <td style="padding: 12px 8px; color: #333333; font-weight: 400; background-color: #ffffff;">{detection_count}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #e9ecef; background-color: #ffffff;">
                            <td style="padding: 12px 8px; color: #333333; font-weight: 500; background-color: #ffffff;">成功</td>
                            <td style="padding: 12px 8px; color: #28a745; font-weight: 400; background-color: #ffffff;">{success_count}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #e9ecef; background-color: #ffffff;">
                            <td style="padding: 12px 8px; color: #333333; font-weight: 500; background-color: #ffffff;">失败</td>
                            <td style="padding: 12px 8px; color: {'#dc3545' if fail_count > 0 else '#28a745'}; font-weight: 400; background-color: #ffffff;">{fail_count}</td>
                        </tr>
                        <tr style="background-color: #ffffff;">
                            <td style="padding: 12px 8px; color: #333333; font-weight: 500; background-color: #ffffff;">成功率</td>
                            <td style="padding: 12px 8px; color: #333333; font-weight: 400; background-color: #ffffff;">{success_rate:.1f}%</td>
                        </tr>
                    </table>
                    
                    <div style="margin-top: 20px; padding: 15px; background-color: #f8f9fa; border-radius: 6px;">
                        <p style="margin: 0; font-size: 13px; color: #666666; line-height: 1.6; font-family: 'Microsoft YaHei', 'SimHei', Arial, sans-serif; background-color: transparent;">
                            - 每3帧进行一次液位检测<br>
                            - 为每一帧绘制液位线（红色）<br>
                            - 使用历史数据填充未检测帧<br>
                            - 视频文件位置: {video_path}
                        </p>
                    </div>
                </div>
            </div>
            """
            
            # 切换到视频面板显示
            if hasattr(self.training_panel, 'display_layout'):
                self.training_panel.display_layout.setCurrentIndex(2)
                print(f"[显示视频] 已切换到视频面板")
            
            # 设置视频面板内容
            if isinstance(video_panel, QtWidgets.QTextEdit):
                video_panel.setHtml(html_content)
                print(f"[显示视频] 视频内容已设置")
            else:
                print(f"[显示视频] 警告: video_panel不是QTextEdit类型")
                
        except Exception as e:
            print(f"[显示视频] 显示失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _handleStartAnnotation(self):
        """处理开始标注按钮点击"""
        # TODO: 完整实现需要从 model_training_handler.py 第1550-1735行复制
        print(f"[标注] 开始标注...")
        pass
    
    def _createAnnotationEngine(self):
        """创建标注引擎"""
        # TODO: 完整实现需要从 model_training_handler.py 第1512-1548行复制
        print(f"[标注引擎] 创建标注引擎...")
        return None
    
    def _saveVideoTestResults(self, model_path, video_path, output_video_path, 
                              frame_count, detection_count, success_count, fail_count,
                              annotation_file):
        """保存视频测试结果到模型目录"""
        import os
        import shutil
        from datetime import datetime
        
        try:
            # 获取模型所在目录
            model_dir = os.path.dirname(model_path)
            model_filename = os.path.basename(model_path)
            model_name = os.path.splitext(model_filename)[0]
            
            # 创建test_results目录
            test_results_dir = os.path.join(model_dir, 'test_results')
            os.makedirs(test_results_dir, exist_ok=True)
            
            # 生成时间戳
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 文件名前缀
            file_prefix = f"{model_name}_video_{timestamp}"
            
            print(f"[保存视频结果] 模型目录: {model_dir}")
            print(f"[保存视频结果] 结果目录: {test_results_dir}")
            print(f"[保存视频结果] 文件前缀: {file_prefix}")
            
            # 1. 复制检测结果视频到test_results目录
            result_video_filename = f"{file_prefix}_result.mp4"
            result_video_path = os.path.join(test_results_dir, result_video_filename)
            shutil.copy2(output_video_path, result_video_path)
            print(f"[保存视频结果] 结果视频已保存: {result_video_path}")
            
            # 2. 定义所有文件名（避免变量未定义错误）
            report_filename = f"{file_prefix}_report.txt"
            json_filename = f"{file_prefix}_result.json"
            curve_csv_filename = f"{file_prefix}_curve.csv"
            curve_image_filename = f"{file_prefix}_curve.png"
            
            report_path = os.path.join(test_results_dir, report_filename)
            
            video_name = os.path.basename(video_path)
            
            # 3. 生成测试报告文本文件
            report_lines = [
                "=" * 60,
                "视频液位检测测试报告",
                "=" * 60,
                f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"模型文件: {model_filename}",
                f"模型路径: {model_path}",
                f"测试视频: {video_name}",
                f"视频路径: {video_path}",
                "",
                "检测统计:",
                f"  总帧数: {frame_count}",
                f"  检测次数: {detection_count}",
                f"  成功检测: {success_count}",
                f"  失败检测: {fail_count}",
                f"  成功率: {(success_count/detection_count*100 if detection_count > 0 else 0):.1f}%",
                "",
                "标注配置:",
                f"  标注文件: {annotation_file}",
                "",
                "生成文件:",
                f"  结果视频: {result_video_filename}",
                f"  测试报告: {report_filename}",
                f"  JSON结果: {json_filename}",
                f"  曲线数据: {curve_csv_filename}",
                f"  曲线图片: {curve_image_filename}",
                "",
                "=" * 60,
            ]
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            
            print(f"[保存视频结果] 测试报告已保存: {report_path}")
            
            # 4. 生成JSON格式的详细结果
            import json
            
            json_path = os.path.join(test_results_dir, json_filename)
            
            result_data = {
                "test_info": {
                    "model_name": model_name,
                    "model_path": model_path,
                    "test_video": video_name,
                    "video_path": video_path,
                    "test_time": datetime.now().isoformat(),
                    "frame_count": frame_count,
                    "detection_count": detection_count,
                    "success_count": success_count,
                    "fail_count": fail_count,
                    "success_rate": (success_count/detection_count*100 if detection_count > 0 else 0),
                    "annotation_file": annotation_file
                },
                "files": {
                    "result_video": result_video_filename,
                    "report": report_filename,
                    "json_result": json_filename,
                    "curve_data_csv": curve_csv_filename,
                    "curve_image_png": curve_image_filename
                }
            }
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            
            print(f"[保存视频结果] JSON结果已保存: {json_path}")
            
            # 5. 保存曲线数据（CSV格式）和曲线图片
            try:
                if hasattr(self.training_panel, 'saveCurveData') and hasattr(self.training_panel, 'saveCurveImage'):
                    # 保存曲线CSV数据
                    curve_csv_path = os.path.join(test_results_dir, curve_csv_filename)
                    if self.training_panel.saveCurveData(curve_csv_path):
                        print(f"[保存视频结果] 曲线CSV数据已保存: {curve_csv_path}")
                    else:
                        print(f"[保存视频结果] [警告] 曲线CSV数据保存失败或无数据")
                    
                    # 保存曲线图片
                    curve_image_path = os.path.join(test_results_dir, curve_image_filename)
                    if self.training_panel.saveCurveImage(curve_image_path):
                        print(f"[保存视频结果] 曲线图片已保存: {curve_image_path}")
                    else:
                        print(f"[保存视频结果] [警告] 曲线图片保存失败或无数据")
                else:
                    print(f"[保存视频结果] [警告] 训练面板不支持曲线保存功能")
            except Exception as curve_error:
                print(f"[保存视频结果] [警告] 曲线保存失败（非致命错误）: {curve_error}")
            
            print(f"[保存视频结果] [成功] 所有测试结果已成功保存到: {test_results_dir}")
            
        except Exception as e:
            print(f"[保存视频结果] [错误] 保存失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _saveImageTestResults(self, model_path, test_frame, detection_result, annotation_file):
        """保存图片测试结果到模型目录"""
        import os
        import cv2
        from datetime import datetime
        
        try:
            # 获取模型所在目录
            model_dir = os.path.dirname(model_path)
            model_filename = os.path.basename(model_path)
            model_name = os.path.splitext(model_filename)[0]
            
            # 创建test_results目录
            test_results_dir = os.path.join(model_dir, 'test_results')
            os.makedirs(test_results_dir, exist_ok=True)
            
            # 生成时间戳
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 文件名前缀
            file_prefix = f"{model_name}_{timestamp}"
            
            print(f"[保存图片结果] 模型目录: {model_dir}")
            print(f"[保存图片结果] 结果目录: {test_results_dir}")
            print(f"[保存图片结果] 文件前缀: {file_prefix}")
            
            # 1. 保存原始测试图像
            original_filename = f"{file_prefix}_original.png"
            original_path = os.path.join(test_results_dir, original_filename)
            cv2.imwrite(original_path, test_frame)
            print(f"[保存图片结果] 原始图像已保存: {original_path}")
            
            # 2. 保存检测结果图像（带标注）
            result_image = test_frame.copy()
            
            # 绘制检测结果
            liquid_level = 0
            if detection_result and 'liquid_line_positions' in detection_result:
                liquid_positions = detection_result['liquid_line_positions']
                if liquid_positions and 0 in liquid_positions:
                    liquid_level = liquid_positions[0]['height_mm']
                
                # 使用PIL绘制中文文本
                from PIL import Image, ImageDraw, ImageFont
                pil_result = Image.fromarray(cv2.cvtColor(result_image, cv2.COLOR_BGR2RGB))
                draw_result = ImageDraw.Draw(pil_result)
                
                # 加载中文字体
                try:
                    font_medium = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
                    font_small = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
                except:
                    font_medium = ImageFont.load_default()
                    font_small = ImageFont.load_default()
                
                # 绘制液位信息
                text = f"液位: {liquid_level:.1f}mm"
                text_bbox = draw_result.textbbox((0, 0), text, font=font_medium)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                
                # 在图像顶部绘制文本背景
                draw_result.rectangle([10, 10, 10 + text_width + 20, 10 + text_height + 10], 
                                    fill=(0, 0, 0, 180))
                draw_result.text((20, 15), text, fill=(255, 255, 255), font=font_medium)
                
                # 转换回OpenCV格式
                result_image = cv2.cvtColor(np.array(pil_result), cv2.COLOR_RGB2BGR)
            
            result_filename = f"{file_prefix}_result.png"
            result_path = os.path.join(test_results_dir, result_filename)
            cv2.imwrite(result_path, result_image)
            print(f"[保存图片结果] 检测结果图像已保存: {result_path}")
            
            # 3. 生成测试报告文本文件
            report_filename = f"{file_prefix}_report.txt"
            report_path = os.path.join(test_results_dir, report_filename)
            
            # 提取检测信息
            liquid_level = 0
            detection_success = False
            if detection_result and 'liquid_line_positions' in detection_result:
                liquid_positions = detection_result['liquid_line_positions']
                if liquid_positions and 0 in liquid_positions:
                    liquid_level = liquid_positions[0]['height_mm']
                    detection_success = True
            
            report_lines = [
                "=" * 60,
                "图片液位检测测试报告",
                "=" * 60,
                f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"模型文件: {model_filename}",
                f"模型路径: {model_path}",
                f"图像尺寸: {test_frame.shape[1]}x{test_frame.shape[0]}",
                "",
                "检测结果:",
                f"  检测状态: {'成功' if detection_success else '失败'}",
                f"  液位高度: {liquid_level:.1f}mm" if detection_success else "  液位高度: 无法检测",
                "",
                "标注配置:",
                f"  标注文件: {annotation_file}",
                "",
                "生成文件:",
                f"  原始图像: {original_filename}",
                f"  检测结果: {result_filename}",
                f"  测试报告: {report_filename}",
                f"  JSON结果: {json_filename}",
                f"  曲线数据: {file_prefix}_curve.csv",
                f"  曲线图片: {file_prefix}_curve.png",
                "",
                "=" * 60,
            ]
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            
            print(f"[保存图片结果] 测试报告已保存: {report_path}")
            
            # 4. 生成JSON格式的详细结果
            import json
            
            json_filename = f"{file_prefix}_result.json"
            json_path = os.path.join(test_results_dir, json_filename)
            
            result_data = {
                "test_info": {
                    "model_name": model_name,
                    "model_path": model_path,
                    "test_time": datetime.now().isoformat(),
                    "image_size": {
                        "width": int(test_frame.shape[1]),
                        "height": int(test_frame.shape[0])
                    },
                    "annotation_file": annotation_file
                },
                "detection_result": {
                    "success": detection_success,
                    "liquid_level_mm": float(liquid_level) if detection_success else None,
                    "raw_result": detection_result
                },
                "files": {
                    "original_image": original_filename,
                    "result_image": result_filename,
                    "report": report_filename,
                    "json_result": json_filename,
                    "curve_data_csv": f"{file_prefix}_curve.csv",
                    "curve_image_png": f"{file_prefix}_curve.png"
                }
            }
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            
            print(f"[保存图片结果] JSON结果已保存: {json_path}")
            
            # 5. 保存曲线数据（CSV格式）和曲线图片
            try:
                if hasattr(self.training_panel, 'saveCurveData') and hasattr(self.training_panel, 'saveCurveImage'):
                    # 保存曲线CSV数据
                    curve_csv_filename = f"{file_prefix}_curve.csv"
                    curve_csv_path = os.path.join(test_results_dir, curve_csv_filename)
                    if self.training_panel.saveCurveData(curve_csv_path):
                        print(f"[保存图片结果] 曲线CSV数据已保存: {curve_csv_path}")
                    
                    # 保存曲线图片
                    curve_image_filename = f"{file_prefix}_curve.png"
                    curve_image_path = os.path.join(test_results_dir, curve_image_filename)
                    if self.training_panel.saveCurveImage(curve_image_path):
                        print(f"[保存图片结果] 曲线图片已保存: {curve_image_path}")
            except Exception as curve_error:
                print(f"[保存图片结果] [警告] 曲线保存失败（非致命错误）: {curve_error}")
            
            print(f"[保存图片结果] [成功] 所有测试结果已成功保存到: {test_results_dir}")
            
        except Exception as e:
            print(f"[保存图片结果] [错误] 保存失败: {e}")
            import traceback
            traceback.print_exc()
