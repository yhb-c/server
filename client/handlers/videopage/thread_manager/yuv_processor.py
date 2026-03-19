# -*- coding: utf-8 -*-

"""
YUV数据处理器 - 高性能YUV裁剪和转换

职责：
1. 直接裁剪YUV数据中的ROI区域（避免全帧转换）
2. 将裁剪后的YUV转换为RGB
3. 坐标自动对齐到偶数（YUV420要求）

性能优势：
- 减少数据处理量：只转换ROI区域，而非全帧
- 减少内存拷贝：直接在YUV空间裁剪
- 适合多ROI场景：每个ROI独立裁剪转换
"""

import numpy as np
import cv2
from typing import List, Tuple, Optional, Dict, Any


class YUVProcessor:
    """YUV数据处理器
    
    支持I420/YV12格式的YUV数据裁剪和转换
    """
    
    @staticmethod
    def align_to_even(value: int) -> int:
        """将值对齐到偶数（向上取整）
        
        Args:
            value: 输入值
            
        Returns:
            偶数值
        """
        return value if value % 2 == 0 else value + 1
    
    @staticmethod
    def align_roi_to_even(x: int, y: int, w: int, h: int, 
                          frame_width: int, frame_height: int) -> Tuple[int, int, int, int]:
        """将ROI坐标对齐到偶数
        
        Args:
            x, y: ROI左上角坐标
            w, h: ROI宽高
            frame_width, frame_height: 帧尺寸（用于边界检查）
            
        Returns:
            (x, y, w, h) 对齐后的坐标
        """
        # 对齐x和y到偶数（向下取整，确保不超出边界）
        x = x - (x % 2)
        y = y - (y % 2)
        
        # 对齐宽高到偶数（向上取整）
        w = YUVProcessor.align_to_even(w)
        h = YUVProcessor.align_to_even(h)
        
        # 边界检查
        if x + w > frame_width:
            w = frame_width - x
            w = w - (w % 2)  # 再次对齐
        if y + h > frame_height:
            h = frame_height - y
            h = h - (h % 2)
        
        return x, y, w, h
    
    @staticmethod
    def crop_yuv420_roi(yuv_data: bytes, frame_width: int, frame_height: int,
                        roi_x: int, roi_y: int, roi_w: int, roi_h: int) -> Optional[np.ndarray]:
        """从YUV420数据中裁剪ROI区域并转换为RGB
        
        YUV420 I420格式内存布局：
        - Y平面: frame_height 行，每行 frame_width 字节
        - U平面: frame_height/2 行，每行 frame_width/2 字节
        - V平面: frame_height/2 行，每行 frame_width/2 字节
        
        Args:
            yuv_data: YUV420原始数据（bytes或numpy数组）
            frame_width: 帧宽度
            frame_height: 帧高度
            roi_x, roi_y: ROI左上角坐标
            roi_w, roi_h: ROI宽高
            
        Returns:
            RGB格式的ROI图像（numpy数组），失败返回None
        """
        try:
            # 对齐坐标到偶数
            roi_x, roi_y, roi_w, roi_h = YUVProcessor.align_roi_to_even(
                roi_x, roi_y, roi_w, roi_h, frame_width, frame_height
            )
            
            # 验证参数
            if roi_w <= 0 or roi_h <= 0:
                return None
            if roi_x < 0 or roi_y < 0:
                return None
            if roi_x + roi_w > frame_width or roi_y + roi_h > frame_height:
                return None
            
            # 计算各平面大小
            y_size = frame_width * frame_height
            uv_width = frame_width // 2
            uv_height = frame_height // 2
            u_size = uv_width * uv_height
            
            # 将bytes转换为numpy数组
            if isinstance(yuv_data, bytes):
                yuv_array = np.frombuffer(yuv_data, dtype=np.uint8)
            else:
                yuv_array = yuv_data
            
            # 验证数据大小
            expected_size = y_size + u_size * 2
            if len(yuv_array) < expected_size:
                return None
            
            # 分离Y、U、V平面
            y_plane = yuv_array[:y_size].reshape((frame_height, frame_width))
            u_plane = yuv_array[y_size:y_size + u_size].reshape((uv_height, uv_width))
            v_plane = yuv_array[y_size + u_size:y_size + u_size * 2].reshape((uv_height, uv_width))
            
            # 裁剪Y平面
            y_roi = y_plane[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w].copy()
            
            # 计算UV平面的ROI坐标（UV是2x2下采样）
            uv_roi_x = roi_x // 2
            uv_roi_y = roi_y // 2
            uv_roi_w = roi_w // 2
            uv_roi_h = roi_h // 2
            
            # 裁剪U、V平面
            u_roi = u_plane[uv_roi_y:uv_roi_y + uv_roi_h, uv_roi_x:uv_roi_x + uv_roi_w].copy()
            v_roi = v_plane[uv_roi_y:uv_roi_y + uv_roi_h, uv_roi_x:uv_roi_x + uv_roi_w].copy()
            
            # 组装裁剪后的YUV数据（I420格式）
            roi_yuv = np.concatenate([
                y_roi.flatten(),
                u_roi.flatten(),
                v_roi.flatten()
            ])
            
            # 重塑为OpenCV期望的格式
            roi_yuv_reshaped = roi_yuv.reshape((roi_h * 3 // 2, roi_w))
            
            # YUV转RGB
            rgb_roi = cv2.cvtColor(roi_yuv_reshaped, cv2.COLOR_YUV2RGB_I420)
            
            return rgb_roi
            
        except Exception as e:
            print(f"[YUVProcessor] 裁剪ROI失败: {e}")
            return None
    
    @staticmethod
    def crop_multiple_rois(yuv_data: bytes, frame_width: int, frame_height: int,
                           rois: List[Tuple[int, int, int, int]]) -> List[Optional[np.ndarray]]:
        """从YUV420数据中裁剪多个ROI区域
        
        Args:
            yuv_data: YUV420原始数据
            frame_width: 帧宽度
            frame_height: 帧高度
            rois: ROI列表，每个元素为 (x, y, w, h)
            
        Returns:
            RGB图像列表，对应每个ROI
        """
        results = []
        for roi in rois:
            x, y, w, h = roi
            rgb_roi = YUVProcessor.crop_yuv420_roi(
                yuv_data, frame_width, frame_height, x, y, w, h
            )
            results.append(rgb_roi)
        return results
    
    @staticmethod
    def yuv420_to_rgb_full(yuv_data: bytes, width: int, height: int) -> Optional[np.ndarray]:
        """将完整YUV420帧转换为RGB（备用方法）
        
        Args:
            yuv_data: YUV420原始数据
            width: 帧宽度
            height: 帧高度
            
        Returns:
            RGB图像，失败返回None
        """
        try:
            if isinstance(yuv_data, bytes):
                yuv_array = np.frombuffer(yuv_data, dtype=np.uint8)
            else:
                yuv_array = yuv_data
            
            yuv_reshaped = yuv_array.reshape((height * 3 // 2, width))
            rgb_frame = cv2.cvtColor(yuv_reshaped, cv2.COLOR_YUV2RGB_I420)
            return rgb_frame
            
        except Exception as e:
            print(f"[YUVProcessor] YUV转RGB失败: {e}")
            return None
    
    @staticmethod
    def boxes_to_rois(boxes: List[List[int]]) -> List[Tuple[int, int, int, int]]:
        """将标注boxes转换为ROI格式
        
        Args:
            boxes: 标注框列表，每个元素为 [x1, y1, x2, y2]
            
        Returns:
            ROI列表，每个元素为 (x, y, w, h)
        """
        rois = []
        for box in boxes:
            if len(box) >= 4:
                x1, y1, x2, y2 = box[:4]
                x = min(x1, x2)
                y = min(y1, y2)
                w = abs(x2 - x1)
                h = abs(y2 - y1)
                rois.append((x, y, w, h))
        return rois
