#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试服务端模型加载功能

此脚本用于测试通过SSH在服务端加载检测模型的功能，验证导入路径和模型初始化是否正确。
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_server_model_loading():
    """测试服务端模型加载功能"""
    print("=" * 60)
    print("测试服务端模型加载功能")
    print("=" * 60)
    
    try:
        # 导入远程配置管理器
        from client.utils.config import RemoteConfigManager
        
        print("[1/4] 初始化远程配置管理器...")
        remote_config = RemoteConfigManager()
        
        print("[2/4] 加载服务端配置...")
        default_config = remote_config.load_default_config()
        
        if not default_config:
            print("[ERROR] 无法从服务端加载配置")
            return False
        
        print(f"[OK] 成功加载配置，包含键: {list(default_config.keys())}")
        
        # 获取模型路径
        model_path = default_config.get('channel1_model_path')
        if not model_path:
            model_config = default_config.get('model', {})
            model_path = model_config.get('model_path')
        
        if not model_path:
            print("[ERROR] 配置中没有找到模型路径")
            return False
        
        print(f"[OK] 找到模型路径: {model_path}")
        
        print("[3/4] 获取SSH连接...")
        ssh_manager = remote_config._get_ssh_manager()
        
        if not ssh_manager:
            print("[ERROR] SSH连接不可用")
            return False
        
        print("[OK] SSH连接可用")
        
        print("[4/4] 测试服务端模型加载...")
        
        # 构建服务端模型加载测试命令
        test_cmd = f"""
cd /home/lqj/liquid/server
source ~/anaconda3/bin/activate liquid
python -c "
import sys
sys.path.append('/home/lqj/liquid/server')
print('Python路径已设置')

try:
    print('尝试导入检测模块...')
    from detection import LiquidDetectionEngine
    print('SUCCESS: 检测模块导入成功')
    
    print('尝试创建检测引擎实例...')
    engine = LiquidDetectionEngine(
        model_path='{model_path}',
        device='cuda',
        batch_size=1
    )
    print('SUCCESS: 检测引擎创建成功')
    
    print('SUCCESS: 服务端模型加载测试完成')
    
except ImportError as ie:
    print(f'IMPORT_ERROR: 导入失败: {{ie}}')
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f'ERROR: 其他错误: {{e}}')
    import traceback
    traceback.print_exc()
"
"""
        
        print("执行服务端测试命令...")
        result = ssh_manager.execute_remote_command(test_cmd)
        
        print(f"命令执行结果: success={result['success']}")
        print(f"标准输出:\n{result.get('stdout', '')}")
        if result.get('stderr'):
            print(f"错误输出:\n{result.get('stderr', '')}")
        
        if result['success'] and 'SUCCESS: 服务端模型加载测试完成' in result['stdout']:
            print("[SUCCESS] 服务端模型加载测试成功！")
            return True
        else:
            print("[FAILED] 服务端模型加载测试失败")
            return False
        
    except Exception as e:
        print(f"[ERROR] 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_server_model_loading()
    if success:
        print("\n✓ 所有测试通过")
        sys.exit(0)
    else:
        print("\n✗ 测试失败")
        sys.exit(1)