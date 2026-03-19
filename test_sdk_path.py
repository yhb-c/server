import sys
import os
sys.path.insert(0, '/home/lqj/liquid/server/lib')

print('=== 测试海康SDK路径问题 ===')

try:
    from HCNetSDK import get_hk_lib_path, netsdkdllpath, playM4dllpath
    
    print(f'get_hk_lib_path(): {get_hk_lib_path()}')
    print(f'netsdkdllpath: {netsdkdllpath}')
    print(f'playM4dllpath: {playM4dllpath}')
    
    print(f'netsdkdllpath存在: {os.path.exists(netsdkdllpath)}')
    print(f'playM4dllpath存在: {os.path.exists(playM4dllpath)}')
    
    # 检查实际的.so文件位置
    actual_lib_dir = '/home/lqj/liquid/server/lib/lib'
    actual_netsdk = os.path.join(actual_lib_dir, 'libhcnetsdk.so')
    actual_playctrl = os.path.join(actual_lib_dir, 'libPlayCtrl.so')
    
    print(f'实际libhcnetsdk.so路径: {actual_netsdk}')
    print(f'实际libhcnetsdk.so存在: {os.path.exists(actual_netsdk)}')
    print(f'实际libPlayCtrl.so路径: {actual_playctrl}')
    print(f'实际libPlayCtrl.so存在: {os.path.exists(actual_playctrl)}')
    
except Exception as e:
    print(f'导入异常: {e}')
    import traceback
    traceback.print_exc()
