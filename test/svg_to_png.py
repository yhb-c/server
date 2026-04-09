"""
SVG转PNG高分辨率转换脚本
"""

import cairosvg
from pathlib import Path

def svg_to_png(svg_path, png_path, scale=4):
    """
    将SVG文件转换为高分辨率PNG图片

    Args:
        svg_path: SVG文件路径
        png_path: 输出PNG文件路径
        scale: 缩放倍数，默认4倍（相当于高分辨率）
    """
    svg_path = Path(svg_path).resolve()
    png_path = Path(png_path).resolve()

    if not svg_path.exists():
        print(f"错误: SVG文件不存在: {svg_path}")
        return False

    png_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(png_path),
            scale=scale
        )

        print(f"转换成功: {png_path}")
        print(f"缩放倍数: {scale}x")
        return True

    except Exception as e:
        print(f"转换过程出错: {e}")
        return False


if __name__ == '__main__':
    import sys

    project_root = Path(__file__).parent.parent

    if len(sys.argv) > 1:
        svg_file = project_root / sys.argv[1]
        png_file = svg_file.with_suffix('.png')
    else:
        svg_file = project_root / 'system_architecture.svg'
        png_file = project_root / 'system_architecture.png'

    print("开始转换SVG到PNG...")
    print(f"输入文件: {svg_file}")
    print(f"输出文件: {png_file}")

    svg_to_png(svg_file, png_file, scale=4)
