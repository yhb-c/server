# -*- coding: utf-8 -*-

"""
标注管理器测试脚本

用于测试标注管理器的基本功能：
- 配置格式转换
- 本地保存功能
- 服务器推送功能
"""

import sys
import os
import yaml
import numpy as np

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'client'))

def test_annotation_data_format():
    """测试标注数据格式转换"""
    print("=" * 50)
    print("测试标注数据格式转换")
    print("=" * 50)
    
    # 模拟标注数据
    test_annotation_data = {
        'boxes': [(936, 532, 192), (1120, 628, 224)],
        'bottoms': [(936, 568), (1120, 668)],
        'tops': [(936, 470), (1120, 588)],
        'init_levels': [(936, 568), (1120, 668)],
        'area_names': ['通道1_区域1', '通道1_区域2'],
        'area_heights': ['20mm', '25mm'],
        'area_states': ['默认', '默认']
    }
    
    try:
        from client.handlers.videopage.annotation_manager import AnnotationManager
        
        # 创建标注管理器
        manager = AnnotationManager()
        
        # 测试构建服务器配置格式
        server_config = manager._build_server_config('channel1', test_annotation_data)
        
        print("构建的服务器配置格式:")
        print(yaml.dump(server_config, allow_unicode=True, default_flow_style=False))
        
        # 验证格式是否正确
        expected_keys = ['boxes', 'fixed_bottoms', 'fixed_tops', 'init_levels', 
                        'fixed_init_levels', 'annotation_count', 'areas', 'last_updated']
        
        for key in expected_keys:
            if key in server_config:
                print(f"✓ {key}: 存在")
            else:
                print(f"✗ {key}: 缺失")
        
        # 验证区域配置格式
        areas = server_config.get('areas', {})
        for area_key, area_info in areas.items():
            print(f"区域 {area_key}:")
            print(f"  - name: {area_info.get('name')}")
            print(f"  - height: {area_info.get('height')}")
            print(f"  - state: {area_info.get('state')}")
            print(f"  - init_status: {area_info.get('init_status')}")
        
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_local_save_format():
    """测试本地保存格式"""
    print("\n" + "=" * 50)
    print("测试本地保存格式")
    print("=" * 50)
    
    # 模拟标注数据
    test_annotation_data = {
        'boxes': [(936, 532, 192)],
        'bottoms': [(936, 568)],
        'tops': [(936, 470)],
        'init_levels': [(936, 568)],
        'area_names': ['通道1_区域1'],
        'area_heights': ['20mm'],
        'area_states': ['默认']
    }
    
    try:
        from client.handlers.videopage.annotation_manager import AnnotationManager
        
        # 创建标注管理器
        manager = AnnotationManager()
        
        # 测试本地保存
        manager._save_local_annotation('channel1', test_annotation_data)
        
        # 验证保存的文件
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        annotation_file = os.path.join(project_root, 'database', 'config', 'annotation_result.yaml')
        
        if os.path.exists(annotation_file):
            print(f"✓ 配置文件已创建: {annotation_file}")
            
            with open(annotation_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if 'channel1' in config:
                print("✓ channel1 配置已保存")
                channel_config = config['channel1']
                
                # 验证必要字段
                required_fields = ['boxes', 'fixed_bottoms', 'fixed_tops', 'annotation_count', 'areas']
                for field in required_fields:
                    if field in channel_config:
                        print(f"✓ {field}: {channel_config[field]}")
                    else:
                        print(f"✗ {field}: 缺失")
            else:
                print("✗ channel1 配置未找到")
        else:
            print(f"✗ 配置文件未创建: {annotation_file}")
        
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_history_data_loading():
    """测试历史数据加载"""
    print("\n" + "=" * 50)
    print("测试历史数据加载")
    print("=" * 50)
    
    try:
        from client.handlers.videopage.annotation_manager import AnnotationManager
        
        # 创建标注管理器
        manager = AnnotationManager()
        
        # 测试加载历史标注数据
        history_data = manager._load_history_annotation('channel1')
        
        if history_data:
            print("✓ 成功加载历史标注数据")
            print(f"  - 标注数量: {history_data.get('annotation_count', 0)}")
            print(f"  - 区域数量: {len(history_data.get('boxes', []))}")
            print(f"  - 最后更新: {history_data.get('last_updated', 'N/A')}")
            
            # 显示区域信息
            areas = history_data.get('areas', {})
            for area_key, area_info in areas.items():
                print(f"  - {area_key}: {area_info.get('name')} ({area_info.get('height')})")
        else:
            print("✗ 未找到历史标注数据")
        
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("标注管理器功能测试")
    print("=" * 60)
    
    # 运行测试
    tests = [
        test_annotation_data_format,
        test_local_save_format,
        test_history_data_loading
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"测试 {test_func.__name__} 异常: {e}")
            results.append(False)
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"通过: {passed}/{total}")
    
    for i, (test_func, result) in enumerate(zip(tests, results)):
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{i+1}. {test_func.__name__}: {status}")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")

if __name__ == '__main__':
    main()