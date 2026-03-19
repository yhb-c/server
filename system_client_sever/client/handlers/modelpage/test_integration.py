# -*- coding: utf-8 -*-
"""
模型测试功能集成验证脚本

用于快速验证 ModelTestHandler 是否成功集成到 ModelTrainingHandler
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def test_import():
    """测试导入"""
    print("=" * 60)
    print("测试1: 导入模块")
    print("=" * 60)
    
    try:
        from handlers.modelpage.model_test_handler import ModelTestHandler
        print("✅ ModelTestHandler 导入成功")
    except Exception as e:
        print(f"❌ ModelTestHandler 导入失败: {e}")
        return False
    
    try:
        from handlers.modelpage.model_training_handler import ModelTrainingHandler
        print("✅ ModelTrainingHandler 导入成功")
    except Exception as e:
        print(f"❌ ModelTrainingHandler 导入失败: {e}")
        return False
    
    return True

def test_inheritance():
    """测试继承关系"""
    print("\n" + "=" * 60)
    print("测试2: 继承关系")
    print("=" * 60)
    
    try:
        from handlers.modelpage.model_test_handler import ModelTestHandler
        from handlers.modelpage.model_training_handler import ModelTrainingHandler
        
        # 检查继承关系
        if issubclass(ModelTrainingHandler, ModelTestHandler):
            print("✅ ModelTrainingHandler 正确继承自 ModelTestHandler")
        else:
            print("❌ ModelTrainingHandler 没有继承 ModelTestHandler")
            return False
        
        # 检查MRO（方法解析顺序）
        mro = ModelTrainingHandler.__mro__
        print(f"\n方法解析顺序 (MRO):")
        for i, cls in enumerate(mro):
            print(f"  {i+1}. {cls.__name__}")
        
        if ModelTestHandler in mro:
            print("\n✅ ModelTestHandler 在 MRO 中")
        else:
            print("\n❌ ModelTestHandler 不在 MRO 中")
            return False
        
    except Exception as e:
        print(f"❌ 继承关系检查失败: {e}")
        return False
    
    return True

def test_methods():
    """测试方法可用性"""
    print("\n" + "=" * 60)
    print("测试3: 方法可用性")
    print("=" * 60)
    
    try:
        from handlers.modelpage.model_training_handler import ModelTrainingHandler
        
        # 检查测试相关方法
        test_methods = [
            'connectTestButtons',
            '_handleStartTest',
            '_handleStopTest',
            '_handleStartTestExecution',
            '_loadTestFrame',
            '_performTestDetection',
            '_performVideoFrameDetection',
            '_showTestDetectionResult',
            '_saveTestDetectionResult',
            '_drawLiquidLinesOnFrame',
            '_createRealtimeVideoPlayer',
            '_updateRealtimeFrame',
            '_saveVideoTestResults',
            '_showDetectionVideo',
        ]
        
        missing_methods = []
        for method_name in test_methods:
            if hasattr(ModelTrainingHandler, method_name):
                print(f"  ✅ {method_name}")
            else:
                print(f"  ❌ {method_name}")
                missing_methods.append(method_name)
        
        if missing_methods:
            print(f"\n❌ 缺少 {len(missing_methods)} 个方法")
            return False
        else:
            print(f"\n✅ 所有 {len(test_methods)} 个测试方法都可用")
        
    except Exception as e:
        print(f"❌ 方法可用性检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def test_instantiation():
    """测试实例化"""
    print("\n" + "=" * 60)
    print("测试4: 实例化")
    print("=" * 60)
    
    try:
        from handlers.modelpage.model_training_handler import ModelTrainingHandler
        
        # 尝试创建实例
        handler = ModelTrainingHandler()
        print("✅ ModelTrainingHandler 实例化成功")
        
        # 检查实例属性（training_panel 在 connectToTrainingPanel 调用后才设置）
        # 这里只检查属性是否可以访问，不要求必须有值
        try:
            _ = handler.training_panel
            print("✅ 实例有 training_panel 属性（初始值为 None，这是正常的）")
        except AttributeError:
            print("❌ 实例缺少 training_panel 属性")
            return False
        
        # 检查是否可以调用测试方法
        if callable(getattr(handler, 'connectTestButtons', None)):
            print("✅ connectTestButtons 方法可调用")
        else:
            print("❌ connectTestButtons 方法不可调用")
            return False
        
    except Exception as e:
        print(f"❌ 实例化失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def test_file_structure():
    """测试文件结构"""
    print("\n" + "=" * 60)
    print("测试5: 文件结构")
    print("=" * 60)
    
    required_files = [
        'model_test_handler.py',
        'model_training_handler.py',
        'MODEL_TEST_MIGRATION_PLAN.md',
        'MODEL_TEST_HANDLER_README.md',
        'MIGRATION_100_PERCENT_COMPLETE.md',
        'INTEGRATION_TEST_GUIDE.md',
    ]
    
    handlers_dir = Path(__file__).parent
    
    missing_files = []
    for filename in required_files:
        filepath = handlers_dir / filename
        if filepath.exists():
            print(f"  ✅ {filename}")
        else:
            print(f"  ❌ {filename}")
            missing_files.append(filename)
    
    if missing_files:
        print(f"\n❌ 缺少 {len(missing_files)} 个文件")
        return False
    else:
        print(f"\n✅ 所有 {len(required_files)} 个文件都存在")
    
    return True

def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("模型测试功能集成验证")
    print("=" * 60)
    print()
    
    tests = [
        ("导入模块", test_import),
        ("继承关系", test_inheritance),
        ("方法可用性", test_methods),
        ("实例化", test_instantiation),
        ("文件结构", test_file_structure),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ 测试 '{test_name}' 执行失败: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # 打印总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status}: {test_name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！集成成功！")
        print("\n下一步:")
        print("  1. 启动应用程序")
        print("  2. 进入模型训练/测试页面")
        print("  3. 尝试单帧图片检测")
        print("  4. 尝试视频检测")
        print("  5. 查看 INTEGRATION_TEST_GUIDE.md 了解详细测试步骤")
        return True
    else:
        print(f"\n❌ {total - passed} 个测试失败，请检查错误信息")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
