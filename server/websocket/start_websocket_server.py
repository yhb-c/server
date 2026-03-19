#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强WebSocket服务端启动脚本
集成液位检测功能，支持实时推送检测结果
"""

import os
import sys
import asyncio
import logging
import signal
from pathlib import Path

# 添加项目路径
current_dir = Path(__file__).parent
server_root = current_dir.parent  # server目录
sys.path.insert(0, str(server_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(server_root / 'logs' / 'websocket_server.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# 全局服务器实例
server_instance = None

async def start_enhanced_ws_server():
    """启动增强WebSocket服务器"""
    global server_instance
    
    try:
        # 修复导入路径 - 直接从当前目录导入
        from enhanced_ws_server import EnhancedWebSocketServer
        from config_manager import ConfigManager

        logger.info("初始化配置管理器...")
        config_manager = ConfigManager()
        
        # 获取WebSocket配置
        ws_config = config_manager.system_config.get('websocket', {})
        host = ws_config.get('host', '0.0.0.0')
        port = ws_config.get('port', 8085)

        logger.info("创建增强WebSocket服务器...")
        server_instance = EnhancedWebSocketServer(host=host, port=port)

        print("=" * 70)
        print("增强WebSocket服务器配置:")
        print(f"  监听地址: {host}:{port}")
        print(f"  客户端连接地址: ws://192.168.0.121:{port}")
        print(f"  支持功能:")
        print(f"    - 液位检测")
        print(f"    - 实时数据推送")
        print(f"    - 多通道管理")
        print(f"    - 模型加载")
        print(f"    - 配置管理")
        print("=" * 70)

        # 启动服务器
        logger.info("启动增强WebSocket服务器...")
        await server_instance.start()

    except Exception as e:
        logger.error(f"增强WebSocket服务器启动失败: {e}")
        import traceback
        traceback.print_exc()
        raise

def signal_handler(signum, frame):
    """信号处理器"""
    logger.info(f"收到信号 {signum}，正在停止服务器...")
    if server_instance:
        # 创建停止任务
        loop = asyncio.get_event_loop()
        loop.create_task(server_instance.stop())

async def main():
    """主函数"""
    try:
        # 注册信号处理器
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)
        if hasattr(signal, 'SIGINT'):
            signal.signal(signal.SIGINT, signal_handler)
        
        # 启动服务器
        await start_enhanced_ws_server()
        
    except KeyboardInterrupt:
        logger.info("用户中断，正在停止服务器...")
    except Exception as e:
        logger.error(f"服务器运行异常: {e}")
        raise
    finally:
        if server_instance:
            await server_instance.stop()
        logger.info("增强WebSocket服务器已停止")

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
