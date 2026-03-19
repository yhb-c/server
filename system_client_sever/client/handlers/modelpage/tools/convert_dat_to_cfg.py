"""
批量将现有的.dat文件重命名为.cfg文件
保持文件内容不变，只修改后缀名
"""

import os
import shutil
from pathlib import Path
import sys

class DatToCfgConverter:
    """DAT文件到CFG文件转换器"""
    
    def __init__(self):
        self.converted_count = 0
        self.failed_count = 0
        self.converted_files = []
        self.failed_files = []
    
    def convert_single_file(self, dat_file_path):
        """转换单个dat文件为cfg文件"""
        try:
            dat_file = Path(dat_file_path)
            
            if not dat_file.exists():
                print(f"❌ 文件不存在: {dat_file}")
                return False
            
            if dat_file.suffix.lower() != '.dat':
                print(f"⚠️ 不是.dat文件: {dat_file}")
                return False
            
            # 生成对应的.cfg文件路径
            cfg_file = dat_file.with_suffix('.cfg')
            
            # 检查目标文件是否已存在
            if cfg_file.exists():
                print(f"⚠️ 目标文件已存在: {cfg_file}")
                response = input("是否覆盖? (y/n): ").lower()
                if response != 'y':
                    return False
            
            # 重命名文件
            shutil.move(str(dat_file), str(cfg_file))
            
            print(f"✅ 转换成功: {dat_file.name} -> {cfg_file.name}")
            self.converted_count += 1
            self.converted_files.append(str(cfg_file))
            return True
            
        except Exception as e:
            print(f"❌ 转换失败 {dat_file_path}: {e}")
            self.failed_count += 1
            self.failed_files.append(str(dat_file_path))
            return False
    
    def convert_directory(self, directory_path, recursive=True):
        """转换目录中的所有.dat文件"""
        directory = Path(directory_path)
        
        if not directory.exists():
            print(f"❌ 目录不存在: {directory}")
            return False
        
        print(f"\n 扫描目录: {directory}")
        
        # 查找所有.dat文件
        if recursive:
            dat_files = list(directory.rglob("*.dat"))
        else:
            dat_files = list(directory.glob("*.dat"))
        
        if not dat_files:
            print(f"⚠️ 目录中没有找到.dat文件")
            return True
        
        print(f"📁 找到 {len(dat_files)} 个.dat文件")
        
        # 显示文件列表
        for i, dat_file in enumerate(dat_files, 1):
            print(f"  {i}. {dat_file}")
        
        # 确认是否继续
        response = input(f"\n是否转换这 {len(dat_files)} 个文件? (y/n): ").lower()
        if response != 'y':
            print("❌ 用户取消操作")
            return False
        
        # 转换每个文件
        for dat_file in dat_files:
            self.convert_single_file(dat_file)
        
        return True
    
    def convert_project_files(self, project_root="."):
        """转换整个项目中的.dat文件"""
        project_root = Path(project_root)
        
        # 定义要扫描的目录
        scan_directories = [
            "database/train/runs",
            "temp_models", 
            "dist111",
            "utils/database/train/runs"
        ]
        
        print(f"🚀 开始转换项目中的.dat文件")
        print(f"📁 项目根目录: {project_root.absolute()}")
        
        for dir_name in scan_directories:
            dir_path = project_root / dir_name
            if dir_path.exists():
                print(f"\n📂 处理目录: {dir_name}")
                self.convert_directory(dir_path, recursive=True)
            else:
                print(f"⚠️ 目录不存在，跳过: {dir_name}")
        
        # 显示总结
        self.print_summary()
    
    def print_summary(self):
        """打印转换总结"""
        print(f"\n" + "="*50)
        print(f"🎉 转换完成!")
        print(f"✅ 成功转换: {self.converted_count} 个文件")
        print(f"❌ 转换失败: {self.failed_count} 个文件")
        
        if self.converted_files:
            print(f"\n📋 成功转换的文件:")
            for file_path in self.converted_files:
                print(f"  ✅ {file_path}")
        
        if self.failed_files:
            print(f"\n📋 转换失败的文件:")
            for file_path in self.failed_files:
                print(f"  ❌ {file_path}")
        
        print(f"="*50)

def main():
    """主函数"""
    converter = DatToCfgConverter()
    
    if len(sys.argv) > 1:
        # 命令行参数模式
        target_path = sys.argv[1]
        
        if os.path.isfile(target_path):
            # 转换单个文件
            print(f"🔄 转换单个文件: {target_path}")
            converter.convert_single_file(target_path)
        elif os.path.isdir(target_path):
            # 转换目录
            print(f"🔄 转换目录: {target_path}")
            converter.convert_directory(target_path)
        else:
            print(f"❌ 路径不存在: {target_path}")
    else:
        # 交互模式
        print("🔄 DAT文件到CFG文件转换工具")
        print("="*40)
        print("1. 转换整个项目")
        print("2. 转换指定目录") 
        print("3. 转换单个文件")
        print("4. 退出")
        
        while True:
            choice = input("\n请选择操作 (1-4): ").strip()
            
            if choice == '1':
                # 转换整个项目
                converter.convert_project_files()
                break
            elif choice == '2':
                # 转换指定目录
                dir_path = input("请输入目录路径: ").strip()
                if dir_path:
                    recursive = input("是否递归扫描子目录? (y/n): ").lower() == 'y'
                    converter.convert_directory(dir_path, recursive)
                break
            elif choice == '3':
                # 转换单个文件
                file_path = input("请输入文件路径: ").strip()
                if file_path:
                    converter.convert_single_file(file_path)
                break
            elif choice == '4':
                print("👋 退出程序")
                break
            else:
                print("❌ 无效选择，请重新输入")

if __name__ == "__main__":
    main() 