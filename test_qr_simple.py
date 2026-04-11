"""简单测试脚本"""
print("脚本开始运行...")

try:
    from qtpy import QtWidgets
    print("qtpy导入成功")
    
    import cv2
    print("cv2导入成功")
    
    import sys
    app = QtWidgets.QApplication(sys.argv)
    print("QApplication创建成功")
    
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("测试窗口")
    window.setGeometry(100, 100, 400, 300)
    window.show()
    print("窗口已显示")
    
    print("进入事件循环...")
    sys.exit(app.exec_())
    
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
