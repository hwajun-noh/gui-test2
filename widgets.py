# widgets.py
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtCore import Qt, QUrl
import json




class ValueSelectionWidget(QtWidgets.QWidget):
    """
    보증금/월세/평수 등 숫자 범위 선택.
    버튼을 누르면 SpinBox 자동 설정,
    SpinBox를 입력하면 버튼 체크 상태도 업데이트.
    """
    def __init__(self, title, options, parent=None):
        super().__init__(parent)
        self.title = title
        self.options = options

        layout = QtWidgets.QVBoxLayout()

        title_label = QtWidgets.QLabel(self.title)
        title_label.setStyleSheet("font-weight: bold; font-size:16px; padding:8px;")
        layout.addWidget(title_label)

        grid_widget = QtWidgets.QWidget()
        grid_layout = QtWidgets.QGridLayout(grid_widget)
        grid_layout.setSpacing(2)

        self.buttons = []
        self.value_map = []
        btn_style = """
            QPushButton {
                background-color: #ffffff; 
                border: 1px solid #ccc;
                border-radius: 2px;
                padding: 0px;
                margin: 0px;
                font-size: 14px;
            }
            QPushButton:checked {
                background-color: #87CEFA; 
                font-weight: bold;
                border: 1px solid #0066cc;
            }
        """

        cols = 6
        for i, (label, val) in enumerate(self.options):
            btn = QtWidgets.QPushButton(label)
            btn.setCheckable(True)
            btn.setStyleSheet(btn_style)
            btn.setFixedWidth(80)
            btn.setFixedHeight(40)
            r = i // cols
            c = i % cols
            grid_layout.addWidget(btn, r, c)
            self.buttons.append(btn)
            self.value_map.append((btn, val))
            btn.clicked.connect(self.on_button_clicked)

        layout.addWidget(grid_widget)

        spin_layout = QtWidgets.QHBoxLayout()
        spin_layout.setSpacing(20)
        spin_layout.setContentsMargins(5, 0, 0, 0)
        spin_layout.setAlignment(Qt.AlignLeft)

        min_label = QtWidgets.QLabel("최소값:")
        min_label.setStyleSheet("font-size:14px; margin:0px; padding:0px;")
        spin_layout.addWidget(min_label)

        self.min_spin = QtWidgets.QSpinBox()
        self.min_spin.setStyleSheet("font-size:17px;")
        self.min_spin.setRange(0, 99999999)
        self.min_spin.setValue(0)
        self.min_spin.setFixedHeight(40)
        self.min_spin.setFixedWidth(80)
        spin_layout.addWidget(self.min_spin)

        spin_layout.addSpacing(30)

        max_label = QtWidgets.QLabel("최대값:")
        max_label.setStyleSheet("font-size:14px; margin:0px; padding:0px;")
        spin_layout.addWidget(max_label)

        self.max_spin = QtWidgets.QSpinBox()
        self.max_spin.setStyleSheet("font-size:17px;")
        self.max_spin.setRange(0, 99999999)
        self.max_spin.setValue(0)
        self.max_spin.setFixedHeight(40)
        self.max_spin.setFixedWidth(80)
        spin_layout.addWidget(self.max_spin)

        spin_layout.addStretch()

        reset_btn = QtWidgets.QPushButton("초기화")
        reset_btn.setStyleSheet("font-size:14px; margin:0px; padding:0px;")
        reset_btn.setFixedHeight(40)
        reset_btn.setFixedWidth(80)
        reset_btn.clicked.connect(self.reset_all)
        spin_layout.addWidget(reset_btn)

        self.min_spin.editingFinished.connect(self.on_spin_edit_finished)
        self.max_spin.editingFinished.connect(self.on_spin_edit_finished)

        layout.addLayout(spin_layout)

        self.setLayout(layout)

    def reset_all(self):
        for (btn, _) in self.value_map:
            btn.setChecked(False)
        self.min_spin.setValue(0)
        self.max_spin.setValue(0)

    def get_selected_values(self):
        selected_opts = [btn.text() for (btn, val) in self.value_map if btn.isChecked()]
        return {
            "title": self.title,
            "selected_options": selected_opts,
            "min_value": self.min_spin.value(),
            "max_value": self.max_spin.value()
        }

    def set_values(self, min_val, max_val, selected_options):
        self.reset_all()
        self.min_spin.blockSignals(True)
        self.max_spin.blockSignals(True)
        self.min_spin.setValue(min_val)
        self.max_spin.setValue(max_val)
        self.min_spin.blockSignals(False)
        self.max_spin.blockSignals(False)

        text_to_btn = {btn.text(): btn for btn, _ in self.value_map}
        for opt in selected_options:
            if opt in text_to_btn:
                text_to_btn[opt].setChecked(True)
        self.on_spin_edit_finished()

    def on_button_clicked(self):
        selected_values = [val for (btn, val) in self.value_map if btn.isChecked()]
        count = len(selected_values)

        if count == 0:
            # 아무것도 체크 X => 0~0
            self.setSpinRange(0, 0)

        elif count == 1:
            # 단일 버튼 => 0~그 값
            x = selected_values[0]
            self.setSpinRange(0, x)

        else:
            # 여러 버튼 => min~max
            current_min = min(selected_values)
            current_max = max(selected_values)
            self.setSpinRange(current_min, current_max)

    def setSpinRange(self, new_min, new_max):
        self.min_spin.blockSignals(True)
        self.max_spin.blockSignals(True)
        self.min_spin.setValue(new_min)
        self.max_spin.setValue(new_max)
        self.min_spin.blockSignals(False)
        self.max_spin.blockSignals(False)

        # 버튼 체크 상태도 min~max에 맞춤
        self.select_range_buttons(new_min, new_max)

    def on_spin_edit_finished(self):
        """SpinBox 값 변경 시 버튼 체크 상태도 갱신."""
        self.update_buttons_from_spin()

    def update_buttons_from_spin(self):
        min_val = self.min_spin.value()
        max_val = self.max_spin.value()
        if min_val > max_val:
            min_val, max_val = max_val, min_val
            self.min_spin.blockSignals(True)
            self.max_spin.blockSignals(True)
            self.min_spin.setValue(min_val)
            self.max_spin.setValue(max_val)
            self.min_spin.blockSignals(False)
            self.max_spin.blockSignals(False)
        self.select_range_buttons(min_val, max_val)

    def select_range_buttons(self, min_val, max_val):
        for (btn, val) in self.value_map:
            if min_val <= val <= max_val:
                if not btn.isChecked():
                    btn.setChecked(True)
            else:
                if btn.isChecked():
                    btn.setChecked(False)


