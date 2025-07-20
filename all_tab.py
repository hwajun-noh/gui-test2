import sys
import os
import json
import requests
from datetime import datetime, date, timedelta
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, QUrl, QObject, pyqtSlot
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QInputDialog,QDialog, QTableWidgetItem, QMessageBox, QAbstractItemView, QTableView, QMenu, QAction, QWidget, QVBoxLayout, QComboBox, QPushButton, QLineEdit, QHBoxLayout, QHeaderView, QApplication
from ui_utils import show_context_menu, save_qtableview_column_widths, restore_qtableview_column_widths
from dialogs import ImageSlideshowWindow, RecommendDialog, StatusChangeDialog # Added StatusChangeDialog
import glob
import logging

logger = logging.getLogger(__name__)

class AllTab(QObject):
    def __init__(self, parent_app, server_host, server_port):
        super().__init__() # Call QObject initializer
        self.parent_app = parent_app # Reference to the main ExcelTableApp instance
        self.server_host = server_host
        self.server_port = server_port

        # UI elements will be initialized in init_tab
        self.all_tab_container = None
        self.all_tab_model = None
        self.all_tab_view = None
        self.all_tab_timer = None
        self.all_tab_search_combo = None
        self.all_tab_search_input = None
        self.all_tab_search_btn = None
        self.is_shutting_down = False  # 종료 상태 플래그 추가

        # Data / State (needs access via parent_app or passed explicitly)
        # self.executor = parent_app.executor
        # self.settings_manager = parent_app.settings_manager
        # ... access other needed attributes like check_confirm_dict, etc., via self.parent_app ...

    def init_tab(self, main_tabs):
        """Initializes the 'All' tab UI elements and adds it to the main_tabs."""
        # Container widget and layout for the 'All' tab
        self.all_tab_container = QWidget()
        layout = QVBoxLayout(self.all_tab_container)

        # Model/View creation
        self.all_tab_model = QtGui.QStandardItemModel()
        headers = [
            "주소", "호", "층", "보증금/월세", "관리비",
            "권리금", "현업종", "평수", "연락처", "매물번호",
            "제목", "매칭업종", "확인메모","광고종료일",
            "주차대수", "용도", "사용승인일", "방/화장실",
            "광고등록일", "사진경로", "소유자명", "관계"
        ]
        self.all_tab_model.setColumnCount(len(headers))
        self.all_tab_model.setHorizontalHeaderLabels(headers)

        # QTableView setup
        self.all_tab_view = QTableView()
        self.all_tab_view.setModel(self.all_tab_model)
        self.all_tab_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.all_tab_view.setSortingEnabled(True)

        # Initial sort by '광고종료일' descending
        try:
            ad_end_col_idx = headers.index("광고종료일")
            self.all_tab_view.sortByColumn(ad_end_col_idx, Qt.DescendingOrder)
        except ValueError:
            print("[WARN] '광고종료일' header not found for initial sort.")

        # Connect signals
        self.all_tab_view.clicked.connect(self.on_all_tab_clicked)
        self.all_tab_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.all_tab_view.customContextMenuRequested.connect(self.on_all_tab_context_menu_requested)

        # Add view to layout
        layout.addWidget(self.all_tab_view)
        self.all_tab_container.setLayout(layout)

        # Add the container to the main tab widget
        main_tabs.insertTab(0, self.all_tab_container, "전체") # Insert at the beginning

        # Restore column widths using the utility function
        restore_qtableview_column_widths(
            self.parent_app.settings_manager, # Pass settings manager from parent
            self.all_tab_view, 
            "AllTabTable"
        )
        # Save column widths on resize using the utility function
        self.all_tab_view.horizontalHeader().sectionResized.connect(
            lambda: save_qtableview_column_widths(
                self.parent_app.settings_manager, # Pass settings manager from parent
                self.all_tab_view, 
                "AllTabTable"
            )
        )

        # 타이머 설정 및 시작
        try:
            # 이미 종료 상태인지 확인
            if self.is_shutting_down:
                logger.info("AllTab: 이미 종료 중이므로 타이머를 시작하지 않습니다.")
                return
                
            # [자동 타이머 비활성화] 성능 최적화를 위해 자동 리로드 타이머를 비활성화함
            # 사용자가 필요시 수동으로 새로고침하도록 변경
            logger.info("AllTab: 자동 리로드 타이머가 성능 최적화를 위해 비활성화되었습니다.")
            
            # self.all_tab_timer = QtCore.QTimer(self.parent_app) # Parent timer to parent_app
            # self.all_tab_timer.setInterval(30 * 1000) # 30 seconds
            
            # # 연결 전에 기존 연결이 있는지 확인하고 해제
            # try:
            #     # 새로 만든 타이머이므로 연결 오류는 없겠지만 안전하게 처리
            #     self.all_tab_timer.timeout.disconnect()
            # except (TypeError, RuntimeError):
            #     # 기존 연결이 없으면 오류가 발생하므로 무시
            #     pass
                
            # self.all_tab_timer.timeout.connect(self._auto_reload_all_tab_data)
            # self.all_tab_timer.start()
        except Exception as e:
            logger.error(f"AllTab 타이머 설정 중 오류 발생: {e}")
            
        # --- Search UI in Corner Widget ---
        # Note: Corner widget logic is handled in main_app.py's initUI
        # We need to connect the search button in main_app.py to self.on_all_tab_search_button_clicked
        # This can be done in main_app.py after instantiating AllTab:
        # self.all_tab_search_btn.clicked.connect(self.all_tab.on_all_tab_search_button_clicked)
        # self.all_tab_search_input.returnPressed.connect(self.all_tab.on_all_tab_search_button_clicked)

    def terminate(self):
        """프로그램 종료 시 호출하여 타이머, 시그널 등의 리소스 정리"""
        logger.info("AllTab: Terminating...")
        self.is_shutting_down = True
        
        # 타이머 정지 강화된 예외 처리
        if hasattr(self, 'all_tab_timer') and self.all_tab_timer:
            try:
                if self.all_tab_timer.isActive():
                    self.all_tab_timer.stop()
                    logger.info("AllTab: Timer stopped")
                    
                # 타이머 연결 해제
                try:
                    self.all_tab_timer.timeout.disconnect()
                    logger.info("AllTab: Timer signal disconnected")
                except (TypeError, RuntimeError):
                    # 이미 연결이 끊어졌거나 예외가 발생했을 경우 무시
                    pass
                    
            except Exception as e:
                logger.warning(f"AllTab: 타이머 정지 중 오류: {e}")
                
        logger.info("AllTab: Termination complete")

    # --- Methods to be moved from ExcelTableApp ---

    @pyqtSlot(str)
    def search_by_address(self, address_str: str):
        """ 슬롯: 다른 창(예: NaverShopSearchDialog)에서 전달된 주소로 검색 실행 """
        logger.info(f"[AllTab] Received address search request: '{address_str}'")
        if not address_str:
            logger.warning("[AllTab] search_by_address called with empty address.")
            return

        # 기존 검색 UI 업데이트 및 검색 실행 로직 활용
        if self.parent_app.all_tab_search_combo and self.parent_app.all_tab_search_input:
            # 검색 타입을 '주소'로 설정
            address_search_index = self.parent_app.all_tab_search_combo.findText("주소")
            if address_search_index != -1:
                self.parent_app.all_tab_search_combo.setCurrentIndex(address_search_index)
            else:
                logger.warning("[AllTab] '주소' search type not found in combo box.")
                # 기본 타입으로 진행하거나 오류 처리

            # 검색어 입력란에 주소 설정
            self.parent_app.all_tab_search_input.setText(address_str)

            # 검색 버튼 클릭 시그널 발생 (또는 직접 검색 함수 호출)
            self.on_all_tab_search_button_clicked()
        else:
            logger.error("[AllTab] Cannot perform address search: Search combo/input not found in parent_app.")

    def on_all_tab_search_button_clicked(self):
        # Needs access to search combo/input from parent_app
        search_type = self.parent_app.all_tab_search_combo.currentText().strip()
        keyword = self.parent_app.all_tab_search_input.text().strip()
        if not keyword:
            QMessageBox.information(self.parent_app, "안내", "검색어를 입력하세요.")
            return

        if search_type == "주소":
            keyword = keyword.replace(" ", "")

        self.parent_app.setCursor(Qt.WaitCursor)
        self.parent_app.from_customer_click = False
        self.parent_app.from_manager_click = False
        self.parent_app.last_selected_address = None

        rows = []
        try:
            url = f"http://{self.server_host}:{self.server_port}/shop/search_in_all_data"
            payload = {"search_type": search_type, "keyword": keyword}
            # Use parent's executor for background task? Or requests directly? Direct for now.
            resp = requests.post(url, json=payload, timeout=5)
            resp.raise_for_status()
            j = resp.json()
            if j.get("status") == "ok":
                rows = j.get("data", [])
        except Exception as ex:
            print("[ERR] AllTab on_search_button_clicked =>", ex)
            rows = []

        self.parent_app.setCursor(Qt.ArrowCursor)
        self.populate_all_tab_view(rows)

        if rows:
            print(f"[INFO] AllTab 검색 결과 {len(rows)}건 표시")
        else:
            print("[INFO] AllTab 검색 결과 없음")

    def populate_all_tab_view(self, unified_rows):
        # 종료 상태 확인
        if self.is_shutting_down:
            logger.info("AllTab: 종료 중이므로 테이블 채우기를 건너뜁니다.")
            return
            
        # 앱이 종료 중인지 확인
        if not self.parent_app or (hasattr(self.parent_app, 'terminating') and self.parent_app.terminating):
            logger.info("AllTab: 앱이 종료 중이므로 테이블 채우기를 건너뜁니다.")
            return
            
        # 모델 객체가 유효한지 확인
        if not self.all_tab_model:
            logger.info("AllTab: Model not available, skipping populate_all_tab_view")
            return
            
        # Method moved from ExcelTableApp (originally found in main_app_part5.py)
        logger.info(f"populate_all_tab_view: Received {len(unified_rows)} unified rows to populate.") # 로그 추가
        # 0) 모델 초기화
        m = self.all_tab_model
        m.setRowCount(0)
        if not unified_rows: return

        def parse_ad_end_date(date_str: str):
            """
            광고종료일 문자열을 datetime 객체로 변환합니다.
            다양한 날짜 형식을 처리하고, 변환 실패 시 매우 오래된 날짜(1970-01-01)를 반환합니다.
            """
            if not date_str or date_str.strip() == "":
                return datetime(1970, 1, 1)
                
            date_str = date_str.strip()
            # 다양한 날짜 형식을 시도합니다
            formats = [
                "%Y-%m-%d",        # 2024-12-02
                "%Y-%m-%d %H:%M:%S",# 2024-12-02 15:30:45
                "%Y/%m/%d",        # 2024/12/02
                "%Y. %m. %d",      # 2024. 12. 02
                "%Y.%m.%d",        # 2024.12.02
                "%Y년 %m월 %d일"   # 2024년 12월 02일
            ]
            
            for fmt in formats:
                try:
                    # 날짜 형식을 정확히 일치시키기 위해 시도
                    # 형식이 시간을 포함하면 전체 문자열 사용, 아니면 첫 10자만 사용
                    if '%H' in fmt or '%M' in fmt or '%S' in fmt:
                        return datetime.strptime(date_str, fmt)
                    else:
                        # 년월일만 있는 형식은 앞 10자만 사용
                        return datetime.strptime(date_str[:10], fmt)
                except ValueError:
                    continue
                except Exception as e:
                    logger.debug(f"날짜 파싱 예외 발생: {e}, 형식: {fmt}, 날짜: {date_str}")
                    continue
            
            # 모든 형식 실패시 기본값 반환 (매우 오래된 날짜)
            logger.warning(f"광고종료일 파싱 실패: '{date_str}' - 기본값 1970-01-01 사용")
            return datetime(1970, 1, 1)

        # 1) 출처별 분류
        done_rows = [r for r in unified_rows if r.get("출처","") == "계약완료"]
        mylist_sanga_rows = [r for r in unified_rows if r.get("출처","") == "마이리스트(상가)"]
        confirm_rows = [r for r in unified_rows if r.get("출처","") == "확인"]
        rec_rows = [r for r in unified_rows if r.get("출처","") == "추천"]
        serve_rows = [r for r in unified_rows if r.get("출처","") in ("상가","원룸")]
        others = [r for r in unified_rows if r.get("출처","") not in ("계약완료","마이리스트(상가)","확인","추천","상가","원룸")]

        # 2) (상가/원룸) dedup - 중복 제거 완전 개선
        logger.info("=== 중복 제거 및 최신 날짜 항목 유지 프로세스 시작 ===")
        dedup_dict = {}
        debug_replacements = []  # 디버깅용: 대체되는 항목 추적
        
        # 1. 각 항목의 광고종료일을 먼저 파싱하여 datetime 객체로 저장
        rows_with_dates = []
        for row in serve_rows:
            # 모든 행에 종료일 객체 추가
            row['_ad_end_dt'] = parse_ad_end_date(row.get("광고종료일", ""))
            # 원본 날짜 문자열도 디버깅용으로 저장
            row['_original_date_str'] = row.get("광고종료일", "")
            rows_with_dates.append(row)
            
        # 2. 종료일 기준으로 내림차순 정렬 (최신 날짜가 앞에 오도록)
        rows_with_dates.sort(key=lambda r: r['_ad_end_dt'], reverse=True)
        
        # 3. 중복 제거 (같은 키에 대해 이미 최신 항목이 앞에 위치하므로 처음 나온 항목만 유지)
        seen_keys = set()
        dedup_serve_list = []
        
        # 날짜 정렬 로그 (상위 5개 항목)
        logger.info(f"날짜로 정렬된 상위 5개 항목:")
        for i, row in enumerate(rows_with_dates[:5]):
            date_str = row.get('_original_date_str', '')
            logger.info(f"  {i+1}. 주소: {row.get('주소', '')}, 종료일: {date_str}, 파싱된 날짜: {row.get('_ad_end_dt')}")
            
        for row in rows_with_dates:
            addr_ = row.get("주소","")
            floor_ = row.get("층","")
            price_ = row.get("보증금/월세","")
            mf_ = row.get("관리비","")
            pm_ = row.get("권리금","")
            cu_ = row.get("현업종","")
            area_ = row.get("평수","")
            phone_ = row.get("연락처","")
            photo_ = row.get("사진경로","")
            
            dedup_key = (addr_, floor_, price_, mf_, pm_, cu_, area_, phone_, photo_)
            
            if dedup_key not in seen_keys:
                seen_keys.add(dedup_key)
                dedup_serve_list.append(row)
                logger.debug(f"중복 없음, 항목 추가: 주소={addr_}, 층={floor_}, 광고종료일={row.get('_original_date_str','')}")
            else:
                # 이미 추가된 항목이므로 스킵 (이미 최신 날짜 순으로 정렬되어 있음)
                logger.debug(f"중복 발견, 건너뜀: 주소={addr_}, 층={floor_}, 광고종료일={row.get('_original_date_str','')}")
                debug_replacements.append({
                    "action": "skip",
                    "key": addr_,  # 주소 정보만 표시
                    "skip_date": row.get('_original_date_str', '')
                })
        
        # 결과에서 임시 필드 제거
        for row in dedup_serve_list:
            if '_ad_end_dt' in row:
                del row['_ad_end_dt']
            if '_original_date_str' in row:
                del row['_original_date_str']
        
        # 결과 로깅
        logger.info(f"중복 제거 후 항목 수: {len(dedup_serve_list)} (원본: {len(serve_rows)})")
        if debug_replacements:
            logger.info(f"중복으로 제외된 항목: {len(debug_replacements)}건")
        
        # 날짜순 정렬은 이미 되어 있음 - 최종 결과를 serve_sorted에 할당
        serve_sorted = dedup_serve_list
        
        # 날짜 정렬 확인을 위한 로그
        if serve_sorted:
            logger.info(f"최종 정렬 후 첫 5개 항목:")
            for i, row in enumerate(serve_sorted[:5]):
                logger.info(f"  {i+1}. 주소: {row.get('주소', '')}, 종료일: {row.get('광고종료일', '')}")

        # 3) 최종 순서
        final_list = []; final_list.extend(done_rows); final_list.extend(mylist_sanga_rows)
        final_list.extend(confirm_rows); final_list.extend(rec_rows); final_list.extend(serve_sorted); final_list.extend(others)

        # 4) from_customer_click 정렬 (Use self.parent_app for state)
        if self.parent_app.from_customer_click and self.parent_app.selected_addresses:
            final_list = self.arrange_recommend_top_for_multiaddr(final_list, self.parent_app.selected_addresses)

        # 5) 테이블 채우기
        headers = [ # Get headers from model to be safe
            self.all_tab_model.horizontalHeaderItem(j).text() if self.all_tab_model.horizontalHeaderItem(j) else f"col_{j}"
            for j in range(self.all_tab_model.columnCount())
        ]
        color_map = { "확인": "#CCFFCC", "상가": "#FFFFCC", "원룸": "#FFCCCC", "추천": "#BBDEFB", "마이리스트(상가)": "#E1BEE7", "계약완료": "#DDDDDD" }
        m.setRowCount(len(final_list))
        used_folders = set()

        for i, row_dict in enumerate(final_list):
            source = row_dict.get("출처",""); bg_hex = color_map.get(source, "#FFFFFF"); bg_color = QtGui.QColor(bg_hex)
            for j, col_name in enumerate(headers):
                raw_val = row_dict.get(col_name, ""); cell_val = str(raw_val)
                if col_name == "매물번호":
                    mb_val = row_dict.get("매물번호","").strip()
                    naver_no = (row_dict.get("naver_no") or "").strip()
                    serve_no = (row_dict.get("serve_no") or "").strip()
                    index_ = m.index(i, j)
                    # Define copy functions locally or as methods if needed frequently
                    def create_copy_func(num, type_name):
                        def copy_num():
                            if num:
                                QApplication.clipboard().setText(num)
                                QMessageBox.information(self.parent_app, "복사", f"[{type_name}:{num}] 복사 완료") # Use parent_app for QMessageBox parent
                            else:
                                QMessageBox.warning(self.parent_app, "오류", f"{type_name}번호가 없습니다.")
                        return copy_num
                    copy_naver_func = create_copy_func(naver_no, "네이버")
                    copy_serve_func = create_copy_func(serve_no, "써브")

                    if mb_val == "N,S":
                        container = QWidget(); hlayout = QHBoxLayout(container); hlayout.setContentsMargins(0,0,0,0)
                        btnN = QPushButton("N"); btnS = QPushButton("S")
                        btnN.clicked.connect(copy_naver_func)
                        btnS.clicked.connect(copy_serve_func)
                        hlayout.addWidget(btnN); hlayout.addWidget(btnS)
                        container.setLayout(hlayout)
                        self.all_tab_view.setIndexWidget(index_, container)
                    elif mb_val == "N":
                        container = QWidget(); hlayout = QHBoxLayout(container); hlayout.setContentsMargins(0,0,0,0)
                        btnN = QPushButton("N")
                        btnN.clicked.connect(copy_naver_func)
                        hlayout.addWidget(btnN); container.setLayout(hlayout)
                        self.all_tab_view.setIndexWidget(index_, container)
                    elif mb_val == "S":
                        container = QWidget(); hlayout = QHBoxLayout(container); hlayout.setContentsMargins(0,0,0,0)
                        btnS = QPushButton("S")
                        btnS.clicked.connect(copy_serve_func)
                        hlayout.addWidget(btnS); container.setLayout(hlayout)
                        self.all_tab_view.setIndexWidget(index_, container)
                    else:
                        fallback_item = QtGui.QStandardItem(mb_val); fallback_item.setBackground(bg_color); m.setItem(i, j, fallback_item)

                elif j == 0: # 주소 열
                    address_text = cell_val; folder_path = row_dict.get("사진경로","") or ""; rep_img_path = ""
                    if os.path.isdir(folder_path):
                        files = [f for f in os.listdir(folder_path) if f.lower().endswith((".jpg",".jpeg",".png",".gif"))]
                        if files: rep_img_path = os.path.join(folder_path, files[0])
                    item_addr = QtGui.QStandardItem(address_text)
                    # 표준화된 위치에만 데이터 저장
                    item_addr.setData(source, Qt.UserRole + 2)  # 출처는 항상 UserRole+2에만 저장
                    item_addr.setData(row_dict.get("id", 0), Qt.UserRole + 3)  # ID는 항상 UserRole+3에만 저장
                    if folder_path and (folder_path not in used_folders):
                        if rep_img_path and os.path.isfile(rep_img_path):
                            pixmap = QtGui.QPixmap(rep_img_path).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            icon_ = QtGui.QIcon(pixmap); item_addr.setIcon(icon_)
                            file_url = QUrl.fromLocalFile(rep_img_path).toString()
                            item_addr.setToolTip(f'<img src="{file_url}" width="200">')
                        item_addr.setData(folder_path, Qt.UserRole+10)
                        item_addr.setData(rep_img_path, Qt.UserRole+11)
                        used_folders.add(folder_path)
                    else: item_addr.setToolTip("")
                    item_addr.setBackground(bg_color); m.setItem(i, j, item_addr)
                else:
                    normal_item = QtGui.QStandardItem(cell_val); normal_item.setBackground(bg_color)
                    if col_name == "확인메모":
                        if cell_val in ["등록종료", "계약완료","부재중","광고X","연락처X"]: normal_item.setForeground(QtGui.QColor("red"))
                        elif cell_val == "확인중": normal_item.setForeground(QtGui.QColor("green"))
                        elif cell_val == "서비스중": normal_item.setForeground(QtGui.QColor("blue"))
                        else: normal_item.setForeground(QtGui.QColor("black"))
                    m.setItem(i, j, normal_item)
        print(f"[INFO] AllTab populate_all_tab_view => 총 {len(final_list)}행 표시 (from_customer_click={self.parent_app.from_customer_click})")

    def arrange_recommend_top_for_multiaddr(self, all_rows, addr_list):
        # ... (Identical logic, no parent needed here) ...
        def parse_ad_end_date(ds):
            try: return datetime.strptime(ds[:10], "%Y-%m-%d")
            except: return datetime(1970,1,1)
        rec_rows = [r for r in all_rows if r.get("출처")=="추천"]
        non_rec_rows = [r for r in all_rows if r.get("출처")!="추천"]
        rec_sorted = sorted(rec_rows, key=lambda row: parse_ad_end_date(row.get("광고종료일","")), reverse=True)
        addr_dict = {}
        for row in non_rec_rows: a_ = row.get("주소",""); addr_dict.setdefault(a_, []).append(row)
        for a_ in addr_dict:
            sub = addr_dict[a_]; sub_sorted = sorted(sub, key=lambda row: parse_ad_end_date(row.get("광고종료일","")), reverse=True)
            addr_dict[a_] = sub_sorted
        new_list = []; new_list.extend(rec_sorted)
        for ad_ in addr_list:
            if ad_ in addr_dict: new_list.extend(addr_dict[ad_])
        return new_list

    def on_all_tab_clicked(self, index: QtCore.QModelIndex):
        # ... (This entire method needs to be moved here) ...
        if not index.isValid(): return
        col_memo_idx = 9; col_addr_idx = 0
        if index.column() == col_memo_idx:
            item_ = self.all_tab_model.item(index.row(), col_memo_idx)
            if not item_: return
            tip_str = item_.toolTip() or ""
            if tip_str.strip():
                QApplication.clipboard().setText(tip_str)
                QMessageBox.information(self.parent_app, "복사", f"매물번호 [{tip_str}] 복사 완료!")
        elif index.column() == col_addr_idx:
            item_clicked = self.all_tab_model.item(index.row(), col_addr_idx)
            if not item_clicked: return
            folder_path = item_clicked.data(Qt.UserRole + 10) or ""
            if (not folder_path) or (not os.path.isdir(folder_path)): return
            image_files = sorted(glob.glob(os.path.join(folder_path, "*.jpg")) + glob.glob(os.path.join(folder_path, "*.jpeg")) + glob.glob(os.path.join(folder_path, "*.png")) + glob.glob(os.path.join(folder_path, "*.gif")))
            if not image_files:
                QMessageBox.warning(self.parent_app, "이미지 없음", "해당 폴더에 이미지가 없습니다.")
                return
            # Handle slideshow window (needs careful handling of self.slider_window reference)
            # Option 1: Store slider_window in parent_app
            if hasattr(self.parent_app, 'slider_window') and self.parent_app.slider_window is not None:
                 if self.parent_app.slider_window.isVisible():
                     self.parent_app.slider_window.set_image_list(image_files)
                     self.parent_app.slider_window.activateWindow(); self.parent_app.slider_window.raise_()
                     return
            # Option 2: Create it locally each time (simpler, but loses state)
            # from dialogs import ImageSlideshowWindow
            # slider_window = ImageSlideshowWindow(image_files, parent=self.parent_app)
            # slider_window.show()
            # Using Option 1 for now:
            self.parent_app.slider_window = ImageSlideshowWindow(image_files, parent=self.parent_app)
            self.parent_app.slider_window.show()
        else: return

    def on_all_tab_context_menu_requested(self, pos):
        # Needs access to parent_app's show_context_menu and callbacks
        # --- 이전 로직으로 복원 (ui_utils.show_context_menu 사용) ---
        show_context_menu(
            parent_widget=self.all_tab_view, # Pass the view as parent for the menu
            pos=pos,
            table_view=self.all_tab_view,
            register_callback=self.on_register_recommend_all_tab, 
            copy_callback=self.on_copy_rows_to_mylist_all,
            status_callback=self.parent_app.on_set_completed_status # Use parent app's status handler
        )

    def on_register_recommend_all_tab(self, index: QtCore.QModelIndex):
        """Handles the 'Register Recommend' action for the All Tab."""
        if hasattr(self.parent_app, 'do_register_recommend'):
            # Pass the index and the specific model to the parent app's handler
            self.parent_app.do_register_recommend(index, self.all_tab_model, calling_tab_name="AllTab")
        else:
            print("[ERROR] parent_app에 do_register_recommend 함수가 없습니다.")
            QtWidgets.QMessageBox.warning(self.parent_app, "오류", "추천 등록 기능을 실행할 수 없습니다.")

    def on_copy_rows_to_mylist_all(self):
        # 부모 앱의 do_copy_rows_to_mylist 함수를 호출하도록 변경
        if hasattr(self.parent_app, 'do_copy_rows_to_mylist'):
            is_admin_ = (self.parent_app.current_role == "admin")
            # 부모 앱의 함수 호출
            self.parent_app.do_copy_rows_to_mylist(
                table_view = self.all_tab_view,
                table_model = self.all_tab_model,
                is_admin = is_admin_
            )
        else:
            print("[ERROR] parent_app에 do_copy_rows_to_mylist 함수가 없습니다.")
            QMessageBox.warning(self.parent_app, "오류", "마이리스트 복사 기능을 실행할 수 없습니다.")

    def _auto_reload_all_tab_data(self):
        # 종료 상태 확인
        if self.is_shutting_down:
            logger.info("AllTab: 종료 중이므로 데이터 로드를 건너뜁니다.")
            return
            
        # parent_app이 유효한지 확인
        if not self.parent_app:
            logger.info("AllTab: parent_app이 None이므로 데이터 로드를 건너뜁니다.")
            return
            
        # parent_app이 종료 중인지 확인
        if hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
            logger.info("AllTab: 앱이 종료 중이므로 데이터 로드를 건너뜁니다.")
            return
            
        # Needs access to parent_app state and methods
        if not self.parent_app.from_customer_click and not self.parent_app.from_manager_click:
            return

        if self.parent_app.from_customer_click and self.parent_app.selected_addresses:
             self._auto_reload_all_tab_data_multi() # Call local version
             return

        if not self.parent_app.last_selected_address:
            self.populate_all_tab_view([])
            print("[INFO] AllTab: last_selected_address 없음 -> 0건")
            return

        unified_list = self._build_unified_rows_for_address(self.parent_app.last_selected_address)
        self.populate_all_tab_view(unified_list)
        # print(f"[INFO] AllTab => {len(unified_list)}건 (주소={self.parent_app.last_selected_address})")

    def _auto_reload_all_tab_data_multi(self):
        # 종료 상태 확인
        if self.is_shutting_down:
            logger.info("AllTab: 종료 중이므로 멀티 데이터 로드를 건너뜁니다.")
            return
            
        # parent_app이 유효한지 확인
        if not self.parent_app:
            logger.info("AllTab: parent_app이 None이므로 멀티 데이터 로드를 건너뜁니다.")
            return
            
        # parent_app이 종료 중인지 확인
        if hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
            logger.info("AllTab: 앱이 종료 중이므로 멀티 데이터 로드를 건너뜁니다.")
            return
            
        # Needs access to parent_app state and methods
        if not self.parent_app.selected_addresses:
            print("[WARN] AllTab selected_addresses is empty => 0건")
            self.populate_all_tab_view([])
            return

        big_list = []
        # --- MODIFIED: Get filters if from_customer_click is true --- 
        wanted_biz = None
        wanted_mgr = None
        if self.parent_app.from_customer_click:
            wanted_biz = getattr(self.parent_app, 'last_selected_customer_biz', None)
            wanted_mgr = getattr(self.parent_app, 'last_selected_customer_manager', None)
            print(f"[DEBUG][AllTab][_auto_reload_multi] Customer click detected. Applying filters: biz='{wanted_biz}', mgr='{wanted_mgr}'")
        # --- END MODIFIED ---
        
        for addr_str in self.parent_app.selected_addresses:
            # Pass filters to the build function
            # --- MODIFIED: Call _build_unified_rows_for_address without filters --- 
            partial_rows = self._build_unified_rows_for_address(addr_str)
            # --- END MODIFIED ---
            if partial_rows: big_list.extend(partial_rows)

        arranged_list = self.arrange_recommend_top_for_multiaddr(big_list, self.parent_app.selected_addresses)
        self.populate_all_tab_view(arranged_list)
        # print(f"[INFO] AllTab => {len(big_list)}건 (주소들={self.parent_app.selected_addresses})")

    def rebuild_and_populate_for_current_selection(self):
        """ Rebuilds the data based on parent_app's selection state and populates the AllTab view. """
        print(f"[DEBUG][AllTab] rebuild_and_populate_for_current_selection called.")
        print(f"[DEBUG][AllTab] Current state: from_customer_click={self.parent_app.from_customer_click}, selected_addresses={self.parent_app.selected_addresses}, last_selected_address={self.parent_app.last_selected_address}")

        unified_rows = []
        if self.parent_app.from_customer_click and self.parent_app.selected_addresses:
            print(f"[DEBUG][AllTab] Mode: Multi-address from customer click. Processing {len(self.parent_app.selected_addresses)} addresses.")
            # Customer click (multi-address mode)
            addresses_to_process = self.parent_app.selected_addresses
            # --- MODIFIED: Correctly get wanted_biz and wanted_mgr from parent_app ---
            wanted_biz = getattr(self.parent_app, 'last_selected_customer_biz', None)
            wanted_mgr = getattr(self.parent_app, 'last_selected_customer_manager', None)
            print(f"[DEBUG][AllTab] Customer selection: biz='{wanted_biz}', manager='{wanted_mgr}'. Fetching data for matched addresses and filtering RecommendTab.") # Corrected log
            # --- END MODIFIED ---
            for addr in addresses_to_process:
                # Pass the filters down, the build function will handle applying them where necessary
                unified_rows.extend(self._build_unified_rows_for_address(addr)) # Fetch all data first

        elif self.parent_app.last_selected_address:
            print(f"[DEBUG][AllTab] Mode: Single address selection: {self.parent_app.last_selected_address}")
            # Other tab click (single address mode)
            addr_ = self.parent_app.last_selected_address
            unified_rows.extend(self._build_unified_rows_for_address(addr_))
        else:
            print("[DEBUG][AllTab] Mode: No selection. Clearing table.")
            # No selection
            pass # unified_rows remains empty

        print(f"[DEBUG][AllTab] Populating table with {len(unified_rows)} unified rows.")
        self.populate_all_tab_view(unified_rows)

    def do_copy_rows_to_mylist(self, table_view: QTableView, table_model: QtGui.QStandardItemModel, is_admin: bool = False):
        """
        AllTab 내에서 처리하는 마이리스트 복사 함수.
        """
        from dialogs import MultiRowMemoDialog
        import requests
        import json
        
        # 선택 모델 확인
        selection_model = table_view.selectionModel()
        if not selection_model: 
            return
            
        # 선택된 인덱스 확인
        selected_indexes = selection_model.selectedIndexes()
        if not selected_indexes: 
            return
            
        # 선택된 행 인덱스 수집
        selected_rows = sorted(set(idx.row() for idx in selected_indexes))
        if not selected_rows: 
            QMessageBox.warning(self.parent_app, "복사", "선택된 레코드가 없습니다.")
            return

        # 행별 (id, source, address) 수집
        row_info_list = []
        for r in selected_rows:
            item_0 = table_model.item(r, 0)
            if not item_0: 
                continue
                
            pid = item_0.data(QtCore.Qt.UserRole + 3)  # ID
            src = item_0.data(QtCore.Qt.UserRole + 2)  # 출처 ("상가", "원룸", "확인", "추천")
            addr_str = item_0.text() or ""
            
            if not pid or not src: 
                print(f"[ERROR] 행 {r}에서 유효한 데이터를 찾을 수 없습니다: ID={pid}, 출처={src}")
                continue
                
            row_info_list.append({
                "id": pid,
                "src": src,
                "addr": addr_str
            })
            print(f"[DEBUG] 마이리스트 복사 - 행 {r} 데이터: ID={pid}, 출처={src}, 주소={addr_str}")

        # 유효한 행이 없으면 종료
        if not row_info_list: 
            QMessageBox.warning(self.parent_app, "복사", "유효한 데이터가 없습니다.")
            return

        # 다이얼로그로 행별 메모 입력받기
        dlg = MultiRowMemoDialog(row_info_list, manager=self.parent_app.current_manager, parent=self.parent_app)
        if dlg.exec_() != QDialog.Accepted: 
            return
            
        # 사용자가 입력한 메모 가져오기
        new_items = dlg.get_memo_list()
        
        # 디버깅 출력
        print(f"[DEBUG] 다이얼로그 결과 - 항목 수: {len(new_items)}")
        for idx, item in enumerate(new_items):
            print(f"[DEBUG] 항목 {idx+1}: ID={item.get('id')}, 출처={item.get('source')}, 메모={item.get('memo')}")

        # 관리자 선택
        chosen_manager = self.parent_app.current_manager
        if is_admin:
            managers = [self.parent_app.manager_dropdown.itemText(i) for i in range(self.parent_app.manager_dropdown.count())]
            manager, ok = QInputDialog.getItem(
                self.parent_app, "담당자 선택", "전송할 담당자 선택:", 
                managers, 0, False
            )
            if ok and manager: 
                chosen_manager = manager
            else: 
                return

        # API 요청 페이로드 및 URL 준비
        payload = {"items": new_items, "manager": chosen_manager}
        url = f"http://{self.server_host}:{self.server_port}/mylist/copy_to_mylist"
        
        print(f"[DEBUG] API 요청 - URL: {url}, 관리자: {chosen_manager}, 항목 수: {len(new_items)}")
        
        # 백그라운드에서 API 요청 전송
        future = self.parent_app.executor.submit(self._bg_copy_to_mylist, url, payload)
        future.add_done_callback(self._on_copy_to_mylist_done)
        
    def _bg_copy_to_mylist(self, url, payload):
        """백그라운드 스레드에서 마이리스트 복사 API 요청을 전송하는 함수"""
        import requests
        import traceback
        import json
        
        try:
            print(f"[DEBUG] API 요청 전송 시작 - URL: {url}")
            print(f"[DEBUG] 페이로드: {json.dumps(payload, ensure_ascii=False, indent=2)}")
            
            resp = requests.post(url, json=payload, timeout=10)
            print(f"[DEBUG] API 응답 상태 코드: {resp.status_code}")
            
            resp.raise_for_status()
            result = resp.json()
            print(f"[DEBUG] API 응답 내용: {json.dumps(result, ensure_ascii=False, indent=2)}")
            return result
            
        except requests.exceptions.RequestException as req_ex:
            print(f"[ERROR][AllTab] 요청 오류: {req_ex}")
            if hasattr(req_ex, 'response') and req_ex.response:
                print(f"[ERROR] 응답 내용: {req_ex.response.text}")
            return {
                "status": "exception",
                "message": f"요청 오류: {req_ex}\n{traceback.format_exc()}"
            }
        except Exception as ex:
            print(f"[ERROR][AllTab] _bg_copy_to_mylist 일반 오류: {ex}")
            return {
                "status": "exception",
                "message": f"일반 오류: {ex}\n{traceback.format_exc()}"
            }
            
    def _on_copy_to_mylist_done(self, future):
        """복사 작업 완료 후 호출되는 콜백 함수"""
        try:
            result = future.result()
            
            # GUI 업데이트는 메인 스레드에서 해야 함
            def update_ui():
                if not result:
                    QMessageBox.warning(self.parent_app, "복사 실패", "서버 응답이 없습니다.")
                    return
                
                if result.get("status") == "ok":
                    if result.get("errors") and len(result.get("errors", [])) > 0:
                        error_msg = "\n".join(result.get("errors", []))
                        QMessageBox.warning(self.parent_app, "복사 부분 성공", f"일부 항목이 복사되었으나, 다음 오류가 발생했습니다:\n{error_msg}")
                    else:
                        QMessageBox.information(self.parent_app, "복사 완료", "선택한 항목이 마이리스트로 복사되었습니다.")
                    
                    # 마이리스트 탭 데이터 리로드
                    if hasattr(self.parent_app.mylist_tab, 'sanga_logic') and self.parent_app.mylist_tab.sanga_logic:
                        self.parent_app.mylist_tab.sanga_logic.load_data()
                else:
                    err_msg = result.get("message", "알 수 없는 오류")
                    QMessageBox.critical(self.parent_app, "복사 실패", f"서버 오류:\n{err_msg}")
            
            # 메인 스레드에서 UI 업데이트 실행
            QtCore.QTimer.singleShot(0, update_ui)
            
        except Exception as e:
            print(f"[ERROR][AllTab] Failed to process copy result: {e}")
            
            def show_error():
                QMessageBox.critical(self.parent_app, "오류", f"결과 처리 중 오류 발생: {e}")
            
            QtCore.QTimer.singleShot(0, show_error)
        
    def _build_unified_rows_for_address(self, address_str: str) -> list:
        # Method moved from ExcelTableApp (originally found in main_app_part6.py)
        # Accesses parent_app's dictionaries (check_confirm_dict, etc.)
        logger.info(f"_build_unified_rows_for_address: Building unified rows for address: '{address_str}'") # 로그 추가
        unified_rows = []
        
        # 임시 비활성화: 중복 ID 처리 제거
        # processed_ids = set() # 중복 ID 처리용

        # 디버깅용 로그 추가
        logger.info("=== 임시: _build_unified_rows_for_address 내부 중복 제거 로직 비활성화됨 ===")

        # Retrieve filters if in customer click mode
        wanted_biz = None
        wanted_mgr = None
        if self.parent_app.from_customer_click:
            wanted_biz = getattr(self.parent_app, 'last_selected_customer_biz', None)
            wanted_mgr = getattr(self.parent_app, 'last_selected_customer_manager', None)
            print(f"[DEBUG][AllTab][_build_unified] Filtering RecommendTab data with biz='{wanted_biz}', mgr='{wanted_mgr}'")

        # 1. Recommend Tab Data
        rec_rows = self.parent_app.recommend_tab.get_data_for_address(address_str)
        print(f"[DEBUG][AllTab] Fetched {len(rec_rows)} rows from RecommendTab for '{address_str}'")
        for row in rec_rows:
            should_add = True
            # --- MODIFIED: Apply customer filter ONLY if from_customer_click is True and filters are set ---
            if self.parent_app.from_customer_click and wanted_biz is not None and wanted_mgr is not None:
                rec_biz = row.get("matching_biz", "")
                rec_mgr = row.get("manager", "")
                # Perform the check only if wanted_biz and wanted_mgr are not None
                if not (rec_biz == wanted_biz and rec_mgr == wanted_mgr):
                    should_add = False
                    # print(f"[DEBUG][AllTab] Recommend row skipped: biz='{rec_biz}'(wanted:'{wanted_biz}'), mgr='{rec_mgr}'(wanted:'{wanted_mgr}')") # Optional detailed log

            if should_add:
                all_unified = self._unify_recommend(row)
                source = all_unified.get("출처", "")
                # '추천' 출처의 row에는 추가 데이터 명시적 설정
                all_unified["source"] = "추천"  # 서버 처리용 출처 명시
                
                # 임시 비활성화: 중복 검사 제거, 모든 항목 추가
                unified_rows.append(all_unified)
                # if source in ("상가", "원룸"): # 추천 탭 데이터는 현재 '추천' 출처를 가지므로 이 조건은 항상 False
                #     full_id = f"{all_unified['주소']}_{all_unified['호']}_{all_unified['층']}_{all_unified['보증금/월세']}_{all_unified['관리비']}_{all_unified['권리금']}_{all_unified['현업종']}_{all_unified['평수']}_{all_unified['연락처']}_{all_unified['매물번호']}"
                #     if full_id not in processed_ids:
                #         processed_ids.add(full_id)
                #         unified_rows.append(all_unified)
                # else: # '추천' 출처 데이터는 중복 검사 없이 추가
                #     unified_rows.append(all_unified)
            # --- END MODIFIED ---

        # 2. Check Confirm Tab Data (No biz/manager filter applied here for AllTab)
        conf_rows = self.parent_app.check_confirm_tab.get_data_for_address(address_str)
        print(f"[DEBUG][AllTab] Fetched {len(conf_rows)} rows from CheckConfirmTab for '{address_str}'")
        for row in conf_rows:
            all_unified = self._unify_confirm(row)
            # 임시 비활성화: 중복 검사 제거, 모든 항목 추가
            unified_rows.append(all_unified)
            # source = all_unified.get("출처", "")
            # if source in ("상가", "원룸"): # 확인 탭 데이터는 현재 '확인' 출처를 가지므로 이 조건은 항상 False
            #     full_id = f"{all_unified['주소']}_{all_unified['호']}_{all_unified['층']}_{all_unified['보증금/월세']}_{all_unified['관리비']}_{all_unified['권리금']}_{all_unified['현업종']}_{all_unified['평수']}_{all_unified['연락처']}_{all_unified['매물번호']}"
            #     if full_id not in processed_ids:
            #         processed_ids.add(full_id)
            #         unified_rows.append(all_unified)
            # else: # '확인' 출처 데이터는 중복 검사 없이 추가
            #     unified_rows.append(all_unified)

        # 3. Serve Shop Tab Data
        shop_rows = self.parent_app.serve_shop_tab.get_data_for_address(address_str)
        print(f"[DEBUG][AllTab] Fetched {len(shop_rows)} rows from ServeShopTab for '{address_str}'")
        for row in shop_rows:
            all_unified = self._unify_shop(row)
            # 임시 비활성화: 중복 검사 제거, 모든 항목 추가
            unified_rows.append(all_unified)
            # source = all_unified.get("출처", "")
            # if source in ("상가", "원룸"): # '상가' 출처 데이터는 중복 검사 수행
            #     full_id = f"{all_unified['주소']}_{all_unified['호']}_{all_unified['층']}_{all_unified['보증금/월세']}_{all_unified['관리비']}_{all_unified['권리금']}_{all_unified['현업종']}_{all_unified['평수']}_{all_unified['연락처']}_{all_unified['매물번호']}"
            #     if full_id not in processed_ids:
            #         processed_ids.add(full_id)
            #         unified_rows.append(all_unified)
            # else: # 혹시 다른 출처가 있다면 검사 없이 추가 (이론상 실행 안 됨)
            #     unified_rows.append(all_unified)

        # 4. Serve Oneroom Tab Data
        oneroom_rows = self.parent_app.serve_oneroom_tab.get_data_for_address(address_str)
        print(f"[DEBUG][AllTab] Fetched {len(oneroom_rows)} rows from ServeOneroomTab for '{address_str}'")
        for row in oneroom_rows:
            all_unified = self._unify_oneroom(row)
            # 임시 비활성화: 중복 검사 제거, 모든 항목 추가
            unified_rows.append(all_unified)
            # source = all_unified.get("출처", "")
            # if source in ("상가", "원룸"): # '원룸' 출처 데이터는 중복 검사 수행
            #     full_id = f"{all_unified['주소']}_{all_unified['호']}_{all_unified['층']}_{all_unified['보증금/월세']}_{all_unified['관리비']}_{all_unified['권리금']}_{all_unified['현업종']}_{all_unified['평수']}_{all_unified['연락처']}_{all_unified['매물번호']}"
            #     if full_id not in processed_ids:
            #         processed_ids.add(full_id)
            #         unified_rows.append(all_unified)
            # else: # 혹시 다른 출처가 있다면 검사 없이 추가 (이론상 실행 안 됨)
            #     unified_rows.append(all_unified)

        # 5. MyList Shop Tab Data (If needed)
        if hasattr(self.parent_app, 'mylist_shop_tab'):
            mylist_rows = self.parent_app.mylist_shop_tab.get_data_for_address(address_str)
            print(f"[DEBUG][AllTab] Fetched {len(mylist_rows)} rows from MyListShopTab for '{address_str}'")
            for row in mylist_rows:
                all_unified = self._unify_mylist_shop(row)
                # 임시 비활성화: 중복 검사 제거, 모든 항목 추가
                unified_rows.append(all_unified)
                # source = all_unified.get("출처", "")
                # if source in ("상가", "원룸"): # 마이리스트 데이터는 '마이리스트(상가)' 출처이므로 이 조건은 False
                #     full_id = f"{all_unified['주소']}_{all_unified['호']}_{all_unified['층']}_{all_unified['보증금/월세']}_{all_unified['관리비']}_{all_unified['권리금']}_{all_unified['현업종']}_{all_unified['평수']}_{all_unified['연락처']}_{all_unified['매물번호']}"
                #     if full_id not in processed_ids:
                #         processed_ids.add(full_id)
                #         unified_rows.append(all_unified)
                # else: # '마이리스트(상가)' 출처 데이터는 중복 검사 없이 추가
                #     unified_rows.append(all_unified)

        # 6. Completed Deals Tab Data (If needed)
        if hasattr(self.parent_app, 'completed_deals_tab'):
            completed_rows = self.parent_app.completed_deals_tab.get_data_for_address(address_str)
            print(f"[DEBUG][AllTab] Fetched {len(completed_rows)} rows from CompletedDealsTab for '{address_str}'")
            for row in completed_rows:
                all_unified = self._unify_completed_deal(row)
                # 임시 비활성화: 중복 검사 제거, 모든 항목 추가
                unified_rows.append(all_unified)
                # source = all_unified.get("출처", "")
                # if source in ("상가", "원룸"): # 계약완료 데이터는 '계약완료' 출처이므로 이 조건은 False
                #     full_id = f"{all_unified['주소']}_{all_unified['호']}_{all_unified['층']}_{all_unified['보증금/월세']}_{all_unified['관리비']}_{all_unified['권리금']}_{all_unified['현업종']}_{all_unified['평수']}_{all_unified['연락처']}_{all_unified['매물번호']}"
                #     if full_id not in processed_ids:
                #         processed_ids.add(full_id)
                #         unified_rows.append(all_unified)
                # else: # '계약완료' 출처 데이터는 중복 검사 없이 추가
                #     unified_rows.append(all_unified)

        # --- DEBUG: Print final count before returning ---
        logger.info(f"_build_unified_rows_for_address: Finished building. Returning {len(unified_rows)} rows for '{address_str}'.") # 로그 추가
        return unified_rows

    # --- ADDED SLOT ---    
    @pyqtSlot(str)
    def _handle_data_loaded_for_address(self, addr_str: str):
        """ Slot to handle signals when data for a specific address is loaded in another tab. """
        # print(f"[DEBUG][AllTab] Received signal: data loaded for address '{addr_str}'") # Commented out this log

        # Check if the loaded address matches the current selection state
        should_rebuild = False
        if self.parent_app.from_customer_click and self.parent_app.selected_addresses:
            # Multi-address mode: rebuild if the loaded address is in the selected list
            if addr_str in self.parent_app.selected_addresses:
                should_rebuild = True
            else:
                 # print(f"[DEBUG][AllTab] Data loaded for '{addr_str}' but it's not in the current multi-selection. Ignoring.") # Keep commented unless needed
                 pass
        elif self.parent_app.last_selected_address:
            # Single address mode: rebuild only if the loaded address matches the selected one
            if addr_str == self.parent_app.last_selected_address:
                should_rebuild = True
            else:
                # print(f"[DEBUG][AllTab] Data loaded for '{addr_str}' but it doesn't match current selection '{self.parent_app.last_selected_address}'. Ignoring.") # Keep commented unless needed
                pass
        else:
            # No selection active, no need to rebuild based on this signal
            # print(f"[DEBUG][AllTab] Data loaded for '{addr_str}' but no selection active. Ignoring.") # Keep commented unless needed
            pass

        if should_rebuild:
            # Call the method that handles rebuilding the unified list and populating the view
            self.rebuild_and_populate_for_current_selection()

    def check_caches_for_address(self, addr_str: str):
        """모든 캐시에서 특정 주소의 데이터 존재 여부를 확인하고 로그로 출력"""
        print(f"[DEBUG][AllTab] Checking caches for address: '{addr_str}'")
        
        # 각 탭에서 주소 데이터 확인
        tab_caches = []
        
        # 1. CheckConfirmTab 확인
        if hasattr(self.parent_app, 'check_confirm_tab') and hasattr(self.parent_app.check_confirm_tab, 'get_data_for_address'):
            confirm_rows = self.parent_app.check_confirm_tab.get_data_for_address(addr_str)
            tab_caches.append(('CheckConfirmTab', len(confirm_rows)))
            
        # 2. ServeShopTab 확인
        if hasattr(self.parent_app, 'serve_shop_tab') and hasattr(self.parent_app.serve_shop_tab, 'get_data_for_address'):
            shop_rows = self.parent_app.serve_shop_tab.get_data_for_address(addr_str)
            tab_caches.append(('ServeShopTab', len(shop_rows)))
            
        # 3. ServeOneroomTab 확인
        if hasattr(self.parent_app, 'serve_oneroom_tab') and hasattr(self.parent_app.serve_oneroom_tab, 'get_data_for_address'):
            oneroom_rows = self.parent_app.serve_oneroom_tab.get_data_for_address(addr_str)
            tab_caches.append(('ServeOneroomTab', len(oneroom_rows)))
            
        # 4. RecommendTab 확인
        if hasattr(self.parent_app, 'recommend_tab') and hasattr(self.parent_app.recommend_tab, 'get_data_for_address'):
            recommend_rows = self.parent_app.recommend_tab.get_data_for_address(addr_str)
            tab_caches.append(('RecommendTab', len(recommend_rows)))
            
        # 5. CompletedDealsTab 확인
        if hasattr(self.parent_app, 'completed_deals_tab') and hasattr(self.parent_app.completed_deals_tab, 'get_data_for_address'):
            completed_rows = self.parent_app.completed_deals_tab.get_data_for_address(addr_str)
            tab_caches.append(('CompletedDealsTab', len(completed_rows)))
            
        # 6. MyListShopTab 확인
        if hasattr(self.parent_app, 'mylist_shop_tab') and hasattr(self.parent_app.mylist_shop_tab, 'get_data_for_address'):
            mylist_shop_rows = self.parent_app.mylist_shop_tab.get_data_for_address(addr_str)
            tab_caches.append(('MyListShopTab', len(mylist_shop_rows)))
            
        # 결과 출력
        print(f"[DEBUG][AllTab] Cache check results for '{addr_str}':")
        for tab_name, row_count in tab_caches:
            print(f"  - {tab_name}: {row_count} rows")
            
        # 주소 문자열 검사 - 만약 유사한 주소가 있는지 확인
        if hasattr(self.parent_app, 'mylist_shop_tab') and hasattr(self.parent_app.mylist_shop_tab, 'mylist_shop_dict'):
            similar_addresses = []
            for cache_addr in self.parent_app.mylist_shop_tab.mylist_shop_dict.keys():
                # 공백 제거 후 비교
                cleaned_addr = cache_addr.strip()
                cleaned_search = addr_str.strip()
                
                if cleaned_addr == cleaned_search:
                    continue  # 정확히 일치하는 주소는 이미 위에서 확인함
                
                # 유사도 검사 (부분 문자열 포함 여부)
                if cleaned_search in cleaned_addr or cleaned_addr in cleaned_search:
                    similar_addresses.append(cache_addr)
                    
            if similar_addresses:
                print(f"[DEBUG][AllTab] Found {len(similar_addresses)} similar addresses in MyListShopTab cache:")
                for similar in similar_addresses[:5]:  # 최대 5개만 출력
                    print(f"  - '{similar}'")
        
        return tab_caches 

    # --- ADDED Unification Methods (Adapted from server.py) ---

    def _decide_status(self, row_dict: dict, source: str) -> str:
        """Determines the status string based on row data and source."""
        status_cd = str(row_dict.get("status_cd", "")).strip()
        ad_end_date_str = row_dict.get("ad_end_date", "")

        if status_cd == "4":
            return "계약완료"
        elif status_cd == "3":
             return "등록종료" # Explicitly marked as ended

        # If status code isn't definitive, check ad_end_date
        if ad_end_date_str:
            try:
                ad_end_date = datetime.strptime(ad_end_date_str.split(" ")[0], "%Y-%m-%d").date()
                today = date.today()
                if ad_end_date < today:
                    return "등록종료" # Expired
                else:
                    # Check if it's from 'serve_oneroom_data' - different logic?
                    # Based on original _unify_oneroom_rows, oneroom seems to default to '서비스중' if date exists and not expired
                    # if source == "원룸": return "서비스중"
                    # For others like '상가', it seems to be '서비스중' too
                    return "서비스중" # Active
            except Exception:
                 # Invalid date format - treat as uncertain for serve sources
                 if source in ["상가", "원룸"]:
                     return "확인필요"
                 else: # For other sources like recommend, maybe default differently? Let's stick to 확인필요
                     return "확인필요" # Or maybe "등록종료"? Let's assume needs check.
        else:
            # No ad_end_date provided
            # Original logic defaulted to '등록종료' for shop/oneroom if no date.
            # Recommend also defaulted to '등록종료' if no date.
            if source in ["상가", "원룸", "추천"]:
                 return "등록종료"
            else:
                 # For confirm, mylist - status is determined differently (e.g., "새광고", check_memo)
                 # This function might not be called or needed for those sources if status is explicit.
                 return "" # Return empty if logic doesn't apply

    def _unify_oneroom(self, row):
        unified = {}
        full_address = (row.get("dong", "") + " " + row.get("jibun", "")).strip()
        unified["주소"] = full_address
        unified["호"] = row.get("ho", "")
        cf = row.get("curr_floor", 0); tf = row.get("total_floor", 0)
        unified["층"] = f"{cf}/{tf}"
        dp = row.get("deposit", 0); mn = row.get("monthly", 0)
        unified["보증금/월세"] = f"{dp}/{mn}"
        unified["관리비"] = str(row.get("manage_fee", ""))
        unified["권리금"] = row.get("password", "")  # Oneroom uses 'password' field for '권리금' column? Check UI intent. Assuming yes for now.
        unified["현업종"] = row.get("in_date", "") # Oneroom uses 'in_date' for '현업종' column? Check UI intent. Assuming yes.
        area_val = row.get("area", 0)
        try: unified["평수"] = float(area_val)
        except: unified["평수"] = 0.0
        unified["연락처"] = row.get("owner_phone", "")
        n_no = row.get("naver_property_no", ""); s_no = row.get("serve_property_no", "")
        mb_val = ""
        if n_no and s_no: mb_val = "N,S"
        elif n_no: mb_val = "N"
        elif s_no: mb_val = "S"
        unified["매물번호"] = mb_val
        unified["naver_no"] = n_no
        unified["serve_no"] = s_no
        unified["제목"] = row.get("memo", "")
        unified["매칭업종"] = row.get("manager", "") # Manager name
        unified["확인메모"] = self._decide_status(row, "원룸")
        unified["주차대수"] = row.get("parking", "")
        unified["용도"] = row.get("building_usage", "")
        unified["사용승인일"] = row.get("approval_date", "")
        rm, bt = row.get("rooms", 0), row.get("baths", 0)
        unified["방/화장실"] = f"{rm}/{bt}"
        unified["광고등록일"] = "" # This source doesn't seem to have ad_start_date
        unified["사진경로"] = row.get("photo_path", "")
        unified["소유자명"] = row.get("owner_name", "")
        unified["관계"] = row.get("owner_relation", "")
        unified["광고종료일"] = row.get("ad_end_date", "")
        unified["출처"] = "원룸"
        unified["id"] = row.get("id", 0)
        return unified

    def _unify_shop(self, row):
        unified = {}
        full_address = (row.get("dong", "") + " " + row.get("jibun", "")).strip()
        unified["주소"] = full_address
        unified["호"] = row.get("ho", "")
        cf = row.get("curr_floor", 0); tf = row.get("total_floor", 0)
        unified["층"] = f"{cf}/{tf}"
        unified["보증금/월세"] = f"{row.get('deposit', 0)}/{row.get('monthly', 0)}"
        unified["관리비"] = str(row.get("manage_fee", ""))
        unified["권리금"] = str(row.get("premium", ""))
        unified["현업종"] = str(row.get("current_use", ""))
        try: unified["평수"] = float(row.get("area", 0))
        except: unified["평수"] = 0.0
        unified["연락처"] = row.get("owner_phone", "")
        n_no = row.get("naver_property_no", ""); s_no = row.get("serve_property_no", "")
        mb_val = ""
        if n_no and s_no: mb_val = "N,S"
        elif n_no: mb_val = "N"
        elif s_no: mb_val = "S"
        unified["매물번호"] = mb_val
        unified["naver_no"] = n_no
        unified["serve_no"] = s_no
        unified["제목"] = row.get("memo", "")
        unified["매칭업종"] = row.get("manager", "") # Manager name
        unified["확인메모"] = self._decide_status(row, "상가")
        unified["주차대수"] = row.get("parking", "")
        unified["용도"] = row.get("building_usage", "")
        unified["사용승인일"] = row.get("approval_date", "")
        rm, bt = row.get("rooms", 0), row.get("baths", 0)
        unified["방/화장실"] = f"{rm}/{bt}"
        unified["광고등록일"] = "" # This source doesn't seem to have ad_start_date
        unified["사진경로"] = row.get("photo_path", "")
        unified["소유자명"] = row.get("owner_name", "")
        unified["관계"] = row.get("owner_relation", "")
        unified["광고종료일"] = row.get("ad_end_date", "")
        unified["출처"] = "상가"
        unified["id"] = row.get("id", 0)
        return unified

    def _unify_confirm(self, row):
        unified = {}
        full_address = (row.get("dong", "") + " " + row.get("jibun", "")).strip()
        unified["주소"] = full_address
        unified["호"] = row.get("ho", "")
        cf = row.get("curr_floor", 0); tf = row.get("total_floor", 0)
        unified["층"] = f"{cf}/{tf}"
        deposit = row.get("deposit", 0); monthly = row.get("monthly", 0)
        unified["보증금/월세"] = f"{deposit}/{monthly}"
        unified["관리비"] = str(row.get("manage_fee", ""))
        unified["권리금"] = str(row.get("premium", ""))
        unified["현업종"] = str(row.get("current_use", ""))
        try: unified["평수"] = float(row.get("area", 0))
        except: unified["평수"] = 0.0
        unified["연락처"] = row.get("owner_phone", "")
        n_no = row.get("naver_property_no", ""); s_no = row.get("serve_property_no", "")
        mb_val = ""
        if n_no and s_no: mb_val = "N,S"
        elif n_no: mb_val = "N"
        elif s_no: mb_val = "S"
        unified["매물번호"] = mb_val
        unified["naver_no"] = n_no
        unified["serve_no"] = s_no
        unified["제목"] = row.get("memo", "") # Confirm uses 'memo' for the '제목' field
        manager_ = row.get("manager", "")
        # Confirm items have biz type stored in check_memo JSON -> "matching_biz_type"
        biz_ = ""
        try:
             check_memo_json = json.loads(row.get("check_memo","{}"))
             biz_ = check_memo_json.get("matching_biz_type","")
        except json.JSONDecodeError:
             pass # Keep biz_ empty if JSON fails
        biz_str = f"{biz_}({manager_})" if biz_ else manager_
        unified["매칭업종"] = biz_str
        # '확인메모' comes from check_memo field in confirm table
        unified["확인메모"] = row.get("check_memo", "") # Or parse JSON if needed? Assume raw string for now.
        unified["주차대수"] = row.get("parking", "")
        unified["용도"] = row.get("building_usage", "")
        unified["사용승인일"] = row.get("approval_date", "")
        rm = row.get("rooms", 0); bt = row.get("baths", 0)
        unified["방/화장실"] = f"{rm}/{bt}"
        unified["광고등록일"] = row.get("ad_start_date", "") # Confirm has ad_start_date
        unified["사진경로"] = row.get("photo_path", "")
        unified["소유자명"] = row.get("owner_name", "")
        unified["관계"] = row.get("owner_relation", "")
        unified["광고종료일"] = "" # Confirm items don't have ad_end_date from source
        unified["출처"] = "확인"
        unified["id"] = row.get("confirm_id", 0) # Use confirm_id
        return unified

    def _unify_recommend(self, row):
        # Recommend data structure seems similar to Serve Shop based on server endpoint
        unified = {}
        full_address = (row.get("dong", "") + " " + row.get("jibun", "")).strip()
        unified["주소"] = full_address
        unified["호"] = row.get("ho", "")
        cf = row.get("curr_floor", 0); tf = row.get("total_floor", 0)
        unified["층"] = f"{cf}/{tf}"
        unified["보증금/월세"] = f"{row.get('deposit', 0)}/{row.get('monthly', 0)}"
        unified["관리비"] = str(row.get("manage_fee", ""))
        unified["권리금"] = str(row.get("premium", ""))
        unified["현업종"] = str(row.get("current_use", ""))
        try: unified["평수"] = float(row.get("area", 0))
        except: unified["평수"] = 0.0
        unified["연락처"] = row.get("owner_phone", "")
        n_no = row.get("naver_property_no", ""); s_no = row.get("serve_property_no", "")
        mb_val = ""
        if n_no and s_no: mb_val = "N,S"
        elif n_no: mb_val = "N"
        elif s_no: mb_val = "S"
        unified["매물번호"] = mb_val
        unified["naver_no"] = n_no
        unified["serve_no"] = s_no
        unified["제목"] = row.get("memo", "")
        # Recommended items have matching_biz and manager fields directly
        biz_ = row.get("matching_biz", "")
        manager_ = row.get("manager", "")
        biz_str = f"{biz_}({manager_})" if biz_ else manager_
        unified["매칭업종"] = biz_str
        unified["확인메모"] = row.get("check_memo", "") # Use check_memo directly
        unified["주차대수"] = row.get("parking", "")
        unified["용도"] = row.get("building_usage", "")
        unified["사용승인일"] = row.get("approval_date", "")
        rm, bt = row.get("rooms", 0), row.get("baths", 0)
        unified["방/화장실"] = f"{rm}/{bt}"
        unified["광고등록일"] = "" # Recommend source doesn't have ad_start_date
        unified["사진경로"] = row.get("photo_path", "")
        unified["소유자명"] = row.get("owner_name", "")
        unified["관계"] = row.get("owner_relation", "")
        unified["광고종료일"] = row.get("ad_end_date", "") # Recommend has ad_end_date
        unified["출처"] = "추천"
        unified["id"] = row.get("id", 0)

        return unified

    def _unify_mylist_shop(self, row):
        # Structure based on _unify_mylist_shop_rows
        unified = {}
        full_address = (row.get("dong","") + " " + row.get("jibun","")).strip()
        unified["주소"] = full_address
        unified["호"] = row.get("ho","")
        cf = row.get("curr_floor",0); tf = row.get("total_floor",0)
        unified["층"] = f"{cf}/{tf}"
        dp = row.get("deposit",0); mn = row.get("monthly",0)
        unified["보증금/월세"] = f"{dp}/{mn}"
        mg_ = row.get("manage_fee","")
        unified["관리비"] = str(mg_)
        premium_ = row.get("premium","")
        unified["권리금"] = str(premium_)
        unified["현업종"] = row.get("current_use","")
        area_ = row.get("area","")
        try: unified["평수"] = float(area_)
        except: unified["평수"] = 0.0
        unified["연락처"] = row.get("owner_phone","")
        n_no = row.get("naver_property_no",""); s_no = row.get("serve_property_no","")
        mb_val = ""
        if n_no and s_no: mb_val = "N,S"
        elif n_no: mb_val = "N"
        elif s_no: mb_val = "S"
        unified["매물번호"] = mb_val
        unified["naver_no"] = n_no; unified["serve_no"] = s_no
        unified["제목"] = row.get("memo","")
        unified["매칭업종"] = row.get("manager","") # Manager name
        unified["확인메모"] = "새광고" # MyList items are always "새광고" status in AllTab
        unified["광고종료일"] = row.get("ad_end_date","") # MyList seems to have ad_end_date
        unified["주차대수"] = row.get("parking","")
        unified["용도"] = row.get("building_usage","")
        unified["사용승인일"] = row.get("approval_date","")
        rm_ = row.get("rooms",""); bt_ = row.get("baths","")
        unified["방/화장실"] = f"{rm_}/{bt_}"
        unified["광고등록일"] = row.get("ad_start_date","") # MyList has ad_start_date
        unified["사진경로"] = row.get("photo_path","")
        unified["소유자명"] = row.get("owner_name","")
        unified["관계"] = row.get("owner_relation","")
        unified["출처"] = "마이리스트(상가)"
        unified["id"] = row.get("id", 0)
        return unified

    def _unify_completed_deal(self, row):
        # Structure based on _unify_completed_deals_rows
        unified = {}
        full_address = (row.get("dong", "") + " " + row.get("jibun", "")).strip()
        unified["주소"] = full_address
        unified["호"] = row.get("ho", "")
        cf = row.get("curr_floor", 0); tf = row.get("total_floor", 0)
        unified["층"] = f"{cf}/{tf}"
        deposit = row.get("deposit", 0); monthly = row.get("monthly", 0)
        unified["보증금/월세"] = f"{deposit}/{monthly}"
        unified["관리비"] = str(row.get("manage_fee", ""))
        unified["권리금"] = str(row.get("premium", ""))
        unified["현업종"] = str(row.get("current_use", ""))
        try: unified["평수"] = float(row.get("area", 0))
        except: unified["평수"] = 0.0
        unified["연락처"] = row.get("owner_phone", "")
        n_no = row.get("naver_property_no", ""); s_no = row.get("serve_property_no", "")
        mb_val = ""
        if n_no and s_no: mb_val = "N,S"
        elif n_no: mb_val = "N"
        elif s_no: mb_val = "S"
        unified["매물번호"] = mb_val
        unified["naver_no"] = n_no
        unified["serve_no"] = s_no
        unified["제목"] = row.get("memo", "")
        # Completed deals might store biz/manager in the check_memo or similar field from original source?
        # Or directly have manager/matching_biz? Assuming similar to 'confirm' for now.
        manager_ = row.get("manager", "") # Directly use manager if available
        biz_ = row.get("matching_biz_type", "") # Directly use biz if available
        # Fallback: try parsing check_memo if fields above are empty
        if not biz_ and not manager_:
             try:
                  check_memo_json = json.loads(row.get("check_memo","{}"))
                  biz_ = check_memo_json.get("matching_biz_type","")
                  # manager_ = check_memo_json.get("manager","") # Does check_memo contain manager? Use row's manager field preferentially
             except json.JSONDecodeError:
                  pass
        biz_str = f"{biz_}({manager_})" if biz_ else manager_
        unified["매칭업종"] = biz_str
        unified["확인메모"] = "계약완료" # Status is always "계약완료"
        unified["주차대수"] = row.get("parking", "")
        unified["용도"] = row.get("building_usage", "")
        unified["사용승인일"] = row.get("approval_date", "")
        rm, bt = row.get("rooms", 0), row.get("baths", 0)
        unified["방/화장실"] = f"{rm}/{bt}"
        unified["광고등록일"] = row.get("ad_start_date", "") # Completed deals retain start date
        unified["사진경로"] = row.get("photo_path", "")
        unified["소유자명"] = row.get("owner_name", "")
        unified["관계"] = row.get("owner_relation", "")
        unified["광고종료일"] = row.get("ad_end_date", "") # Completed deals retain end date
        unified["출처"] = "계약완료"
        unified["id"] = row.get("id", 0) # Use completed_deals table's id
        return unified 