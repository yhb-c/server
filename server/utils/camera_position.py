"""
相机姿态检测模块
基于特征点匹配 + 单应矩阵的方法判断相机姿态是否发生变化
"""

import cv2
import numpy as np
from typing import Tuple, Optional, List, Dict
import logging
import os
from datetime import datetime

# 配置日志
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_LOG_DIR = os.path.join(_PROJECT_ROOT, 'logs')
os.makedirs(_LOG_DIR, exist_ok=True)
_LOG_FILE = os.path.join(_LOG_DIR, f'cameraposition_{datetime.now().strftime("%Y%m%d")}.log')

_camera_logger = logging.getLogger('cameraposition')
_camera_logger.setLevel(logging.DEBUG)
# 避免重复添加handler
if not _camera_logger.handlers:
    _file_handler = logging.FileHandler(_LOG_FILE, encoding='utf-8')
    _file_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s'))
    _camera_logger.addHandler(_file_handler)
    _camera_logger.propagate = False  # 不传播到根logger


class CameraPositionDetector:
    """
    相机姿态检测器
    
    通过对比基准帧与当前帧的特征点，在排除液位孔区域后，
    判断相机姿态是否发生改变
    """
    
    def __init__(
        self,
        translation_threshold: float = 3.0,  # 平移阈值(像素)
        rotation_threshold: float = 0.5,      # 旋转阈值(度)
        scale_threshold: float = 0.02,        # 尺度变化阈值(2%)
        inlier_ratio_threshold: float = 0.5,  # 内点比例阈值
        min_match_count: int = 10,            # 最少匹配点数量
        voting_frames: int = 3,               # 投票帧数
        voting_ratio: float = 0.7             # 投票通过比例
    ):
        """
        初始化相机姿态检测器
        
        Args:
            translation_threshold: 平移变化超过此值(像素)判定为姿态变化
            rotation_threshold: 旋转变化超过此值(度)判定为姿态变化
            scale_threshold: 尺度变化超过此值判定为姿态变化
            inlier_ratio_threshold: RANSAC内点比例低于此值判定为姿态变化
            min_match_count: 特征匹配最少点数，低于此值判定为姿态变化
            voting_frames: 用于投票的历史帧数
            voting_ratio: 投票通过比例
        """
        self.translation_threshold = translation_threshold
        self.rotation_threshold = rotation_threshold
        self.scale_threshold = scale_threshold
        self.inlier_ratio_threshold = inlier_ratio_threshold
        self.min_match_count = min_match_count
        self.voting_frames = voting_frames
        self.voting_ratio = voting_ratio
        
        # 初始化ORB特征检测器
        self.orb = cv2.ORB_create(nfeatures=1000)
        
        # 初始化特征匹配器
        self.bf_matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        
        # 基准帧相关
        self.ref_frame = None
        self.ref_gray = None
        self.ref_keypoints = None
        self.ref_descriptors = None
        
        # 掩膜（用于屏蔽液位孔区域）
        self.static_mask = None
        
        # 投票队列
        self.vote_queue: List[bool] = []
        
        # 日志
        self.logger = logging.getLogger(__name__)
        
    def set_reference_frame(
        self,
        frame: np.ndarray,
        hole_bbox: Optional[Tuple[int, int, int, int]] = None,
        hole_mask: Optional[np.ndarray] = None
    ) -> bool:
        """
        设置基准帧
        
        Args:
            frame: 基准图像(BGR格式)
            hole_bbox: 液位孔边界框 (x1, y1, x2, y2)，用于生成掩膜
            hole_mask: 液位孔掩膜(可选)，如果提供则直接使用
            
        Returns:
            是否设置成功
        """
        if frame is None or frame.size == 0:
            self.logger.error("基准帧无效")
            return False
            
        # 转换为灰度图
        self.ref_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame.copy()
        self.ref_frame = frame.copy()
        
        # 生成静止区域掩膜
        h, w = self.ref_gray.shape
        self.static_mask = np.ones((h, w), dtype=np.uint8) * 255
        
        if hole_mask is not None:
            # 使用提供的掩膜
            self.static_mask[hole_mask > 0] = 0
        elif hole_bbox is not None:
            # 使用边界框生成掩膜，并适当扩展
            x1, y1, x2, y2 = hole_bbox
            # 扩展5%防止边缘干扰
            expand_x = int((x2 - x1) * 0.05)
            expand_y = int((y2 - y1) * 0.05)
            x1 = max(0, x1 - expand_x)
            y1 = max(0, y1 - expand_y)
            x2 = min(w, x2 + expand_x)
            y2 = min(h, y2 + expand_y)
            self.static_mask[y1:y2, x1:x2] = 0
        
        # 在静止区域提取特征点
        self.ref_keypoints, self.ref_descriptors = self.orb.detectAndCompute(
            self.ref_gray, 
            self.static_mask
        )
        
        if self.ref_descriptors is None or len(self.ref_keypoints) < self.min_match_count:
            self.logger.warning(f"基准帧特征点不足: {len(self.ref_keypoints) if self.ref_keypoints else 0}")
            return False
            
        self.logger.info(f"基准帧设置成功，提取特征点数: {len(self.ref_keypoints)}")
        
        # 重置投票队列
        self.vote_queue.clear()
        
        return True
    
    def detect_position_change(
        self,
        current_frame: np.ndarray
    ) -> Dict:
        """
        检测当前帧相对于基准帧的姿态变化
        
        Args:
            current_frame: 当前帧图像(BGR格式)
            
        Returns:
            检测结果字典，包含:
            - changed: 是否发生姿态变化(布尔值)
            - translation: 平移量 (dx, dy)
            - rotation: 旋转角度(度)
            - scale: 尺度变化
            - inlier_ratio: 内点比例
            - match_count: 匹配点数量
            - confidence: 置信度
            - voted_changed: 投票后的结果
        """
        result = {
            'changed': False,
            'translation': (0.0, 0.0),
            'rotation': 0.0,
            'scale': 1.0,
            'inlier_ratio': 0.0,
            'match_count': 0,
            'confidence': 0.0,
            'voted_changed': False,
            'error': None
        }
        
        # 检查是否已设置基准帧
        if self.ref_gray is None or self.ref_descriptors is None:
            result['error'] = "未设置基准帧"
            return result
        
        if current_frame is None or current_frame.size == 0:
            result['error'] = "当前帧无效"
            return result
        
        # 转换为灰度图
        current_gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY) if len(current_frame.shape) == 3 else current_frame.copy()
        
        # 提取当前帧特征点
        current_keypoints, current_descriptors = self.orb.detectAndCompute(
            current_gray,
            self.static_mask
        )
        
        if current_descriptors is None or len(current_keypoints) < self.min_match_count:
            result['error'] = "当前帧特征点不足"
            result['changed'] = True  # 特征点不足也认为是异常
            self._update_vote(True)
            result['voted_changed'] = self._get_vote_result()
            return result
        
        result['match_count'] = len(current_keypoints)
        
        # 特征匹配
        matches = self.bf_matcher.knnMatch(self.ref_descriptors, current_descriptors, k=2)
        
        # Lowe's ratio test
        good_matches = []
        for match_pair in matches:
            if len(match_pair) == 2:
                m, n = match_pair
                if m.distance < 0.75 * n.distance:
                    good_matches.append(m)
        
        if len(good_matches) < self.min_match_count:
            result['error'] = f"有效匹配点不足: {len(good_matches)}"
            result['changed'] = True
            self._update_vote(True)
            result['voted_changed'] = self._get_vote_result()
            return result
        
        # 提取匹配点坐标
        ref_pts = np.float32([self.ref_keypoints[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        cur_pts = np.float32([current_keypoints[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        
        # RANSAC估计单应矩阵
        H, mask = cv2.findHomography(ref_pts, cur_pts, cv2.RANSAC, 5.0)
        
        if H is None:
            result['error'] = "单应矩阵估计失败"
            result['changed'] = True
            self._update_vote(True)
            result['voted_changed'] = self._get_vote_result()
            return result
        
        # 计算内点比例
        inlier_count = np.sum(mask)
        inlier_ratio = inlier_count / len(good_matches)
        result['inlier_ratio'] = inlier_ratio
        
        # 从单应矩阵提取姿态变化参数
        h, w = self.ref_gray.shape
        center = np.array([[w/2, h/2]], dtype=np.float32).reshape(-1, 1, 2)
        transformed_center = cv2.perspectiveTransform(center, H)
        
        # 平移
        dx = transformed_center[0, 0, 0] - center[0, 0, 0]
        dy = transformed_center[0, 0, 1] - center[0, 0, 1]
        translation = np.sqrt(dx**2 + dy**2)
        result['translation'] = (float(dx), float(dy))
        
        # 旋转（近似）
        rotation = np.arctan2(H[1, 0], H[0, 0]) * 180 / np.pi
        result['rotation'] = float(rotation)
        
        # 尺度变化
        scale = np.sqrt(H[0, 0]**2 + H[1, 0]**2)
        result['scale'] = float(scale)
        scale_change = abs(scale - 1.0)
        
        # 判断是否发生姿态变化
        changed = False
        reasons = []
        
        if translation > self.translation_threshold:
            changed = True
            reasons.append(f"平移超限({translation:.2f}px)")
            
        if abs(rotation) > self.rotation_threshold:
            changed = True
            reasons.append(f"旋转超限({rotation:.2f}°)")
            
        if scale_change > self.scale_threshold:
            changed = True
            reasons.append(f"尺度变化超限({scale_change:.3f})")
            
        if inlier_ratio < self.inlier_ratio_threshold:
            changed = True
            reasons.append(f"内点比例过低({inlier_ratio:.2f})")
        
        result['changed'] = changed
        result['confidence'] = inlier_ratio
        
        if reasons:
            result['error'] = "; ".join(reasons)
        
        # 更新投票队列
        self._update_vote(changed)
        result['voted_changed'] = self._get_vote_result()
        
        return result
    
    def _update_vote(self, changed: bool):
        """更新投票队列"""
        self.vote_queue.append(changed)
        if len(self.vote_queue) > self.voting_frames:
            self.vote_queue.pop(0)
    
    def _get_vote_result(self) -> bool:
        """获取投票结果"""
        if len(self.vote_queue) == 0:
            return False
        change_count = sum(self.vote_queue)
        return change_count / len(self.vote_queue) >= self.voting_ratio
    
    def reset(self):
        """重置检测器状态"""
        self.vote_queue.clear()
        
    def update_reference_frame(
        self,
        frame: np.ndarray,
        hole_bbox: Optional[Tuple[int, int, int, int]] = None,
        hole_mask: Optional[np.ndarray] = None
    ) -> bool:
        """
        更新基准帧（当需要重新标定时）
        
        Args:
            frame: 新的基准图像
            hole_bbox: 液位孔边界框
            hole_mask: 液位孔掩膜
            
        Returns:
            是否更新成功
        """
        self.reset()
        return self.set_reference_frame(frame, hole_bbox, hole_mask)
    
    def visualize_matches(
        self,
        current_frame: np.ndarray,
        max_matches: int = 50
    ) -> Optional[np.ndarray]:
        """
        可视化特征匹配结果（用于调试）
        
        Args:
            current_frame: 当前帧
            max_matches: 最多显示的匹配数量
            
        Returns:
            可视化图像
        """
        if self.ref_frame is None or self.ref_descriptors is None:
            return None
        
        current_gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY) if len(current_frame.shape) == 3 else current_frame
        current_keypoints, current_descriptors = self.orb.detectAndCompute(current_gray, self.static_mask)
        
        if current_descriptors is None:
            return None
        
        matches = self.bf_matcher.knnMatch(self.ref_descriptors, current_descriptors, k=2)
        good_matches = []
        for match_pair in matches:
            if len(match_pair) == 2:
                m, n = match_pair
                if m.distance < 0.75 * n.distance:
                    good_matches.append(m)
        
        # 限制显示数量
        good_matches = sorted(good_matches, key=lambda x: x.distance)[:max_matches]
        
        # 绘制匹配
        img_matches = cv2.drawMatches(
            self.ref_frame, self.ref_keypoints,
            current_frame, current_keypoints,
            good_matches, None,
            flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS
        )
        
        return img_matches


# 便捷函数
def create_detector(
    translation_threshold: float = 3.0,
    rotation_threshold: float = 0.5,
    scale_threshold: float = 0.02
) -> CameraPositionDetector:
    """
    创建相机姿态检测器的便捷函数
    
    Args:
        translation_threshold: 平移阈值(像素)
        rotation_threshold: 旋转阈值(度)
        scale_threshold: 尺度变化阈值
        
    Returns:
        CameraPositionDetector实例
    """
    return CameraPositionDetector(
        translation_threshold=translation_threshold,
        rotation_threshold=rotation_threshold,
        scale_threshold=scale_threshold
    )


# ============== 函数式接口 ==============

# 全局参数配置（调整为更宽松的阈值，避免误报）
_detector_params = {
    'translation_threshold': 20.0,  # 平移阈值(像素) - 相机移动超过20像素才报警
    'rotation_threshold': 3.0,      # 旋转阈值(度) - 相机旋转超过3度才报警
    'scale_threshold': 0.1,         # 尺度变化阈值 - 缩放超过10%才报警
    'inlier_ratio_threshold': 0.2,  # 内点比例阈值 - 低于20%才认为异常
    'min_match_count': 15,          # 最少匹配点数量
    'voting_frames': 5,             # 投票帧数
    'voting_ratio': 0.8,            # 投票通过比例（5帧中4帧异常才报警）
}

# 调试开关（设为True可查看检测详情）
_camera_debug = False

# 共享的ORB和匹配器（所有通道共用）
_shared_detector = {
    'orb': None,
    'bf_matcher': None,
}

# 按通道存储状态（支持多通道独立检测）
# {channel_id: {'ref_gray': ..., 'ref_keypoints': ..., 'ref_descriptors': ..., 'static_mask': ..., 'vote_queue': []}}
_channel_detector_states = {}


def _init_detector():
    """初始化检测器（懒加载）"""
    if _shared_detector['orb'] is None:
        _shared_detector['orb'] = cv2.ORB_create(nfeatures=1000)
        _shared_detector['bf_matcher'] = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)


def _get_channel_state(channel_id: str = 'default') -> dict:
    """获取或创建通道特定的状态"""
    if channel_id not in _channel_detector_states:
        _channel_detector_states[channel_id] = {
            'ref_gray': None,
            'ref_keypoints': None,
            'ref_descriptors': None,
            'static_mask': None,
            'vote_queue': [],
        }
    return _channel_detector_states[channel_id]


def set_camera_reference(
    roi_image: np.ndarray,
    exclude_mask: Optional[np.ndarray] = None,
    channel_id: str = 'default'
) -> bool:
    """
    设置相机姿态检测的基准帧
    
    Args:
        roi_image: 大ROI区域图像（已裁剪，BGR格式）
        exclude_mask: 排除区域掩膜（小ROI区域为255，其他为0）
                     如果为None则不排除任何区域
        channel_id: 通道ID，用于多通道独立检测
    
    Returns:
        是否设置成功
    """
    _init_detector()
    
    if roi_image is None or roi_image.size == 0:
        return False
    
    # 获取通道特定状态
    state = _get_channel_state(channel_id)
    
    # 转灰度
    gray = cv2.cvtColor(roi_image, cv2.COLOR_BGR2GRAY) if len(roi_image.shape) == 3 else roi_image.copy()
    state['ref_gray'] = gray
    
    # 生成检测区域掩膜（排除小ROI）
    h, w = gray.shape
    mask = np.ones((h, w), dtype=np.uint8) * 255
    if exclude_mask is not None:
        mask[exclude_mask > 0] = 0
    state['static_mask'] = mask
    
    # 提取特征点
    orb = _shared_detector['orb']
    keypoints, descriptors = orb.detectAndCompute(gray, mask)
    
    if descriptors is None or len(keypoints) < _detector_params['min_match_count']:
        return False
    
    state['ref_keypoints'] = keypoints
    state['ref_descriptors'] = descriptors
    state['vote_queue'] = []
    
    return True


def detect_camera_moved(
    roi_image: np.ndarray,
    exclude_mask: Optional[np.ndarray] = None,
    channel_id: str = 'default'
) -> bool:
    """
    检测相机是否发生移动
    
    Args:
        roi_image: 大ROI区域图像（已裁剪，BGR格式）
        exclude_mask: 排除区域掩膜（小ROI区域为255，其他为0）
                     如果为None则使用设置基准帧时的掩膜
        channel_id: 通道ID，用于多通道独立检测
    
    Returns:
        bool: True表示相机发生移动，False表示相机稳定
    """
    result = detect_camera_moved_detail(roi_image, exclude_mask, channel_id)
    return result['moved']


def detect_camera_moved_detail(
    roi_image: np.ndarray,
    exclude_mask: Optional[np.ndarray] = None,
    channel_id: str = 'default'
) -> dict:
    """
    检测相机是否发生移动（返回详细信息）
    
    Args:
        roi_image: 大ROI区域图像（已裁剪，BGR格式）
        exclude_mask: 排除区域掩膜（小ROI区域为255，其他为0）
        channel_id: 通道ID
    
    Returns:
        dict: {
            'moved': bool,           # 是否移动
            'ref_pts': list,         # 基准帧匹配点 [(x,y), ...]
            'cur_pts': list,         # 当前帧匹配点 [(x,y), ...]
            'outlier_pts': list,     # 异常点（外点）[(x,y), ...]
            'inlier_pts': list,      # 正常点（内点）[(x,y), ...]
            'translation': float,    # 平移量
            'rotation': float,       # 旋转角度
            'scale_change': float,   # 尺度变化
        }
    """
    _init_detector()
    
    result = {
        'moved': False,
        'ref_pts': [],
        'cur_pts': [],
        'outlier_pts': [],
        'inlier_pts': [],
        'translation': 0.0,
        'rotation': 0.0,
        'scale_change': 0.0,
    }
    
    # 获取通道特定状态
    state = _get_channel_state(channel_id)
    
    # 检查基准帧
    if state['ref_gray'] is None or state['ref_descriptors'] is None:
        result['moved'] = True
        return result
    
    if roi_image is None or roi_image.size == 0:
        result['moved'] = True
        return result
    
    # 转灰度
    gray = cv2.cvtColor(roi_image, cv2.COLOR_BGR2GRAY) if len(roi_image.shape) == 3 else roi_image.copy()
    
    # 使用掩膜
    if exclude_mask is not None:
        h, w = gray.shape
        mask = np.ones((h, w), dtype=np.uint8) * 255
        mask[exclude_mask > 0] = 0
    else:
        mask = state['static_mask']
    
    # 提取特征点
    orb = _shared_detector['orb']
    bf_matcher = _shared_detector['bf_matcher']
    
    keypoints, descriptors = orb.detectAndCompute(gray, mask)
    
    if _camera_debug:
        valid_pixels = np.sum(mask > 0)
        total_pixels = mask.shape[0] * mask.shape[1]
        _camera_logger.debug(f"[相机检测] channel={channel_id} | mask有效区域: {valid_pixels}/{total_pixels} ({100*valid_pixels/total_pixels:.1f}%) | 特征点: {len(keypoints) if keypoints else 0}")
    
    if descriptors is None or len(keypoints) < _detector_params['min_match_count']:
        _update_vote_queue(True, channel_id)
        result['moved'] = _get_vote_result(channel_id)
        return result
    
    # 特征匹配
    ref_descriptors = state['ref_descriptors']
    matches = bf_matcher.knnMatch(ref_descriptors, descriptors, k=2)
    
    # Lowe's ratio test
    good_matches = []
    for match_pair in matches:
        if len(match_pair) == 2:
            m, n = match_pair
            if m.distance < 0.75 * n.distance:
                good_matches.append(m)
    
    if len(good_matches) < _detector_params['min_match_count']:
        _update_vote_queue(True, channel_id)
        result['moved'] = _get_vote_result(channel_id)
        return result
    
    # 提取匹配点坐标
    ref_keypoints = state['ref_keypoints']
    ref_pts = np.float32([ref_keypoints[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    cur_pts = np.float32([keypoints[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    
    # 保存匹配点
    result['ref_pts'] = [(int(p[0][0]), int(p[0][1])) for p in ref_pts]
    result['cur_pts'] = [(int(p[0][0]), int(p[0][1])) for p in cur_pts]
    
    # RANSAC估计单应矩阵
    H, mask_h = cv2.findHomography(ref_pts, cur_pts, cv2.RANSAC, 5.0)
    
    if H is None:
        _update_vote_queue(True, channel_id)
        result['moved'] = _get_vote_result(channel_id)
        return result
    
    # 分离内点和外点
    for i, (cur_pt, is_inlier) in enumerate(zip(cur_pts, mask_h)):
        pt = (int(cur_pt[0][0]), int(cur_pt[0][1]))
        if is_inlier[0]:
            result['inlier_pts'].append(pt)
        else:
            result['outlier_pts'].append(pt)
    
    # 计算内点比例
    inlier_ratio = np.sum(mask_h) / len(good_matches)
    
    # 从单应矩阵提取姿态变化参数
    ref_gray = state['ref_gray']
    h, w = ref_gray.shape
    center = np.array([[w/2, h/2]], dtype=np.float32).reshape(-1, 1, 2)
    transformed_center = cv2.perspectiveTransform(center, H)
    
    # 平移
    dx = transformed_center[0, 0, 0] - center[0, 0, 0]
    dy = transformed_center[0, 0, 1] - center[0, 0, 1]
    translation = np.sqrt(dx**2 + dy**2)
    result['translation'] = translation
    
    # 旋转
    rotation = abs(np.arctan2(H[1, 0], H[0, 0]) * 180 / np.pi)
    result['rotation'] = rotation
    
    # 尺度变化
    scale = np.sqrt(H[0, 0]**2 + H[1, 0]**2)
    scale_change = abs(scale - 1.0)
    result['scale_change'] = scale_change
    
    # 判断是否发生姿态变化
    changed = False
    change_reason = None
    
    if translation > _detector_params['translation_threshold']:
        changed = True
        change_reason = f"平移超限({translation:.2f}>{_detector_params['translation_threshold']})"
    elif rotation > _detector_params['rotation_threshold']:
        changed = True
        change_reason = f"旋转超限({rotation:.2f}>{_detector_params['rotation_threshold']})"
    elif scale_change > _detector_params['scale_threshold']:
        changed = True
        change_reason = f"尺度超限({scale_change:.3f}>{_detector_params['scale_threshold']})"
    elif inlier_ratio < _detector_params['inlier_ratio_threshold']:
        changed = True
        change_reason = f"内点比例过低({inlier_ratio:.2f}<{_detector_params['inlier_ratio_threshold']})"
    
    if _camera_debug:
        log_msg = (f"[相机检测] channel={channel_id} | 匹配点={len(good_matches)} | "
                   f"平移={translation:.2f}px | 旋转={rotation:.2f}° | 尺度变化={scale_change:.3f} | "
                   f"内点比例={inlier_ratio:.2f} | changed={changed}")
        if change_reason:
            log_msg += f" | 原因: {change_reason}"
        _camera_logger.debug(log_msg)
    
    _update_vote_queue(changed, channel_id)
    result['moved'] = _get_vote_result(channel_id)
    return result


def _update_vote_queue(changed: bool, channel_id: str = 'default'):
    """更新投票队列"""
    state = _get_channel_state(channel_id)
    queue = state['vote_queue']
    queue.append(changed)
    max_frames = _detector_params['voting_frames']
    if len(queue) > max_frames:
        queue.pop(0)


def _get_vote_result(channel_id: str = 'default') -> bool:
    """获取投票结果"""
    state = _get_channel_state(channel_id)
    queue = state['vote_queue']
    if len(queue) == 0:
        return False
    change_count = sum(queue)
    return change_count / len(queue) >= _detector_params['voting_ratio']


def reset_camera_detector(channel_id: str = None):
    """重置相机姿态检测器状态
    
    Args:
        channel_id: 通道ID，如果为None则重置所有通道
    """
    if channel_id is None:
        # 重置所有通道
        _channel_detector_states.clear()
    else:
        # 重置指定通道
        if channel_id in _channel_detector_states:
            _channel_detector_states[channel_id] = {
                'ref_gray': None,
                'ref_keypoints': None,
                'ref_descriptors': None,
                'static_mask': None,
                'vote_queue': [],
            }


def set_camera_detector_params(
    translation_threshold: float = None,
    rotation_threshold: float = None,
    scale_threshold: float = None,
    inlier_ratio_threshold: float = None,
    min_match_count: int = None,
    voting_frames: int = None,
    voting_ratio: float = None
):
    """
    设置检测器参数（全局参数，影响所有通道）
    
    Args:
        translation_threshold: 平移阈值(像素)
        rotation_threshold: 旋转阈值(度)
        scale_threshold: 尺度变化阈值
        inlier_ratio_threshold: 内点比例阈值
        min_match_count: 最少匹配点数量
        voting_frames: 投票帧数
        voting_ratio: 投票通过比例
    """
    if translation_threshold is not None:
        _detector_params['translation_threshold'] = translation_threshold
    if rotation_threshold is not None:
        _detector_params['rotation_threshold'] = rotation_threshold
    if scale_threshold is not None:
        _detector_params['scale_threshold'] = scale_threshold
    if inlier_ratio_threshold is not None:
        _detector_params['inlier_ratio_threshold'] = inlier_ratio_threshold
    if min_match_count is not None:
        _detector_params['min_match_count'] = min_match_count
    if voting_frames is not None:
        _detector_params['voting_frames'] = voting_frames
    if voting_ratio is not None:
        _detector_params['voting_ratio'] = voting_ratio


def extract_detection_roi(
    frame: np.ndarray,
    big_roi: Tuple[int, int, int, int],
    small_roi: Optional[Tuple[int, int, int, int]] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """
    从完整帧中提取检测区域（大ROI - 小ROI）
    
    Args:
        frame: 完整帧图像
        big_roi: 大ROI坐标 (x1, y1, x2, y2)
        small_roi: 小ROI坐标 (x1, y1, x2, y2)，可选
    
    Returns:
        (roi_image, exclude_mask)
        - roi_image: 大ROI区域图像
        - exclude_mask: 排除掩膜（小ROI区域为255，其他为0）
    """
    bx1, by1, bx2, by2 = big_roi
    roi_image = frame[by1:by2, bx1:bx2].copy()
    
    # 创建排除掩膜
    roi_h, roi_w = roi_image.shape[:2]
    exclude_mask = np.zeros((roi_h, roi_w), dtype=np.uint8)
    
    if small_roi is not None:
        sx1, sy1, sx2, sy2 = small_roi
        # 转换到大ROI坐标系
        sx1_rel = max(0, sx1 - bx1)
        sy1_rel = max(0, sy1 - by1)
        sx2_rel = min(roi_w, sx2 - bx1)
        sy2_rel = min(roi_h, sy2 - by1)
        if sx2_rel > sx1_rel and sy2_rel > sy1_rel:
            exclude_mask[sy1_rel:sy2_rel, sx1_rel:sx2_rel] = 255
    
    return roi_image, exclude_mask


# ============== 独立调试入口 ==============
if __name__ == "__main__":
    """
    独立调试模式 - 使用海康SDK获取画面测试相机姿态检测
    运行: python utils/cameraposition.py
    
    操作流程:
    1. 连接相机后先设置大ROI（按B键）
    2. 再设置小ROI（按S键）
    3. 按R键设置基准帧开始检测
    """
    import sys
    import os
    import time
    from PIL import Image, ImageDraw, ImageFont
    
    # 添加项目根目录到路径
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from handlers.videopage.HK_SDK.HKcapture import HKcapture
    
    # 开启调试
    _camera_debug = True
    
    # RTSP配置
    RTSP_URL = "rtsp://admin:cei345678@192.168.8.127:8000/stream1"
    
    # ROI状态
    big_roi = None      # 大ROI (x1, y1, x2, y2)
    small_roi = None    # 小ROI (x1, y1, x2, y2)
    drawing = False     # 是否正在绘制
    draw_mode = None    # 'big' or 'small'
    start_point = None  # 绘制起点
    temp_end = None     # 临时终点（用于实时显示）
    
    # 中文字体（尝试加载系统字体）
    _cn_font = None
    _cn_font_small = None
    try:
        # Windows系统字体路径
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",    # 黑体
            "C:/Windows/Fonts/simsun.ttc",    # 宋体
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                _cn_font = ImageFont.truetype(fp, 24)
                _cn_font_small = ImageFont.truetype(fp, 16)
                break
    except:
        pass
    
    def put_chinese_text(img, text, pos, color, font=None):
        """在图像上绘制中文文本"""
        if font is None:
            font = _cn_font
        if font is None:
            # 回退到OpenCV（中文会乱码）
            cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)
            return img
        
        # 转换BGR到RGB
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        # PIL颜色是RGB，OpenCV是BGR
        rgb_color = (color[2], color[1], color[0])
        draw.text(pos, text, font=font, fill=rgb_color)
        return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    
    def mouse_callback(event, x, y, flags, param):
        """鼠标回调函数"""
        global big_roi, small_roi, drawing, draw_mode, start_point, temp_end
        
        if draw_mode is None:
            return
        
        if event == cv2.EVENT_LBUTTONDOWN:
            drawing = True
            start_point = (x, y)
            temp_end = (x, y)
        elif event == cv2.EVENT_MOUSEMOVE and drawing:
            temp_end = (x, y)
        elif event == cv2.EVENT_LBUTTONUP and drawing:
            drawing = False
            x1, y1 = start_point
            x2, y2 = x, y
            # 确保坐标顺序正确
            roi = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            if draw_mode == 'big':
                big_roi = roi
                _camera_logger.info(f"大ROI已设置: {big_roi}")
            elif draw_mode == 'small':
                small_roi = roi
                _camera_logger.info(f"小ROI已设置: {small_roi}")
            draw_mode = None
            start_point = None
            temp_end = None
    
    _camera_logger.info("=" * 50)
    _camera_logger.info("相机姿态检测独立调试启动")
    _camera_logger.info(f"RTSP: {RTSP_URL}")
    _camera_logger.info("=" * 50)
    
    # 使用HKcapture连接
    cap = HKcapture(source=RTSP_URL, debug=False)
    
    if not cap.open():
        _camera_logger.error("连接失败")
        exit(1)
    
    if not cap.start_capture():
        _camera_logger.error("启动捕获失败")
        cap.release()
        exit(1)
    
    _camera_logger.info("连接成功，等待数据流...")
    time.sleep(2)
    
    width, height = cap.get_frame_size()
    _camera_logger.info(f"分辨率: {width}x{height}")
    
    # 创建窗口并绑定鼠标回调
    cv2.namedWindow("Camera Position Debug")
    cv2.setMouseCallback("Camera Position Debug", mouse_callback)
    
    reference_set = False
    frame_count = 0
    last_time = time.time()
    fps_display = 0
    alert_shown = False  # 是否已弹出警告对话框
    
    def show_camera_moved_alert():
        """弹出相机移动警告对话框"""
        import ctypes
        # Windows MessageBox
        # MB_OK = 0x0, MB_ICONWARNING = 0x30
        ctypes.windll.user32.MessageBoxW(
            0, 
            "检测到相机位置发生变化！\n\n"
            "检测输入已暂停。\n"
            "请检查相机是否被移动或震动。\n"
            "点击确定后将重置基准帧并恢复检测。", 
            "相机姿态警告", 
            0x30
        )
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue
            
            frame_count += 1
            current_time = time.time()
            if current_time - last_time >= 1.0:
                fps_display = frame_count
                frame_count = 0
                last_time = current_time
            
            # 提取ROI区域进行检测
            if big_roi is not None:
                roi_image, exclude_mask = extract_detection_roi(frame, big_roi, small_roi)
            else:
                roi_image = frame.copy()
                exclude_mask = None
            
            # 首帧或重置后设置基准
            if not reference_set and big_roi is not None:
                if set_camera_reference(roi_image, exclude_mask, 'debug'):
                    reference_set = True
                    alert_shown = False  # 重置警告状态
                    _camera_logger.info("基准帧已设置")
                else:
                    _camera_logger.warning("特征点不足，请调整ROI")
            
            # 检测
            camera_moved = False
            detect_result = None
            if reference_set:
                detect_result = detect_camera_moved_detail(roi_image, exclude_mask, 'debug')
                camera_moved = detect_result['moved']
                
                # 相机移动时弹出对话框（只弹一次）
                if camera_moved and not alert_shown:
                    alert_shown = True
                    print("⚠️ 检测到相机移动，弹出警告...")
                    show_camera_moved_alert()
                    # 对话框关闭后重置基准帧
                    reset_camera_detector('debug')
                    reference_set = False
                    _camera_logger.warning("检测到相机移动，基准帧已重置")
            
            # 显示
            display = frame.copy()
            
            # 绘制检测点（在大ROI坐标系内，需要偏移到原图坐标）
            if detect_result and big_roi is not None:
                bx1, by1 = big_roi[0], big_roi[1]
                # 绘制内点（绿色小圆）
                for pt in detect_result['inlier_pts']:
                    cv2.circle(display, (pt[0] + bx1, pt[1] + by1), 3, (0, 255, 0), -1)
                # 绘制外点（红色大圆，表示变化区域）
                for pt in detect_result['outlier_pts']:
                    cv2.circle(display, (pt[0] + bx1, pt[1] + by1), 6, (0, 0, 255), -1)
                    cv2.circle(display, (pt[0] + bx1, pt[1] + by1), 10, (0, 0, 255), 2)
            
            # 绘制大ROI（蓝色）
            if big_roi is not None:
                cv2.rectangle(display, (big_roi[0], big_roi[1]), (big_roi[2], big_roi[3]), (255, 0, 0), 2)
                display = put_chinese_text(display, "大ROI", (big_roi[0], big_roi[1] - 25), (255, 0, 0), _cn_font_small)
            
            # 绘制小ROI（黄色）
            if small_roi is not None:
                cv2.rectangle(display, (small_roi[0], small_roi[1]), (small_roi[2], small_roi[3]), (0, 255, 255), 2)
                display = put_chinese_text(display, "小ROI", (small_roi[0], small_roi[1] - 25), (0, 255, 255), _cn_font_small)
            
            # 绘制正在拖拽的矩形
            if drawing and start_point and temp_end:
                color = (255, 0, 0) if draw_mode == 'big' else (0, 255, 255)
                cv2.rectangle(display, start_point, temp_end, color, 1)
            
            # 状态栏背景
            cv2.rectangle(display, (0, 0), (width, 100), (40, 40, 40), -1)
            
            # 检测状态
            status_color = (0, 0, 255) if camera_moved else (0, 255, 0)
            status_text = "相机移动!" if camera_moved else "相机稳定"
            display = put_chinese_text(display, status_text, (10, 8), status_color)
            
            # FPS和基准帧状态
            ref_text = f"FPS:{fps_display}  基准帧:{'已设置' if reference_set else '未设置'}"
            display = put_chinese_text(display, ref_text, (10, 40), (255, 255, 255), _cn_font_small)
            
            # ROI状态
            roi_status = f"大ROI:{'已设置' if big_roi else '未设置'}  小ROI:{'已设置' if small_roi else '未设置'}"
            display = put_chinese_text(display, roi_status, (10, 65), (200, 200, 200), _cn_font_small)
            
            # 绘制模式提示
            if draw_mode:
                mode_text = f"绘制{'大' if draw_mode == 'big' else '小'}ROI中..."
                display = put_chinese_text(display, mode_text, (250, 8), (0, 255, 255))
            
            # 操作提示
            display = put_chinese_text(display, "[B]大ROI [S]小ROI [C]清除 [R]基准 [D]调试 [Q]退出", 
                                       (250, 65), (180, 180, 180), _cn_font_small)
            
            cv2.imshow("Camera Position Debug", display)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
            elif key == ord('b'):
                draw_mode = 'big'
                _camera_logger.info("开始绘制大ROI...")
            elif key == ord('s'):
                draw_mode = 'small'
                _camera_logger.info("开始绘制小ROI...")
            elif key == ord('c'):
                big_roi = None
                small_roi = None
                reference_set = False
                reset_camera_detector('debug')
                _camera_logger.info("ROI已清除")
            elif key == ord('r'):
                reset_camera_detector('debug')
                reference_set = False
                _camera_logger.info("基准帧重置，等待重新设置...")
            elif key == ord('d'):
                _camera_debug = not _camera_debug
                _camera_logger.info(f"调试模式: {'ON' if _camera_debug else 'OFF'}")
                
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        _camera_logger.info("程序退出")
