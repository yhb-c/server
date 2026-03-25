# -*- coding: utf-8 -*-
"""
数据库客户端模块
提供与服务器 MySQL 数据库交互的接口
"""

import requests
from typing import List, Dict, Optional, Any
from datetime import datetime
import json


class DatabaseClient:
    """数据库客户端 - 通过 HTTP API 与服务器数据库交互"""

    def __init__(self, base_url: str = "http://localhost:8080"):
        """
        初始化数据库客户端

        Args:
            base_url: API 服务器地址
        """
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })

    # ==================== 任务相关接口 ====================

    def create_mission(self, mission_data: Dict) -> Dict:
        """
        创建任务

        Args:
            mission_data: 任务数据
                {
                    "task_id": "1",
                    "task_name": "测试任务",
                    "status": "未启动",
                    "selected_channels": ["通道1", "通道2"],
                    "created_time": "2026-03-25T10:00:00Z",
                    "mission_result_folder_path": "/path/to/results"
                }

        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/missions"
        try:
            response = self.session.post(url, json=mission_data, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def get_missions(self, limit: int = 10, offset: int = 0) -> List[Dict]:
        """
        获取任务列表

        Args:
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            list: 任务列表
        """
        url = f"{self.base_url}/api/missions"
        params = {"limit": limit, "offset": offset}

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取任务列表失败: {e}")
            return []

    def get_mission(self, task_id: str) -> Optional[Dict]:
        """
        获取单个任务

        Args:
            task_id: 任务ID

        Returns:
            dict: 任务数据
        """
        url = f"{self.base_url}/api/missions/{task_id}"

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取任务失败: {e}")
            return None

    def update_mission_status(self, task_id: str, status: str) -> Dict:
        """
        更新任务状态

        Args:
            task_id: 任务ID
            status: 新状态（未启动/进行中/已完成/已暂停）

        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/missions/{task_id}/status"
        data = {"status": status}

        try:
            response = self.session.put(url, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def delete_mission(self, task_id: str) -> Dict:
        """
        删除任务

        Args:
            task_id: 任务ID

        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/missions/{task_id}"

        try:
            response = self.session.delete(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    # ==================== 任务结果相关接口 ====================

    def get_mission_results(
        self,
        task_id: str,
        channel: Optional[str] = None,
        region: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict]:
        """
        获取任务结果数据

        Args:
            task_id: 任务ID
            channel: 通道名称（可选）
            region: 区域名称（可选）
            start_time: 开始时间（可选）
            end_time: 结束时间（可选）

        Returns:
            list: 结果数据列表
        """
        url = f"{self.base_url}/api/missions/{task_id}/results"
        params = {}

        if channel:
            params["channel"] = channel
        if region:
            params["region"] = region
        if start_time:
            params["start_time"] = start_time.isoformat()
        if end_time:
            params["end_time"] = end_time.isoformat()

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取任务结果失败: {e}")
            return []

    def create_mission_result(
        self,
        task_id: str,
        channel_name: str,
        region_name: str,
        timestamp: datetime,
        value: float
    ) -> Dict:
        """
        创建任务结果记录

        Args:
            task_id: 任务ID
            channel_name: 通道名称
            region_name: 区域名称
            timestamp: 时间戳
            value: 数值

        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/missions/{task_id}/results"
        data = {
            "channel_name": channel_name,
            "region_name": region_name,
            "timestamp": timestamp.isoformat(),
            "value": value
        }

        try:
            response = self.session.post(url, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def batch_create_results(
        self,
        task_id: str,
        results: List[Dict]
    ) -> Dict:
        """
        批量创建任务结果

        Args:
            task_id: 任务ID
            results: 结果列表
                [
                    {
                        "channel_name": "通道1",
                        "region_name": "区域1",
                        "timestamp": "2026-03-25T10:00:00Z",
                        "value": 1.5
                    },
                    ...
                ]

        Returns:
            dict: 响应数据
        """
        success_count = 0
        error_count = 0

        for result in results:
            timestamp = datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))
            response = self.create_mission_result(
                task_id,
                result["channel_name"],
                result["region_name"],
                timestamp,
                result["value"]
            )

            if "error" not in response:
                success_count += 1
            else:
                error_count += 1

        return {
            "success": success_count,
            "error": error_count,
            "total": len(results)
        }

    # ==================== 配置相关接口 ====================

    def save_config(
        self,
        config_type: str,
        config_name: str,
        config_data: Dict
    ) -> Dict:
        """
        保存配置

        Args:
            config_type: 配置类型（system/channel/mission等）
            config_name: 配置名称
            config_data: 配置数据

        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/configs"
        data = {
            "config_type": config_type,
            "config_name": config_name,
            "config_data": config_data
        }

        try:
            response = self.session.post(url, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def get_config(
        self,
        config_type: str,
        config_name: str
    ) -> Optional[Dict]:
        """
        获取配置

        Args:
            config_type: 配置类型
            config_name: 配置名称

        Returns:
            dict: 配置数据
        """
        url = f"{self.base_url}/api/configs/{config_type}/{config_name}"

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取配置失败: {e}")
            return None

    def list_configs(self, config_type: Optional[str] = None) -> List[Dict]:
        """
        列出配置

        Args:
            config_type: 配置类型（可选）

        Returns:
            list: 配置列表
        """
        url = f"{self.base_url}/api/configs"
        params = {}

        if config_type:
            params["type"] = config_type

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取配置列表失败: {e}")
            return []

    def delete_config(
        self,
        config_type: str,
        config_name: str
    ) -> Dict:
        """
        删除配置

        Args:
            config_type: 配置类型
            config_name: 配置名称

        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}/api/configs/{config_type}/{config_name}"

        try:
            response = self.session.delete(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    # ==================== 工具方法 ====================

    def test_connection(self) -> bool:
        """
        测试连接

        Returns:
            bool: 连接是否成功
        """
        try:
            response = self.session.get(f"{self.base_url}/api/missions", timeout=5)
            return response.status_code == 200
        except:
            return False

    def close(self):
        """关闭连接"""
        self.session.close()
