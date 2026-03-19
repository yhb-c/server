import sys
import os
sys.path.insert(0, '/home/lqj/liquid/server/lib')

print('=== HKcapture初始化调试 ===')

try:
    from HKcapture import HKcapture
    
    rtsp_url = 'rtsp://admin:cei345678@192.168.0.27:8000/stream1'
    print(f'创建HKcapture实例: {rtsp_url}')
    
    capture = HKcapture(source=rtsp_url, debug=True)
    print(f'✓ HKcapture实例创建成功')
    
    # 手动调用SDK初始化方法进行调试
    print('手动调用_init_hikvision_sdk...')
    init_result = capture._init_hikvision_sdk()
    print(f'_init_hikvision_sdk结果: {init_result}')
    
    print(f'capture.hikSDK: {capture.hikSDK}')
    print(f'capture.playM4SDK: {capture.playM4SDK}')
    
    if capture.hikSDK:
        print('✓ hikSDK初始化成功')
        
        # 测试登录方法
        print('测试_login_device方法...')
        try:
            login_result = capture._login_device()
            print(f'_login_device结果: {login_result}')
        except Exception as e:
            print(f'_login_device异常: {e}')
            import traceback
            traceback.print_exc()
    else:
        print('✗ hikSDK为None')
    
except Exception as e:
    print(f'测试异常: {e}')
    import traceback
    traceback.print_exc()

print('调试完成')
