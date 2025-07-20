import sys
import os
import glob
import requests
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5 import sip  # PyQt5 패키지에 포함된 sip 모듈 사용
from PyQt5.QtWidgets import (
    QTableView, QAbstractItemView, QHeaderView, QMenu, 
    QWidget, QVBoxLayout, QMessageBox
)
import concurrent.futures
import traceback
from PyQt5.QtCore import pyqtSignal, QObject
from ui_utils import restore_qtableview_column_widths, save_qtableview_column_widths
from dialogs import RecommendDialog, StatusChangeDialog

class RecommendTab(QObject):
    data_loaded_for_address = pyqtSignal(str)

    def __init__(self, parent_app=None, server_host=None, server_port=None):
        super().__init__()
        """추천 탭 클래스 초기화"""
        self.parent_app = parent_app
        self.server_host = server_host
        self.server_port = server_port
        self.recommend_tab_model = None
        self.recommend_tab_view = None
        self.recommend_tab_timer = None
        self.loading_data_flag = False
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        self.recommend_dict = {} # 추천 매물 캐시
        self.is_shutting_down = False  # 종료 중 플래그

    def init_tab(self, main_tabs_widget):
        """
        '추천매물' 탭 UI 컴포넌트 초기화.
        """
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)

        self.recommend_tab_model = QtGui.QStandardItemModel()
        headers = self._get_headers() # 헤더 가져오기
        self.recommend_tab_model.setColumnCount(len(headers))
        self.recommend_tab_model.setHorizontalHeaderLabels(headers)

        self.recommend_tab_view = QtWidgets.QTableView()
        self.recommend_tab_view.setModel(self.recommend_tab_model)
        self.recommend_tab_view.setSortingEnabled(True)
        self.recommend_tab_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)

        # 초기 정렬 (예: 추천일 기준 내림차순, 13번 열이라고 가정)
        # 실제 열 인덱스는 headers 리스트에서 확인 필요
        try:
            # 헤더 이름이 '추천일' 또는 유사한 이름으로 되어있다고 가정
            recommend_date_col_idx = headers.index("추천일") # 또는 "광고종료일" 등 실제 헤더 이름
            self.recommend_tab_view.sortByColumn(recommend_date_col_idx, QtCore.Qt.DescendingOrder)
        except ValueError:
            print("[WARN] RecommendTab: Could not find '추천일' column for initial sort.")
            # 필요하다면 다른 열 기준으로 정렬하거나 정렬 없이 진행
            pass

        # self.recommend_tab_view.clicked.connect(self.on_recommend_tab_clicked) # 필요 시 연결

        layout.addWidget(self.recommend_tab_view)
        container.setLayout(layout)

        # main_tabs_widget에 탭 추가
        main_tabs_widget.addTab(container, "추천매물")

        # Restore column widths using utility function
        restore_qtableview_column_widths(
            self.parent_app.settings_manager, 
            self.recommend_tab_view, 
            "RecommendTabTable"
        )
        # Save column widths on resize using utility function
        self.recommend_tab_view.horizontalHeader().sectionResized.connect(
            lambda: save_qtableview_column_widths(
                self.parent_app.settings_manager, 
                self.recommend_tab_view, 
                "RecommendTabTable"
            )
        )

        # 타이머 설정 및 시작
        try:
            # 이미 종료 상태인지 확인
            if self.is_shutting_down:
                print("[INFO] RecommendTab: 이미 종료 중이므로 타이머를 시작하지 않습니다.")
                return
                
            # [자동 타이머 비활성화] 성능 최적화를 위해 자동 리로드 타이머를 비활성화함
            # 사용자가 필요시 수동으로 새로고침하도록 변경
            print("[INFO] RecommendTab: 자동 리로드 타이머가 성능 최적화를 위해 비활성화되었습니다.")
            
            # self.recommend_tab_timer = QtCore.QTimer(self.parent_app)
            # self.recommend_tab_timer.setInterval(10 * 1000)  # 10초 간격
            
            # # 연결 전에 기존 연결이 있는지 확인하고 해제
            # try:
            #     # 새로 만든 타이머이므로 연결 오류는 없겠지만 안전하게 처리
            #     self.recommend_tab_timer.timeout.disconnect()
            # except (TypeError, RuntimeError):
            #     # 기존 연결이 없으면 오류가 발생하므로 무시
            #     pass
                
            # self.recommend_tab_timer.timeout.connect(self.auto_reload_recommend_tab_data)
            
            # [제거됨] 초기 데이터 로드 - 성능 최적화를 위해 비활성화
            # 필요시 사용자가 주소 선택 시 filter_and_populate()에서 실시간 로드됨
            # self.auto_reload_recommend_tab_data() # 비활성화
            
            # # 타이머 시작
            # self.recommend_tab_timer.start()
            # print("[INFO] RecommendTab: 타이머 시작 완료 (10초 간격)")
        except Exception as e:
            print(f"[ERROR] RecommendTab: 타이머 초기화 중 오류 발생: {e}")
            import traceback
            print(traceback.format_exc())

    def auto_reload_recommend_tab_data(self):
        """
        타이머에 의해 호출되어 현재 사용자의 모든 추천 매물 데이터를 백그라운드에서 로드.
        (이제 new_addresses 에 의존하지 않음)
        """
        # 먼저 앱이 종료 중인지 확인
        if self.is_shutting_down:
            print("[INFO] RecommendTab: 종료 중이므로 데이터 로드를 건너뜁니다.")
            return
            
        # parent_app이 유효한지 확인
        if not self.parent_app:
            print("[INFO] RecommendTab: parent_app이 None이므로 데이터 로드를 건너뜁니다.")
            return
            
        # parent_app이 종료 중인지 확인
        if hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
            print("[INFO] RecommendTab: 앱이 종료 중이므로 데이터 로드를 건너뜁니다.")
            return
            
        # executor가 이미 종료 상태인지 확인
        if (not hasattr(self.parent_app, 'executor') or 
            self.parent_app.executor is None or
            (hasattr(self.parent_app.executor, '_shutdown') and 
             self.parent_app.executor._shutdown)):
            print("[WARN] RecommendTab: Executor is already shut down, skipping auto reload")
            return
            
        try:
            future = self.parent_app.executor.submit(
                self._bg_load_recommend_data # Pass no address list
            )
            future.add_done_callback(self._on_recommend_data_fetched)
        except RuntimeError as e:
            print(f"[WARN] RecommendTab: RuntimeError during executor submit: {e}")
        except Exception as e:
            print(f"[ERROR] RecommendTab: 데이터 로드 요청 중 예외 발생: {e}")
            import traceback
            print(traceback.format_exc())

    def _bg_load_recommend_data(self):
        """
        (Background Thread) Fetches ALL recommend data from the server.
        Server endpoint now ignores manager/role.
        """
        url = f"http://{self.server_host}:{self.server_port}/recommend/get_recommend_data"
        
        try:
            resp = requests.post(url, json={}, timeout=10) # 빈 JSON으로 POST 요청 (서버가 POST body를 기대할 경우)
            
            resp.raise_for_status()
            j = resp.json()
            if j.get("status") == "ok":
                return {"status": "ok", "data": j.get("data", [])}
            else:
                print(f"[ERROR] RecommendTab _bg_load: Server error: {j}")
                return {"status": "error", "data": [], "message": j.get("message", "Unknown server error")}
        except requests.exceptions.RequestException as ex:
            print(f"[ERROR] RecommendTab _bg_load: Request failed: {ex}")
            return {"status": "exception", "message": str(ex), "data": []}
        except Exception as ex:
             print(f"[ERROR] RecommendTab _bg_load: Unexpected error: {ex}")
             return {"status": "exception", "message": str(ex), "data": []}


    def _on_recommend_data_fetched(self, future):
        """
        (Main Thread) Processes fetched data, updates cache, and populates view.
        """
        # 프로그램 종료 중인지 확인
        if self.is_shutting_down:
            print("[INFO] RecommendTab: Tab is shutting down, skipping data processing")
            return
            
        # 앱이 종료 중인지 확인
        if not self.parent_app or getattr(self.parent_app, 'terminating', False):
            print("[INFO] RecommendTab: Application is terminating, skipping data update")
            return
            
        # 모델 객체가 유효한지 확인
        if not self.recommend_tab_model or sip.isdeleted(self.recommend_tab_model):
            print("[INFO] RecommendTab: Model has been deleted, skipping data update")
            return
            
        try:
            result = future.result()
        except Exception as e:
            print(f"[ERROR] RecommendTab _on_fetched: Future error: {e}")
            return

        st = result.get("status")
        if st != "ok":
            print(f"[WARN] RecommendTab: Auto-load failed: {result}")
            return

        new_rows = result.get("data", [])
        print(f"[INFO] RecommendTab: Auto-refresh loaded {len(new_rows)} recommend items.")

        # 다시 한번 객체 유효성 확인
        if self.is_shutting_down:
            print("[INFO] RecommendTab: Tab is shutting down, skipping cache update")
            return
            
        if not self.parent_app or getattr(self.parent_app, 'terminating', False):
            print("[INFO] RecommendTab: Application is terminating, skipping cache update")
            return
            
        # Update cache (self.recommend_dict)
        if not hasattr(self.parent_app, 'recommend_dict') or not isinstance(self.parent_app.recommend_dict, dict):
            self.parent_app.recommend_dict = {} # Initialize if not exists or wrong type
        self.parent_app.recommend_dict.clear() 
        
        loaded_addresses = set()
        for row in new_rows:
            addr_str = (row.get("dong", "") + " " + row.get("jibun", "")).strip()
            if addr_str:
                self.parent_app.recommend_dict.setdefault(addr_str, []).append(row)
                loaded_addresses.add(addr_str)

        # Emit signal for each loaded address
        if not self.is_shutting_down:
            for addr in loaded_addresses:
                 self.data_loaded_for_address.emit(addr)

        # 마지막으로 UI 업데이트 전에 다시 객체 유효성 확인
        if self.is_shutting_down:
            print("[INFO] RecommendTab: Tab is shutting down, skipping UI update")
            return
            
        if not self.recommend_tab_model or sip.isdeleted(self.recommend_tab_model):
            print("[INFO] RecommendTab: Model has been deleted, skipping UI update")
            return
            
        # Filter and populate based on current selection mode
        try:
            self.filter_and_populate()
        except RuntimeError as e:
            print(f"[INFO] RecommendTab: Could not update UI, likely during shutdown: {e}")
            return

    def filter_and_populate(self):
         """ [변경됨] API 쿼리 기반으로 선택된 주소의 추천 데이터를 실시간 로드합니다. """
         # 종료 중인지 확인
         if self.is_shutting_down:
             print("[INFO] RecommendTab: 종료 중이므로 데이터 로드를 건너뜁니다.")
             return
         
         # 객체 유효성 확인
         if not self.parent_app:
             print("[INFO] RecommendTab: parent_app이 None이므로 데이터 로드를 건너뜁니다.")
             return
             
         # 앱이 종료 중인지 확인 
         if hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
             print("[INFO] RecommendTab: 앱이 종료 중이므로 데이터 로드를 건너뜁니다.")
             return
             
         if not self.recommend_tab_model or sip.isdeleted(self.recommend_tab_model):
             print("[INFO] RecommendTab: Model has been deleted, skipping filter operation")
             return

         # 선택된 주소 및 필터 조건 가져오기
         target_addresses = []
         filter_params = {}
         
         if getattr(self.parent_app, 'from_customer_click', False) and getattr(self.parent_app, 'selected_addresses', None):
             # Multi-address mode from customer tab
             target_addresses = self.parent_app.selected_addresses
             # 고객 선택시 특정 biz/manager 필터링
             wanted_biz = getattr(self.parent_app, 'last_selected_customer_biz', None)
             wanted_mgr = getattr(self.parent_app, 'last_selected_customer_manager', None)
             if wanted_biz:
                 filter_params['matching_biz'] = wanted_biz
             if wanted_mgr:
                 filter_params['manager'] = wanted_mgr
         elif getattr(self.parent_app, 'last_selected_address', None):
             # Single address mode (show all for the address)
             target_addresses = [self.parent_app.last_selected_address]
         
         if not target_addresses:
             # No address selected, show empty table
             print("[INFO] RecommendTab: 선택된 주소가 없으므로 빈 테이블을 표시합니다.")
             try:
                 self.populate_recommend_tab_view([])
             except RuntimeError as e:
                 print(f"[INFO] RecommendTab: Could not update view during empty display: {e}")
             return

         # API 쿼리로 실시간 데이터 로드
         print(f"[INFO] RecommendTab: API 쿼리로 데이터 로드 시작 - 주소: {target_addresses}, 필터: {filter_params}")
         
         # 백그라운드에서 API 호출
         if hasattr(self.parent_app, 'executor') and self.parent_app.executor:
             future = self.parent_app.executor.submit(
                 self._bg_load_recommend_data_for_addresses,
                 target_addresses,
                 filter_params
             )
             future.add_done_callback(self._on_filter_data_loaded)
         else:
             print("[ERROR] RecommendTab: 백그라운드 executor를 찾을 수 없습니다.")

    def _bg_load_recommend_data_for_addresses(self, addresses_to_fetch: list, filter_params: dict = None):
        """ (Background Thread) API 쿼리로 지정된 주소들의 추천 데이터를 실시간 로드합니다. """
        if not addresses_to_fetch:
            print("[WARN] RecommendTab _bg_load_recommend_data_for_addresses: 빈 주소 리스트를 받았습니다.")
            return {"status": "empty", "data": [], "fetched_addresses": []}

        url = f"http://{self.server_host}:{self.server_port}/recommend/get_recommend_data"
        payload = {"addresses": addresses_to_fetch}
        
        # 필터 파라미터가 있으면 추가
        if filter_params:
            payload.update(filter_params)
        
        try:
            print(f"[DEBUG] RecommendTab: API 요청 시작 - {url}, 주소: {addresses_to_fetch}, 필터: {filter_params}")
            resp = requests.post(url, json=payload, timeout=20)
            resp.raise_for_status()
            j = resp.json()
            
            if j.get("status") == "ok":
                data = j.get("data", [])
                print(f"[INFO] RecommendTab: API 응답 성공 - {len(data)}개 항목")
                return {"status": "ok", "data": data, "fetched_addresses": addresses_to_fetch}
            else:
                print(f"[ERROR] RecommendTab API 응답 오류: {j}")
                return {"status": "error", "data": [], "message": j.get("message", "Unknown server error"), "fetched_addresses": []}
                
        except requests.exceptions.RequestException as ex:
            print(f"[ERROR] RecommendTab API 요청 실패: {ex}")
            return {"status": "exception", "message": str(ex), "data": [], "fetched_addresses": []}
        except Exception as ex:
            print(f"[ERROR] RecommendTab 예상치 못한 오류: {ex}")
            return {"status": "exception", "message": str(ex), "data": [], "fetched_addresses": []}

    def _on_filter_data_loaded(self, future):
        """ (Main Thread) API 쿼리 결과를 처리하고 테이블을 업데이트합니다. """
        # 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] RecommendTab: 종료 중이므로 데이터 처리를 건너뜁니다.")
            return
            
        # 앱이 종료 중인지 확인
        if not self.parent_app or (hasattr(self.parent_app, 'terminating') and self.parent_app.terminating):
            print("[INFO] RecommendTab: 앱이 종료 중이므로 데이터 업데이트를 건너뜁니다.")
            return
            
        # 모델 유효성 확인
        if not self.recommend_tab_model or sip.isdeleted(self.recommend_tab_model):
            print("[INFO] RecommendTab: Model has been deleted, skipping data processing")
            return
            
        try:
            result = future.result()
        except Exception as e:
            print(f"[ERROR] RecommendTab _on_filter_data_loaded: Future 오류: {e}")
            try:
                self.populate_recommend_tab_view([])  # 오류 시 빈 테이블
            except RuntimeError as re:
                print(f"[INFO] RecommendTab: Could not update view during error handling: {re}")
            return

        status = result.get("status")
        data = result.get("data", [])
        fetched_addresses = result.get("fetched_addresses", [])
        
        if status == "ok":
            print(f"[INFO] RecommendTab: 데이터 로드 완료 - {len(data)}개 항목, 주소: {fetched_addresses}")
            try:
                # 딕셔너리 업데이트 - AllTab에서 데이터를 가져갈 수 있도록
                for row in data:
                    addr_str = (row.get("dong", "") + " " + row.get("jibun", "")).strip()
                    if addr_str:
                        # 기존 데이터를 새 데이터로 교체
                        self.recommend_dict[addr_str] = self.recommend_dict.get(addr_str, [])
                        if row not in self.recommend_dict[addr_str]:  # 중복 방지
                            self.recommend_dict[addr_str].append(row)
                
                self.populate_recommend_tab_view(data)
                # 시그널 보내기 - AllTab에서 데이터 로드 완료를 감지할 수 있도록
                for addr in fetched_addresses:
                    if addr:  # 빈 주소가 아닌 경우만
                        self.data_loaded_for_address.emit(addr)
            except RuntimeError as e:
                print(f"[INFO] RecommendTab: Could not update view during normal update: {e}")
        elif status == "empty":
            print(f"[INFO] RecommendTab: 주소 {fetched_addresses}에 대한 데이터가 없습니다.")
            try:
                self.populate_recommend_tab_view([])
            except RuntimeError as e:
                print(f"[INFO] RecommendTab: Could not update view during empty display: {e}")
        else:
            error_msg = result.get("message", "Unknown error")
            print(f"[ERROR] RecommendTab: 데이터 로드 실패 - {error_msg}")
            try:
                self.populate_recommend_tab_view([])  # 오류 시 빈 테이블
            except RuntimeError as e:
                print(f"[INFO] RecommendTab: Could not update view during error display: {e}")

    def populate_recommend_tab_view(self, rows):
        """ Populates the recommend tab table view with the given rows data. """
        # 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] RecommendTab: 종료 중이므로 테이블 업데이트를 건너뜁니다.")
            return
            
        # 객체 유효성 확인
        if not self.recommend_tab_model or sip.isdeleted(self.recommend_tab_model):
            print("[INFO] RecommendTab: Model has been deleted, skipping population")
            return
            
        try:
            m = self.recommend_tab_model
            m.setRowCount(0)
            if not rows: return

            headers = self._get_headers()
            m.setColumnCount(len(headers))
            m.setHorizontalHeaderLabels(headers)
            m.setRowCount(len(rows))
        except RuntimeError as e:
            print(f"[INFO] RecommendTab: Could not set up model, likely during shutdown: {e}")
            return
        except Exception as e:
            print(f"[ERROR] RecommendTab: 테이블 설정 중 오류 발생: {e}")
            return

        try:
            # 한 번 더 종료 상태 확인
            if self.is_shutting_down:
                print("[INFO] RecommendTab: 종료 중이므로 행 데이터 채우기를 건너뜁니다.")
                return
                
            for i, r in enumerate(rows):
                # 주기적으로 종료 상태 재확인 (50행마다)
                if i % 50 == 0 and self.is_shutting_down:
                    print(f"[INFO] RecommendTab: 종료 중이므로 {i}행까지만 처리하고 중단합니다.")
                    break
                
                # 0) 주소 + 아이콘 + 툴팁 + UserData
                addr_ = (r.get("dong", "") + " " + r.get("jibun", "")).strip()
                folder_path = r.get("photo_path", "") or ""
                rep_img_path = ""
                if folder_path and os.path.isdir(folder_path): # Check if path is a directory
                    files = [f for f in os.listdir(folder_path)
                             if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
                    if files:
                        rep_img_path = os.path.join(folder_path, files[0])

                item = QtGui.QStandardItem(addr_)
                if rep_img_path and os.path.isfile(rep_img_path): # Check if image file exists
                    pixmap = QtGui.QPixmap(rep_img_path).scaled(
                        24, 24, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation
                    )
                    icon = QtGui.QIcon(pixmap)
                    item.setIcon(icon)
                    file_url = QtCore.QUrl.fromLocalFile(rep_img_path).toString()
                    html_tooltip = f'<img src="{file_url}" width="200">'
                    item.setToolTip(html_tooltip)
                else:
                    item.setToolTip("")

                # Store data in UserRole
                item.setData(folder_path, QtCore.Qt.UserRole + 10)
                item.setData(rep_img_path, QtCore.Qt.UserRole + 11)
                item.setData("추천", QtCore.Qt.UserRole + 2) # Source identifier
                item.setData(r.get("id", 0), QtCore.Qt.UserRole + 3) # Primary Key (recommend_id)

                m.setItem(i, 0, item)

                # Populate other columns based on headers
                m.setItem(i, 1, QtGui.QStandardItem(str(r.get("ho", "")))) # 호
                cf = r.get("curr_floor", 0)
                tf = r.get("total_floor", 0)
                m.setItem(i, 2, QtGui.QStandardItem(f"{cf}/{tf}")) # 층
                dp = r.get("deposit", 0)
                mn = r.get("monthly", 0)
                m.setItem(i, 3, QtGui.QStandardItem(f"{dp}/{mn}")) # 보증금/월세
                m.setItem(i, 4, QtGui.QStandardItem(str(r.get("manage_fee", "")))) # 관리비
                m.setItem(i, 5, QtGui.QStandardItem(str(r.get("premium", "")))) # 권리금
                m.setItem(i, 6, QtGui.QStandardItem(r.get("current_use", ""))) # 현업종
                m.setItem(i, 7, QtGui.QStandardItem(str(r.get("area", "")))) # 평수
                m.setItem(i, 8, QtGui.QStandardItem(r.get("owner_phone", ""))) # 연락처

                nav = r.get("naver_property_no", "")
                srv = r.get("serve_property_no", "")
                mm_ = f"{nav}/{srv}" if (nav or srv) else ""
                m.setItem(i, 9, QtGui.QStandardItem(mm_)) # 매물번호

                m.setItem(i, 10, QtGui.QStandardItem(r.get("title", ""))) # 제목

                matching_biz = r.get("matching_biz", "")
                manager_ = r.get("manager", "")
                biz_str = f"{matching_biz}({manager_})" if matching_biz and manager_ else matching_biz
                m.setItem(i, 11, QtGui.QStandardItem(biz_str)) # 매칭업종

                m.setItem(i, 12, QtGui.QStandardItem(r.get("check_memo", ""))) # 확인메모

                # Use recommend_date for the 13th column (광고종료일 in main header, but recommend_date here)
                m.setItem(i, 13, QtGui.QStandardItem(str(r.get("recommend_date", ""))))

                m.setItem(i, 14, QtGui.QStandardItem(str(r.get("parking", "")))) # 주차대수
                m.setItem(i, 15, QtGui.QStandardItem(r.get("building_usage", ""))) # 용도
                m.setItem(i, 16, QtGui.QStandardItem(str(r.get("approval_date", "")))) # 사용승인일
                rm_ = r.get("rooms", "")
                bt_ = r.get("baths", "")
                m.setItem(i, 17, QtGui.QStandardItem(f"{rm_}/{bt_}" if rm_ or bt_ else "")) # 방/화장실
                m.setItem(i, 18, QtGui.QStandardItem(str(r.get("ad_start_date", "")))) # 광고등록일
                m.setItem(i, 19, QtGui.QStandardItem(r.get("photo_path", ""))) # 사진경로
                m.setItem(i, 20, QtGui.QStandardItem(r.get("owner_name", ""))) # 소유자명
                m.setItem(i, 21, QtGui.QStandardItem(r.get("owner_relation", ""))) # 관계
                
                # 주기적으로 이벤트 처리 - 더 자주 UI 업데이트와 이벤트 처리 (10행마다)
                if i % 10 == 0:
                    QtWidgets.QApplication.processEvents()
                    
                    # UI 처리 중 앱 종료 상태 확인
                    if self.is_shutting_down:
                        print(f"[INFO] RecommendTab: 이벤트 처리 중 종료 상태 감지, {i}행까지만 처리하고 중단합니다.")
                        break
                        
        except RuntimeError as e:
            print(f"[INFO] RecommendTab: 테이블 행 채우는 중 런타임 오류 (종료 중일 수 있음): {e}")
        except Exception as e:
            print(f"[ERROR] RecommendTab: 테이블 행 채우는 중 예상치 못한 오류: {e}")
            import traceback
            print(traceback.format_exc())

    def filter_recommend_by_address(self, address_str: str):
        """ Filters the table to show only recommend rows matching the address_str. """
        if not address_str:
            self.populate_recommend_tab_view([])
            return

        # Important: When filtering JUST by address (not from customer click),
        # show ALL recommendations for that address, regardless of biz/manager.
        rows_for_addr = self.recommend_dict.get(address_str, [])
        self.populate_recommend_tab_view(rows_for_addr)

    def get_data_for_address(self, addr_str: str) -> list:
        """ Returns the list of recommend items for the given address from the local cache. """
        # Note: Depending on the use case, you might want to add filtering here
        # based on self.parent_app.customer_tab.last_selected_biz/manager 
        # if called from a context where that's relevant.
        # For simple unification by address in AllTab, returning all is usually correct.
        if hasattr(self.parent_app, 'recommend_dict') and isinstance(self.parent_app.recommend_dict, dict):
             return self.parent_app.recommend_dict.get(addr_str, [])
        else:
             print(f"[WARN][RecommendTab] get_data_for_address: parent_app.recommend_dict not found or not a dict.")
             return []

    def _get_headers(self):
        """ Returns the list of headers for the recommend tab. """
        # This should match the headers used in populate_recommend_tab_view
        # and ideally align with the '전체' tab headers where applicable.
        return [
            "주소", "호", "층", "보증금/월세", "관리비",
            "권리금", "현업종", "평수", "연락처", "매물번호",
            "제목", "매칭업종", "확인메모", "추천일", # Changed from 광고종료일
            "주차대수", "용도", "사용승인일", "방/화장실",
            "광고등록일", "사진경로", "소유자명", "관계"
        ]

    def on_recommend_tab_clicked(self, index: QtCore.QModelIndex):
        """
        추천매물 탭에서 셀 클릭 처리
        """
        if not index.isValid():
            return
            
        col_idx = index.column()
        
        # 주소 열(0번) 클릭 시 이미지 표시
        if col_idx == 0:
            item = self.recommend_tab_model.item(index.row(), 0)
            if not item:
                return
                
            folder_path = item.data(QtCore.Qt.UserRole + 10) or ""
            if not folder_path or not os.path.isdir(folder_path):
                return
                
            # 폴더 내 이미지 파일 찾기
            image_files = sorted(
                glob.glob(os.path.join(folder_path, "*.jpg")) +
                glob.glob(os.path.join(folder_path, "*.jpeg")) +
                glob.glob(os.path.join(folder_path, "*.png")) +
                glob.glob(os.path.join(folder_path, "*.gif"))
            )
            
            if not image_files:
                QtWidgets.QMessageBox.warning(self.parent_app, "이미지 없음", "해당 폴더에 이미지가 없습니다.")
                return
                
            # 이미지 슬라이드쇼 표시
            if hasattr(self.parent_app, 'slider_window') and self.parent_app.slider_window:
                if self.parent_app.slider_window.isVisible():
                    self.parent_app.slider_window.set_image_list(image_files)
                    self.parent_app.slider_window.activateWindow()
                    self.parent_app.slider_window.raise_()
                    return
            
            # 슬라이드쇼 창 생성 및 표시
            try:
                # dialogs 모듈에서 ImageSlideshowWindow 클래스 가져오기
                from dialogs import ImageSlideshowWindow
                self.parent_app.slider_window = ImageSlideshowWindow(image_files, parent=self.parent_app)
                self.parent_app.slider_window.show()
            except ImportError as e:
                print(f"[ERR] 이미지 뷰어 로딩 실패: {str(e)}")
                QtWidgets.QMessageBox.warning(self.parent_app, "오류", "이미지 뷰어를 불러올 수 없습니다.")
        
        # 매물번호 열(9번) 클릭 시 클립보드 복사
        elif col_idx == 9:
            item = self.recommend_tab_model.item(index.row(), 9)
            if not item:
                return
                
            property_no = item.text()
            if property_no:
                QtWidgets.QApplication.clipboard().setText(property_no)
                QtWidgets.QMessageBox.information(self.parent_app, "복사", f"매물번호 [{property_no}] 복사 완료!")

    def terminate(self):
        """앱 종료 시 호출되는 정리 메서드"""
        print("[INFO] RecommendTab: Terminating...")
        self.is_shutting_down = True
        
        # 타이머 정지 강화된 예외 처리
        if hasattr(self, 'recommend_tab_timer') and self.recommend_tab_timer:
            try:
                if self.recommend_tab_timer.isActive():
                    self.recommend_tab_timer.stop()
                    print("[INFO] RecommendTab: Timer stopped")
                    
                # 타이머 연결 해제
                try:
                    self.recommend_tab_timer.timeout.disconnect()
                    print("[INFO] RecommendTab: Timer signal disconnected")
                except (TypeError, RuntimeError):
                    # 이미 연결이 끊어졌거나 예외가 발생했을 경우 무시
                    pass
                    
                # 타이머 참조 제거
                self.recommend_tab_timer = None
                print("[INFO] RecommendTab: Timer reference removed")
            except Exception as e:
                print(f"[WARN] RecommendTab: Error handling timer: {e}")
        
        # 실행기 종료 (비동기 작업 취소)
        if hasattr(self, 'executor') and self.executor:
            try:
                print("[INFO] RecommendTab: Shutting down local executor...")
                self.executor.shutdown(wait=False)
                print("[INFO] RecommendTab: Local executor shutdown complete")
                self.executor = None
            except Exception as e:
                print(f"[WARN] RecommendTab: Error shutting down local executor: {e}")
        
        # 시그널 연결 해제 시도
        try:
            # 데이터 로드 시그널 해제
            self.data_loaded_for_address.disconnect()
        except (TypeError, RuntimeError):
            # 시그널이 연결되어 있지 않으면 무시
            pass
        
        # 모델 참조 제거
        self.recommend_tab_model = None
        self.recommend_tab_view = None
        
        # 메모리 정리를 위해 캐시 비우기
        if hasattr(self, 'recommend_dict'):
            self.recommend_dict.clear()
            
        print("[INFO] RecommendTab: Termination complete")