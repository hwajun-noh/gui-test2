# dialogs/dong_select_dialog.py

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox, 
    QCheckBox, QScrollArea, QWidget, QGridLayout
)

class MultiGuDongDialog(QtWidgets.QDialog):
    """
    (예시) 구/동 선택 창
    - 구(GroupBox)별로 동 체크박스 나열
    - "전체선택" 버튼
    - 확인/취소
    - OK 시 => dict 형태 반환( { "서구": {"갈마동","가장동"}, ... } )
    """

    def __init__(self, real_dong_map: dict, selected_dongs_by_gu: dict, parent=None):
        """
        real_dong_map: { "동구": ["가양동","대동",...], "서구":[...], ... }
        selected_dongs_by_gu: { "동구": set(["가양동"]), ... }  # 현재 선택된 상태
        또는 리스트 형식: ["가양동", "대동", ...]
        """
        super().__init__(parent)
        self.setWindowTitle("구/동 선택")
        self.resize(600, 400)

        # 현재 선택 상태를 복사
        self.temp_dict = {}
        
        # selected_dongs_by_gu가 딕셔너리인 경우
        if isinstance(selected_dongs_by_gu, dict):
            for g, ds in selected_dongs_by_gu.items():
                self.temp_dict[g] = set(ds)
        # selected_dongs_by_gu가 리스트인 경우
        elif isinstance(selected_dongs_by_gu, list):
            # 각 동이 어느 구에 속하는지 확인하여 temp_dict에 추가
            for dong in selected_dongs_by_gu:
                for gu, dong_list in real_dong_map.items():
                    if dong in dong_list:
                        if gu not in self.temp_dict:
                            self.temp_dict[gu] = set()
                        self.temp_dict[gu].add(dong)
                        break

        main_layout = QtWidgets.QVBoxLayout(self)

        # 필요한 구(區) 목록 - 임의 정렬 대신 지정된 순서로 표시
        # 지정된 순서: 서구, 중구, 유성구, 동구, 대덕구
        custom_order = ["서구", "중구", "유성구", "동구", "대덕구"]
        
        # 사용 가능한 구 목록 가져오기
        available_gus = list(real_dong_map.keys())
        
        # 지정된 순서대로 구 정렬하되, 나머지는 뒤에 알파벳 순으로 추가
        gu_names = []
        
        # 먼저 지정된 순서대로 추가
        for gu in custom_order:
            if gu in available_gus:
                gu_names.append(gu)
                
        # 나머지 구를 알파벳 순으로 추가
        for gu in sorted(available_gus):
            if gu not in gu_names:
                gu_names.append(gu)

        self.checkboxes = {}  # { "서구": { "갈마동": QCheckBox, ... }, ... }

        for gu in gu_names:
            group = QtWidgets.QGroupBox(gu)
            vlay = QtWidgets.QVBoxLayout(group)

            # (1) "전체선택" 버튼
            btn_select_all = QtWidgets.QPushButton(f"{gu} 전체선택")
            btn_select_all.clicked.connect(lambda _, g=gu: self.on_select_all_in_gu(g))
            vlay.addWidget(btn_select_all)

            # (2) 스크롤 영역
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setContentsMargins(0, 0, 0, 0)

            # (3) 스크롤 내부 컨테이너 + GridLayout
            container = QtWidgets.QWidget()
            grid = QtWidgets.QGridLayout(container)
            grid.setContentsMargins(5, 0, 5, 0)
            grid.setVerticalSpacing(2)
            grid.setHorizontalSpacing(5)

            # (4) dong_list
            dong_list = real_dong_map.get(gu, [])
            dong_list_sorted = sorted(dong_list)

            c_map = {}  # {"동이름": 체크박스객체, ...}
            for i, d_ in enumerate(dong_list_sorted):
                row = i // 4
                col = i % 4
                cb = QtWidgets.QCheckBox(d_)
                if d_ in self.temp_dict.get(gu, set()):
                    cb.setChecked(True)
                grid.addWidget(cb, row, col)
                c_map[d_] = cb

            remainder = len(dong_list_sorted) % 4
            if remainder != 0:
                last_row = len(dong_list_sorted) // 4
                for col in range(remainder, 4):
                    placeholder = QtWidgets.QLabel("")
                    grid.addWidget(placeholder, last_row, col)

            # (5) scroll container
            self.checkboxes[gu] = c_map
            container.setLayout(grid)
            scroll.setWidget(container)
            vlay.addWidget(scroll)

            main_layout.addWidget(group)

        # (6) 확인/취소 버튼
        btn_layout = QtWidgets.QHBoxLayout()
        btn_reset = QtWidgets.QPushButton("초기화")
        btn_reset.clicked.connect(self.on_reset_clicked)
        btn_layout.addWidget(btn_reset)

        btn_ok = QtWidgets.QPushButton("확인")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QtWidgets.QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        main_layout.addLayout(btn_layout)

    def on_select_all_in_gu(self, gu):
        if gu not in self.checkboxes:
            return
        for dong_name, cb in self.checkboxes[gu].items():
            cb.setChecked(True)
            
    def on_reset_clicked(self):
        for gu, c_map in self.checkboxes.items():
            for d_, cb in c_map.items():
                cb.setChecked(False)

    def get_selected_dongs_by_gu(self):
        result = {}
        for gu, c_map in self.checkboxes.items():
            selected = set()
            for d_, cb in c_map.items():
                if cb.isChecked():
                    selected.add(d_)
            if selected:
                # Use list instead of set for JSON compatibility if needed elsewhere
                result[gu] = list(selected) 
        return result


