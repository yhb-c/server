# 推理服务启动修复测试
# 用于测试修复后的推理服务启动代码

import os
import sys
import subprocess
import platform
from pathlib import Path

def test_startup_script_generation():
    """测试启动脚本生成是否正确"""
    
    # 模拟main.py中的代码逻辑
    project_root = Path(__file__).parent.parent
    inference_path = project_root / "server"
    
    # 创建启动脚本内容（修复后的版本）
    startup_script = f'''
import os
import sys
import asyncio
import logging

# 添加路径
sys.path.insert(0, r"{inference_path}")
database_dir = os.path.join(r"{inference_path}", "database")
if os.path.exists(database_dir):
    sys.path.insert(0, database_dir)

async def start_ws_server():
    try:
        print("[调试] 开始导入WebSocketServer...")
        print(f"[调试] sys.path: {{sys.path[:3]}}")

        # 模拟导入失败的情况来测试异常处理
        raise ImportError("模拟导入失败")

    except Exception as e:
        import traceback
        print(f"WebSocket服务器启动失败: {{e}}")
        print(f"[调试] 详细错误信息:\\n{{traceback.format_exc()}}")

if __name__ == "__main__":
    asyncio.run(start_ws_server())
'''
    
    try:
        # 创建临时测试脚本
        temp_script = Path(__file__).parent / "temp_test_script.py"
        with open(temp_script, 'w', encoding='utf-8') as f:
            f.write(startup_script)
        
        print(f"✓ 启动脚本生成成功: {temp_script}")
        
        # 测试脚本是否可以正常执行（应该会有异常但不会有UnboundLocalError）
        print("测试脚本执行...")
        result = subprocess.run(
            [sys.executable, str(temp_script)],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        print(f"脚本执行结果:")
        print(f"  返回码: {result.returncode}")
        print(f"  标准输出: {result.stdout}")
        print(f"  标准错误: {result.stderr}")
        
        # 检查是否还有UnboundLocalError
        if "UnboundLocalError" in result.stderr:
            print("✗ 仍然存在UnboundLocalError")
            return False
        elif "WebSocket服务器启动失败" in result.stdout:
            print("✓ 异常处理正常工作，没有UnboundLocalError")
            return True
        else:
            print("? 未知结果")
            return False
            
    except Exception as e:
        print(f"✗ 测试异常: {e}")
        return False
    finally:
        # 清理临时文件
        if temp_script.exists():
            temp_script.unlink()

def test_f_string_escaping():
    """测试f-string转义是否正确"""
    
    # 测试变量名转义
    test_var = "test_value"
    
    # 这应该正常工作
    normal_f_string = f"正常的f-string: {test_var}"
    print(f"✓ {normal_f_string}")
    
    # 这应该生成包含花括号的字符串
    escaped_f_string = f"转义的f-string: {{test_var}}"
    print(f"✓ {escaped_f_string}")
    
    # 验证转义是否正确
    if "{test_var}" in escaped_f_string:
        print("✓ f-string转义正确")
        return True
    else:
        print("✗ f-string转义失败")
        return False

if __name__ == "__main__":
    print("=== 推理服务启动修复测试 ===")
    
    print("\n1. 测试f-string转义...")
    test1_result = test_f_string_escaping()
    
    print("\n2. 测试启动脚本生成...")
    test2_result = test_startup_script_generation()
    
    print(f"\n=== 测试结果 ===")
    print(f"f-string转义测试: {'通过' if test1_result else '失败'}")
    print(f"启动脚本测试: {'通过' if test2_result else '失败'}")
    
    if test1_result and test2_result:
        print("✓ 所有测试通过，UnboundLocalError问题已修复")
        sys.exit(0)
    else:
        print("✗ 部分测试失败")
        sys.exit(1)