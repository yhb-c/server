"""
二维码生成脚本
用于生成测试用二维码图片
"""

import qrcode
import os

def generate_test_qrcode():
    """生成测试用二维码"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_path = os.path.join(project_root, 'test', 'test_qrcode.png')

    # 创建二维码内容
    qr_data = "液位检测系统测试二维码-Liquid Detection System Test QR Code"

    # 创建二维码对象
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )

    # 添加数据
    qr.add_data(qr_data)
    qr.make(fit=True)

    # 生成图片
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(output_path)

    print(f"二维码已生成: {output_path}")
    print(f"二维码内容: {qr_data}")

    return output_path

if __name__ == "__main__":
    generate_test_qrcode()
