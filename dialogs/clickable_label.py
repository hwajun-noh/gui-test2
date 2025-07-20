from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt

class ClickableLabel(QtWidgets.QLabel):
    """
    QLabel을 상속해, 마우스 왼쪽클릭 시 clicked() 시그널을 발생시키는 간단한 커스텀 위젯.
    """
    clicked = QtCore.pyqtSignal()

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        super().mousePressEvent(event)
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit() 