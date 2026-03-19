import sys
import os
import time
import numpy as np
sys.path.insert(0, '/home/lqj/liquid/server/lib')

print('=== 简单YUV数据测试 ===')

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
        success_count = 0
        
        for i in range(3):
            try:
                yuv_data = capture.get_yuv_data(timeout=3.0)
                
                print(f'第{i+1}次获取:')
                if yuv_data:
                    print(f'  YUV数据类型: {type(yuv_data)}')
                    
                    if isinstance(yuv_data, dict):
                        width = yuv_data.get('width', 0)
                        height = yuv_data.get('height', 0)
                        data = yuv_data.get('data')
                        
                        print(f'  尺寸: {width}x{height}')
                        
                        if data and width > 0 and height > 0:
                            success_count += 1
                            print(f'  ✓ 获取到有效YUV数据，长度: {len(data)}')
                            
                            # 尝试转换为BGR
                            try:
                                yuv_array = np.frombuffer(data, dtype=np.uint8)
                                expected_size = width * height * 3 // 2
                                
                                if len(yuv_array) >= expected_size:
                                    yuv_image = yuv_array[:expected_size].reshape((height * 3 // 2, width))
                                    
                                    import cv2
                                    bgr_image = cv2.cvtColor(yuv_image, cv2.COLOR_YUV2BGR_I420)
                                    print(f'  ✓ 成功转换为BGR: {bgr_image.shape}')
                                    print(f'  ✓ 数据可用于模型检测')
                                    
                                    if i == 0:
                                        cv2.imwrite('/home/lqj/liquid/test_detection_frame.jpg', bgr_image)
                                        print(f'  ✓ 检测用帧已保存')
                                        
                                else:
                                    print(f'  ✗ YUV数据大小不足')
                                    
                            except Exception as e:
                                print(f'  ✗ 转换失败: {e}')
                        else:
                            print(f'  ✗ YUV数据无效')
                    else:
                        print(f'  ✗ YUV数据格式错误')
                else:
                    print(f'  ✗ 未获取到YUV数据')
                
                time.sleep(1)
                
            except Exception as e:
                print(f'  第{i+1}次异常: {e}')
        
        print(f'\\n成功获取YUV数据: {success_count}/3')
        
        if success_count > 0:
            print('✓ 海康SDK可以输出用于检测的数据给模型')
        else:
            print('✗ 海康SDK无法输出有效的检测数据')
        
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
