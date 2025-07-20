# check_confirm_tab.py
import requests
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QTableView, QAbstractItemView, QHeaderView, QMenu
from PyQt5.QtCore import Qt
from ui_utils import restore_qtableview_column_widths, save_qtableview_column_widths
from dialogs import EditConfirmMemoDialog, StatusChangeDialog, MultiRowMemoDialog
# Add pyqtSignal import and QObject
from PyQt5.QtCore import pyqtSignal, QObject

# Inherit from QObject
class CheckConfirmTab(QObject):
    # Add the signal definition
    data_loaded_for_address = pyqtSignal(str)

    def __init__(self, parent_app=None, server_host=None, server_port=None):
        super().__init__() # Call QObject initializer
        self.parent_app = parent_app
        self.server_host = server_host
        self.server_port = server_port

        self.check_confirm_model = None
        self.check_confirm_view = None
        self.check_confirm_dict = {} # Cache for confirm data by address
        self.confirm_timer = None

    def init_tab(self, main_tabs_widget):
        """
        Initializes the '매물체크(확인)' tab UI components.
        """
        container = QtWidgets.QWidget()
        vlay = QtWidgets.QVBoxLayout(container)

        self.check_confirm_model = QtGui.QStandardItemModel()
        headers = self._get_headers()
        self.check_confirm_model.setColumnCount(len(headers))
        self.check_confirm_model.setHorizontalHeaderLabels(headers)

        self.check_confirm_view = QTableView() # Use QTableView
        self.check_confirm_view.setModel(self.check_confirm_model)
        self.check_confirm_view.setSortingEnabled(True)
        self.check_confirm_view.horizontalHeader().setStretchLastSection(True)

        # Restore column widths using utility function
        restore_qtableview_column_widths(
            self.parent_app.settings_manager, # Pass settings manager
            self.check_confirm_view, 
            "CheckConfirmTable"
        )
        # Save column widths on resize using utility function
        self.check_confirm_view.horizontalHeader().sectionResized.connect(
            lambda: save_qtableview_column_widths(
                self.parent_app.settings_manager, # Pass settings manager
                self.check_confirm_view, 
                "CheckConfirmTable"
            )
        )
        
        # Connect signals if needed (e.g., context menu)
        # self.check_confirm_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        # self.check_confirm_view.customContextMenuRequested.connect(self.on_context_menu_requested) 

        vlay.addWidget(self.check_confirm_view)
        container.setLayout(vlay)
        main_tabs_widget.addTab(container, "매물체크(확인)")

        # [자동 타이머 비활성화] 성능 최적화를 위해 자동 리로드 타이머를 비활성화함
        # 사용자가 필요시 수동으로 새로고침하도록 변경
        print("[INFO] CheckConfirmTab: 자동 리로드 타이머가 성능 최적화를 위해 비활성화되었습니다.")
        
        # # Setup and start the timer
        # self.confirm_timer = QtCore.QTimer(self.parent_app)
        # self.confirm_timer.setInterval(10 * 1000)  # 10 seconds interval
        # self.confirm_timer.timeout.connect(self._auto_reload_confirm_data)
        
        # [제거됨] 초기 데이터 로드 - 성능 최적화를 위해 비활성화
        # 필요시 사용자가 주소 선택 시 filter_and_populate()에서 실시간 로드됨
        # self._auto_reload_confirm_data() # 비활성화
        # self.confirm_timer.start()

    def _auto_reload_confirm_data(self):
        """
        Triggered by the timer to reload all confirm data.
        (No longer depends on new_addresses)
        """
        # 애플리케이션 종료 중인지 확인
        if hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
            print("[INFO] CheckConfirmTab: Application is terminating, skipping auto reload")
            return
            
        # 전역 종료 플래그 확인
        if 'APP_SHUTTING_DOWN' in globals() and globals()['APP_SHUTTING_DOWN']:
            print("[INFO] CheckConfirmTab: APP_SHUTTING_DOWN is set, skipping auto reload")
            return
            
        # Executor가 이미 종료되었는지 확인
        if not hasattr(self.parent_app, 'executor') or not self.parent_app.executor:
            print("[WARN] CheckConfirmTab: Executor is not available, skipping auto reload")
            return
            
        # Executor가 shutdown 중인지 확인
        if hasattr(self.parent_app.executor, '_shutdown') and self.parent_app.executor._shutdown:
            print("[WARN] CheckConfirmTab: Executor is already shut down, skipping auto reload")
            return
            
        try:
            future = self.parent_app.executor.submit(
                self._bg_load_confirm_data_with_addresses # Call without address list
            )
            future.add_done_callback(self._on_confirm_data_fetched)
        except RuntimeError as e:
            print(f"[ERROR] CheckConfirmTab: Cannot schedule new task: {e}")
        except Exception as e:
            print(f"[ERROR] CheckConfirmTab: Unexpected error while scheduling task: {e}")

    def _bg_load_confirm_data_with_addresses(self):
        """
        (Background Thread) Fetches ALL confirm data from the server.
        (Now includes manager/role in the payload)
        Returns the raw rows data.
        """
        url = f"http://{self.server_host}:{self.server_port}/shop/get_all_confirm_with_items"
        # Send manager/role in the payload
        manager = self.parent_app.current_manager
        role = self.parent_app.current_role
        payload = {"manager": manager, "role": role} 

        try:
            resp = requests.post(url, json=payload, timeout=10) # Increased timeout
            resp.raise_for_status()
            j = resp.json()
            if j.get("status") == "ok":
                return {"status": "ok", "data": j.get("data", [])}
            else:
                print(f"[ERROR] CheckConfirmTab _bg_load_confirm_data: Server error: {j}")
                return {"status": "error", "data": [], "message": j.get("message", "Unknown server error")}
        except requests.exceptions.RequestException as ex:
            print(f"[ERROR] CheckConfirmTab _bg_load_confirm_data: Request failed: {ex}")
            return {"status": "exception", "message": str(ex), "data": []}
        except Exception as ex:
            print(f"[ERROR] CheckConfirmTab _bg_load_confirm_data: Unexpected error: {ex}")
            return {"status": "exception", "message": str(ex), "data": []}

    def _on_confirm_data_fetched(self, future):
        """
        (Main Thread) Processes the fetched data, updates the cache, and populates the view.
        """
        # 프로그램 종료 중 호출 시 처리 안함 (모델이 이미 삭제된 경우 방지)
        if not self.parent_app or not hasattr(self, 'check_confirm_model') or not self.check_confirm_model:
            print("[INFO] CheckConfirmTab: Application is terminating, skipping data update")
            return
            
        try:
            result = future.result()
        except Exception as e:
            print(f"[ERROR] CheckConfirmTab _on_confirm_data_fetched: Future error: {e}")
            # Optionally show an error message to the user
            # QtWidgets.QMessageBox.warning(self.parent_app, "데이터 로딩 오류", f"매물체크(확인) 탭 데이터 로딩 중 오류 발생: {e}")
            return

        st = result.get("status")
        if st != "ok":
            print(f"[WARN] CheckConfirmTab: Confirm data auto-load failed: {result}")
            # Optionally show an error message to the user
            # msg = result.get("message", "알 수 없는 오류")
            # QtWidgets.QMessageBox.warning(self.parent_app, "데이터 로딩 실패", f"매물체크(확인) 탭 로딩 실패: {msg}")
            return

        new_rows = result.get("data", [])
        print(f"[INFO] CheckConfirmTab: Auto-refresh loaded {len(new_rows)} confirm items.")

        # 모델이 여전히 유효한지 다시 확인
        if not hasattr(self, 'check_confirm_model') or not self.check_confirm_model:
            print("[INFO] CheckConfirmTab: Model no longer exists, skipping update")
            return

        # (A) Update cache (self.check_confirm_dict)
        self.check_confirm_dict.clear()
        loaded_addresses = set()
        for row in new_rows:
            addr_str = (row.get("dong", "") + " " + row.get("jibun", "")).strip()
            if addr_str:
                self.check_confirm_dict.setdefault(addr_str, []).append(row)
                loaded_addresses.add(addr_str)
        
        # Emit signal for each loaded address
        for addr in loaded_addresses:
             self.data_loaded_for_address.emit(addr)

        # (B) Filter and populate based on current selection mode
        self.filter_and_populate()


    def filter_and_populate(self):
        """ [변경됨] API 쿼리 기반으로 선택된 주소의 확인 데이터를 실시간 로드합니다. """
        # 프로그램 종료 중 호출 시 처리 안함 (모델이 이미 삭제된 경우 방지)
        if not self.parent_app or not hasattr(self, 'check_confirm_model') or not self.check_confirm_model:
            print("[INFO] CheckConfirmTab: Model not available, skipping filter_and_populate")
            return
        
        # 앱이 종료 중인지 확인
        if hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
            print("[INFO] CheckConfirmTab: 앱이 종료 중이므로 데이터 로드를 건너뜁니다.")
            return

        # 선택된 주소 가져오기
        target_addresses = []
        if self.parent_app.from_customer_click and self.parent_app.selected_addresses:
            # Multi-address mode from customer tab
            target_addresses = self.parent_app.selected_addresses
        elif self.parent_app.last_selected_address:
            # Single address mode (likely from manager_check_tab or mylist_shop_tab)
            target_addresses = [self.parent_app.last_selected_address]
        
        if not target_addresses:
            # No address selected, show empty table
            print("[INFO] CheckConfirmTab: 선택된 주소가 없으므로 빈 테이블을 표시합니다.")
            self.populate_check_confirm_view([])
            return

        # API 쿼리로 실시간 데이터 로드
        print(f"[INFO] CheckConfirmTab: API 쿼리로 데이터 로드 시작 - 주소: {target_addresses}")
        
        # 백그라운드에서 API 호출
        if hasattr(self.parent_app, 'executor') and self.parent_app.executor:
            future = self.parent_app.executor.submit(
                self._bg_load_confirm_data_for_addresses,
                target_addresses
            )
            future.add_done_callback(self._on_filter_data_loaded)
        else:
            print("[ERROR] CheckConfirmTab: 백그라운드 executor를 찾을 수 없습니다.")

    def _bg_load_confirm_data_for_addresses(self, addresses_to_fetch: list):
        """ (Background Thread) API 쿼리로 지정된 주소들의 확인 데이터를 실시간 로드합니다. """
        if not addresses_to_fetch:
            print("[WARN] CheckConfirmTab _bg_load_confirm_data_for_addresses: 빈 주소 리스트를 받았습니다.")
            return {"status": "empty", "data": [], "fetched_addresses": []}

        url = f"http://{self.server_host}:{self.server_port}/shop/get_all_confirm_with_items"
        payload = {"addresses": addresses_to_fetch}
        
        try:
            print(f"[DEBUG] CheckConfirmTab: API 요청 시작 - {url}, 주소: {addresses_to_fetch}")
            resp = requests.post(url, json=payload, timeout=20)
            resp.raise_for_status()
            j = resp.json()
            
            if j.get("status") == "ok":
                data = j.get("data", [])
                print(f"[INFO] CheckConfirmTab: API 응답 성공 - {len(data)}개 항목")
                return {"status": "ok", "data": data, "fetched_addresses": addresses_to_fetch}
            else:
                print(f"[ERROR] CheckConfirmTab API 응답 오류: {j}")
                return {"status": "error", "data": [], "message": j.get("message", "Unknown server error"), "fetched_addresses": []}
                
        except requests.exceptions.RequestException as ex:
            print(f"[ERROR] CheckConfirmTab API 요청 실패: {ex}")
            return {"status": "exception", "message": str(ex), "data": [], "fetched_addresses": []}
        except Exception as ex:
            print(f"[ERROR] CheckConfirmTab 예상치 못한 오류: {ex}")
            return {"status": "exception", "message": str(ex), "data": [], "fetched_addresses": []}

    def _on_filter_data_loaded(self, future):
        """ (Main Thread) API 쿼리 결과를 처리하고 테이블을 업데이트합니다. """
        # 모델 유효성 확인
        if not hasattr(self, 'check_confirm_model') or not self.check_confirm_model:
            print("[INFO] CheckConfirmTab: Model not available, skipping data processing")
            return
            
        # 앱이 종료 중인지 확인
        if not self.parent_app or (hasattr(self.parent_app, 'terminating') and self.parent_app.terminating):
            print("[INFO] CheckConfirmTab: 앱이 종료 중이므로 데이터 업데이트를 건너뜁니다.")
            return
            
        try:
            result = future.result()
        except Exception as e:
            print(f"[ERROR] CheckConfirmTab _on_filter_data_loaded: Future 오류: {e}")
            self.populate_check_confirm_view([])  # 오류 시 빈 테이블
            return

        status = result.get("status")
        data = result.get("data", [])
        fetched_addresses = result.get("fetched_addresses", [])
        
        if status == "ok":
            print(f"[INFO] CheckConfirmTab: 데이터 로드 완료 - {len(data)}개 항목, 주소: {fetched_addresses}")
            # 딕셔너리 업데이트 - AllTab에서 데이터를 가져갈 수 있도록
            for row in data:
                addr_str = (row.get("dong", "") + " " + row.get("jibun", "")).strip()
                if addr_str:
                    # 기존 데이터를 새 데이터로 교체
                    self.check_confirm_dict[addr_str] = self.check_confirm_dict.get(addr_str, [])
                    if row not in self.check_confirm_dict[addr_str]:  # 중복 방지
                        self.check_confirm_dict[addr_str].append(row)
            
            self.populate_check_confirm_view(data)
            # 시그널 보내기 - AllTab에서 데이터 로드 완료를 감지할 수 있도록
            for addr in fetched_addresses:
                if addr:  # 빈 주소가 아닌 경우만
                    self.data_loaded_for_address.emit(addr)
        elif status == "empty":
            print(f"[INFO] CheckConfirmTab: 주소 {fetched_addresses}에 대한 데이터가 없습니다.")
            self.populate_check_confirm_view([])
        else:
            error_msg = result.get("message", "Unknown error")
            print(f"[ERROR] CheckConfirmTab: 데이터 로드 실패 - {error_msg}")
            self.populate_check_confirm_view([])  # 오류 시 빈 테이블

    def populate_check_confirm_view(self, data_list):
        """
        Populates the QTableView (self.check_confirm_view) with the provided data_list.
        """
        # 프로그램 종료 중 호출 시 처리 안함 (모델이 이미 삭제된 경우 방지)
        if not hasattr(self, 'check_confirm_model') or not self.check_confirm_model:
            print("[INFO] CheckConfirmTab: Model not available, skipping populate_check_confirm_view")
            return
            
        model = self.check_confirm_model
        
        try:
            model.clear() # Clear existing items first
        except RuntimeError as e:
            print(f"[WARN] CheckConfirmTab: Model access error in populate_check_confirm_view: {e}")
            return

        if not data_list:
            # Set headers even if data is empty
            headers = self._get_headers()
            model.setColumnCount(len(headers))
            model.setHorizontalHeaderLabels(headers)
            model.setRowCount(0) # Explicitly set row count to 0
            return

        headers = self._get_headers()
        model.setColumnCount(len(headers))
        model.setHorizontalHeaderLabels(headers)
        model.setRowCount(len(data_list))

        for i, row_data in enumerate(data_list):
            addr_str = (row_data.get("dong", "") + " " + row_data.get("jibun", "")).strip()
            item_addr = QtGui.QStandardItem(addr_str)
            c_id = row_data.get("confirm_id", None) # Use 'confirm_id' as primary key
            if c_id is not None:
                # Store the primary key (confirm_id) in UserRole for the first column
                item_addr.setData(c_id, QtCore.Qt.UserRole + 3) # Use +3 to be consistent with other tabs
                item_addr.setData("확인", QtCore.Qt.UserRole + 2) # Source identifier

            model.setItem(i, 0, item_addr) # 주소

            model.setItem(i, 1, QtGui.QStandardItem(str(row_data.get("ho", "")))) # 호

            cf = row_data.get("curr_floor", 0)
            tf = row_data.get("total_floor", 0)
            floor_str = f"{cf}/{tf}"
            model.setItem(i, 2, QtGui.QStandardItem(floor_str)) # 층

            dep = row_data.get("deposit", 0)
            mon = row_data.get("monthly", 0)
            bm_str = f"{dep}/{mon}"
            model.setItem(i, 3, QtGui.QStandardItem(bm_str)) # 보증금/월세

            model.setItem(i, 4, QtGui.QStandardItem(str(row_data.get("manage_fee", "")))) # 관리비
            model.setItem(i, 5, QtGui.QStandardItem(str(row_data.get("premium", "")))) # 권리금
            model.setItem(i, 6, QtGui.QStandardItem(row_data.get("current_use", ""))) # 현업종
            model.setItem(i, 7, QtGui.QStandardItem(str(row_data.get("area", 0.0)))) # 평수
            model.setItem(i, 8, QtGui.QStandardItem(row_data.get("owner_phone", ""))) # 연락처

            nav_no = row_data.get("naver_property_no", "")
            srv_no = row_data.get("serve_property_no", "")
            mnum_str = ""
            if nav_no and srv_no: mnum_str = f"{nav_no}/{srv_no}"
            elif nav_no: mnum_str = nav_no
            elif srv_no: mnum_str = srv_no
            model.setItem(i, 9, QtGui.QStandardItem(mnum_str)) # 매물번호

            model.setItem(i, 10, QtGui.QStandardItem(row_data.get("memo", ""))) # 제목 (using 'memo')

            biz_ = row_data.get("matching_biz_type", "") or ""
            manager_ = row_data.get("manager", "") or ""
            biz_str = f"{biz_}({manager_})" if biz_ and manager_ else biz_
            model.setItem(i, 11, QtGui.QStandardItem(biz_str)) # 매칭업종

            model.setItem(i, 12, QtGui.QStandardItem(row_data.get("check_memo", "") or "")) # 확인메모

            # Remaining columns matching the headers
            model.setItem(i, 13, QtGui.QStandardItem(str(row_data.get("parking", "")))) # 주차대수
            model.setItem(i, 14, QtGui.QStandardItem(row_data.get("building_usage", ""))) # 용도
            model.setItem(i, 15, QtGui.QStandardItem(str(row_data.get("approval_date", "") or ""))) # 사용승인일

            r_ = row_data.get("rooms", "")
            b_ = row_data.get("baths", "")
            rb_str = f"{r_}/{b_}" if r_ or b_ else ""
            model.setItem(i, 16, QtGui.QStandardItem(rb_str)) # 방/화장실

            model.setItem(i, 17, QtGui.QStandardItem(str(row_data.get("ad_start_date", "") or ""))) # 광고등록일
            model.setItem(i, 18, QtGui.QStandardItem(row_data.get("photo_path", ""))) # 사진경로
            model.setItem(i, 19, QtGui.QStandardItem(row_data.get("owner_name", ""))) # 소유자명
            model.setItem(i, 20, QtGui.QStandardItem(row_data.get("owner_relation", ""))) # 관계


    def filter_check_confirm_by_address(self, addr_str: str):
        """
        Filters the view to show only data for the given address string.
        """
        if not addr_str:
            self.populate_check_confirm_view([])
            return

        filtered = self.check_confirm_dict.get(addr_str, [])
        self.populate_check_confirm_view(filtered)

    def get_data_for_address(self, addr_str: str) -> list:
        """ Returns the list of confirm items for the given address from the local cache. """
        return self.check_confirm_dict.get(addr_str, [])

    def _get_headers(self):
        """ Returns the list of headers for the confirm tab. """
        return [
            "주소", "호", "층", "보증금/월세", "관리비",
            "권리금", "현업종", "평수", "연락처",
            "매물번호", "제목", "매칭업종", "확인메모",
            "주차대수", "용도", "사용승인일", "방/화장실",
            "광고등록일", "사진경로", "소유자명", "관계"
        ]
        
    def cleanup(self):
        """프로그램 종료 시 호출하여 타이머 중지 및 리소스 정리"""
        print("[INFO] CheckConfirmTab: Cleaning up resources...")
        if hasattr(self, 'confirm_timer') and self.confirm_timer:
            try:
                self.confirm_timer.stop()
                print("[INFO] CheckConfirmTab: Timer stopped")
            except Exception as e:
                print(f"[WARN] CheckConfirmTab: Error stopping timer: {e}")
                
        # 백그라운드 작업 중인 Future가 있으면 취소 (구현 가능하다면)
        print("[INFO] CheckConfirmTab: Cleanup complete") 