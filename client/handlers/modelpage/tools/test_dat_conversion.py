"""
测试.dat文件转换和使用功能
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from handlers.videopage.detection.detection import LiquidDetectionEngine


def test_dat_conversion():
    """测试.dat文件转换功能"""
    print("🧪 测试.dat文件转换功能")
    print("=" * 50)
    
    # 创建检测引擎（用于模型加载和.dat文件解码）
    loader = LiquidDetectionEngine()
    
    # 查找测试用的.pt文件
    test_pt_files = []
    
    # 在database/train/runs目录中查找.pt文件
    runs_dir = Path("database/train/runs")
    if runs_dir.exists():
        for pt_file in runs_dir.rglob("*.pt"):
            test_pt_files.append(pt_file)
    
    if not test_pt_files:
        print("❌ 未找到测试用的.pt文件")
        return
    
    print(f"📁 找到 {len(test_pt_files)} 个.pt文件用于测试")
    
    for pt_file in test_pt_files:
        print(f"\n 测试文件: {pt_file}")
        
        try:
            # 检查文件大小
            file_size = pt_file.stat().st_size
            print(f"   文件大小: {file_size:,} 字节")
            
            # 创建对应的.dat文件路径
            dat_file = pt_file.with_suffix('.dat')
            
            # 检查是否已存在.dat文件
            if dat_file.exists():
                print(f"   ⚠️ .dat文件已存在: {dat_file}")
                continue
            
            # 读取.pt文件
            with open(pt_file, 'rb') as f:
                original_data = f.read()
            
            print(f"   ✅ 成功读取.pt文件")
            
            # 模拟.dat文件创建过程
            from convert_all_pt_to_dat import BatchConverter
            converter = BatchConverter()
            
            # 转换为.dat文件
            dat_path = converter.convert_file(str(pt_file))
            print(f"   ✅ 成功转换为.dat文件: {dat_path}")
            
            # 验证.dat文件
            if Path(dat_path).exists():
                dat_size = Path(dat_path).stat().st_size
                print(f"   📊 .dat文件大小: {dat_size:,} 字节")
                
                # 测试解码功能
                try:
                    decoded_path = loader._decode_dat_model(dat_path)
                    if decoded_path:
                        with open(decoded_path, 'rb') as f:
                            decoded_data = f.read()
                        print(f"   ✅ 成功解码.dat文件")
                    
                        # 验证解码后的数据是否与原始数据相同
                        if decoded_data == original_data:
                            print(f"   ✅ 数据完整性验证通过")
                        else:
                            print(f"   ❌ 数据完整性验证失败")
                    else:
                        print(f"   ❌ 解码返回空路径")
                        
                except Exception as e:
                    print(f"   ❌ 解码失败: {e}")
            else:
                print(f"   ❌ .dat文件创建失败")
                
        except Exception as e:
            print(f"   ❌ 处理失败: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 测试完成")


def test_dat_loading():
    """测试.dat文件加载功能"""
    print("\n🧪 测试.dat文件加载功能")
    print("=" * 50)
    
    # 创建检测引擎（用于模型加载）
    loader = LiquidDetectionEngine()
    
    # 查找.dat文件
    dat_files = []
    runs_dir = Path("database/train/runs")
    if runs_dir.exists():
        for dat_file in runs_dir.rglob("*.dat"):
            dat_files.append(dat_file)
    
    if not dat_files:
        print("❌ 未找到.dat文件用于测试")
        return
    
    print(f"📁 找到 {len(dat_files)} 个.dat文件")
    
    for dat_file in dat_files:
        print(f"\n 测试加载: {dat_file}")
        
        try:
            # 测试加载.dat模型（内部会自动解码）
            success = loader.load_model(str(dat_file))
            if success:
                print(f"   ✅ 成功加载.dat模型")
                print(f"   📋 模型类型: {type(loader.model)}")
                print(f"   📊 模型路径: {loader.model_path}")
            else:
                print(f"   ❌ 加载.dat模型失败")
                
        except Exception as e:
            print(f"   ❌ 加载失败: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 加载测试完成")


def main():
    """主函数"""
    print("🚀 开始测试.dat文件功能")
    print("=" * 60)
    
    # 测试转换功能
    test_dat_conversion()
    
    # 测试加载功能
    test_dat_loading()
    
    print("\n" + "=" * 60)
    print("✅ 所有测试完成")


if __name__ == "__main__":
    main() 