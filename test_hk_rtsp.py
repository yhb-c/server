import sys
import time
sys.path.insert(0, '/home/lqj/liquid/server/lib')

print('=== 海康SDK RTSP连接测试 ===')

try:
    from HKcapture import HKcapture
    print('✓ HKcapture导入成功')
    
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
            time.sleep(3)
            
            print('尝试获取YUV数据...')
            yuv_data = capture.get_yuv_data(timeout=5.0)
            if yuv_data:
                width = yuv_data.get('width', 0)
                height = yuv_data.get('height', 0)
                print(f'✓ 成功获取YUV数据: {width}x{height}')
            else:
                print('✗ 未获取到YUV数据')
            
            print('尝试read方法...')
            frame = capture.read()
            if frame is not None:
                print(f'✓ read方法成功: {frame.shape}')
            else:
                print('✗ read方法返回None')
            
            capture.stop_capture()
            capture.release()
            print('✓ 资源已清理')
            
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
