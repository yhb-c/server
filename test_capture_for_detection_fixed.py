import sys
import os
import time
import numpy as np
sys.path.insert(0, '/home/lqj/liquid/server/lib')

print('=== 测试捕获数据用于模型检测 ===')

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
        
        capture.enable_yuv_queue(enabled=True)
        print('✓ YUV队列已启用')
        
        print('等待数据流稳定...')
        time.sleep(3)
        
        print('测试获取帧数据用于检测...')
        for i in range(3):
            try:
                frame_data = capture.read()
                
                print(f'第{i+1}次获取:')
                print(f'  数据类型: {type(frame_data)}')
                
                if frame_data is not None:
                    if isinstance(frame_data, tuple):
                        print(f'  tuple长度: {len(frame_data)}')
                        for j, item in enumerate(frame_data):
                            shape_info = getattr(item, 'shape', '无shape属性')
                            print(f'    元素{j}: 类型={type(item)}, 形状={shape_info}')
                            
                        # 尝试获取实际的图像数据
                        if len(frame_data) > 0:
                            # 通常图像数据在tuple的最后一个元素
                            image_data = None
                            for item in frame_data:
                                if isinstance(item, np.ndarray) and len(item.shape) >= 2:
                                    image_data = item
                                    break
                            
                            if image_data is not None:
                                print(f'  图像数据: 形状={image_data.shape}, 数据类型={image_data.dtype}')
                                print(f'  像素值范围: {image_data.min()} - {image_data.max()}')
                                
                                # 检查是否为有效的图像格式
                                if len(image_data.shape) == 3 and image_data.shape[2] == 3:
                                    print(f'  ✓ 有效的BGR图像格式，可用于模型检测')
                                    height, width = image_data.shape[:2]
                                    print(f'  图像尺寸: {width}x{height}')
                                    
                                    if image_data.sum() > 0:
                                        print(f'  ✓ 图像包含有效像素数据')
                                        
                                        # 保存一帧用于验证
                                        if i == 0:
                                            try:
                                                import cv2
                                                cv2.imwrite('/home/lqj/liquid/test_frame.jpg', image_data)
                                                print(f'  ✓ 测试帧已保存到 test_frame.jpg')
                                            except:
                                                print(f'  - 无法保存测试帧（cv2不可用）')
                                    else:
                                        print(f'  ✗ 图像为全黑或空白')
                                        
                                elif len(image_data.shape) == 2:
                                    print(f'  灰度图像格式，形状: {image_data.shape}')
                                else:
                                    print(f'  ✗ 图像格式不正确，形状: {image_data.shape}')
                            else:
                                print(f'  ✗ 无法找到有效的图像数据')
                                
                    elif isinstance(frame_data, np.ndarray):
                        print(f'  numpy数组: 形状={frame_data.shape}, 数据类型={frame_data.dtype}')
                        print(f'  像素值范围: {frame_data.min()} - {frame_data.max()}')
                        
                        if len(frame_data.shape) == 3 and frame_data.shape[2] == 3:
                            print(f'  ✓ 有效的BGR图像格式，可用于模型检测')
                        else:
                            print(f'  图像格式: {frame_data.shape}')
                    else:
                        print(f'  ✗ 未知的数据格式')
                else:
                    print(f'  ✗ 获取到None')
                
                time.sleep(1)
                
            except Exception as e:
                print(f'  第{i+1}次获取异常: {e}')
        
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
