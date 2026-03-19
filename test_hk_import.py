import sys
sys.path.insert(0, '/home/lqj/liquid/server/lib')

print('开始测试HKcapture导入')
try:
    from HKcapture import HKcapture
    print('✓ HKcapture导入成功')
    
    rtsp_url = 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
    capture = HKcapture(source=rtsp_url, debug=True)
    print('✓ HKcapture实例创建成功')
    
except Exception as e:
    print(f'✗ 导入失败: {e}')
    import traceback
    traceback.print_exc()
