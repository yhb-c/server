"""
测试PyQt5窗口显示
"""
import sys
from PyQt5 import QtWidgets

app = QtWidgets.QApplication(sys.argv)
window = QtWidgets.QMainWindow()
window.setWindowTitle("测试窗口")
window.setGeometry(100, 100, 400, 300)

label = QtWidgets.QLabel("如果你看到这个窗口，说明PyQt5工作正常", window)
label.setGeometry(50, 100, 300, 50)

window.show()
window.raise_()
window.activateWindow()

print("测试窗口已显示")
sys.exit(app.exec_())
