import sys
import os
import time
import numpy as np
sys.path.insert(0, '/home/lqj/liquid/server/lib')

print('=== 测试YUV数据获取用于模型检测 ===')

try:
    from HKcapture import HKcapture
    
    rtsp_url = 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
    print(f'RTSP地址: {rtsp_url}')
    
    capture = HKcapture(
        source=rtsp_url,
        username='admin',
        password='cei345678',
        debug=False
    )
    print('✓ HKcapture实例创建成功')
    
    if capture.open() and capture.start_capture():
        print('✓ 捕获启动成功')
        
        capture.enable_yuv_queue(enabled=True, interval=0.1)
        print('✓ YUV队列已启用')
        
        print('等待数据流稳定...')
        time.sleep(5)
        
        print('测试获取YUV数据...')
        for i in range(5):
            try:
                # 使用get_yuv_data方法获取YUV数据
                yuv_data = capture.get_yuv_data(timeout=2.0)
                
                print(f'第{i+1}次获取YUV数据:')
                if yuv_data:
                    print(f'  YUV数据类型: {type(yuv_data)}')
                    print(f'  YUV数据内容: {yuv_data.keys() if isinstance(yuv_data, dict) else " 非字典类型\}')
 
 if isinstance(yuv_data, dict):
 width = yuv_data.get('width', 0)
 height = yuv_data.get('height', 0)
 data = yuv_data.get('data')
 
 print(f' 尺寸: {width}x{height}')
 print(f' 数据类型: {type(data)}')
 
 if data:
 print(f' 数据长度: {len(data)}')
 
 # 尝试转换为numpy数组
 try:
 yuv_array = np.frombuffer(data, dtype=np.uint8)
 print(f' YUV数组形状: {yuv_array.shape}')
 
 # 计算预期的YUV420数据大小
 expected_size = width * height * 3 // 2
 print(f' 预期YUV420大小: {expected_size}')
 
 if len(yuv_array) >= expected_size:
 # 重塑为YUV420格式
 yuv_image = yuv_array[:expected_size].reshape((height * 3 // 2, width))
 print(f' YUV图像形状: {yuv_image.shape}')
 
 # 转换为BGR格式
 try:
 import cv2
 bgr_image = cv2.cvtColor(yuv_image, cv2.COLOR_YUV2BGR_I420)
 print(f' ✓ 成功转换为BGR图像: {bgr_image.shape}')
 print(f' 像素值范围: {bgr_image.min()} - {bgr_image.max()}')
 
 # 保存第一帧用于验证
 if i == 0:
 cv2.imwrite('/home/lqj/liquid/test_yuv_frame.jpg', bgr_image)
 print(f' ✓ 测试帧已保存到 test_yuv_frame.jpg')
 
 print(f' ✓ 数据可用于模型检测')
 
 except Exception as e:
 print(f' ✗ YUV转BGR失败: {e}')
 else:
 print(f' ✗ YUV数据大小不足: {len(yuv_array)} < {expected_size}')
 
 except Exception as e:
 print(f' ✗ YUV数据转换失败: {e}')
 else:
 print(f' ✗ YUV数据为空')
 else:
 print(f' ✗ YUV数据格式错误')
 else:
 print(f' ✗ 未获取到YUV数据')
 
 time.sleep(1)
 
 except Exception as e:
 print(f' 第{i+1}次获取异常: {e}')
 
 capture.stop_capture()
 capture.release()
 print('✓ 资源已清理')
 
 else:
 print('✗ 捕获启动失败')
 
except Exception as e:
 print(f'✗ 测试异常: {e}')
 import traceback
 traceback.print_exc()

print('测试完成')
