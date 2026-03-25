#!/usr/bin/env python3
"""
Convert SVG files to high-resolution PNG images
"""
import subprocess
import sys
import os

def install_cairosvg():
    """Install cairosvg if not available"""
    try:
        import cairosvg
        return True
    except ImportError:
        print("Installing cairosvg...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "cairosvg"])
            return True
        except subprocess.CalledProcessError:
            print("Failed to install cairosvg")
            return False

def convert_svg_to_png(svg_path, png_path, dpi=300):
    """
    Convert SVG to high-resolution PNG

    Args:
        svg_path: Path to input SVG file
        png_path: Path to output PNG file
        dpi: Resolution in DPI (default 300 for high quality)
    """
    import cairosvg

    # Calculate scale factor (default SVG is 96 DPI)
    scale = dpi / 96.0

    print(f"Converting {svg_path} to {png_path} at {dpi} DPI...")

    # Read SVG file with UTF-8 encoding
    with open(svg_path, 'r', encoding='utf-8') as f:
        svg_content = f.read()

    cairosvg.svg2png(
        bytestring=svg_content.encode('utf-8'),
        write_to=png_path,
        scale=scale
    )
    print(f"✓ Created {png_path}")

def main():
    # Install cairosvg if needed
    if not install_cairosvg():
        print("Error: Could not install cairosvg")
        sys.exit(1)

    # Import after installation
    import cairosvg

    # Define SVG files to convert
    svg_files = [
        "方案/architecture_comparison.svg",
        "方案/development_mode.svg"
    ]

    # Convert each SVG to PNG at 300 DPI
    for svg_file in svg_files:
        if not os.path.exists(svg_file):
            print(f"Warning: {svg_file} not found, skipping...")
            continue

        # Generate PNG filename
        png_file = svg_file.replace('.svg', '_high_res.png')

        try:
            convert_svg_to_png(svg_file, png_file, dpi=300)
        except Exception as e:
            print(f"Error converting {svg_file}: {e}")

    print("\nConversion complete!")

if __name__ == "__main__":
    main()
