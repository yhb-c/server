import sys
import os
import time
sys.path.insert(0, '/home/lqj/liquid/server/lib')

print('=== 海康SDK完整RTSP捕获测试 ===')

try:
    from HKcapture import HKcapture
    
    rtsp_url = 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
    print(f'RTSP地址: {rtsp_url}')
    
    capture = HKcapture(
        source=rtsp_url,
        username='admin',
        password='cei345678',
        debug=True
    )
    print('✓ HKcapture实例创建成功')
    
    print('尝试打开连接...')
    if capture.open():
        print('✓ 连接打开成功')
        
        print('尝试启动捕获...')
        if capture.start_capture():
            print('✓ 捕获启动成功')
            
            capture.enable_yuv_queue(enabled=True)
            print('✓ YUV队列已启用')
            
            print('等待数据流稳定...')
            time.sleep(5)
            
            print('测试获取YUV数据...')
            success_count = 0
            for i in range(3):
                try:
                    yuv_data = capture.get_yuv_data(timeout=3.0)
                    if yuv_data:
                        success_count += 1
                        width = yuv_data.get('width', 0)
                        height = yuv_data.get('height', 0)
                        print(f'  第{i+1}次: 成功获取YUV数据 {width}x{height}')
                    else:
                        print(f'  第{i+1}次: YUV数据为空')
                except Exception as e:
                    print(f'  第{i+1}次: 获取YUV数据异常 - {e}')
                
                time.sleep(1)
            
            print(f'YUV数据获取成功: {success_count}/3')
            
            print('测试read方法...')
            read_success_count = 0
            for i in range(3):
                try:
                    frame = capture.read()
                    if frame is not None:
                        read_success_count += 1
                        print(f'  第{i+1}次: read成功 {frame.shape}')
                    else:
                        print(f'  第{i+1}次: read返回None')
                except Exception as e:
                    print(f'  第{i+1}次: read异常 - {e}')
                
                time.sleep(1)
            
            print(f'read方法成功: {read_success_count}/3')
            
            capture.stop_capture()
            capture.release()
            print('✓ 资源已清理')
            
            # 输出最终结果
            print('\\n=== 测试结果汇总 ===')
            if success_count > 0 or read_success_count > 0:
                print('✓ 海康SDK RTSP捕获测试成功')
                print(f'YUV数据获取成功率: {success_count}/3')
                print(f'read方法成功率: {read_success_count}/3')
            else:
                print('✗ 海康SDK RTSP捕获测试失败')
                
        else:
            print('✗ 捕获启动失败')
            capture.release()
    else:
        print('✗ 连接打开失败')
        
except Exception as e:
    print(f'✗ 测试异常: {e}')
    import traceback
    traceback.print_exc()

print('测试完成')
