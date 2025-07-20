import json
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt
import os

# MapSelectDialog, DongSelectDialog, FloorRangeDialog 가져오기
from .map_select_dialog import MapSelectDialog
from .dong_select_dialog import DongSelectDialog
from .floor_range_dialog import FloorRangeDialog
from .memo_dialog import MemoDialog

class CustomerRowEditDialog(QtWidgets.QDialog):
    """
    고객 테이블 행 편집용 Dialog.
    지역, 보증금, 월세, 평수, 층 등 필수값 체크 후 DB 업데이트(부모 위젯 이용).
    """
    def __init__(self, parent=None, district_data=None, headers=None,
                 row_data=None, saved_state=None):
        super().__init__(parent)
        self.setWindowTitle("행 편집")
        self.resize(1000, 600)

        self.district_data = district_data if district_data else {}
        self.headers = headers if headers else [
            "지역", "보증금", "월세", "평수", "층",
            "권리금", "업종", "연락처", "실보증금/월세",
            "최근연락날짜", "메모", "담당자"
        ]
        self.row_data = row_data[:] if row_data else []
        self.custom_floor_range = []
        self.delete_requested = False

        # 추가: id, manager, edit_row
        self.id = None
        self.manager = None
        self.edit_row = -1

        # 메모 관련
        self.memo_data = {}
        self.current_memo_row = None

        # 새 고객 등록인 경우 (edit_row가 -1) 초기화된 새 saved_conditions 사용
        # 이전 선택이 유지되지 않도록 항상 새로운 객체로 초기화
        if saved_state is not None and self.edit_row != -1:
            # 기존 고객 편집 시에만 saved_state 사용
            self.saved_conditions = saved_state.copy() if isinstance(saved_state, dict) else {
                "deposit": {"min": 0, "max": 0, "selected_values": []},
                "rent": {"min": 0, "max": 0, "selected_values": []},
                "pyeong": {"min": 0, "max": 0, "selected_values": []},
                "dongs": {"all_area": False, "selected": {}},
                "map_rectangles": [],
                "floors": {"selected_buttons": [], "custom_floor_range": []}
            }
        else:
            # 새 고객 등록 시 초기화된 새 saved_conditions 사용
            self.saved_conditions = {
                "deposit": {"min": 0, "max": 0, "selected_values": []},
                "rent": {"min": 0, "max": 0, "selected_values": []},
                "pyeong": {"min": 0, "max": 0, "selected_values": []},
                "dongs": {"all_area": False, "selected": {}},
                "map_rectangles": [],
                "floors": {"selected_buttons": [], "custom_floor_range": []}
            }

        # ValueSelectionWidgets
        deposit_options = [(str(i), i) for i in range(1000, 11000, 1000)]
        deposit_options[-1] = ("1억", 10000)
        deposit_options.append(("1억~", 99999999))

        rent_list = [(str(i), i) for i in range(50, 201, 10)]
        rent_list.append(("200~", 99999999))

        pyeong_options = [(f"{i}평", i) for i in range(10, 101, 10)]
        pyeong_options.append(("100평~", 99999999))
        from widgets import ValueSelectionWidget
        self.deposit_widget = ValueSelectionWidget("보증금", deposit_options)
        self.rent_widget = ValueSelectionWidget("월세", rent_list)
        self.pyeong_widget = ValueSelectionWidget("평수", pyeong_options)

        if self.saved_conditions:
            self.deposit_widget.set_values(
                self.saved_conditions["deposit"]["min"],
                self.saved_conditions["deposit"]["max"],
                self.saved_conditions["deposit"]["selected_values"]
            )
            self.rent_widget.set_values(
                self.saved_conditions["rent"]["min"],
                self.saved_conditions["rent"]["max"],
                self.saved_conditions["rent"]["selected_values"]
            )
            self.pyeong_widget.set_values(
                self.saved_conditions["pyeong"]["min"],
                self.saved_conditions["pyeong"]["max"],
                self.saved_conditions["pyeong"]["selected_values"]
            )

        form_layout = QtWidgets.QFormLayout()

        # 지역 선택 구역
        gu_box = QtWidgets.QGroupBox("지역 선택")
        gu_layout = QtWidgets.QVBoxLayout()
        btn_layout = QtWidgets.QHBoxLayout()
        dong_select_btn = QtWidgets.QPushButton("동선택")
        dong_select_btn.setStyleSheet("font-size:14px;")
        dong_select_btn.clicked.connect(self.on_dong_select_popup)

        map_select_btn = QtWidgets.QPushButton("지도 선택")
        map_select_btn.setStyleSheet("font-size:14px;")
        map_select_btn.clicked.connect(self.on_map_select)

        btn_layout.addWidget(dong_select_btn)
        btn_layout.addWidget(map_select_btn)
        gu_layout.addLayout(btn_layout)

        self.selected_dongs_label = QtWidgets.QLabel("")
        self.selected_dongs_label.setStyleSheet("font-size:14px;")
        gu_layout.addWidget(self.selected_dongs_label)
        gu_box.setLayout(gu_layout)

        # 층 선택
        self.floor_group = QtWidgets.QGroupBox("층 선택")
        self.floor_range_label = QtWidgets.QLabel("")
        self.floor_range_label.setStyleSheet("font-size:14px;")
        floor_layout = QtWidgets.QHBoxLayout()
        floor_names = ["1층", "2층이상", "탑층", "지하층"]
        self.floor_buttons = []
        for fname in floor_names:
            fb = QtWidgets.QPushButton(fname)
            fb.setCheckable(True)
            fb.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0; 
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    padding: 5px;
                    font-size:14px;
                }
                QPushButton:checked {
                    background-color: #98FB98; 
                    font-weight: bold;
                    border: 1px solid #0066cc;
                }
            """)
            self.floor_buttons.append(fb)
            floor_layout.addWidget(fb)

        self.floor_custom_btn = QtWidgets.QPushButton("층 지정")
        self.floor_custom_btn.setStyleSheet("font-size:14px;")
        self.floor_custom_btn.clicked.connect(self.on_floor_custom_clicked)
        floor_layout.addWidget(self.floor_custom_btn)
        self.floor_reset_btn = QtWidgets.QPushButton("초기화")
        self.floor_reset_btn.clicked.connect(self.on_floor_reset_clicked)
        floor_layout.addWidget(self.floor_reset_btn)

        self.floor_group.setLayout(floor_layout)

        for fb in self.floor_buttons:
            fb.clicked.connect(self.update_floor_label)

        line1 = QtWidgets.QFrame()
        line1.setFrameShape(QtWidgets.QFrame.HLine)
        line2 = QtWidgets.QFrame()
        line2.setFrameShape(QtWidgets.QFrame.HLine)
        line3 = QtWidgets.QFrame()
        line3.setFrameShape(QtWidgets.QFrame.HLine)

        form_layout.addRow(gu_box)
        form_layout.addRow(self.floor_group)
        form_layout.addRow(self.floor_range_label)
        form_layout.addRow(line1)
        form_layout.addRow(self.deposit_widget)
        form_layout.addRow(line2)
        form_layout.addRow(self.rent_widget)
        form_layout.addRow(line3)
        form_layout.addRow(self.pyeong_widget)

        left_widget = QtWidgets.QWidget()
        left_vlayout = QtWidgets.QVBoxLayout(left_widget)
        left_vlayout.addLayout(form_layout)

        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setSpacing(2)

        money_layout = QtWidgets.QFormLayout()
        money_layout.setSpacing(2)
        self.right_kwoligi_line = QtWidgets.QLineEdit()
        self.right_upjong_line = QtWidgets.QLineEdit()
        self.right_contact_line = QtWidgets.QLineEdit()
        self.right_silbw_line = QtWidgets.QLineEdit()
        money_layout.addRow("권리금:", self.right_kwoligi_line)
        money_layout.addRow("업종:", self.right_upjong_line)
        money_layout.addRow("연락처:", self.right_contact_line)
        money_layout.addRow("실보증금/월세:", self.right_silbw_line)
        right_layout.addLayout(money_layout)

        memo_add_btn = QtWidgets.QPushButton("메모 추가")
        memo_add_btn.clicked.connect(self.on_add_memo)
        right_layout.addWidget(memo_add_btn)

        memo_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)

        self.memo_table = QtWidgets.QTableWidget()
        self.memo_table.setColumnCount(2)
        self.memo_table.setHorizontalHeaderLabels(["날짜", "메모요약"])
        self.memo_table.horizontalHeader().setStretchLastSection(True)
        self.memo_table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.memo_table.setSelectionMode(QtWidgets.QTableWidget.SingleSelection)
        self.memo_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.memo_table.itemSelectionChanged.connect(self.on_memo_selection_changed)
        memo_splitter.addWidget(self.memo_table)

        self.memo_detail = QtWidgets.QPlainTextEdit()
        self.memo_detail.setReadOnly(False)
        self.memo_detail.textChanged.connect(self.on_memo_detail_changed)
        # 메모 테이블 우클릭 메뉴
        self.memo_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.memo_table.customContextMenuRequested.connect(self.on_memo_table_context_menu)
        memo_splitter.addWidget(self.memo_detail)

        right_layout.addWidget(memo_splitter)

        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget)

        bottom_layout = QtWidgets.QHBoxLayout()
        cond_reset_btn = QtWidgets.QPushButton("전체 초기화")
        cond_reset_btn.setStyleSheet("font-size:16px;")
        cond_reset_btn.setFixedHeight(50)
        cond_reset_btn.clicked.connect(self.on_reset_conditions)
        bottom_layout.addWidget(cond_reset_btn)

        self.ok_btn = QtWidgets.QPushButton("확인")
        self.ok_btn.setStyleSheet("font-size:16px;")
        self.ok_btn.setFixedHeight(50)
        self.ok_btn.clicked.connect(self.on_ok)
        bottom_layout.addWidget(self.ok_btn)

        container_layout = QtWidgets.QVBoxLayout()
        container_layout.addLayout(main_layout)
        container_layout.addLayout(bottom_layout)
        self.setLayout(container_layout)

        # 행 데이터 파싱
        if self.row_data and len(self.row_data) == len(self.headers):
            self.parse_init_values()

    def _init_ui(self):
        # ValueSelectionWidgets
        deposit_options = [(str(i), i) for i in range(1000, 11000, 1000)]
        deposit_options[-1] = ("1억", 10000)
        deposit_options.append(("1억~", 99999999))

        rent_list = [(str(i), i) for i in range(50, 201, 10)]
        rent_list.append(("200~", 99999999))

        pyeong_options = [(f"{i}평", i) for i in range(10, 101, 10)]
        pyeong_options.append(("100평~", 99999999))
        from widgets import ValueSelectionWidget
        self.deposit_widget = ValueSelectionWidget("보증금", deposit_options)
        self.rent_widget = ValueSelectionWidget("월세", rent_list)
        self.pyeong_widget = ValueSelectionWidget("평수", pyeong_options)

        if self.saved_conditions:
            self.deposit_widget.set_values(
                self.saved_conditions["deposit"]["min"],
                self.saved_conditions["deposit"]["max"],
                self.saved_conditions["deposit"]["selected_values"]
            )
            self.rent_widget.set_values(
                self.saved_conditions["rent"]["min"],
                self.saved_conditions["rent"]["max"],
                self.saved_conditions["rent"]["selected_values"]
            )
            self.pyeong_widget.set_values(
                self.saved_conditions["pyeong"]["min"],
                self.saved_conditions["pyeong"]["max"],
                self.saved_conditions["pyeong"]["selected_values"]
            )

        form_layout = QtWidgets.QFormLayout()

        # 지역 선택 구역
        gu_box = QtWidgets.QGroupBox("지역 선택")
        gu_layout = QtWidgets.QVBoxLayout()
        btn_layout = QtWidgets.QHBoxLayout()
        dong_select_btn = QtWidgets.QPushButton("동선택")
        dong_select_btn.setStyleSheet("font-size:14px;")
        dong_select_btn.clicked.connect(self.on_dong_select_popup)

        map_select_btn = QtWidgets.QPushButton("지도 선택")
        map_select_btn.setStyleSheet("font-size:14px;")
        map_select_btn.clicked.connect(self.on_map_select)

        btn_layout.addWidget(dong_select_btn)
        btn_layout.addWidget(map_select_btn)
        gu_layout.addLayout(btn_layout)

        self.selected_dongs_label = QtWidgets.QLabel("")
        self.selected_dongs_label.setStyleSheet("font-size:14px;")
        gu_layout.addWidget(self.selected_dongs_label)
        gu_box.setLayout(gu_layout)

        # 층 선택
        self.floor_group = QtWidgets.QGroupBox("층 선택")
        self.floor_range_label = QtWidgets.QLabel("")
        self.floor_range_label.setStyleSheet("font-size:14px;")
        floor_layout = QtWidgets.QHBoxLayout()
        floor_names = ["1층", "2층이상", "탑층", "지하층"]
        self.floor_buttons = []
        for fname in floor_names:
            fb = QtWidgets.QPushButton(fname)
            fb.setCheckable(True)
            fb.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0; 
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    padding: 5px;
                    font-size:14px;
                }
                QPushButton:checked {
                    background-color: #98FB98; 
                    font-weight: bold;
                    border: 1px solid #0066cc;
                }
            """)
            self.floor_buttons.append(fb)
            floor_layout.addWidget(fb)

        self.floor_custom_btn = QtWidgets.QPushButton("층 지정")
        self.floor_custom_btn.setStyleSheet("font-size:14px;")
        self.floor_custom_btn.clicked.connect(self.on_floor_custom_clicked)
        floor_layout.addWidget(self.floor_custom_btn)
        self.floor_reset_btn = QtWidgets.QPushButton("초기화")
        self.floor_reset_btn.clicked.connect(self.on_floor_reset_clicked)
        floor_layout.addWidget(self.floor_reset_btn)

        self.floor_group.setLayout(floor_layout)

        for fb in self.floor_buttons:
            fb.clicked.connect(self.update_floor_label)

        line1 = QtWidgets.QFrame()
        line1.setFrameShape(QtWidgets.QFrame.HLine)
        line2 = QtWidgets.QFrame()
        line2.setFrameShape(QtWidgets.QFrame.HLine)
        line3 = QtWidgets.QFrame()
        line3.setFrameShape(QtWidgets.QFrame.HLine)

        form_layout.addRow(gu_box)
        form_layout.addRow(self.floor_group)
        form_layout.addRow(self.floor_range_label)
        form_layout.addRow(line1)
        form_layout.addRow(self.deposit_widget)
        form_layout.addRow(line2)
        form_layout.addRow(self.rent_widget)
        form_layout.addRow(line3)
        form_layout.addRow(self.pyeong_widget)

        left_widget = QtWidgets.QWidget()
        left_vlayout = QtWidgets.QVBoxLayout(left_widget)
        left_vlayout.addLayout(form_layout)

        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setSpacing(2)

        money_layout = QtWidgets.QFormLayout()
        money_layout.setSpacing(2)
        self.right_kwoligi_line = QtWidgets.QLineEdit()
        self.right_upjong_line = QtWidgets.QLineEdit()
        self.right_contact_line = QtWidgets.QLineEdit()
        self.right_silbw_line = QtWidgets.QLineEdit()
        money_layout.addRow("권리금:", self.right_kwoligi_line)
        money_layout.addRow("업종:", self.right_upjong_line)
        money_layout.addRow("연락처:", self.right_contact_line)
        money_layout.addRow("실보증금/월세:", self.right_silbw_line)
        right_layout.addLayout(money_layout)

        memo_add_btn = QtWidgets.QPushButton("메모 추가")
        memo_add_btn.clicked.connect(self.on_add_memo)
        right_layout.addWidget(memo_add_btn)

        memo_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)

        self.memo_table = QtWidgets.QTableWidget()
        self.memo_table.setColumnCount(2)
        self.memo_table.setHorizontalHeaderLabels(["날짜", "메모요약"])
        self.memo_table.horizontalHeader().setStretchLastSection(True)
        self.memo_table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.memo_table.setSelectionMode(QtWidgets.QTableWidget.SingleSelection)
        self.memo_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.memo_table.itemSelectionChanged.connect(self.on_memo_selection_changed)
        memo_splitter.addWidget(self.memo_table)

        self.memo_detail = QtWidgets.QPlainTextEdit()
        self.memo_detail.setReadOnly(False)
        self.memo_detail.textChanged.connect(self.on_memo_detail_changed)
        # 메모 테이블 우클릭 메뉴
        self.memo_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.memo_table.customContextMenuRequested.connect(self.on_memo_table_context_menu)
        memo_splitter.addWidget(self.memo_detail)

        right_layout.addWidget(memo_splitter)

        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget)

        bottom_layout = QtWidgets.QHBoxLayout()
        cond_reset_btn = QtWidgets.QPushButton("전체 초기화")
        cond_reset_btn.setStyleSheet("font-size:16px;")
        cond_reset_btn.setFixedHeight(50)
        cond_reset_btn.clicked.connect(self.on_reset_conditions)
        bottom_layout.addWidget(cond_reset_btn)

        self.ok_btn = QtWidgets.QPushButton("확인")
        self.ok_btn.setStyleSheet("font-size:16px;")
        self.ok_btn.setFixedHeight(50)
        self.ok_btn.clicked.connect(self.on_ok)
        bottom_layout.addWidget(self.ok_btn)

        container_layout = QtWidgets.QVBoxLayout()
        container_layout.addLayout(main_layout)
        container_layout.addLayout(bottom_layout)
        self.setLayout(container_layout)

    # 필요한 메소드들 (일부만 먼저 추가)
    def on_memo_table_context_menu(self, pos):
        """
        메모 테이블에서 우클릭 시, '메모 삭제' 메뉴를 띄워
        선택된 행을 제거하는 기능.
        """
        menu = QtWidgets.QMenu(self)
        act_delete = menu.addAction("메모 삭제")

        global_pos = self.memo_table.viewport().mapToGlobal(pos)
        chosen_action = menu.exec_(global_pos)
        if chosen_action == act_delete:
            # 현재 선택된 행(들)
            selected = self.memo_table.selectionModel().selectedRows()
            if not selected:
                return
            row_idx = selected[0].row()
            
            # 테이블에서 행 제거
            self.memo_table.removeRow(row_idx)
            
            # 혹시 현재 열람 중인 메모 행이면 상세창도 비움
            if self.current_memo_row == row_idx:
                self.memo_detail.clear()
                self.current_memo_row = None
                
            # 삭제 뒤 memo_data 재구성
            self.rebuild_memo_data_from_table()

    def rebuild_memo_data_from_table(self):
        """
        메모 테이블 현재 상태를 다시 스캔하여 self.memo_data 갱신.
        (행 인덱스를 0부터 차례대로 매핑)
        """
        new_memo_data = {}  # 새로운 딕셔너리 생성
        row_count = self.memo_table.rowCount()
        
        for r in range(row_count):
            date_item = self.memo_table.item(r, 0)
            date_str = date_item.text().strip() if date_item else "고정메모"
            
            # 요약 텍스트 가져오기
            summary_item = self.memo_table.item(r, 1)
            summary_text = summary_item.text().strip() if summary_item else ""
            
            # 기존 메모 데이터에서 전체 텍스트 가져오기 (가능한 경우)
            # 삭제된 항목 이후의 인덱스는 기존 데이터에서 r+1에 해당함
            full_text = ""
            for old_idx, text in self.memo_data.items():
                # 삭제된 행 이전의 항목들은 그대로 가져옴
                if old_idx < r:
                    if old_idx in self.memo_data:
                        full_text = self.memo_data[old_idx]
                # 삭제된 행 이후의 항목들은 인덱스 조정
                elif old_idx > r:
                    if (old_idx - 1) in self.memo_data:
                        full_text = self.memo_data[old_idx]
                        
            # 현재 행이 선택된 경우 메모 상세 내용 사용
            if r == self.current_memo_row:
                full_text = self.memo_detail.toPlainText()
                
            # 없으면 summary 사용
            if not full_text:
                full_text = summary_text
                
            new_memo_data[r] = full_text
            
        # 새로운 memo_data로 교체
        self.memo_data = new_memo_data
            
        # 혹시 지금 선택된 행이 있으면 -> self.current_memo_row 재설정
        selected = self.memo_table.selectionModel().selectedRows()
        if selected:
            self.current_memo_row = selected[0].row()
        else:
            self.current_memo_row = None

    def on_floor_reset_clicked(self):
        """
        '초기화' 버튼 → 모든 층 버튼 해제, custom_floor_range 초기화, 표시 갱신
        """
        # 1) 층 버튼 전부 해제
        for fb in self.floor_buttons:
            fb.setChecked(False)

        # 2) 커스텀 범위 없애기
        self.custom_floor_range = []

        # 3) 라벨 갱신
        self.update_floor_label()

    def parse_init_values(self):
        """
        전달받은 row_data에서 초기값을 추출하여 UI 상태를 설정합니다.
        """
        try:
            # 지역, 동(들) 추출
            region_col = self.headers.index("지역") if "지역" in self.headers else -1
            if region_col >= 0 and region_col < len(self.row_data):
                region_val = self.row_data[region_col]
                if region_val:
                    try:
                        region_obj = json.loads(region_val)
                        dongs_list = region_obj.get("dong_list", [])
                        rects_list = region_obj.get("rectangles", [])
                        self.saved_conditions["dongs"]["selected"] = dongs_list
                        self.saved_conditions["map_rectangles"] = rects_list
                        self.update_dong_label(dongs_list)
                    except json.JSONDecodeError:
                        print(f"[WARN] JSON 파싱 실패: region_val='{region_val}'")
                        self.update_dong_label([])
            
            # 층 버튼 상태 초기화
            floor_col = self.headers.index("층") if "층" in self.headers else -1
            if floor_col >= 0 and floor_col < len(self.row_data):
                floor_val = self.row_data[floor_col]
                if floor_val:
                    self._init_floor_buttons_from_value(floor_val)

            # 가격/평수 입력 범위 추출 및 설정
            deposit_col = self.headers.index("보증금") if "보증금" in self.headers else -1
            if deposit_col >= 0 and deposit_col < len(self.row_data):
                deposit_val = self.row_data[deposit_col]
                deposit_range = self.parse_range(deposit_val)
                if deposit_range:
                    min_, max_ = deposit_range
                    self.deposit_widget.set_values(min_, max_, [])
            
            rent_col = self.headers.index("월세") if "월세" in self.headers else -1
            if rent_col >= 0 and rent_col < len(self.row_data):
                rent_val = self.row_data[rent_col]
                rent_range = self.parse_range(rent_val)
                if rent_range:
                    min_, max_ = rent_range
                    self.rent_widget.set_values(min_, max_, [])
            
            pyeong_col = self.headers.index("평수") if "평수" in self.headers else -1
            if pyeong_col >= 0 and pyeong_col < len(self.row_data):
                pyeong_val = self.row_data[pyeong_col]
                pyeong_range = self.parse_range(pyeong_val)
                if pyeong_range:
                    min_, max_ = pyeong_range
                    self.pyeong_widget.set_values(min_, max_, [])
                
            # 계약금 등 나머지 필드
            premium_col = self.headers.index("권리금") if "권리금" in self.headers else -1
            if premium_col >= 0 and premium_col < len(self.row_data):
                premium_val = self.row_data[premium_col]
                self.right_kwoligi_line.setText(str(premium_val))
                
            upjong_col = self.headers.index("업종") if "업종" in self.headers else -1
            if upjong_col >= 0 and upjong_col < len(self.row_data):
                upjong_val = self.row_data[upjong_col]
                self.right_upjong_line.setText(str(upjong_val))
                
            contact_col = self.headers.index("연락처") if "연락처" in self.headers else -1
            if contact_col >= 0 and contact_col < len(self.row_data):
                contact_val = self.row_data[contact_col]
                self.right_contact_line.setText(str(contact_val))
                
            silbw_col = self.headers.index("실보증금/월세") if "실보증금/월세" in self.headers else -1
            if silbw_col >= 0 and silbw_col < len(self.row_data):
                silbw_val = self.row_data[silbw_col]
                self.right_silbw_line.setText(str(silbw_val))
            
            # 메모 파싱
            memo_col = self.headers.index("메모") if "메모" in self.headers else -1
            if memo_col >= 0 and memo_col < len(self.row_data):
                memo_val = self.row_data[memo_col]
                if memo_val:
                    self.load_memos_from_str(memo_val)
        except Exception as ex:
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.warning(self, "필드 파싱 오류", f"데이터 파싱 중 오류:\n{ex}")

    def parse_range(self, range_str: str):
        """
        문자열로 된 범위 표현을 파싱하여 (min, max) 튜플로 반환합니다.
        예: "100~200" -> (100, 200)
            "100" -> (100, 100)
        """
        range_str = (range_str or "").strip()
        if "~" in range_str:
            s, e = range_str.split("~", 1)
            try:
                return (int(s.strip()), int(e.strip()))
            except ValueError:
                return (0, 0)
        else:
            try:
                val = int(range_str) if range_str else 0
                return (val, val)
            except ValueError:
                return (0, 0)

    # 층 버튼 상태를 floor_val 문자열 기반으로 초기화하는 메서드 추가
    def _init_floor_buttons_from_value(self, floor_val):
        """
        전달된 floor_val 문자열에서 층 정보를 추출하여 UI 버튼 상태 설정
        
        예시:
        - "1층" -> 1층 버튼 선택
        - "2층이상" -> 2층이상 버튼 선택
        - "3~5층" -> 커스텀 범위 설정
        - "탑층+1층" -> 탑층과 1층 버튼 모두 선택
        - "1~999층" -> 1층과 2층이상 버튼 모두 선택
        - "전체층" -> 지하층, 1층, 2층이상 버튼 모두 선택
        - "-999~999층" 또는 "-999층~999층" -> 전체층으로 처리하여 지하층, 1층, 2층이상 버튼 모두 선택
        """
        # 모든 층 버튼 초기화 (해제)
        for btn in self.floor_buttons:
            btn.setChecked(False)
            
        # 커스텀 범위 초기화
        self.custom_floor_range = []
        
        # 층 값이 비어있으면 처리하지 않음
        if not floor_val:
            return
            
        # 탑층 포함 여부 확인
        is_top_floor = "탑층" in floor_val
        
        # 특별 케이스: "전체층"은 지하층, 1층, 2층이상 버튼 모두 선택
        if "전체층" in floor_val:
            selected_btn_names = ["지하층", "1층", "2층이상"]
            if is_top_floor:
                selected_btn_names.append("탑층")
                
            # 버튼 상태 설정
            for btn_name in selected_btn_names:
                for btn in self.floor_buttons:
                    if btn.text() == btn_name:
                        btn.setChecked(True)
                        break
                
            # saved_conditions 업데이트
            self.saved_conditions["floors"] = {
                "selected_buttons": selected_btn_names,
                "custom_floor_range": []
            }
            
            # 라벨 업데이트
            self.update_floor_label()
            return
        
        # 특별 케이스: "-999~999층" 또는 "-999층~999층"은 전체층으로 처리
        if "-999" in floor_val and "999" in floor_val:
            selected_btn_names = ["지하층", "1층", "2층이상"]
            if is_top_floor:
                selected_btn_names.append("탑층")
                
            # 버튼 상태 설정
            for btn_name in selected_btn_names:
                for btn in self.floor_buttons:
                    if btn.text() == btn_name:
                        btn.setChecked(True)
                        break
                
            # saved_conditions 업데이트
            self.saved_conditions["floors"] = {
                "selected_buttons": selected_btn_names,
                "custom_floor_range": []
            }
            
            # 라벨 업데이트
            self.update_floor_label()
            return
        
        # 복합 선택 처리 ("+", "," 등의 구분자로 나뉜 경우)
        parts = floor_val.replace("+", ",").split(",")
        selected_btn_names = []
        
        # 특별 케이스: "1~999층"은 1층과 2층이상 버튼 모두 선택
        if "1~999층" in floor_val:
            selected_btn_names.extend(["1층", "2층이상"])
        else:
            for part in parts:
                part = part.strip()
                
                # 층 버튼 선택 처리
                if part == "1층":
                    selected_btn_names.append("1층")
                elif part == "2층이상" or part == "2층 이상":
                    selected_btn_names.append("2층이상")
                elif part == "지하층":
                    selected_btn_names.append("지하층")
                elif part == "탑층":
                    selected_btn_names.append("탑층")
                elif "~" in part:
                    # 커스텀 범위 설정 (예: 3~5층)
                    try:
                        range_part = part.replace("층", "")
                        start, end = range_part.split("~")
                        start = start.strip()
                        end = end.strip()
                        
                        # 1~999층은 특별 케이스로 이미 처리됨
                        if start == "1" and end == "999":
                            selected_btn_names.extend(["1층", "2층이상"])
                        elif start.isdigit() and end.isdigit():
                            self.custom_floor_range = [f"{start}층", f"{end}층"]
                    except:
                        pass
        
        # 버튼 상태 설정
        for btn_name in selected_btn_names:
            for btn in self.floor_buttons:
                if btn.text() == btn_name:
                    btn.setChecked(True)
                    break
        
        # saved_conditions 업데이트
        self.saved_conditions["floors"] = {
            "selected_buttons": selected_btn_names,
            "custom_floor_range": self.custom_floor_range
        }
        
        # 라벨 업데이트
        self.update_floor_label()

    def collect_floor_info_from_ui(self):
        """
        원하는 동작:
        - 여러 버튼(지하층, 1층, 2층이상)을 합집합으로 계산 (floor_min, floor_max)
        - '탑층' 버튼은 is_top = True 만 세팅 (floor_min/floor_max에는 영향 안 줌)
        - 만약 아무 버튼도 안 누르고 탑층만 있으면 => (0,0,is_top=1)
        - 만약 '1층' + '탑층' => (1,1,is_top=1)
        - 만약 '1층' + '2층이상' + '탑층' => (1,999,is_top=1)
        - 커스텀도 합집합 (예: 3층~5층).
        """

        # 탑층은 아래 button_map에는 넣지 않고, 따로 처리
        button_map = {
            "지하층":   (-999, -1),
            "1층":      (1, 1),
            "2층이상":  (2, 999),
        }

        # 1) 선택된 버튼
        all_checked_btns = []
        for fb in self.floor_buttons:
            if fb.isChecked():
                all_checked_btns.append(fb.text())

        # 2) 선택된 층 범위와 탑층 여부 추출
        is_top_floor = False
        floor_ranges = []

        for btn_text in all_checked_btns:
            if btn_text == "탑층":
                is_top_floor = True
            elif btn_text in button_map:
                floor_ranges.append(button_map[btn_text])

        # 3) 커스텀 층 범위 추가
        if len(self.custom_floor_range) == 2:
            start_str, end_str = self.custom_floor_range
            try:
                start_val = int(start_str.replace("층", "").strip())
                end_val = int(end_str.replace("층", "").strip())
                floor_ranges.append((start_val, end_val))
            except ValueError:
                # 숫자 변환 실패시 무시
                pass

        # 4) 정보 저장 
        # 필요한 정보를 saved_conditions에 저장
        self.saved_conditions["floors"] = {
            "selected_buttons": all_checked_btns,
            "custom_floor_range": self.custom_floor_range
        }

        # 5) floor_min, floor_max 계산
        if not floor_ranges:
            # 아무 범위도 없으면 (0,0) 반환  
            return (0, 0, is_top_floor)
        
        # 합집합 계산
        floor_min = min(r[0] for r in floor_ranges)
        floor_max = max(r[1] for r in floor_ranges)
        
        return (floor_min, floor_max, is_top_floor)

    def on_dong_select_popup(self):
        """동 선택 다이얼로그를 띄워 동 선택"""
        dlg = DongSelectDialog(self.district_data, self)
        
        # saved_conditions["dongs"]["selected"]가 리스트인지 딕셔너리인지 확인하고 처리
        selected_dongs = self.saved_conditions["dongs"]["selected"]
        
        # 동 선택 다이얼로그에 현재 선택된 동 정보 전달
        dlg.set_selected_dongs(selected_dongs)
        
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            selected = dlg.get_selected_dongs()
            self.saved_conditions["dongs"]["selected"] = selected
            self.saved_conditions["dongs"]["all_area"] = False
            self.update_dong_label(selected)

    def on_map_select(self):
        """
        지도 선택 다이얼로그 열기
        """
        prev_rects = self.saved_conditions.get("map_rectangles", [])
        dlg = MapSelectDialog(self, initial_rectangles=prev_rects)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.saved_conditions["map_rectangles"] = dlg.rectangles
            self.update_dong_label(self.saved_conditions["dongs"]["selected"])

    def update_dong_label(self, selected):
        lines = []
        tooltip_lines = []
        total_gu_count = len(self.district_data.keys())
        selected_gu_count = 0
        all_gu_fully_selected = True

        # selected가 리스트인 경우(dong_list), 구별로 분류하여 딕셔너리로 변환
        if isinstance(selected, list):
            selected_dict = {}
            for dong in selected:
                gu = self.find_which_gu(dong)
                if gu not in selected_dict:
                    selected_dict[gu] = []
                selected_dict[gu].append(dong)
            selected = selected_dict

        # 이제 selected는 딕셔너리 형태로 처리
        for gu, dong_list_in_gu in self.district_data.items():
            sel_dongs = selected.get(gu, [])
            if not sel_dongs:
                all_gu_fully_selected = False
                continue
            selected_gu_count += 1

            if len(sel_dongs) == len(dong_list_in_gu):
                lines.append(f"{gu}(전체)")
                tooltip_lines.append(f"{gu}: {', '.join(sel_dongs)}")
            else:
                lines.append(f"{gu}({len(sel_dongs)})")
                tooltip_lines.append(f"{gu}: {', '.join(sel_dongs)}")
                all_gu_fully_selected = False

        rects = self.saved_conditions.get("map_rectangles", [])
        rect_count = len(rects)
        if rect_count > 0:
            lines.append(f"지도({rect_count})")
            for idx, arr in enumerate(rects):
                if not isinstance(arr, list) or len(arr) != 4:
                    tooltip_lines.append(f"지도{idx + 1}: ??? (invalid array)")
                    continue
                tooltip_lines.append(f"지도{idx + 1}: {arr}")

        if selected_gu_count == 0 and rect_count == 0:
            if self.saved_conditions["dongs"].get("all_area", False):
                self.selected_dongs_label.setText("전지역")
                self.selected_dongs_label.setToolTip("")
            else:
                self.selected_dongs_label.setText("")
                self.selected_dongs_label.setToolTip("")
            return

        if selected_gu_count == total_gu_count and all_gu_fully_selected and rect_count == 0:
            self.selected_dongs_label.setText("전지역")
            self.selected_dongs_label.setToolTip("")
            return

        short_text = ", ".join(lines)
        self.selected_dongs_label.setText(short_text)
        self.selected_dongs_label.setToolTip("\n".join(tooltip_lines))

    def update_floor_label(self):
        """
        층 라벨 업데이트
        """
        selected_floors = [fb.text() for fb in self.floor_buttons if fb.isChecked()]
        if self.custom_floor_range:
            selected_floors.append("-".join(self.custom_floor_range))
        if not selected_floors:
            self.floor_range_label.setText("")
        else:
            self.floor_range_label.setText(", ".join(selected_floors))

    def on_add_memo(self):
        dlg = MemoDialog(self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            full_text = dlg.get_memo_text()
            if not full_text:
                QtWidgets.QMessageBox.warning(self, "메모 없음", "메모를 입력해주세요.")
                return
            current_date = QtCore.QDate.currentDate().toString(QtCore.Qt.ISODate)
            self.add_memo_to_table(current_date, full_text)

    def on_memo_selection_changed(self):
        if self.current_memo_row is not None:
            self.memo_data[self.current_memo_row] = self.memo_detail.toPlainText()
            full_text = self.memo_data[self.current_memo_row]
            first_line = full_text.split('\n', 1)[0]
            if len(first_line) > 20:
                first_line = first_line[:20] + "..."
            self.memo_table.setItem(self.current_memo_row, 1, QtWidgets.QTableWidgetItem(first_line))

        selected_items = self.memo_table.selectedItems()
        if not selected_items:
            self.memo_detail.clear()
            self.current_memo_row = None
            return
        row = selected_items[0].row()
        self.current_memo_row = row
        full_text = self.memo_data.get(row, "")
        self.memo_detail.setPlainText(full_text)

    def on_memo_detail_changed(self):
        if self.current_memo_row is not None:
            new_text = self.memo_detail.toPlainText()
            self.memo_data[self.current_memo_row] = new_text
            first_line = new_text.split('\n', 1)[0]
            if len(first_line) > 20:
                first_line = first_line[:20] + "..."
            self.memo_table.setItem(self.current_memo_row, 1, QtWidgets.QTableWidgetItem(first_line))

    def on_floor_custom_clicked(self):
        """
        '층 지정' 버튼 클릭:
        (1) FloorRangeDialog 열기
        (2) 이미 custom_floor_range가 있으면, 그 값으로 콤보박스 미리 셋팅
        """
        from dialogs import FloorRangeDialog
        dlg = FloorRangeDialog(self)

        # (A) 혹시 이전에 self.custom_floor_range = ["3층","5층"] 식으로 저장돼 있다면
        #     콤보 박스에 미리 셋팅
        if len(self.custom_floor_range) == 2:
            start_str, end_str = self.custom_floor_range
            # 만약 "999층"이나 "3층" 같은 형태라면 그대로 setCurrentText 가능
            dlg.start_combo.setCurrentText(start_str)
            dlg.end_combo.setCurrentText(end_str)
        # 혹은 parse_floor_range()로 실제 숫자(floor_min,floor_max)를 가져와
        # start_combo/end_combo에 index를 맞추는 방법도 가능.

        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            # 사용자가 확인을 눌렀을 때
            start_floor, end_floor = dlg.get_floor_range()   # 예: ("3층", "5층") or ("999층","999층")
            self.custom_floor_range = [start_floor, end_floor]
            self.update_floor_label()

    def on_reset_conditions(self):
        self.deposit_widget.reset_all()
        self.rent_widget.reset_all()
        self.pyeong_widget.reset_all()

        self.saved_conditions["dongs"]["selected"] = {}
        self.saved_conditions["dongs"]["all_area"] = False
        self.update_dong_label({})

        for fb in self.floor_buttons:
            fb.setChecked(False)
        self.custom_floor_range = []
        self.saved_conditions["floors"] = {"selected_buttons": [], "custom_floor_range": []}
        self.update_floor_label()

    def on_ok(self):
        # 1) 위젯에서 min~max
        deposit_data = self.deposit_widget.get_selected_values()
        rent_data    = self.rent_widget.get_selected_values()
        pyeong_data  = self.pyeong_widget.get_selected_values()

        deposit_str = (
            f"{deposit_data['min_value']}~{deposit_data['max_value']}"
            if deposit_data['max_value'] > deposit_data['min_value']
            else str(deposit_data['min_value'])
        )
        rent_str = (
            f"{rent_data['min_value']}~{rent_data['max_value']}"
            if rent_data['max_value'] > rent_data['min_value']
            else str(rent_data['min_value'])
        )
        pyeong_str = (
            f"{pyeong_data['min_value']}~{pyeong_data['max_value']}"
            if pyeong_data['max_value'] > pyeong_data['min_value']
            else str(pyeong_data['min_value'])
        )

        # 2) 합집합 계산
        floor_min, floor_max, is_top_floor = self.collect_floor_info_from_ui()
        floor_str = self.build_floor_str(floor_min, floor_max, is_top_floor)

        # 3) 지역 JSON
        selected_dongs = []
        selected_gu = []
        
        # 저장된 동 목록이 리스트인지 딕셔너리인지 확인하고 처리
        dongs_selected = self.saved_conditions["dongs"]["selected"]
        if isinstance(dongs_selected, list):
            # 리스트인 경우 그대로 사용
            selected_dongs = dongs_selected
            # 구 목록은 중복 없이 추출
            for dong in selected_dongs:
                gu = self.find_which_gu(dong)
                if gu not in selected_gu:
                    selected_gu.append(gu)
        else:
            # 딕셔너리인 경우 items() 사용
            for gu, dlist in dongs_selected.items():
                selected_dongs.extend(dlist)
                selected_gu.append(gu)

        rects = self.saved_conditions.get("map_rectangles", [])
        region_obj = {
            "gu_list": selected_gu,
            "dong_list": selected_dongs,
            "rectangles": rects
        }
        region_json_str = json.dumps(region_obj, ensure_ascii=False)

        # 4) 메모
        memo_json_str, last_contact_str = self.save_memos_to_str()

        # 5) 나머지
        premium_str  = self.right_kwoligi_line.text().strip()
        biz_type_str = self.right_upjong_line.text().strip()
        contact_str  = self.right_contact_line.text().strip()
        real_dep_mon = self.right_silbw_line.text().strip()

        # 6) 최종 row_data
        final_values = []
        for i, header in enumerate(self.headers):
            if header == "지역":
                final_values.append(region_json_str)
            elif header == "보증금":
                final_values.append(deposit_str)
            elif header == "월세":
                final_values.append(rent_str)
            elif header == "평수":
                final_values.append(pyeong_str)
            elif header == "층":
                final_values.append(floor_str)
            elif header == "메모":
                final_values.append(memo_json_str)
            elif header == "최근연락날짜":
                final_values.append(last_contact_str)
            elif header == "권리금":
                final_values.append(premium_str)
            elif header == "업종":
                final_values.append(biz_type_str)
            elif header == "연락처":
                final_values.append(contact_str)
            elif header == "실보증금/월세":
                final_values.append(real_dep_mon)
            elif header == "담당자":
                final_values.append(self.manager)
            else:
                # 기타
                val_orig = self.row_data[i] if i < len(self.row_data) else ""
                final_values.append(val_orig)

        # 7) 필수값 체크
        required_headers = ["지역","층","보증금","월세","평수"]
        for req_h in required_headers:
            if req_h in self.headers:
                idx = self.headers.index(req_h)
                if not final_values[idx].strip():
                    QtWidgets.QMessageBox.warning(self, "값 누락", f"{req_h} 값을 설정해주세요.")
                    return

        self.row_data = final_values

        # 8) DB 반영
        # parent = self.parent()
        # if parent and hasattr(parent, 'update_customer_sheet'):
        #     parent.update_customer_sheet(self.row_data, self.edit_row, self.id, self.manager)

        self.accept()

    def get_row_data(self):
        return self.row_data

    def is_delete_requested(self):
        return self.delete_requested

    def find_which_gu(self, dong):
        """
        dong: 동 이름(문자열).
        - 만약 dong이 숫자(좌표)나 JSON 구조 등이면 '기타' 처리
        """
        # 1) 만약 JSON처럼 보이면 '기타' 바로 리턴
        if dong.startswith("{") and dong.endswith("}"):
            print(f"[WARN] find_which_gu() - JSON or dict-like? => '{dong}' => skip")
            return "기타"

        # 2) 만약 숫자 형태('127.3', '36.35')면 '기타'
        #    => 간단히 try float 변환 가능
        try:
            float_val = float(dong)
            # 변환 성공 => dong은 실제 동이 아니라 숫자
            print(f"[WARN] find_which_gu() - numeric? => '{dong}' => skip")
            return "기타"
        except ValueError:
            pass  # 아니면 다음 단계로

        # 3) 실제 district_data 매핑
        for gu, dongs in self.district_data.items():
            if dong in dongs:
                return gu

        print(f"[WARN] find_which_gu() 매칭 실패: '{dong}' => district_data에 없음!")
        return "기타" 

    def add_memo_to_table(self, date_str, full_text):
        row_count = self.memo_table.rowCount()
        self.memo_table.insertRow(row_count)
        self.memo_table.setItem(row_count, 0, QtWidgets.QTableWidgetItem(date_str))
        first_line = full_text.split('\n', 1)[0]
        if len(first_line) > 20:
            first_line = first_line[:20] + "..."
        self.memo_table.setItem(row_count, 1, QtWidgets.QTableWidgetItem(first_line))
        self.memo_data[row_count] = full_text


    def load_memos_from_str(self, memo_str: str):
        """
        memo_str는 DB에서 가져온 memo_json(문자열).
        예: '[{"date":"고정메모","text":"사장님이 2층 희망"}, {"date":"2024-12-28","text":"전화안받음"}]'
        """
        self.memo_table.setRowCount(0)
        self.memo_data = {}

        if not memo_str:
            memo_str = "[]"

        try:
            memos = json.loads(memo_str)
        except json.JSONDecodeError:
            memos = []


        self.memo_table.insertRow(0)
        self.memo_data[0] = ""
        self.memo_table.setItem(0, 0, QtWidgets.QTableWidgetItem("고정메모"))
        self.memo_table.setItem(0, 1, QtWidgets.QTableWidgetItem(""))

        # 고정메모 객체 가져오기
        fixed_obj = None
        normal_objs= []
        for mo in memos:
            if mo.get("date") == "고정메모":
                fixed_obj = mo
            else:
                normal_objs.append(mo)

        # 고정메모가 있다면 0행 세팅
        if fixed_obj:
            self.memo_data[0] = fixed_obj.get("text","")
            self.memo_table.setItem(0,1, QtWidgets.QTableWidgetItem(self.memo_data[0]))

        # (B) 일반메모(1행부터)
        for nm in normal_objs:
            idx = self.memo_table.rowCount()
            self.memo_table.insertRow(idx)
            d_ = nm.get("date","")
            t_ = nm.get("text","")
            self.memo_data[idx] = t_
            self.memo_table.setItem(idx, 0, QtWidgets.QTableWidgetItem(d_))

            # 요약
            first_line = t_.split('\n',1)[0]
            if len(first_line)>20:
                first_line = first_line[:20]+"..."
            self.memo_table.setItem(idx, 1, QtWidgets.QTableWidgetItem(first_line))
    def save_memos_to_str(self):
        """
        self.memo_table: 첫 열(0열)은 날짜(date), 둘째 열(1열)은 메모 요약.
        self.memo_data[row] = 실제 전체 메모 문자열(여러 줄 가능).
        
        이 함수를 호출하면:
        1) 메모 테이블 전체 row를 돌면서, 
            date = YYYY-MM-DD 형태면 QDate 변환 → max_date 찾기
        2) memo_list 배열에 { "date":..., "text":... } 형태로 담아서 JSON 문자열 생성
        3) memo_json_str 와 가장 최근 날짜( last_contact_str ) 반환
        """
        row_count = self.memo_table.rowCount()
        if row_count < 1:
            # 테이블에 아무 메모가 없으면
            return "[]", ""  # 빈 JSON, 빈 날짜

        memo_list = []
        max_date = None  # 가장 최근 날짜(QDate)

        for row in range(row_count):
            date_item = self.memo_table.item(row, 0)    # 날짜 셀
            date_str = date_item.text().strip() if date_item else ""

            full_text = self.memo_data.get(row, "")     # 실제 메모(여러 줄)

            # "고정메모" 행이라면, date="고정메모"
            # 일반 행이라면 date="2024-12-27" 등
            if date_str.lower() == "고정메모":
                # 원하는 정책에 따라, 
                # "고정메모"도 memo_list에 넣거나 / 스킵할 수도 있음
                memo_list.append({
                    "date": "고정메모",
                    "text": full_text
                })
                continue

            # 날짜가 YYYY-MM-DD 형식인지 확인
            qd = QtCore.QDate.fromString(date_str, "yyyy-MM-dd")
            if qd.isValid():
                if max_date is None or qd > max_date:
                    max_date = qd

            memo_list.append({
                "date": date_str,
                "text": full_text
            })

        memo_json_str = json.dumps(memo_list, ensure_ascii=False)
        
        # max_date -> "YYYY-MM-DD" 문자열
        if max_date:
            last_contact_str = max_date.toString("yyyy-MM-dd")
        else:
            last_contact_str = ""

        return memo_json_str, last_contact_str

    def on_all_area_selected(self):
        self.saved_conditions["dongs"]["all_area"] = True
        self.saved_conditions["dongs"]["selected"] = {}
        self.update_dong_label(self.saved_conditions["dongs"]["selected"])

    def get_saved_conditions(self):
        return self.saved_conditions 

    def build_floor_str(self, fmin, fmax, is_top):
        """
        층 정보를 문자열로 변환
        
        특별 케이스:
        - 1층 + 2층이상 선택 시 -> "1~999층"으로 표시
        - 지하층 + 1층 + 2층이상 선택 시 -> "전체층"으로 표시
        - 그 외에는 선택된 버튼들을 콤마로 구분하여 표시
        """
        # 선택된 버튼들 확인
        selected_floor_buttons = [fb.text() for fb in self.floor_buttons if fb.isChecked()]
        
        # 특별 케이스 처리
        has_basement = "지하층" in selected_floor_buttons
        has_first_floor = "1층" in selected_floor_buttons
        has_above_second = "2층이상" in selected_floor_buttons
        has_top_floor = "탑층" in selected_floor_buttons
        
        # 지하층 + 1층 + 2층이상 = 전체층
        if has_basement and has_first_floor and has_above_second:
            result = "전체층"
            if has_top_floor:
                result += ", 탑층"
            return result
            
        # 1층 + 2층이상 = 1~999층
        if has_first_floor and has_above_second and not has_basement:
            result = "1~999층"
            if has_top_floor:
                result += ", 탑층"
            return result
            
        # 일반 케이스 - 선택된 버튼들을 표시
        floor_parts = []
        
        # 각 층 옵션 처리
        if has_basement:
            floor_parts.append("지하층")
            
        if has_first_floor:
            floor_parts.append("1층")
            
        if has_above_second:
            floor_parts.append("2층이상")
        
        # 커스텀 층 범위 추가
        if len(self.custom_floor_range) == 2:
            start_str, end_str = self.custom_floor_range
            try:
                start_val = int(start_str.replace("층", "").strip())
                end_val = int(end_str.replace("층", "").strip())
                if start_val == end_val:
                    floor_parts.append(f"{start_val}층")
                else:
                    floor_parts.append(f"{start_val}~{end_val}층")
            except:
                pass
                
        # 탑층 처리
        if has_top_floor:
            floor_parts.append("탑층")
            
        # 모든 층 옵션을 콤마로 연결
        result = ", ".join(floor_parts)
        
        # 아무것도 선택하지 않았을 경우
        if not result:
            return ""
            
        return result

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
        self.biz_list = biz_list
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

            # "추천예정" 버튼 -> 누르면 memo_edit에 "추천예정" 자동 입력
            btn_predefine = QtWidgets.QPushButton("추천예정", row_widget)
            btn_predefine.clicked.connect(
                lambda checked, le=memo_edit: le.setText("추천예정")
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