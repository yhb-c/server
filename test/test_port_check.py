#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试端口检测功能
验证WebSocket端口检测不会导致服务器报错
"""

import socket
import http.client


def check_port(host, port, timeout=2, is_websocket=False):
    """
    检查指定主机端口是否开放

    Args:
        host: 主机地址
        port: 端口号
        timeout: 超时时间（秒）
        is_websocket: 是否为WebSocket端口（需要发送HTTP升级请求）

    Returns:
        bool: 端口开放返回 True，否则返回 False
    """
    try:
        if is_websocket:
            # WebSocket端口检测：发送完整的WebSocket握手请求
            try:
                conn = http.client.HTTPConnection(host, port, timeout=timeout)
                headers = {
                    'Upgrade': 'websocket',
                    'Connection': 'Upgrade',
                    'Sec-WebSocket-Key': 'dGhlIHNhbXBsZSBub25jZQ==',
                    'Sec-WebSocket-Version': '13'
                }
                conn.request("GET", "/", headers=headers)
                response = conn.getresponse()
                conn.close()
                # 101 Switching Protocols 或任何响应都说明端口开放
                return True
            except Exception:
                return False
        else:
            # 普通TCP端口检测
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
    except Exception as e:
        print(f"[端口检测] 检测 {host}:{port} 失败: {e}")
        return False


if __name__ == "__main__":
    print("测试端口检测功能")
    print("=" * 50)

    # 测试API端口（普通HTTP）
    api_host = "192.168.0.121"
    api_port = 8084
    print(f"\n检测API端口: {api_host}:{api_port}")
    api_result = check_port(api_host, api_port, is_websocket=False)
    print(f"结果: {'开放' if api_result else '关闭'}")

    # 测试WebSocket端口
    ws_host = "192.168.0.121"
    ws_port = 8085
    print(f"\n检测WebSocket端口: {ws_host}:{ws_port}")
    ws_result = check_port(ws_host, ws_port, is_websocket=True)
    print(f"结果: {'开放' if ws_result else '关闭'}")

    print("\n" + "=" * 50)
    print("测试完成")
