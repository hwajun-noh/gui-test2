# dialogs/range_dialogs.py

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QComboBox, QFormLayout, QHBoxLayout, QPushButton

class FloorRangeDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("층 범위 지정")

        layout = QtWidgets.QVBoxLayout()

        self.start_combo = QtWidgets.QComboBox()
        self.end_combo = QtWidgets.QComboBox()
        # 범위 확장 (예: 1~20층 + 999층)
        floors = [f"{i}층" for i in range(1, 21)] + ["999층"]
        self.start_combo.addItems(floors)
        self.end_combo.addItems(floors)

        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow("시작 층:", self.start_combo)
        form_layout.addRow("끝 층:", self.end_combo)
        layout.addLayout(form_layout)

        btn_layout = QtWidgets.QHBoxLayout()
        ok_btn = QtWidgets.QPushButton("확인")
        ok_btn.setStyleSheet("font-size:16px;")
        cancel_btn = QtWidgets.QPushButton("취소")
        cancel_btn.setStyleSheet("font-size:16px;")
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def get_floor_range(self):
        return self.start_combo.currentText(), self.end_combo.currentText()
