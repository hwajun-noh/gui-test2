from PyQt5 import QtWidgets, QtGui, QtCore

class RecommendDialog(QtWidgets.QDialog):
    """
    RecommendDialog:
      - biz_list: [{"biz": ..., "manager": ...}, ...] 형태
      - 각 항목마다 체크박스, 확인메모 입력 QLineEdit, "추천예정" 버튼을 표시
      - OK를 누르면 선택된 항목들의 {"biz":..., "manager":..., "memo":...} 리스트를 반환
    """
    def __init__(self, biz_list, parent=None):
        super().__init__(parent)
        # biz_list -> [{"biz":"치킨집", "manager":"김철수"}, ...]
        self.biz_list = biz_list if biz_list else []
        self.selected_items = []  # OK 시점에 담길 최종 선택 정보
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("추천매물 등록 - 업종 선택 및 확인메모 입력")
        self.resize(450, 300)
        layout = QtWidgets.QVBoxLayout(self)

        # 스크롤 영역(업종이 많을 수 있으므로)
        scroll_area = QtWidgets.QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(5, 5, 5, 5)
        content_layout.setSpacing(5)

        # biz_list를 순회하며 행(checkbox + memo_edit + button)을 만든다
        self.biz_rows = []
        
        # biz_list가 비어있으면 메시지 표시
        if not self.biz_list:
            info_label = QtWidgets.QLabel("등록 가능한 업종 정보가 없습니다.\n데이터를 확인해 주세요.", content_widget)
            info_label.setAlignment(QtCore.Qt.AlignCenter)
            info_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
            content_layout.addWidget(info_label)
        else:
            for item in self.biz_list:
                biz = item.get("biz", "")
                manager_full = item.get("manager", "")
                # 표시 텍스트: "치킨집[김철수]" 형태
                display_text = f"{biz}[{manager_full}]" if manager_full else biz

                row_widget = QtWidgets.QWidget()
                row_layout = QtWidgets.QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(5)

                # 체크박스
                checkbox = QtWidgets.QCheckBox(display_text, row_widget)

                # 메모 입력 QLineEdit
                memo_edit = QtWidgets.QLineEdit(row_widget)
                memo_edit.setPlaceholderText("확인메모 입력")
                # textChanged 시그널 연결: 텍스트가 있으면 체크박스 체크
                memo_edit.textChanged.connect(
                    lambda text, cb=checkbox: cb.setChecked(True) if text else None
                )

                # "추천예정" 버튼 -> 누르면 memo_edit에 "추천예정" 자동 입력 및 체크박스 체크
                btn_predefine = QtWidgets.QPushButton("추천예정", row_widget)
                btn_predefine.clicked.connect(
                    lambda checked, le=memo_edit, cb=checkbox: (le.setText("추천예정"), cb.setChecked(True))
                )

                row_layout.addWidget(checkbox)
                row_layout.addWidget(memo_edit)
                row_layout.addWidget(btn_predefine)

                row_widget.setLayout(row_layout)
                content_layout.addWidget(row_widget)

                self.biz_rows.append({
                    "checkbox": checkbox,
                    "memo_edit": memo_edit,
                    "biz": biz,
                    "manager": manager_full
                })

        content_widget.setLayout(content_layout)
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

        # 버튼 박스 (OK / Cancel)
        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            parent=self
        )
        btn_box.accepted.connect(self.on_ok_clicked)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def on_ok_clicked(self):
        """
        OK 버튼 누르면, 선택된 체크박스에 대해서
        biz, manager, memo를 읽어서 self.selected_items 에 저장 후 다이얼로그 accept
        """
        self.selected_items = []
        for row in self.biz_rows:
            if row["checkbox"].isChecked():
                memo_text = row["memo_edit"].text().strip()
                self.selected_items.append({
                    "biz": row["biz"],
                    "manager": row["manager"],
                    "memo": memo_text
                })
        self.accept()  # QDialog.accept() -> exec_() 종료(정상)

    def get_selected_items(self):
        """
        다이얼로그 종료 후, 선택된 항목들을 반환
        [
          {"biz":"치킨집", "manager":"김철수", "memo":"추천예정"},
          ...
        ]
        """
        return self.selected_items 