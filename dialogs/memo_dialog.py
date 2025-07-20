from PyQt5 import QtWidgets, QtGui, QtCore

class MemoDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("메모 추가")
        self.resize(650, 350)  # 메모창 크기

        layout = QtWidgets.QVBoxLayout()

        # 메모 입력 위젯
        self.memo_edit = QtWidgets.QPlainTextEdit()
        layout.addWidget(self.memo_edit)

        # 버튼 레이아웃
        btn_layout = QtWidgets.QHBoxLayout()
        ok_btn = QtWidgets.QPushButton("확인")
        cancel_btn = QtWidgets.QPushButton("취소")
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        self.setLayout(layout)

    def get_memo_text(self):
        return self.memo_edit.toPlainText().strip() 