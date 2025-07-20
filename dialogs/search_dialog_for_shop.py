from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QMessageBox

class SearchDialogForShop(QDialog):
    """
    상가(새광고) 테이블 전용 검색 다이얼로그:
    - 검색어 입력 / 엔터 시 검색
    - 검색 결과 (현재 i / 총 n) 형태 표시
    - [이전], [다음], [닫기] 버튼으로 검색 결과 순회
    """
    def __init__(self, table_view: QtWidgets.QTableView, parent=None):
        super().__init__(parent)
        self.setWindowTitle("상가 검색")
        self.resize(400, 120)

        self.table_view = table_view  # 어떤 테이블에서 검색할지 주입
        self.search_results = []      # [(row, col), ...]
        self.curr_index = -1         # 검색 결과 중 현재 몇 번째 match에 위치

        # --- UI 구성 ---
        layout = QVBoxLayout(self)

        # (A) 검색어 입력 라인
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("검색어를 입력 후 엔터")
        layout.addWidget(self.line_edit)

        # (B) 현재 결과 위치 표시 라벨: "결과: 0 / 0"
        self.label_status = QLabel("결과: 0 / 0")
        layout.addWidget(self.label_status)

        # (C) 버튼 영역
        hlay = QHBoxLayout()
        self.btn_prev = QPushButton("이전")
        self.btn_next = QPushButton("다음")
        self.btn_close = QPushButton("닫기")

        hlay.addWidget(self.btn_prev)
        hlay.addWidget(self.btn_next)
        hlay.addWidget(self.btn_close)
        layout.addLayout(hlay)

        # (D) 시그널 연결
        self.line_edit.returnPressed.connect(self.do_search)  # 엔터 치면 검색
        self.btn_prev.clicked.connect(self.on_prev)
        self.btn_next.clicked.connect(self.on_next)
        self.btn_close.clicked.connect(self.close)

    def do_search(self):
        """
        라인에딧에 입력된 텍스트로 테이블 전체 검색 후,
        self.search_results 에 (row, col) 목록 저장. 첫 match로 이동.
        """
        text = self.line_edit.text().strip()
        if not text:
            QMessageBox.information(self, "알림", "검색어를 입력하세요.")
            return

        # (1) 테이블 전체 스캔
        model = self.table_view.model()
        row_count = model.rowCount()
        col_count = model.columnCount()
        lower_search = text.lower()

        results = []
        for r in range(row_count):
            for c in range(col_count):
                idx = model.index(r, c)
                cell_val = model.data(idx, QtCore.Qt.DisplayRole)
                if not cell_val:
                    continue
                if lower_search in str(cell_val).lower():
                    results.append((r, c))

        # (2) 결과 없으면 안내
        if not results:
            QMessageBox.information(self, "검색 결과", "일치하는 항목이 없습니다.")
            self.search_results = []
            self.curr_index = -1
            self.label_status.setText("결과: 0 / 0")
            return

        # (3) 결과가 있으면 전부 selection에 표시 + 첫 번째로 이동
        self.search_results = results
        self.curr_index = 0

        sel_model = self.table_view.selectionModel()
        sel_model.clearSelection()
        for (rr, cc) in results:
            idx_ = model.index(rr, cc)
            sel_model.select(idx_, QtCore.QItemSelectionModel.Select)

        self._go_to_current_match()
        self._update_label()

    def on_next(self):
        """ '다음' 버튼 클릭 시 => 다음 match로 이동 """
        if not self.search_results:
            QMessageBox.information(self, "알림", "검색 결과가 없습니다. (검색어 입력 후 '다음')")
            return

        self.curr_index += 1
        if self.curr_index >= len(self.search_results):
            self.curr_index = 0  # 맨 처음으로 순환
        self._go_to_current_match()
        self._update_label()

    def on_prev(self):
        """ '이전' 버튼 클릭 시 => 이전 match로 이동 """
        if not self.search_results:
            QMessageBox.information(self, "알림", "검색 결과가 없습니다. (검색어 입력 후 '이전')")
            return

        self.curr_index -= 1
        if self.curr_index < 0:
            self.curr_index = len(self.search_results) - 1  # 맨 뒤로 순환
        self._go_to_current_match()
        self._update_label()

    def _go_to_current_match(self):
        """ curr_index 위치로 커서/스크롤 이동 """
        row_i, col_i = self.search_results[self.curr_index]
        model = self.table_view.model()
        idx = model.index(row_i, col_i)
        self.table_view.setCurrentIndex(idx)
        self.table_view.scrollTo(idx)

    def _update_label(self):
        """ 라벨에 "결과: 현재 / 총개수" 표시 """
        total = len(self.search_results)
        curr = self.curr_index + 1
        self.label_status.setText(f"결과: {curr} / {total}") 