class MyWebEnginePage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source_id):
        print(f"[JSConsole] {message} (line: {line}, source: {source_id})")



    def parse_init_values(self):
        """
        1) row_data[...] 중 "지역" 칼럼은
        '{"gu_list":["동구"],"dong_list":["가양동","대동"],"rectangles":[...]}' 구조의 JSON string.
        => json.loads() 후, self.saved_conditions["dongs"]["selected"], self.saved_conditions["map_rectangles"] 에 반영.
        2) 그 외 "보증금", "월세", "평수", "층", "권리금", "업종", "연락처", ...
        => 기존 로직대로 UI에 세팅.
        """


        # 0) 혹시 row_data 길이가 headers와 다를 경우 대비
        if not self.row_data or len(self.row_data) != len(self.headers):
            return

        # 1) "지역" => region_json_str 파싱
        if "지역" in self.headers:
            region_idx = self.headers.index("지역")
            region_str = self.row_data[region_idx].strip()  # 예: '{"gu_list":[],"dong_list":[],"rectangles":[]}'
            selected_dict = {}
            rects_list = []

            # (a) JSON 파싱
            try:
                region_obj = json.loads(region_str) if region_str else {}
                # region_obj = { "gu_list":["동구"], "dong_list":["가양동"], "rectangles":[[127.36,...],...] }

                gu_list   = region_obj.get("gu_list", [])
                dong_list = region_obj.get("dong_list", [])
                rects_list= region_obj.get("rectangles", [])

                # (b) self.saved_conditions["map_rectangles"] = rects_list
                self.saved_conditions["map_rectangles"] = rects_list

                # (c) 동 선택을 saved_conditions["dongs"]["selected"] 형식으로 만들어주기
                #     예: dong_list=["가양동","대동"] => {"동구":["가양동","대동"]} 등등
                #     이때 find_which_gu()는 dong 이름으로 구를 찾아주는 함수
                #     단, gu_list가 여러개면 "전역" 처리가 필요할 수도 있음
                #     여기서는 dong_list 기반으로만 편의상 예시
                for dong in dong_list:
                    gu_ = self.find_which_gu(dong)  # dong→어느 구?
                    if gu_ not in selected_dict:
                        selected_dict[gu_] = []
                    selected_dict[gu_].append(dong)

                # 만약 gu_list가 유의미하게 있다면,
                # "구 전체" 선택 처리를 추가하고 싶을 수도 있음.
                # 예) if gu_list: ... 

            except (json.JSONDecodeError, TypeError, ValueError):
                # 만약 JSON 파싱 실패하면, region_str가 "가양동,대동" 식으로 들어있을 가능성
                splitted = [x.strip() for x in region_str.split(",") if x.strip()]
                for dong in splitted:
                    gu_ = self.find_which_gu(dong)
                    if gu_ not in selected_dict:
                        selected_dict[gu_] = []
                    selected_dict[gu_].append(dong)

            # 최종적으로 saved_conditions["dongs"]["selected"] 에 넣어주기
            self.saved_conditions["dongs"]["selected"] = selected_dict
            # rectangles는 위에서 self.saved_conditions["map_rectangles"] 에 할당

            # UI에 표시 (동선택 라벨 등 갱신)
            self.update_dong_label(selected_dict)

        # 2) "보증금" (예: "1000~3000")
        if "보증금" in self.headers:
            d_col = self.headers.index("보증금")
            deposit_val = self.row_data[d_col].strip()
            if "~" in deposit_val:
                dmin, dmax = deposit_val.split("~")
                dmin, dmax = int(dmin), int(dmax)
                self.deposit_widget.set_values(dmin, dmax, [])
            else:
                val = int(deposit_val) if deposit_val.isdigit() else 0
                self.deposit_widget.set_values(val, val, [])

        # 3) "월세"
        if "월세" in self.headers:
            r_col = self.headers.index("월세")
            rent_val = self.row_data[r_col].strip()
            if "~" in rent_val:
                rmin, rmax = rent_val.split("~")
                rmin, rmax = int(rmin), int(rmax)
                self.rent_widget.set_values(rmin, rmax, [])
            else:
                val = int(rent_val) if rent_val.isdigit() else 0
                self.rent_widget.set_values(val, val, [])

        # 4) "평수"
        if "평수" in self.headers:
            p_col = self.headers.index("평수")
            p_val = self.row_data[p_col].strip()
            if "~" in p_val:
                pmin, pmax = p_val.split("~")
                pmin, pmax = int(pmin), int(pmax)
                self.pyeong_widget.set_values(pmin, pmax, [])
            else:
                val = int(p_val) if p_val.isdigit() else 0
                self.pyeong_widget.set_values(val, val, [])

        # 5) "층"
        if "층" in self.headers:
            f_col = self.headers.index("층")
            floor_str = self.row_data[f_col].strip()  # 예: "1층", "지하층", "2층이상", "3~5층" etc
            floor_min, floor_max, is_top = self.parse_floor_range(floor_str)

            # (a) 버튼들 초기화
            for fb in self.floor_buttons:
                fb.setChecked(False)

            # (b) 지하층
            if floor_min < 0 and floor_max < 0:
                for fb in self.floor_buttons:
                    if fb.text() == "지하층":
                        fb.setChecked(True)

            # (c) 탑층
            if is_top:
                for fb in self.floor_buttons:
                    if fb.text() == "탑층":
                        fb.setChecked(True)

            # (d) 1층, 2층이상, 기타 커스텀
            if not is_top:
                if floor_min == floor_max and floor_min == 1:
                    # => '1층'
                    for fb in self.floor_buttons:
                        if fb.text() == "1층":
                            fb.setChecked(True)
                elif floor_min >= 2 and floor_max >= 999:
                    # => '2층이상'
                    for fb in self.floor_buttons:
                        if fb.text() == "2층이상":
                            fb.setChecked(True)
                # 커스텀(예: '3~5층')
                if floor_min > 0 and floor_max > floor_min + 1:
                    self.custom_floor_range = [f"{floor_min}층", f"{floor_max}층"]

            self.update_floor_label()

        # 6) "권리금"
        if "권리금" in self.headers:
            k_col = self.headers.index("권리금")
            self.right_kwoligi_line.setText(self.row_data[k_col])

        # 7) "연락처"
        if "연락처" in self.headers:
            c_col = self.headers.index("연락처")
            self.right_contact_line.setText(self.row_data[c_col])

        # 8) "실보증금/월세"
        if "실보증금/월세" in self.headers:
            s_col = self.headers.index("실보증금/월세")
            self.right_silbw_line.setText(self.row_data[s_col])

        # 9) "업종"
        if "업종" in self.headers:
            u_col = self.headers.index("업종")
            self.right_upjong_line.setText(self.row_data[u_col])

        # 10) "메모"
        if "메모" in self.headers:
            memo_idx = self.headers.index("메모") if "메모" in self.headers else -1
            memo_str = self.row_data[memo_idx] if (memo_idx >= 0) else ""

            # 메모 테이블 초기화(이제 하나의 memo_json만 로드)
            self.load_memos_from_str(memo_str)
        
    def parse_floor_range(self, floor_str):
        """
        floor_str 예:
        "지하층" => (-999, -1, False)
        "탑층"   => (0, 999, True)
        "2층이상"=> (2, 999, False)
        "1층"    => (1, 1, False)
        "3~5층" => (3, 5, False)
        """
        floor_str = (floor_str or "").strip()
        is_top = False
        fmin, fmax = 0, 999

        if not floor_str:
            return (0, 0, False)
        if "지하" in floor_str:
            fmin, fmax = -999, -1
        elif "탑층" in floor_str:
            is_top = True
            fmin, fmax = 0, 999
        elif "이상" in floor_str:
            # "2층이상"
            num_part = floor_str.replace("층이상", "").replace("층", "").strip()
            fmin = int(num_part) if num_part.isdigit() else 2
            fmax = 999
        elif "~" in floor_str:
            # "3~5층"
            range_part = floor_str.replace("층","")
            s,e = range_part.split("~",1)
            try:
                fmin = int(s)
                fmax = int(e)
            except:
                fmin,fmax=0,0
        else:
            # 단일 층수 "1층"
            num_part = floor_str.replace("층","").strip()
            try:
                val = int(num_part)
                fmin,fmax= val,val
            except:
                fmin,fmax=0,0
        return (fmin,fmax,is_top)

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


    def on_add_memo(self):
        from dialogs import MemoDialog
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

    def on_dong_select_popup(self):
        from dialogs import DongSelectDialog
        dlg = DongSelectDialog(self.district_data, self)
        dlg.set_selected_dongs(self.saved_conditions["dongs"]["selected"])
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            selected = dlg.get_selected_dongs()
            self.saved_conditions["dongs"]["selected"] = selected
            self.saved_conditions["dongs"]["all_area"] = False
            self.update_dong_label(selected)

    def update_floor_label(self):
        selected_floors = [fb.text() for fb in self.floor_buttons if fb.isChecked()]
        if self.custom_floor_range:
            selected_floors.append("-".join(self.custom_floor_range))
        if not selected_floors:
            self.floor_range_label.setText("")
        else:
            self.floor_range_label.setText(", ".join(selected_floors))
    def get_saved_conditions(self):
        return self.saved_conditions

    def on_map_select(self):
        from dialogs import MapSelectDialog
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

    def on_floor_custom_clicked(self):
        from dialogs import FloorRangeDialog
        dlg = FloorRangeDialog(self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            start_floor, end_floor = dlg.get_floor_range()
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
        for gu, dlist in self.saved_conditions["dongs"]["selected"].items():
            selected_dongs.extend(dlist)
        selected_gu = list(self.saved_conditions["dongs"]["selected"].keys())
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
        parent = self.parent()
        if parent and hasattr(parent, 'update_customer_sheet'):
            parent.update_customer_sheet(self.row_data, self.edit_row, self.id, self.manager)

        self.accept()


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

        floor_min =  999999  # 합집합 최소를 찾기 위해 초기값 '매우 큰 수'
        floor_max = -999999  # 합집합 최대를 찾기 위해 초기값 '매우 작은 수'
        is_top = False
        any_checked = False  # 지하층/1층/2층이상/커스텀 중 하나라도 체크되었는지

        # (A) 버튼들 순회
        for fb in self.floor_buttons:
            if fb.isChecked():
                txt = fb.text().strip()
                if txt == "탑층":
                    # 탑층은 is_top만 True
                    is_top = True
                else:
                    any_checked = True
                    fmin_i, fmax_i = button_map.get(txt, (0, 0))
                    if fmin_i < floor_min:
                        floor_min = fmin_i
                    if fmax_i > floor_max:
                        floor_max = fmax_i

        # (B) 커스텀 범위도 합집합
        if len(self.custom_floor_range) == 2:
            try:
                part1 = self.custom_floor_range[0].replace("층","").strip()
                part2 = self.custom_floor_range[1].replace("층","").strip()
                cmin = int(part1)
                cmax = int(part2)
                any_checked = True

                if cmin < floor_min:
                    floor_min = cmin
                if cmax > floor_max:
                    floor_max = cmax
            except:
                pass

        # (C) 아무 버튼+커스텀도 없는데 탑층만 눌렀으면 => (0,0,is_top=1)
        if (not any_checked) and is_top:
            floor_min = 0
            floor_max = 0

        # (D) 아무것도 안 눌렀으면 => (0,0,False)
        elif (not any_checked) and (not is_top):
            floor_min = 0
            floor_max = 0

        return (floor_min, floor_max, is_top)
   
    def build_floor_str(self, fmin, fmax, is_top):
        """
        - 탑층이 체크되었지만, 다른 층범위도 있으면 "지하층, 탑층" / "1층, 탑층" / "2층이상, 탑층" 처럼 콤마로 같이 표시
        - 즉, 먼저 range_str을 만든 뒤, if is_top: return range_str+", 탑층" 형태
        (만약 range_str=""면 "탑층" 단독)
        """

        # 먼저 range_str부터 계산
        range_str = ""
        if fmin < 0:
            range_str = "지하층"
        elif fmin >= 2 and fmax >= 999:
            range_str = "2층이상"
        elif fmin == fmax and fmin > 0:
            # ex) 1층, 3층 등
            range_str = f"{fmin}층"
        elif (fmin > 0) and (fmax > fmin):
            # ex) 3~5층
            range_str = f"{fmin}층~{fmax}층"

        # 이제 탑층 여부에 따라
        if is_top:
            if range_str:
                # 예) "1층, 탑층"
                return f"{range_str}, 탑층"
            else:
                # range_str가 공백이라면 => "탑층" 단독
                return "탑층"

        # 여기까지 왔다면 is_top=False
        return range_str

    def get_row_data(self):
        return self.row_data

    def is_delete_requested(self):
        return self.delete_requested