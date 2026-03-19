"""
批量将所有.pt文件转换为.dat文件
"""

import os
import struct
import hashlib
import json
from pathlib import Path
import argparse


class BatchConverter:
    """批量转换器"""
    
    # 自定义标识符
    SIGNATURE = b'LDS_MODEL_FILE'
    VERSION = 1
    
    def __init__(self, key: str = "liquid_detection_system_2024"):
        """
        初始化转换器
        
        Args:
            key: 处理密钥
        """
        self.key = key.encode('utf-8')
        self._key_hash = hashlib.sha256(self.key).digest()
    
    def _process_data(self, data: bytes) -> bytes:
        """数据处理"""
        processed = bytearray()
        key_len = len(self._key_hash)
        
        for i, byte in enumerate(data):
            processed.append(byte ^ self._key_hash[i % key_len])
        
        return bytes(processed)
    
    def convert_file(self, input_path: str, output_path: str = None) -> str:
        """
        转换单个文件
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径，如果为None则自动生成
            
        Returns:
            输出文件路径
        """
        input_path = Path(input_path)
        
        if not input_path.exists():
            raise FileNotFoundError(f"输入文件不存在: {input_path}")
        
        if output_path is None:
            # 自动生成输出路径，将.pt替换为.dat
            output_path = input_path.with_suffix('.dat')
        else:
            output_path = Path(output_path)
        
        # 读取原始文件
        with open(input_path, 'rb') as f:
            original_data = f.read()
        
        # 创建处理后的数据
        # 格式: [标识符][版本][原始文件名长度][原始文件名][数据长度][处理后数据]
        original_filename = input_path.name.encode('utf-8')
        filename_len = len(original_filename)
        data_len = len(original_data)
        
        # 处理原始数据
        processed_data = self._process_data(original_data)
        
        # 构建文件头
        header = (
            self.SIGNATURE +
            struct.pack('<I', self.VERSION) +
            struct.pack('<I', filename_len) +
            original_filename +
            struct.pack('<Q', data_len) +
            processed_data
        )
        
        # 写入处理后的文件
        with open(output_path, 'wb') as f:
            f.write(header)
        
        print(f"✅ 文件已转换: {input_path} -> {output_path}")
        return str(output_path)
    
    def batch_convert_directory(self, directory: str) -> list[str]:
        """
        批量转换目录中的.pt文件
        
        Args:
            directory: 目录路径
            
        Returns:
            已转换的文件列表
        """
        directory = Path(directory)
        converted_files = []
        
        # 查找所有.pt文件
        pt_files = list(directory.rglob("*.pt"))
        
        if not pt_files:
            print(f"⚠️ 在目录 {directory} 中未找到.pt文件")
            return converted_files
        
        print(f"📁 在目录 {directory} 中找到 {len(pt_files)} 个.pt文件")
        
        for pt_file in pt_files:
            try:
                output_path = self.convert_file(str(pt_file))
                converted_files.append(output_path)
            except Exception as e:
                print(f"❌ 转换文件失败 {pt_file}: {e}")
        
        return converted_files
    
    def update_config_files(self, config_dir: str = "resources/channel_configs"):
        """
        更新配置文件中的.pt路径为.dat路径
        
        Args:
            config_dir: 配置文件目录
        """
        config_dir = Path(config_dir)
        
        if not config_dir.exists():
            print(f"⚠️ 配置文件目录不存在: {config_dir}")
            return
        
        # 查找所有配置文件
        config_files = list(config_dir.glob("*.json"))
        
        if not config_files:
            print(f"⚠️ 在目录 {config_dir} 中未找到配置文件")
            return
        
        print(f"📁 找到 {len(config_files)} 个配置文件")
        
        for config_file in config_files:
            try:
                # 读取配置文件
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # 检查并更新模型路径
                updated = False
                
                # 递归更新配置中的模型路径
                def update_model_paths(obj):
                    nonlocal updated
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            if isinstance(value, str) and value.endswith('.pt'):
                                # 替换.pt为.dat
                                new_value = value.replace('.pt', '.dat')
                                obj[key] = new_value
                                updated = True
                                print(f"  🔄 更新路径: {value} -> {new_value}")
                            elif isinstance(value, (dict, list)):
                                update_model_paths(value)
                    elif isinstance(obj, list):
                        for item in obj:
                            update_model_paths(item)
                
                update_model_paths(config_data)
                
                # 保存更新后的配置文件
                if updated:
                    with open(config_file, 'w', encoding='utf-8') as f:
                        json.dump(config_data, f, ensure_ascii=False, indent=2)
                    print(f"✅ 配置文件已更新: {config_file}")
                else:
                    print(f"ℹ️ 配置文件无需更新: {config_file}")
                
            except Exception as e:
                print(f"❌ 更新配置文件失败 {config_file}: {e}")
    
    def update_python_files(self):
        """
        更新Python文件中的.pt引用为.dat
        """
        # 需要更新的文件列表
        files_to_update = [
            "core/model_loader.py",
            "core/constants.py",
            "components/panels/model_panel.py",
            "components/panels/video_panel.py",
            "components/panels/information_panel.py",
            "components/dialogs/model_settings.py"
        ]
        
        for file_path in files_to_update:
            if not Path(file_path).exists():
                continue
            
            try:
                # 读取文件内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 替换.pt为.dat
                original_content = content
                content = content.replace('.pt', '.dat')
                
                # 如果内容有变化，保存文件
                if content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"✅ Python文件已更新: {file_path}")
                else:
                    print(f"ℹ️ Python文件无需更新: {file_path}")
                
            except Exception as e:
                print(f"❌ 更新Python文件失败 {file_path}: {e}")


def main():
    parser = argparse.ArgumentParser(description="批量将所有.pt文件转换为.dat文件")
    parser.add_argument("--input", "-i", type=str, default="D:/111/liquid4/tools/unconverted_pt",
                        help="输入目录路径")
    parser.add_argument("--config", "-c", type=str, default="resources/channel_configs",
                        help="配置文件目录路径")
    parser.add_argument("--key", "-k", type=str, 
                        default="liquid_detection_system_2024",
                        help="处理密钥")
    parser.add_argument("--update-config", action="store_true",
                        help="是否更新配置文件")
    parser.add_argument("--update-python", action="store_true",
                        help="是否更新Python文件")
    
    args = parser.parse_args()
    
    converter = BatchConverter(args.key)
    
    try:
        print("🚀 开始批量转换.pt文件为.dat文件")
        print("=" * 60)
        
        # 1. 转换模型文件
        print("\n📦 步骤1: 转换模型文件")
        converted_files = converter.batch_convert_directory(args.input)
        print(f"✅ 成功转换 {len(converted_files)} 个文件")
        
        # 2. 更新配置文件
        if args.update_config:
            print("\n📝 步骤2: 更新配置文件")
            converter.update_config_files(args.config)
        
        # 3. 更新Python文件
        if args.update_python:
            print("\n🔧 步骤3: 更新Python文件")
            converter.update_python_files()
        
        # 4. 输出总结
        print("\n📊 转换完成总结")
        print("=" * 60)
        print(f"✅ 已转换 {len(converted_files)} 个模型文件")
        if args.update_config:
            print("✅ 已更新配置文件")
        if args.update_python:
            print("✅ 已更新Python文件")
        print("✅ 所有.pt文件已成功转换为.dat文件")
        
    except Exception as e:
        print(f"❌ 批量转换失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 