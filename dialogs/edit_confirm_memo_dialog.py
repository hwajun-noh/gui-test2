from PyQt5 import QtWidgets, QtGui, QtCore

class EditConfirmMemoDialog(QtWidgets.QDialog):
    """
    업종별로 메모를 수정하는 간단 Dialog.
    - upjong_list: ['카페','음식점',...]
    - biz_to_memo_map: {'카페': '...', '음식점': '...'}
    """
    def __init__(self, upjong_list, biz_to_memo_map, parent=None):
        super().__init__(parent)
        self.setWindowTitle("업종별 확인메모")
        self.upjong_list = upjong_list[:]
        self.biz_to_memo_map = dict(biz_to_memo_map)  # copy

        layout = QtWidgets.QVBoxLayout(self)

        # 스크롤 영역
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        w_container = QtWidgets.QWidget()
        form_layout = QtWidgets.QFormLayout(w_container)

        self.editors = {}  # { "카페": QPlainTextEdit(), "음식점": QPlainTextEdit(), ... }
        for biz in self.upjong_list:
            label = QtWidgets.QLabel(biz)
            pedit = QtWidgets.QPlainTextEdit()
            pedit.setPlainText(self.biz_to_memo_map.get(biz,""))
            form_layout.addRow(label, pedit)
            self.editors[biz] = pedit

        w_container.setLayout(form_layout)
        scroll.setWidget(w_container)

        layout.addWidget(scroll)

        btn_box = QtWidgets.QHBoxLayout()
        btn_ok = QtWidgets.QPushButton("확인")
        btn_cancel = QtWidgets.QPushButton("취소")
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)

        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

    def get_biz_to_memo(self):
        """
        Dialog 닫힐 때, 각 업종별 메모를 dict로 반환
        """
        for biz, editor in self.editors.items():
            self.biz_to_memo_map[biz] = editor.toPlainText().strip()
        return self.biz_to_memo_map 