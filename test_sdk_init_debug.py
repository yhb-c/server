import sys
import os
sys.path.insert(0, '/home/lqj/liquid/server/lib')

print('=== 海康SDK初始化调试 ===')

try:
    from HCNetSDK import load_library, netsdkdllpath
    from PlayCtrl import playM4dllpath
    
    print(f'netsdkdllpath: {netsdkdllpath}')
    print(f'playM4dllpath: {playM4dllpath}')
    
    # 尝试加载库
    print('尝试加载libhcnetsdk.so...')
    try:
        hikSDK = load_library(netsdkdllpath)
        print(f'✓ hikSDK加载成功: {hikSDK}')
        print(f'hikSDK类型: {type(hikSDK)}')
        
        # 检查关键函数是否存在
        if hasattr(hikSDK, 'NET_DVR_Init'):
            print('✓ NET_DVR_Init函数存在')
        else:
            print('✗ NET_DVR_Init函数不存在')
            
        if hasattr(hikSDK, 'NET_DVR_Login_V40'):
            print('✓ NET_DVR_Login_V40函数存在')
        else:
            print('✗ NET_DVR_Login_V40函数不存在')
            
    except Exception as e:
        print(f'✗ hikSDK加载失败: {e}')
        hikSDK = None
    
    print('尝试加载libPlayCtrl.so...')
    try:
        playM4SDK = load_library(playM4dllpath)
        print(f'✓ playM4SDK加载成功: {playM4SDK}')
        print(f'playM4SDK类型: {type(playM4SDK)}')
    except Exception as e:
        print(f'✗ playM4SDK加载失败: {e}')
        playM4SDK = None
    
    # 如果SDK加载成功，尝试初始化
    if hikSDK:
        print('尝试初始化海康SDK...')
        try:
            init_result = hikSDK.NET_DVR_Init()
            print(f'NET_DVR_Init结果: {init_result}')
            if init_result:
                print('✓ 海康SDK初始化成功')
            else:
                print('✗ 海康SDK初始化失败')
        except Exception as e:
            print(f'✗ 海康SDK初始化异常: {e}')
    
except Exception as e:
    print(f'导入异常: {e}')
    import traceback
    traceback.print_exc()

print('调试完成')
