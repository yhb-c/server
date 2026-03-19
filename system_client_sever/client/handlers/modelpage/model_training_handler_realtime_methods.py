# 视频检测实时显示相关方法（从历史代码恢复）
# 这些方法需要添加到 ModelTrainingHandler 类中

# 导入全局字体管理器
try:
    from ...widgets.style_manager import FontManager
except (ImportError, ValueError):
    try:
        from widgets.style_manager import FontManager
    except ImportError:
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))
        from widgets.style_manager import FontManager

def _drawLiquidLinesOnFrame(self, frame, detection_result, boxes, bottoms, tops):
    """在帧上绘制液位线"""
    try:
        import cv2
        
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
                        left = position_data.get('left', 0)
                        right = position_data.get('right', 0)
                        
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
                
                if line_count > 0:
                    print(f"[液位线绘制] 成功绘制 {line_count} 条液位线")
        
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
            if not hasattr(self, '_yellow_line_warning_shown'):
                print(f"[液位线绘制] 未检测到液位，绘制默认0mm液位线（共{len(bottoms)}个区域）")
                self._yellow_line_warning_shown = True
        
        return result_frame
        
    except Exception as e:
        print(f"[液位线绘制] 绘制失败: {e}")
        import traceback
        traceback.print_exc()
        return frame


def _updateRealtimeFrame(self, result_frame):
    """更新实时显示帧"""
    try:
        if hasattr(self, '_realtime_frame_label') and result_frame is not None:
            import cv2
            from PyQt5.QtGui import QImage, QPixmap
            from PyQt5 import QtCore, QtWidgets
            
            # OpenCV帧转换为QPixmap
            height, width, channel = result_frame.shape
            bytes_per_line = 3 * width
            
            # BGR转RGB
            rgb_frame = cv2.cvtColor(result_frame, cv2.COLOR_BGR2RGB)
            
            # 创建QImage
            q_image = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
            
            # 转换为QPixmap
            pixmap = QPixmap.fromImage(q_image)
            
            # 缩放以适应标签大小
            label_width = self._realtime_frame_label.width()
            label_height = self._realtime_frame_label.height()
            
            if label_width > 0 and label_height > 0:
                scaled_pixmap = pixmap.scaled(
                    label_width - 4,  # 留出边框空间
                    label_height - 4,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation
                )
                self._realtime_frame_label.setPixmap(scaled_pixmap)
            else:
                self._realtime_frame_label.setPixmap(pixmap)
            
            QtWidgets.QApplication.processEvents()
            
    except Exception as e:
        print(f"[实时帧更新] 更新失败: {e}")


def _updateRealtimePlayerStats(self, current_frame, total_frames, success_count, fail_count):
    """更新实时播放器统计信息"""
    try:
        if hasattr(self, '_realtime_stats_text'):
            from PyQt5 import QtWidgets
            progress_percent = int((current_frame / total_frames) * 100)
            stats_text = (
                f"进度: {current_frame}/{total_frames} 帧 ({progress_percent}%) | "
                f"成功: {success_count} | 失败: {fail_count}"
            )
            self._realtime_stats_text.setText(stats_text)
            QtWidgets.QApplication.processEvents()
    except Exception as e:
        print(f"[统计信息更新] 更新失败: {e}")


def _createRealtimeVideoPlayer(self, video_path, total_frames, fps=25.0):
    """创建实时视频播放器界面"""
    try:
        from PyQt5 import QtWidgets, QtCore
        from PyQt5.QtGui import QPixmap
        import os
        
        print(f"[实时播放器] ========== 创建实时播放器 ==========")
        print(f"[实时播放器] 视频路径: {video_path}")
        print(f"[实时播放器] 总帧数: {total_frames}")
        print(f"[实时播放器] 帧率: {fps} fps")
        print(f"[实时播放器] 文件存在: {os.path.exists(video_path)}")
        
        # 检查display_layout是否存在
        if not hasattr(self.training_panel, 'display_layout'):
            print(f"[实时播放器] 错误: 找不到display_layout")
            return
        
        print(f"[实时播放器] 找到display_layout")
        
        # 创建视频容器
        video_container = QtWidgets.QWidget()
        container_layout = QtWidgets.QVBoxLayout(video_container)
        container_layout.setContentsMargins(15, 15, 15, 15)
        container_layout.setSpacing(10)
        
        # 标题区域
        title_widget = QtWidgets.QWidget()
        title_widget.setStyleSheet("background: #fff3cd; border: 1px solid #ffc107; border-radius: 5px; padding: 12px;")
        title_layout = QtWidgets.QVBoxLayout(title_widget)
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QtWidgets.QLabel("⏳ 正在检测中...")
        title_label.setStyleSheet("color: #856404; background: transparent; border: none; padding: 0;")
        FontManager.applyToWidget(title_label, size=FontManager.FONT_SIZE_LARGE, weight=FontManager.WEIGHT_BOLD)
        title_layout.addWidget(title_label)
        container_layout.addWidget(title_widget)
        
        # 统计信息区域
        stats_widget = QtWidgets.QWidget()
        stats_widget.setStyleSheet("background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px; padding: 12px;")
        stats_layout = QtWidgets.QVBoxLayout(stats_widget)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        
        stats_title = QtWidgets.QLabel("检测进度")
        stats_title.setStyleSheet("color: #333; background: transparent; border: none; padding: 0;")
        FontManager.applyToWidget(stats_title, size=FontManager.FONT_SIZE_MEDIUM, weight=FontManager.WEIGHT_BOLD)
        stats_layout.addWidget(stats_title)
        
        # 统计文本
        stats_text = QtWidgets.QLabel(f"进度: 0/{total_frames} 帧 (0%)")
        stats_text.setObjectName("stats_text")  # 设置对象名称以便后续查找
        stats_text.setStyleSheet("color: #666; background: transparent; border: none; padding: 5px 0;")
        FontManager.applyToWidget(stats_text, size=FontManager.FONT_SIZE_SMALL)
        stats_layout.addWidget(stats_text)
        container_layout.addWidget(stats_widget)
        
        # 帧显示区域（使用QLabel）
        frame_label = QtWidgets.QLabel()
        frame_label.setMinimumHeight(400)
        frame_label.setAlignment(QtCore.Qt.AlignCenter)
        frame_label.setStyleSheet("background: black; border: 2px solid #dee2e6; border-radius: 4px;")
        frame_label.setScaledContents(False)  # 不自动缩放，保持宽高比
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
        self._realtime_stats_text = stats_text
        self._realtime_title_label = title_label
        self._realtime_video_path = video_path
        self._realtime_frame_buffer = []  # 帧缓冲区
        self._realtime_frame_index = 0
        
        print(f"[实时播放器] 界面组件已创建")
        print(f"[实时播放器] - frame_label: {frame_label}")
        
        # 添加到display_layout
        if hasattr(self.training_panel, '_video_container_index'):
            old_index = self.training_panel._video_container_index
            old_widget = self.training_panel.display_layout.widget(old_index)
            if old_widget:
                print(f"[实时播放器] 移除旧的视频容器（索引{old_index}）")
                self.training_panel.display_layout.removeWidget(old_widget)
                old_widget.deleteLater()
        
        video_index = self.training_panel.display_layout.addWidget(video_container)
        self.training_panel._video_container_index = video_index
        self.training_panel.display_layout.setCurrentIndex(video_index)
        
        print(f"[实时播放器] 视频容器已添加到布局（索引{video_index}）")
        print(f"[实时播放器] ========== 创建完成 ==========")
        
    except Exception as e:
        print(f"[实时播放器] 创建失败: {e}")
        import traceback
        traceback.print_exc()
