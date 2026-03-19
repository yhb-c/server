#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强WebSocket服务器启动脚本
确保停止旧服务器并启动新的增强服务器
"""

import os
import sys
import asyncio
import logging
import signal
import subprocess
from pathlib import Path

# 添加项目路径
current_dir = Path(__file__).parent
websocket_dir = current_dir / 'websocket'
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(websocket_dir))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def kill_existing_servers():
    """停止现有的WebSocket服务器进程"""
    try:
        logger.info("检查并停止现有的WebSocket服务器进程...")
        
        # 查找占用8085端口的进程
        result = subprocess.run(['lsof', '-ti:8085'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    logger.info(f"停止进程 PID: {pid}")
                    subprocess.run(['kill', '-9', pid])
                    
        logger.info("现有服务器进程已停止")
        
    except Exception as e:
        logger.warning(f"停止现有进程时出错: {e}")

async def start_enhanced_server():
    """启动增强WebSocket服务器"""
    try:
        # 直接导入模块
        import enhanced_ws_server
        import config_manager
        
        logger.info("=" * 60)
        logger.info("启动增强WebSocket服务器")
        logger.info("=" * 60)

        # 初始化配置管理器
        logger.info("初始化配置管理器...")
        config_mgr = config_manager.ConfigManager()
        
        # 获取WebSocket配置
        ws_config = config_mgr.system_config.get('websocket', {})
        host = ws_config.get('host', '0.0.0.0')
        port = ws_config.get('port', 8085)

        # 创建增强WebSocket服务器
        logger.info("创建增强WebSocket服务器...")
        server = enhanced_ws_server.EnhancedWebSocketServer(host=host, port=port)

        print("=" * 60)
        print("WebSocket服务器配置:")
        print(f"监听地址: {host}:{port}")
        print(f"客户端连接地址: ws://192.168.0.121:{port}")
        print("=" * 60)

        # 启动服务器
        logger.info("启动增强WebSocket服务器...")
        await server.start()

    except Exception as e:
        logger.error(f"✗ WebSocket服务器启动失败: {e}")
        import traceback
        logger.error(f"错误详情:\n{traceback.format_exc()}")
        raise

async def main():
    """主函数"""
    try:
        # 停止现有服务器
        kill_existing_servers()
        
        # 等待端口释放
        await asyncio.sleep(2)
        
        # 启动新服务器
        await start_enhanced_server()
        
    except KeyboardInterrupt:
        logger.info("用户中断，正在停止服务器...")
    except Exception as e:
        logger.error(f"服务器运行异常: {e}")
        raise

if __name__ == "__main__":
    try:
        print("启动增强WebSocket服务器...")
        print("按 Ctrl+C 停止服务器")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n正在停止服务器...")
        print("服务器已停止")
    except Exception as e:
        print(f"启动失败: {e}")
        sys.exit(1)