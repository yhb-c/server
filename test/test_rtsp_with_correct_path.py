#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用正确路径测试服务端RTSP流捕获功能
"""

import os
import sys
import subprocess
import time
import json

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def create_corrected_rtsp_test_script():
    """创建修正路径的RTSP测试脚本"""
    print("=== 创建修正路径的RTSP测试脚本 ===")
    
    test_script = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
服务端RTSP流捕获测试 - 修正版本
"""

import os
import sys
import cv2
import time
import logging
import json

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_opencv_rtsp():
    """测试OpenCV RTSP连接"""
    logger.info("=== 测试OpenCV RTSP连接 ===")
    
    rtsp_url = "rtsp://admin:cei345678@192.168.0.27:8000/stream1"
    logger.info(f"RTSP地址: {rtsp_url}")
    
    try:
        # 创建VideoCapture对象
        cap = cv2.VideoCapture(rtsp_url)
        
        if not cap.isOpened():
            logger.error("无法打开RTSP流")
            return False
        
        logger.info("RTSP流打开成功")
        
        # 设置缓冲区大小
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # 获取视频信息
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        logger.info(f"视频信息 - FPS: {fps}, 分辨率: {width}x{height}")
        
        # 读取几帧测试
        frame_count = 0
        success_count = 0
        start_time = time.time()
        
        for i in range(10):  # 测试10帧
            ret, frame = cap.read()
            frame_count += 1
            
            if ret:
                success_count += 1
                logger.info(f"成功读取第{frame_count}帧, 形状: {frame.shape}")
            else:
                logger.warning(f"读取第{frame_count}帧失败")
            
            time.sleep(0.2)  # 200ms间隔
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        logger.info(f"测试完成 - 总帧数: {frame_count}, 成功: {success_count}, 耗时: {elapsed:.2f}s")
        logger.info(f"成功率: {success_count/frame_count*100:.1f}%")
        
        cap.release()
        return success_count > 0
        
    except Exception as e:
        logger.error(f"OpenCV RTSP测试异常: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_hikvision_sdk():
    """测试海康威视SDK"""
    logger.info("=== 测试海康威视SDK ===")
    
    # 正确的SDK库路径
    sdk_lib_path = "/home/lqj/liquid/server/lib/lib"
    
    if not os.path.exists(sdk_lib_path):
        logger.error(f"海康SDK库路径不存在: {sdk_lib_path}")
        return False
    
    logger.info(f"SDK库路径: {sdk_lib_path}")
    
    # 列出库文件
    try:
        lib_files = os.listdir(sdk_lib_path)
        logger.info(f"SDK库文件数量: {len(lib_files)}")
        
        # 查找关键的库文件
        key_libs = [f for f in lib_files if 'hcnetsdk' in f.lower() or 'hikvision' in f.lower()]
        if key_libs:
            logger.info(f"找到关键库文件: {key_libs}")
        else:
            logger.warning("未找到关键的海康SDK库文件")
            
    except Exception as e:
        logger.error(f"无法列出SDK库文件: {e}")
        return False
    
    # 检查环境变量
    ld_library_path = os.environ.get('LD_LIBRARY_PATH', '')
    logger.info(f"当前LD_LIBRARY_PATH: {ld_library_path}")
    
    if sdk_lib_path not in ld_library_path:
        logger.warning("SDK库路径不在LD_LIBRARY_PATH中")
        # 设置环境变量
        os.environ['LD_LIBRARY_PATH'] = f"{sdk_lib_path}:{ld_library_path}"
        logger.info(f"已设置LD_LIBRARY_PATH: {os.environ['LD_LIBRARY_PATH']}")
    
    # 尝试加载海康SDK库
    try:
        import ctypes
        
        # 查找libhcnetsdk.so文件
        hcnetsdk_path = None
        for file in lib_files:
            if 'hcnetsdk' in file.lower() and file.endswith('.so'):
                hcnetsdk_path = os.path.join(sdk_lib_path, file)
                break
        
        if hcnetsdk_path:
            logger.info(f"尝试加载海康SDK: {hcnetsdk_path}")
            hcnetsdk = ctypes.CDLL(hcnetsdk_path)
            logger.info("海康SDK加载成功")
            return True
        else:
            logger.error("未找到libhcnetsdk.so文件")
            return False
            
    except Exception as e:
        logger.error(f"加载海康SDK失败: {e}")
        return False

def test_video_capture_factory():
    """测试视频捕获工厂"""
    logger.info("=== 测试视频捕获工厂 ===")
    
    try:
        # 添加项目路径
        sys.path.insert(0, '/home/lqj/liquid/server')
        
        from video.video_capture_factory import VideoCaptureFactory
        
        rtsp_url = "rtsp://admin:cei345678@192.168.0.27:8000/stream1"
        channel_id = "test_channel"
        
        # 创建视频捕获对象 - 修正参数
        capture = VideoCaptureFactory.create_capture(rtsp_url, channel_id)
        
        if capture is None:
            logger.error("视频捕获对象创建失败")
            return False
        
        logger.info("视频捕获对象创建成功")
        
        # 测试读取帧
        success_count = 0
        for i in range(5):
            frame = capture.read()
            if frame is not None:
                logger.info(f"成功读取帧 {i+1}, 形状: {frame.shape}")
                success_count += 1
            else:
                logger.warning(f"读取帧 {i+1} 失败")
            
            time.sleep(0.5)
        
        # 释放资源
        if hasattr(capture, 'release'):
            capture.release()
        
        return success_count > 0
        
    except Exception as e:
        logger.error(f"视频捕获工厂测试异常: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_network_connectivity():
    """测试网络连通性"""
    logger.info("=== 测试网络连通性 ===")
    
    try:
        import subprocess
        
        # ping相机IP
        result = subprocess.run(['ping', '-c', '3', '192.168.0.27'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            logger.info("相机网络连通正常")
            return True
        else:
            logger.error(f"相机网络连通失败: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"网络连通性测试异常: {e}")
        return False

def main():
    """主函数"""
    logger.info("开始测试服务端RTSP流捕获功能 - 修正版本")
    
    results = {}
    
    # 1. 测试网络连通性
    results['network_connectivity'] = test_network_connectivity()
    
    # 2. 测试OpenCV RTSP连接
    results['opencv_rtsp'] = test_opencv_rtsp()
    
    # 3. 测试海康威视SDK
    results['hikvision_sdk'] = test_hikvision_sdk()
    
    # 4. 测试视频捕获工厂
    results['video_capture_factory'] = test_video_capture_factory()
    
    # 输出测试结果
    logger.info("=== 测试结果汇总 ===")
    for test_name, result in results.items():
        status = "成功" if result else "失败"
        logger.info(f"{test_name}: {status}")
    
    # 保存结果到文件
    result_file = "/home/lqj/liquid/rtsp_test_result_corrected.json"
    try:
        with open(result_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"测试结果已保存到: {result_file}")
    except Exception as e:
        logger.error(f"保存测试结果失败: {e}")

if __name__ == "__main__":
    main()
'''
    
    # 保存测试脚本
    script_path = "test/server_rtsp_test_corrected.py"
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(test_script)
    
    print(f"修正的RTSP测试脚本已创建: {script_path}")
    return script_path

def upload_and_run_corrected_test():
    """上传并运行修正的测试脚本"""
    print("\n=== 上传并运行修正的RTSP测试 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    
    # 创建测试脚本
    script_path = create_corrected_rtsp_test_script()
    
    # 上传测试脚本
    remote_script = "/home/lqj/liquid/server_rtsp_test_corrected.py"
    scp_cmd = f'scp "{script_path}" {username}@{server_ip}:"{remote_script}"'
    
    try:
        result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print("✓ 修正的测试脚本上传成功")
        else:
            print(f"✗ 测试脚本上传失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ 上传测试脚本异常: {e}")
        return False
    
    # 设置脚本权限并执行
    ssh_commands = [
        f"chmod +x {remote_script}",
        f"cd /home/lqj/liquid && source ~/anaconda3/bin/activate liquid && export LD_LIBRARY_PATH=/home/lqj/liquid/server/lib/lib:$LD_LIBRARY_PATH && python {remote_script}"
    ]
    
    for i, cmd in enumerate(ssh_commands):
        ssh_cmd = f'ssh {username}@{server_ip} "{cmd}"'
        print(f"执行命令 {i+1}: {cmd}")
        
        try:
            result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=60, encoding='utf-8', errors='ignore')
            
            print(f"返回码: {result.returncode}")
            if result.stdout:
                print(f"输出:\n{result.stdout}")
            if result.stderr:
                print(f"错误:\n{result.stderr}")
                
        except subprocess.TimeoutExpired:
            print("命令执行超时")
        except Exception as e:
            print(f"命令执行异常: {e}")
    
    return True

def check_corrected_test_results():
    """检查修正测试的结果"""
    print("\n=== 检查修正测试结果 ===")
    
    server_ip = "192.168.0.121"
    username = "lqj"
    
    # 检查结果文件
    check_cmd = "cat /home/lqj/liquid/rtsp_test_result_corrected.json 2>/dev/null || echo '结果文件不存在'"
    ssh_cmd = f'ssh {username}@{server_ip} "{check_cmd}"'
    
    try:
        result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
        
        if result.stdout:
            print("修正测试结果:")
            print(result.stdout)
        else:
            print("无法获取测试结果")
            
    except Exception as e:
        print(f"检查结果异常: {e}")

def main():
    """主函数"""
    print("开始使用正确路径测试服务端RTSP流捕获功能")
    
    try:
        # 1. 上传并运行修正测试
        if upload_and_run_corrected_test():
            # 2. 等待测试完成
            print("\n等待测试完成...")
            time.sleep(5)
            
            # 3. 检查测试结果
            check_corrected_test_results()
        else:
            print("修正测试上传失败")
            
    except Exception as e:
        print(f"测试过程异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()