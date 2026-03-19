"""
将.pt文件转换为.bat文件
"""

import os
import struct
import hashlib
from pathlib import Path
import argparse


class FileConverter:
    """文件转换器"""
    
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
            # 自动生成输出路径，将.pt替换为.bat
            output_path = input_path.with_suffix('.bat')
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
        
        print(f"文件已转换: {input_path} -> {output_path}")
        return str(output_path)
    
    def batch_convert(self, directory: str, pattern: str = "*.pt") -> list[str]:
        """
        批量转换目录中的文件
        
        Args:
            directory: 目录路径
            pattern: 文件匹配模式
            
        Returns:
            已转换的文件列表
        """
        directory = Path(directory)
        converted_files = []
        
        for file_path in directory.rglob(pattern):
            if file_path.is_file():
                try:
                    output_path = self.convert_file(str(file_path))
                    converted_files.append(output_path)
                except Exception as e:
                    print(f"转换文件失败 {file_path}: {e}")
        
        return converted_files


def main():
    parser = argparse.ArgumentParser(description="将.pt文件转换为.bat文件")
    parser.add_argument("--input", "-i", type=str, default="D:/111/liquid4/tools/unconverted_pt",
                       help="输入目录路径")
    parser.add_argument("--file", "-f", type=str, help="转换单个文件")
    parser.add_argument("--key", "-k", type=str, 
                       default="liquid_detection_system_2024",
                       help="处理密钥")
    
    args = parser.parse_args()
    
    converter = FileConverter(args.key)
    
    if args.file:
        # 转换单个文件
        if os.path.exists(args.file):
            converter.convert_file(args.file)
        else:
            print(f"文件不存在: {args.file}")
    else:
        # 批量转换
        print(f"正在转换目录: {args.input}")
        converted_files = converter.batch_convert(args.input, "*.pt")
        print(f"已转换 {len(converted_files)} 个文件:")
        for file in converted_files:
            print(f"  {file}")


if __name__ == "__main__":
    main() 