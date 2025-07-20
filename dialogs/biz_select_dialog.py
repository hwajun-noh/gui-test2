# dialogs/biz_select_dialog.py

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt

class BizSelectDialog(QtWidgets.QDialog):
    """
    '동선택' 로직과 동일하게:
    주어진 업종 목록(biz_list)을
    여러 버튼(토글)로 표시.
    확인 시 선택된 업종 리스트 반환.
    """
    def __init__(self, biz_list, pre_selected=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("업종 선택")
        self.resize(600, 400)
        if pre_selected is None:
            pre_selected = []
        self.pre_selected_biz = set(pre_selected)
        self.selected_biz = set()  # 선택 업종 보관
        layout = QtWidgets.QVBoxLayout(self)

        # 전체선택 버튼
        btn_all = QtWidgets.QPushButton("전체선택")
        btn_all.clicked.connect(self.on_select_all)
        layout.addWidget(btn_all, alignment=QtCore.Qt.AlignLeft)

        # 스크롤(업종이 많을 수도 있으니)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        container = QtWidgets.QWidget()
        scroll.setWidget(container)
        form_layout = QtWidgets.QFormLayout(container)

        # 항상 정렬된 업종 목록 사용 (일관성)
        sorted_biz_list = sorted(biz_list)
        
        # 토글 가능한 버튼들
        self.btn_list = []
        for biz in sorted_biz_list:
            btn = QtWidgets.QPushButton(biz)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    padding: 5px;
                }
                QPushButton:checked {
                    background-color: #87CEFA;
                    font-weight: bold;
                    border: 1px solid #0066cc;
                }
            """)
            if biz in self.pre_selected_biz:
                btn.setChecked(True)
            self.btn_list.append(btn)
            form_layout.addRow(btn)

        # 확인/취소 버튼
        btn_layout = QtWidgets.QHBoxLayout()
        btn_reset = QtWidgets.QPushButton("초기화")
        btn_reset.clicked.connect(self.on_reset_clicked)
        btn_layout.addWidget(btn_reset)

        btn_ok = QtWidgets.QPushButton("확인")
        btn_ok.clicked.connect(self.on_ok_clicked)
        btn_cancel = QtWidgets.QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def on_select_all(self):
        for btn in self.btn_list:
            btn.setChecked(True)

    def on_reset_clicked(self):
        """ '초기화' -> 모든 버튼 해제 """
        for btn in self.btn_list:
            btn.setChecked(False)

    def on_ok_clicked(self):
        # 선택된 버튼만 self.selected_biz에
        self.selected_biz = set()
        for btn in self.btn_list:
            if btn.isChecked():
                self.selected_biz.add(btn.text())
        self.accept()

    def get_selected_biz(self):
        return list(self.selected_biz)