class DongSelectDialog(QtWidgets.QDialog):
    """
    구/동 선택 Dialog.
    """
    def __init__(self, district_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("동 선택")
        self.district_data = district_data

        self.resize(1000, 600)

        layout = QtWidgets.QVBoxLayout()

        # "대전 전지역" 선택 버튼
        all_city_btn = QtWidgets.QPushButton("대전 전지역")
        all_city_btn.setStyleSheet("font-size:16px; padding:8px;")
        all_city_btn.clicked.connect(self.select_all_city)
        layout.addWidget(all_city_btn, alignment=Qt.AlignLeft)

        self.district_tab = QtWidgets.QTabWidget()
        self.edits = {}

        # 구 순서 지정 - "서구, 중구, 유성구, 동구, 대덕구" 순
        custom_order = ["서구", "중구", "유성구", "동구", "대덕구"]
        
        # 1) 먼저 지정된 순서대로 처리
        for gu in custom_order:
            if gu in self.district_data:
                dongs = self.district_data[gu]
                
                # (1) 스크롤 영역 + 내부 위젯
                scroll = QtWidgets.QScrollArea()
                scroll.setWidgetResizable(True)

                inner_widget = QtWidgets.QWidget()
                vbox = QtWidgets.QVBoxLayout(inner_widget)

                # (2) "구 전체" 버튼
                select_all_gu_btn = QtWidgets.QPushButton(f"{gu} 전체")
                select_all_gu_btn.setStyleSheet("font-size:14px; padding:6px;")
                select_all_gu_btn.clicked.connect(lambda _, g=gu: self.on_select_all_gu(g))
                vbox.addWidget(select_all_gu_btn, alignment=Qt.AlignLeft)

                # (3) 동 버튼을 5열로 배치하기 위해 GridLayout 생성
                grid = QtWidgets.QGridLayout()
                grid.setContentsMargins(0, 0, 0, 0)
                grid.setVerticalSpacing(5)     # 위아래 간격 (원하면 0도 가능)
                grid.setHorizontalSpacing(5)   # 좌우 간격

                # self.edits[gu] = [ (dong_name, QPushButton) ... ]
                self.edits[gu] = []
                cols = 5  # 5열

                for i, dong in enumerate(dongs):
                    row = i // cols
                    col = i % cols

                    btn = QtWidgets.QPushButton(dong)
                    btn.setCheckable(True)
                    btn.setMinimumWidth(120)
                    btn.setFixedHeight(40)
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #ffffff; 
                            border: 1px solid #ccc;
                            border-radius: 4px;
                            padding: 8px;
                            font-size:14px;
                            text-align: left;
                        }
                        QPushButton:checked {
                            background-color: #87CEFA; 
                            font-weight: bold;
                            border: 1px solid #0066cc;
                        }
                    """)
                    self.edits[gu].append((dong, btn))

                    # (4) 그리드에 버튼 배치
                    grid.addWidget(btn, row, col)

                # (4-1) 남은 칸 채우기(동 개수가 5로 나누어떨어지지 않으면)
                remainder = len(dongs) % cols
                if remainder != 0:
                    last_row = len(dongs) // cols
                    for col in range(remainder, cols):
                        placeholder = QtWidgets.QLabel("")
                        grid.addWidget(placeholder, last_row, col)

                # (5) GridLayout을 vbox에 추가 + 스페이서
                vbox.addLayout(grid)
                vbox.addStretch()

                # (6) 스크롤 설정
                inner_widget.setLayout(vbox)
                scroll.setWidget(inner_widget)
                self.district_tab.addTab(scroll, gu)
        
        # 2) 나머지 구(custom_order에 없는 구)가 있다면 알파벳 순으로 처리
        for gu, dongs in sorted(self.district_data.items()):
            if gu not in custom_order:
                # (1) 스크롤 영역 + 내부 위젯
                scroll = QtWidgets.QScrollArea()
                scroll.setWidgetResizable(True)

                inner_widget = QtWidgets.QWidget()
                vbox = QtWidgets.QVBoxLayout(inner_widget)

                # (2) "구 전체" 버튼
                select_all_gu_btn = QtWidgets.QPushButton(f"{gu} 전체")
                select_all_gu_btn.setStyleSheet("font-size:14px; padding:6px;")
                select_all_gu_btn.clicked.connect(lambda _, g=gu: self.on_select_all_gu(g))
                vbox.addWidget(select_all_gu_btn, alignment=Qt.AlignLeft)

                # (3) 동 버튼을 5열로 배치하기 위해 GridLayout 생성
                grid = QtWidgets.QGridLayout()
                grid.setContentsMargins(0, 0, 0, 0)
                grid.setVerticalSpacing(5)     # 위아래 간격 (원하면 0도 가능)
                grid.setHorizontalSpacing(5)   # 좌우 간격

                # self.edits[gu] = [ (dong_name, QPushButton) ... ]
                self.edits[gu] = []
                cols = 5  # 5열

                for i, dong in enumerate(dongs):
                    row = i // cols
                    col = i % cols

                    btn = QtWidgets.QPushButton(dong)
                    btn.setCheckable(True)
                    btn.setMinimumWidth(120)
                    btn.setFixedHeight(40)
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #ffffff; 
                            border: 1px solid #ccc;
                            border-radius: 4px;
                            padding: 8px;
                            font-size:14px;
                            text-align: left;
                        }
                        QPushButton:checked {
                            background-color: #87CEFA; 
                            font-weight: bold;
                            border: 1px solid #0066cc;
                        }
                    """)
                    self.edits[gu].append((dong, btn))

                    # (4) 그리드에 버튼 배치
                    grid.addWidget(btn, row, col)

                # (4-1) 남은 칸 채우기(동 개수가 5로 나누어떨어지지 않으면)
                remainder = len(dongs) % cols
                if remainder != 0:
                    last_row = len(dongs) // cols
                    for col in range(remainder, cols):
                        placeholder = QtWidgets.QLabel("")
                        grid.addWidget(placeholder, last_row, col)

                # (5) GridLayout을 vbox에 추가 + 스페이서
                vbox.addLayout(grid)
                vbox.addStretch()

                # (6) 스크롤 설정
                inner_widget.setLayout(vbox)
                scroll.setWidget(inner_widget)
                self.district_tab.addTab(scroll, gu)

        layout.addWidget(self.district_tab)

        # (7) 확인/취소 버튼
        btn_layout = QtWidgets.QHBoxLayout()
        self.ok_btn = QtWidgets.QPushButton("확인")
        self.ok_btn.setStyleSheet("font-size:16px; padding:6px;")
        self.cancel_btn = QtWidgets.QPushButton("취소")
        self.cancel_btn.setStyleSheet("font-size:16px; padding:6px;")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def set_selected_dongs(self, selected):
        """
        selected: { "서구":["갈마동","가장동"], "동구":["가양동"], ... }
        또는 리스트 형식: ["갈마동", "가장동", "가양동", ...]
        -> 각 구 탭의 버튼 상태를 자동 체크
        """
        # selected가 리스트인 경우 처리
        if isinstance(selected, list):
            # 모든 동을 순회하면서 selected 리스트에 있는지 확인
            for gu, dong_btn_list in self.edits.items():
                for (dong_name, btn) in dong_btn_list:
                    btn.setChecked(dong_name in selected)
        else:
            # 기존 딕셔너리 형식 처리
            for gu, dong_btn_list in self.edits.items():
                sel_dongs = selected.get(gu, [])
                for (dong_name, btn) in dong_btn_list:
                    btn.setChecked(dong_name in sel_dongs)

    def on_select_all_gu(self, gu):
        """
        해당 구(gu)의 모든 동 버튼을 체크 상태로
        """
        for (dong_name, btn) in self.edits[gu]:
            btn.setChecked(True)

    def select_all_city(self):
        """
        모든 구의 모든 동 버튼을 전부 체크
        """
        for gu in self.edits.keys():
            for (dong_name, btn) in self.edits[gu]:
                btn.setChecked(True)

    def get_selected_dongs(self):
        """
        OK 누를 때, 선택된 동만 모아서 {구: [동1,동2,...], ...} 형태로 반환
        """
        selected = {}
        for gu, dong_btn_list in self.edits.items():
            sel = []
            for (dong_name, btn) in dong_btn_list:
                if btn.isChecked():
                    sel.append(dong_name)
            if sel:
                selected[gu] = sel
        return selected
