# -*- coding: utf-8 -*-
"""
数据集管理 API
"""

from .base_api import BaseAPI


class DatasetAPI(BaseAPI):
    """数据集管理 API 客户端"""
    
    def __init__(self, base_url, token_manager=None):
        super().__init__(base_url, token_manager)
    
    def list_datasets(self):
        """
        获取数据集列表
        
        Returns:
            dict: {'success': bool, 'data': list, 'message': str}
        """
        return self.get('/api/datasets')
    
    def get_dataset(self, dataset_id):
        """
        获取数据集详情
        
        Args:
            dataset_id: 数据集ID
            
        Returns:
            dict: {'success': bool, 'data': dict, 'message': str}
        """
        return self.get(f'/api/datasets/{dataset_id}')
    
    def create_dataset(self, dataset_name, description=''):
        """
        创建数据集
        
        Args:
            dataset_name: 数据集名称
            description: 描述
            
        Returns:
            dict: {'success': bool, 'data': dict, 'message': str}
        """
        data = {
            'name': dataset_name,
            'description': description
        }
        return self.post('/api/datasets', json=data)
    
    def delete_dataset(self, dataset_id):
        """
        删除数据集
        
        Args:
            dataset_id: 数据集ID
            
        Returns:
            dict: {'success': bool, 'message': str}
        """
        return self.delete(f'/api/datasets/{dataset_id}')
    
    def upload_images(self, dataset_id, image_files):
        """
        批量上传图片到数据集
        
        Args:
            dataset_id: 数据集ID
            image_files: 图片文件路径列表
            
        Returns:
            dict: {'success': bool, 'data': dict, 'message': str}
        """
        files = []
        for img_path in image_files:
            with open(img_path, 'rb') as f:
                files.append(('files', (img_path, f.read(), 'image/jpeg')))
        
        return self.post(f'/api/datasets/{dataset_id}/images', files=files)
    
    def delete_image(self, dataset_id, image_id):
        """
        删除数据集中的图片
        
        Args:
            dataset_id: 数据集ID
            image_id: 图片ID
            
        Returns:
            dict: {'success': bool, 'message': str}
        """
        return self.delete(f'/api/datasets/{dataset_id}/images/{image_id}')
    
    def list_images(self, dataset_id, page=1, page_size=50):
        """
        获取数据集图片列表
        
        Args:
            dataset_id: 数据集ID
            page: 页码
            page_size: 每页数量
            
        Returns:
            dict: {'success': bool, 'data': list, 'message': str}
        """
        params = {'page': page, 'page_size': page_size}
        return self.get(f'/api/datasets/{dataset_id}/images', params=params)
    
    def get_dataset_statistics(self, dataset_id):
        """
        获取数据集统计信息
        
        Args:
            dataset_id: 数据集ID
            
        Returns:
            dict: {'success': bool, 'data': dict, 'message': str}
        """
        return self.get(f'/api/datasets/{dataset_id}/statistics')
    
    def export_dataset(self, dataset_id, format='yolo'):
        """
        导出数据集
        
        Args:
            dataset_id: 数据集ID
            format: 导出格式 (yolo, coco, voc)
            
        Returns:
            dict: {'success': bool, 'data': str, 'message': str}
        """
        params = {'format': format}
        return self.get(f'/api/datasets/{dataset_id}/export', params=params)
