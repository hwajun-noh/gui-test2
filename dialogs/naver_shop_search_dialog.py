import requests
import json
import re  # 정규표현식 모듈 임포트
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, QUrl, pyqtSlot, QMetaObject, Q_ARG
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QMessageBox, QFrame, QComboBox,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QWidget, QSplitter,
    QInputDialog  # QInputDialog 임포트
)
from concurrent.futures import ThreadPoolExecutor
import os
import traceback
import logging
from PyQt5.QtCore import pyqtSignal # 시그널 임포트

# 필요한 환경 변수 로드
SERVER_HOST_CONNECT = os.environ.get("SERVER_HOST_CONNECT", "localhost")
SERVER_PORT_DEFAULT = int(os.environ.get("SERVER_PORT_DEFAULT", "8000"))

# 로거 설정 (모듈 레벨)
logger = logging.getLogger(__name__)

class NaverShopSearchDialog(QDialog):
    # 주소 문자열을 전달하는 시그널 정의
    addressClicked = pyqtSignal(str)

    """
    - 상단 테이블(검색 결과)
    - 하단 테이블(담은 매물 목록)
    - [추가] 버튼: 상단 테이블에서 선택된 행 → 하단테이블
    - [복사] 버튼: 하단 테이블 → MyList 테이블에 실제 행 추가
    - 검색은 비동기로 수행
    """
    def __init__(self,
                 parent=None,
                 server_host="localhost",
                 server_port="8000",
                 mylist_tab=None,
                 parent_app=None):
        
        """
        :param mylist_tab: MyListTab 객체의 참조(필요하면, 여기서 직접 on_add_mylist_shop_row(...) 등을 호출 가능)
        """
        super().__init__(parent)
        self.server_host = server_host
        self.server_port = server_port
        self.mylist_tab = mylist_tab  # 마이리스트에 복사하기 위함
        self.parent_app = parent_app

        self.setWindowTitle("네이버 매물 검색")
        self.resize(900, 600)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose) # 창 닫을 때 자동 삭제

        # (A) 백그라운드 스레드 풀(또는 parent_app.executor 사용)
        self.executor = ThreadPoolExecutor(max_workers=2)

        self.init_ui()
        self.init_signals()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # 1) 검색 영역
        top_layout = QHBoxLayout()
        self.combo_search_type = QComboBox()
        self.combo_search_type.addItems(["전체","주소","매물번호"])
        lbl_search = QLabel("검색어:")
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("예: 둔산동 or 123456")

        self.check_1month = QCheckBox("한 달 이내(광고중)")
        self.check_1month.setChecked(True)

        self.btn_search = QPushButton("검색")
        self.btn_url_search = QPushButton("URL로 검색")

        top_layout.addWidget(self.combo_search_type)
        top_layout.addWidget(lbl_search)
        top_layout.addWidget(self.edit_search)
        top_layout.addWidget(self.check_1month)
        top_layout.addWidget(self.btn_search)
        top_layout.addWidget(self.btn_url_search)
        main_layout.addLayout(top_layout)

        # 2) QSplitter(수직모드)
        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)

        # ─────────[위쪽 컨테이너]─────────
        top_container = QWidget()
        top_container_layout = QVBoxLayout(top_container)

        # 상단 테이블 + "추가" 버튼 (수평 배치)
        h_top_table_layout = QHBoxLayout()
        self.top_table = QTableWidget()
        self.top_table.setColumnCount(8)
        top_headers = ["주소","층","보증금/월세","평수","매물번호","광고등록일","담당자","메모"]
        self.top_table.setHorizontalHeaderLabels(top_headers)
        self.top_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        h_top_table_layout.addWidget(self.top_table)

        self.btn_add_to_bottom = QPushButton("추가 >>")
        self.btn_add_to_bottom.setFixedWidth(80)
        h_top_table_layout.addWidget(self.btn_add_to_bottom)

        # 위쪽 레이아웃에 추가
        top_container_layout.addLayout(h_top_table_layout)

        # splitter에 이 top_container 붙임
        splitter.addWidget(top_container)

        # ─────────[아래쪽 컨테이너]─────────
        bottom_container = QWidget()
        bottom_container_layout = QVBoxLayout(bottom_container)

        h_bottom_layout = QHBoxLayout()
        self.bottom_table = QTableWidget()
        self.bottom_table.setColumnCount(8)
        bottom_headers = ["주소","층","보증금/월세","평수","매물번호","광고등록일","담당자","메모"]
        self.bottom_table.setHorizontalHeaderLabels(bottom_headers)
        self.bottom_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # 다중 행 선택 가능하도록 설정
        self.bottom_table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.bottom_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        h_bottom_layout.addWidget(self.bottom_table)

        # 버튼들을 담을 작은 수직 레이아웃
        v_button_layout = QVBoxLayout()

        self.btn_delete_bottom = QPushButton("<<삭제")
        self.btn_delete_bottom.setFixedWidth(80) # 너비 통일
        self.btn_delete_bottom.clicked.connect(self.on_delete_bottom_clicked)
        v_button_layout.addWidget(self.btn_delete_bottom)

        self.btn_bulk_update_manager = QPushButton("담당자 변경") # 새 버튼
        self.btn_bulk_update_manager.setFixedWidth(80) # 너비 통일
        v_button_layout.addWidget(self.btn_bulk_update_manager)

        v_button_layout.addStretch() # 버튼들을 위로 밀기

        h_bottom_layout.addLayout(v_button_layout) # 수직 버튼 레이아웃을 수평 레이아웃에 추가

        bottom_container_layout.addLayout(h_bottom_layout)

        # splitter에 bottom_container 붙임
        splitter.addWidget(bottom_container)

        # 3) 복사 버튼
        self.btn_copy_to_mylist = QPushButton("복사(하단→마이리스트)")
        main_layout.addWidget(self.btn_copy_to_mylist)

        # QSplitter 높이 비율 맞추기(동등)
        splitter.setStretchFactor(0, 1)  # top
        splitter.setStretchFactor(1, 1)  # bottom

        self.setLayout(main_layout)

    def on_delete_bottom_clicked(self):
        sel = self.bottom_table.selectionModel()
        if not sel:
            return
        selected_indexes = sel.selectedIndexes()
        if not selected_indexes:
            return

        rows = sorted(set(idx.row() for idx in selected_indexes), reverse=True)
        for row_idx in rows:
            self.bottom_table.removeRow(row_idx)

    def init_signals(self):
        # (1) 검색버튼 => 비동기로 검색
        self.btn_search.clicked.connect(self.on_search_clicked)
        self.edit_search.returnPressed.connect(self.on_search_clicked)

        # (2) 추가버튼 => 상단 테이블의 선택행 → 하단테이블
        self.btn_add_to_bottom.clicked.connect(self.on_add_to_bottom_clicked)
        self.btn_url_search.clicked.connect(self.on_url_search_clicked)

        # (3) 복사버튼 => 하단테이블 rows => MyListTab (if self.mylist_tab != None)
        self.btn_copy_to_mylist.clicked.connect(self.on_copy_to_mylist_clicked)
        self.top_table.doubleClicked.connect(self.on_top_table_double_clicked)

        # (4) 하단 테이블 버튼 시그널
        self.btn_delete_bottom.clicked.connect(self.on_delete_bottom_clicked) # 중복 연결 제거 가능 (init_ui에서 이미 연결함)
        self.btn_bulk_update_manager.clicked.connect(self.on_bulk_update_manager_clicked) # 새 버튼 시그널 연결

        # 하단 테이블 더블클릭 시그널 연결 (추가)
        self.bottom_table.clicked.connect(self.on_bottom_table_clicked)

    def on_top_table_double_clicked(self, index: QtCore.QModelIndex):
        if not index.isValid():
            return

        row_idx = index.row()
        self.append_row_to_bottom(row_idx)  # 상단 → 하단

    # ─────────────────────────────────────────────────────────────
    # (A) 검색(비동기)
    # ─────────────────────────────────────────────────────────────
    def on_search_clicked(self):
        search_type = self.combo_search_type.currentText()   # "전체","주소","매물번호"
        keyword_raw = self.edit_search.text().strip()
        within_1month = "1" if self.check_1month.isChecked() else "0"

        # 공백 제거
        keyword = keyword_raw.replace(" ","")
        # (비동기로)
        future = self.executor.submit(self._bg_search, search_type, keyword, within_1month)
        future.add_done_callback(self._on_search_finished)

    def _bg_search(self, search_type, keyword, within_1month):
        """
        실제 GET 요청 -> JSON 응답
        """
        import requests

        # 수정: prefix "/shop" 추가
        url = f"http://{self.server_host}:{self.server_port}/shop/search_naver_shop_simple"
        params = {
            "search_type": search_type,
            "keyword": keyword,
            "within_1month": within_1month
        }
        try:
            resp = requests.get(url, params=params, timeout=5)
            resp.raise_for_status()
            j = resp.json()
            return j
        except Exception as ex:
            return {"status":"error","message":str(ex)}

    def _on_search_finished(self, future):
        print("[DEBUG] _on_search_finished called")
        try:
            result = future.result()
            print("[DEBUG] future.result =>", result)
        except Exception as e:
            print("[DEBUG] exception =>", e)
            result = {"status":"error","message": str(e)}

        # 여기서 바로 찍어도 됨
        print("[DEBUG] result before singleShot =>", result)

        QtCore.QMetaObject.invokeMethod(self, "_finalize_search_result", Qt.QueuedConnection, Q_ARG(dict, result))

    @pyqtSlot(dict)
    def _finalize_search_result(self, result):
        st = result.get("status")
        if st != "ok":
            msg = result.get("message", "unknown error")
            QMessageBox.warning(self, "검색 오류", msg)
            return

        rows = result.get("data", [])
        print(f"rows: {rows}")
        self.populate_top_table(rows)

    def populate_top_table(self, rows):
        tbl = self.top_table
        tbl.setRowCount(0)
        if not rows:
            return

        for i, r in enumerate(rows):
            tbl.insertRow(i)
            # 0) 주소
            addr_ = (r.get("dong","") + " " + r.get("jibun","")).strip()
            tbl.setItem(i, 0, QTableWidgetItem(addr_))

            # 1) 층
            cf = r.get("curr_floor",0)
            tf = r.get("total_floor",0)
            tbl.setItem(i, 1, QTableWidgetItem(f"{cf}/{tf}"))

            # 2) 보증금/월세
            dp = r.get("deposit",0)
            mn = r.get("monthly",0)
            bm_ = f"{dp}/{mn}"
            tbl.setItem(i, 2, QTableWidgetItem(bm_))

            # 3) 평수
            area_ = str(r.get("area",0))
            tbl.setItem(i, 3, QTableWidgetItem(area_))

            # 4) 매물번호
            nav_ = r.get("naver_property_no","")
            tbl.setItem(i, 4, QTableWidgetItem(nav_))

            # 5) 광고등록일
            ad_ = str(r.get("ad_start_date",""))
            tbl.setItem(i, 5, QTableWidgetItem(ad_))

            # 6) 담당자 (단순 텍스트)
            mgr_ = r.get("manager","").strip()
            tbl.setItem(i, 6, QTableWidgetItem(mgr_))

            # 7) 메모 (초기 빈칸)
            tbl.setItem(i, 7, QTableWidgetItem(""))

    # ─────────────────────────────────────────────────────────────
    # (A-2) URL 기반 다중 검색 (새로 추가)
    # ─────────────────────────────────────────────────────────────
    def _parse_article_nos_from_text(self, text):
        """
        입력된 텍스트에서 'articleNo=' 뒤의 숫자(매물 번호)를 추출합니다.
        정규표현식을 사용합니다.
        """
        if not text:
            return []
        # articleNo= 다음에 오는 숫자(\d+)를 찾습니다.
        pattern = r"articleNo=(\d+)"
        matches = re.findall(pattern, text)
        # 중복 제거 및 유효한 번호만 필터링 (예: 빈 문자열 등 제외)
        valid_nos = list(set(no for no in matches if no.isdigit()))
        logger.debug(f"_parse_article_nos_from_text: Found {len(valid_nos)} article numbers: {valid_nos}")
        return valid_nos

    def on_url_search_clicked(self):
        """
        'URL로 검색' 버튼 클릭 시 호출됩니다.
        QInputDialog를 사용하여 여러 줄의 URL 텍스트를 입력받고,
        매물 번호를 파싱하여 다중 검색을 시작합니다.
        """
        text, ok = QInputDialog.getMultiLineText(self, 'URL로 검색',
                                                '네이버 부동산 매물 URL(여러 개 가능) 또는 텍스트를 붙여넣으세요:\\n(예: https://new.land.naver.com/...articleNo=12345...\\n...)')

        if ok and text:
            article_nos = self._parse_article_nos_from_text(text)
            if not article_nos:
                QMessageBox.information(self, "알림", "텍스트에서 유효한 매물 번호(articleNo)를 찾을 수 없습니다.")
                return

            logger.info(f"on_url_search_clicked: Starting search for {len(article_nos)} article numbers.")
            # 백그라운드에서 다중 검색 실행
            # 각 번호에 대해 _bg_search를 호출하고 결과를 모읍니다.
            # 'within_1month'는 URL 검색 시 의미가 없을 수 있으므로 '0'으로 고정합니다.
            future = self.executor.submit(self._bg_search_multiple, article_nos, "0")
            future.add_done_callback(self._on_multi_search_finished)
        else:
            logger.debug("on_url_search_clicked: User cancelled or entered empty text.")

    def _bg_search_multiple(self, article_nos, within_1month):
        """
        주어진 매물 번호 목록에 대해 병렬로 검색을 수행하고 결과를 집계합니다.
        _bg_search 함수를 각 번호에 대해 호출합니다.
        """
        all_results_data = [] # 성공한 검색 결과의 'data'만 모음
        errors = [] # 발생한 오류 메시지 모음

        futures = {}
        # ThreadPoolExecutor를 사용하여 병렬 처리
        # (self.executor를 사용하거나, 여기서 새로 생성 가능. 여기선 self.executor 사용 가정)
        with ThreadPoolExecutor(max_workers=len(article_nos) if article_nos else 1) as executor: # 동적으로 워커 수 조절
            for no in article_nos:
                # 각 매물 번호에 대해 _bg_search 작업을 제출
                # search_type은 '매물번호'로 고정
                future = executor.submit(self._bg_search, "매물번호", no, within_1month)
                futures[future] = no # future 객체와 매물 번호 매핑

            for future in futures:
                no = futures[future]
                try:
                    result = future.result() # 각 작업의 결과 기다림
                    if result.get("status") == "ok":
                        data = result.get("data", [])
                        if data: # 데이터가 있는 경우만 추가 (보통 매물번호 검색은 1개)
                            all_results_data.extend(data)
                        else:
                            logger.warning(f"_bg_search_multiple: No data found for article number {no}")
                    else:
                        error_msg = result.get("message", f"Unknown error for article number {no}")
                        logger.error(f"_bg_search_multiple: Search failed for {no}: {error_msg}")
                        errors.append(f"매물번호 {no}: {error_msg}")
                except Exception as e:
                    logger.error(f"_bg_search_multiple: Exception during search for {no}: {e}", exc_info=True)
                    errors.append(f"매물번호 {no} 검색 중 예외 발생: {e}")

        # 최종 결과 반환 (성공 데이터와 오류 메시지 함께)
        return {"status": "ok" if not errors else "partial_error",
                "data": all_results_data,
                "errors": errors}

    def _on_multi_search_finished(self, future):
        """
        다중 검색 완료 후 호출되는 콜백 함수.
        결과를 메인 스레드에서 처리하여 테이블을 업데이트합니다.
        """
        try:
            result = future.result()
            logger.debug(f"_on_multi_search_finished: Received result: {result}")
        except Exception as e:
            logger.error(f"_on_multi_search_finished: Exception getting future result: {e}", exc_info=True)
            # 예외 발생 시 오류 메시지를 포함한 결과 객체 생성
            result = {"status": "error", "message": f"다중 검색 결과 처리 중 예외 발생: {e}", "data": [], "errors": [str(e)]}

        # 오류가 있었다면 사용자에게 알림
        if result.get("errors"):
            error_summary = "\n".join(result["errors"])
            QMessageBox.warning(self, "일부 검색 오류", f"다음 매물 번호 검색 중 오류가 발생했습니다:\n{error_summary}")

        # 성공한 데이터만 사용하여 UI 업데이트 (메인 스레드에서 실행)
        # 기존 _finalize_search_result 와 유사하게 처리하기 위해 데이터 형식 맞춤
        final_result_for_ui = {"status": "ok", "data": result.get("data", [])}
        if not final_result_for_ui["data"] and not result.get("errors"):
             QMessageBox.information(self, "검색 결과 없음", "입력된 매물 번호에 대한 검색 결과가 없습니다.")

        # Qt의 메인 이벤트 루프를 통해 _finalize_search_result 호출
        QtCore.QMetaObject.invokeMethod(self, "_finalize_search_result", Qt.QueuedConnection,
                                        Q_ARG(dict, final_result_for_ui))

    # ─────────────────────────────────────────────────────────────
    # (B) 추가 버튼 => 상단 테이블에서 선택된 행 → 하단 테이블
    # ─────────────────────────────────────────────────────────────
    def on_add_to_bottom_clicked(self):
        sel = self.top_table.selectedIndexes()
        if not sel:
            QMessageBox.information(self, "알림", "상단 테이블에서 행을 선택해주세요.")
            return

        rows = list(set(idx.row() for idx in sel))
        if not rows:
            return

        # 상단 table => 하단 table append
        for r in rows:
            self.append_row_to_bottom(r)

    def append_row_to_bottom(self, row_idx):
        """
        상단테이블 row_idx 행을 읽어서 -> 하단테이블에 1행 추가
        하단테이블 구조:
        0: 주소, 1: 층, 2: 보증금/월세, 3: 평수, 4: 매물번호,
        5: 광고등록일, 6: 담당자(QComboBox), 7: 메모
        """
        src = self.top_table
        dst = self.bottom_table

        new_row = dst.rowCount()
        dst.insertRow(new_row)

        # (A) 먼저 기존 0~5,7은 QTableWidgetItem 으로 복사
        for col in range(6):
            item_src = src.item(row_idx, col)
            text_src = item_src.text() if item_src else ""
            dst.setItem(new_row, col, QtWidgets.QTableWidgetItem(text_src))


        # (B) 담당자( col=6 ) => QComboBox
        #     parent_app.manager_dropdown을 참조해 manager_list 뽑아온 뒤,
        #     거기에 setCurrentText
        if self.parent_app and hasattr(self.parent_app, 'manager_dropdown'):
            manager_list = []
            combo_box_src = self.parent_app.manager_dropdown
            # 드롭다운에 아이템이 있는지 확인 후 추가
            if combo_box_src and combo_box_src.count() > 0:
                for i in range(combo_box_src.count()):
                    manager_list.append(combo_box_src.itemText(i))
            # 드롭다운에 아이템이 없으면 기본 관리자 사용
            if not manager_list:
                manager_list = ["관리자"] 
        else:
            # parent_app 또는 manager_dropdown이 없으면 기본 관리자 사용
            manager_list = ["관리자"]

        # top_table에서 manager는 item(row_idx,6)에 들어있음
        mgr_item = src.item(row_idx,6)
        mgr_text = mgr_item.text().strip() if mgr_item else ""
        class NoWheelComboBox(QtWidgets.QComboBox):
            def wheelEvent(self, event: QtGui.QWheelEvent):
                # 기본 동작(스크롤) 무시
                event.ignore()
        combo_manager = NoWheelComboBox()
        combo_manager.addItems(manager_list)
        combo_manager.setCurrentText(mgr_text)
        dst.setCellWidget(new_row, 6, combo_manager)

    # ─────────────────────────────────────────────────────────────
    # (C) 복사 버튼 => 하단 테이블 전부 → MyListTab에 새 행으로 추가
    # ─────────────────────────────────────────────────────────────
    def on_copy_to_mylist_clicked(self):
        if not self.mylist_tab:
            logger.warning("on_copy_to_mylist_clicked: mylist_tab is not set.")
            QMessageBox.information(self, "안내", "mylist_tab (MyListContainer) 참조가 설정되지 않았습니다.")
            return

        tbl = self.bottom_table
        rc = tbl.rowCount()
        if rc == 0:
            logger.info("on_copy_to_mylist_clicked: bottom_table is empty.")
            QMessageBox.information(self, "안내", "하단 테이블이 비어있습니다.")
            return

        # 하단 테이블 모든 행 => MyListContainer의 add_new_shop_row 메서드 호출
        copied_count = 0
        logger.debug(f"on_copy_to_mylist_clicked: Starting to iterate {rc} rows in bottom_table.")
        for row_idx in range(rc):
            logger.debug(f"on_copy_to_mylist_clicked: Calling extract_row_data for row {row_idx}")
            row_data = self.extract_row_data(tbl, row_idx)
            if row_data:
                try:
                    # self.mylist_tab은 MyListContainer 인스턴스를 가리킨다고 가정
                    logger.debug(f"on_copy_to_mylist_clicked: Calling mylist_tab.add_new_shop_row for row {row_idx} with data: {row_data}")
                    self.mylist_tab.add_new_shop_row(initial_data=row_data, parse_naver_format=True)
                    copied_count += 1
                except Exception as e:
                     logger.error(f"Error adding row to MyList (row {row_idx+1}): {e}", exc_info=True)
                     QMessageBox.critical(self, "복사 오류", f"마이리스트에 행 추가 중 오류 발생 (행 {row_idx+1}):\n{e}")
                     # 오류 발생 시 중단하거나 계속 진행할 수 있음 (여기서는 계속 진행)
            else:
                 logger.warning(f"on_copy_to_mylist_clicked: extract_row_data returned None for row {row_idx}")

        if copied_count > 0:
            logger.info(f"on_copy_to_mylist_clicked: Copied {copied_count} items to MyList.")
            QMessageBox.information(self, "완료", f"{copied_count}개 매물을 마이리스트에 복사했습니다.")

    def extract_row_data(self, table_widget, row_idx):
        """
        하단 테이블의 한 행 데이터를 MyListContainer.add_new_shop_row가 이해하는 dict 형태로 변환.
        이 함수는 add_new_shop_row의 initial_data 형식에 맞춰야 함.
        """
        logger.info(f"--- [EXTRACT] Extracting data for row: {row_idx} --- suboptimal")
        try:
            addr_item = table_widget.item(row_idx,0)
            floor_item= table_widget.item(row_idx,1)
            bm_item   = table_widget.item(row_idx,2)
            area_item = table_widget.item(row_idx,3)
            nav_item  = table_widget.item(row_idx,4)
            ad_item   = table_widget.item(row_idx,5)
            combo_mgr = table_widget.cellWidget(row_idx, 6)
            memo_item = table_widget.item(row_idx, 7)
            
            # 각 셀에서 읽은 원본 텍스트 로깅
            addr_text = addr_item.text() if addr_item else "<Item None>"
            floor_text = floor_item.text() if floor_item else "<Item None>"
            bm_text = bm_item.text() if bm_item else "<Item None>"
            area_text = area_item.text() if area_item else "<Item None>"
            nav_text = nav_item.text() if nav_item else "<Item None>"
            ad_text = ad_item.text() if ad_item else "<Item None>"
            combo_text = combo_mgr.currentText() if combo_mgr and isinstance(combo_mgr, QComboBox) else "<Widget None or Wrong Type>"
            memo_text = memo_item.text() if memo_item else "<Item None>"
            logger.info(f"  [EXTRACT] Raw Addr : '{addr_text}'")
            logger.info(f"  [EXTRACT] Raw Floor: '{floor_text}'")
            logger.info(f"  [EXTRACT] Raw B/M  : '{bm_text}'")
            logger.info(f"  [EXTRACT] Raw Area : '{area_text}'")
            logger.info(f"  [EXTRACT] Raw NavNo: '{nav_text}'")
            logger.info(f"  [EXTRACT] Raw AdDt : '{ad_text}'")
            logger.info(f"  [EXTRACT] Raw Mgr  : '{combo_text}'")
            logger.info(f"  [EXTRACT] Raw Memo : '{memo_text}'")
            

            addr_str = addr_text.strip() if addr_text != "<Item None>" else ""
            dong_, jibun_ = "", ""
            if " " in addr_str:
                sp=addr_str.split(" ",1)
                dong_=sp[0].strip()
                jibun_=sp[1].strip()
            floor_str = floor_text.strip() if floor_text != "<Item None>" else ""
            cf, tf=0,0
            if "/" in floor_str:
                c_, t_=floor_str.split("/",1)
                try: cf=int(c_)
                except: cf=0
                try: tf=int(t_)
                except: tf=0
            bm_str = bm_text.strip() if bm_text != "<Item None>" else ""
            dep, mon=0,0
            if "/" in bm_str:
                d_, m_=bm_str.split("/",1)
                try: dep=int(d_)
                except: dep=0
                try: mon=int(m_)
                except: mon=0
            area_str = area_text.strip() if area_text != "<Item None>" else ""
            try:
                area_float = float(area_str) # 평수를 float으로 변환 시도
            except:
                area_float = 0.0
                
            nav_str = nav_text.strip() if nav_text != "<Item None>" else ""
            memo_str = memo_text.strip() if memo_text != "<Item None>" else ""
            
            manager_str = combo_text if combo_text != "<Widget None or Wrong Type>" else ""
            manager_str = manager_str.strip()

            # add_new_shop_row 의 parse_naver_format=True일 때 필요한 키 반환
            # (DB 필드명과 유사해야 함)
            result_dict = {
                "dong": dong_,
                "jibun": jibun_,
                "curr_floor": cf,
                "total_floor": tf,
                "deposit": dep,
                "monthly": mon,
                "area": area_float, # float 값 전달
                "naver_property_no": nav_str,
                "memo": memo_str,
                "manager": manager_str, 
                # 기타 필요한 필드들 (add_new_shop_row에서 처리할 수 있는 형식으로)
                # 예: "premium": None, "current_use": None 등 기본값 설정
            }
            logger.info(f"  [EXTRACT] Parsed data: {result_dict}")
            logger.info(f"--- [EXTRACT] End extracting row: {row_idx} --- suboptimal")
            return result_dict
        except Exception as e:
            logger.error(f"Error extracting row data at row {row_idx}: {e}", exc_info=True)
            return None 

    def on_bulk_update_manager_clicked(self):
        """
        하단 테이블에서 선택된 행들의 '담당자' 콤보박스를 일괄 변경합니다.
        """
        selected_indexes = self.bottom_table.selectionModel().selectedIndexes()
        if not selected_indexes:
            QMessageBox.information(self, "알림", "하단 테이블에서 변경할 행을 먼저 선택해주세요.")
            return

        # 중복 제거된 선택 행 인덱스 목록 (오름차순)
        selected_rows = sorted(list(set(index.row() for index in selected_indexes)))

        # 담당자 목록 가져오기 (append_row_to_bottom과 유사한 로직)
        manager_list = []
        if self.parent_app and hasattr(self.parent_app, 'manager_dropdown'):
            combo_box_src = self.parent_app.manager_dropdown
            if combo_box_src and combo_box_src.count() > 0:
                for i in range(combo_box_src.count()):
                    manager_list.append(combo_box_src.itemText(i))

        # 담당자 목록이 비어 있으면 기본값 사용 또는 오류 처리
        if not manager_list:
            # 여기서 오류 메시지를 표시하거나, 기본 목록을 사용할 수 있습니다.
            # 예: manager_list = ["담당자 없음"] # 또는
            QMessageBox.warning(self, "오류", "사용 가능한 담당자 목록이 없습니다.")
            return

        # QInputDialog로 사용자에게 담당자 선택 요청
        chosen_manager, ok = QInputDialog.getItem(self, "담당자 선택",
                                                  "선택된 행들에 적용할 담당자를 선택하세요:",
                                                  manager_list, 0, False) # editable=False

        if ok and chosen_manager:
            # 선택된 모든 행에 대해 담당자 콤보박스 업데이트
            updated_count = 0
            for row_idx in selected_rows:
                widget = self.bottom_table.cellWidget(row_idx, 6) # 6번 열이 담당자
                if isinstance(widget, QComboBox):
                    widget.setCurrentText(chosen_manager)
                    updated_count += 1
                else:
                    logger.warning(f"Row {row_idx}, Col 6 is not a QComboBox. Skipping update.")

            if updated_count > 0:
                QMessageBox.information(self, "완료", f"{updated_count}개 행의 담당자를 '{chosen_manager}'(으)로 변경했습니다.")
            else:
                 QMessageBox.warning(self, "실패", "선택된 행에서 담당자 콤보박스를 찾을 수 없거나 변경하지 못했습니다.")
        else:
            logger.debug("User cancelled the manager selection dialog.") 

    # 하단 테이블 더블클릭 슬롯 (새로 추가)
    def on_bottom_table_clicked(self, index: QtCore.QModelIndex):
        if not index.isValid():
            return

        row_idx = index.row()
        addr_item = self.bottom_table.item(row_idx, 0) # 0번 열이 주소
        if addr_item:
            address = addr_item.text().strip()
            if address:
                logger.debug(f"Bottom table double-clicked on row {row_idx}, emitting address: {address}")
                self.addressClicked.emit(address) # 시그널 발생!
            else:
                 logger.debug(f"Bottom table double-clicked on row {row_idx}, but address is empty.")
        else:
            logger.debug(f"Bottom table double-clicked on row {row_idx}, but address item is None.") 