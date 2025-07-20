# serve_shop_tab.py
import os
import glob
import requests
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (
    QTableView, QAbstractItemView, QHeaderView, QWidget, 
    QVBoxLayout, QMenu, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from dialogs import ImageSlideshowWindow, StatusChangeDialog, RecommendDialog, BizSelectDialog
# Import moved utility functions
from ui_utils import restore_qtableview_column_widths, save_qtableview_column_widths

# Inherit from QObject
class ServeShopTab(QObject):
    # Add the signal definition
    data_loaded_for_address = pyqtSignal(str)

    def __init__(self, parent_app=None, server_host=None, server_port=None):
        super().__init__() # Call QObject initializer
        self.parent_app = parent_app
        self.server_host = server_host
        self.server_port = server_port

        self.serve_shop_model = None
        self.serve_shop_view = None
        self.serve_shop_dict = {} # Cache for serve_shop data by address
        self.serve_shop_timer = None
        self.slider_window = None # Keep track of the slideshow window
        self.is_shutting_down = False  # 종료 상태 플래그 추가

    def init_tab(self, main_tabs_widget):
        """
        Initializes the '써브(상가)' tab UI components.
        """
        container = QtWidgets.QWidget()
        vlay = QtWidgets.QVBoxLayout(container)

        self.serve_shop_model = QtGui.QStandardItemModel()
        headers = self._get_headers()
        self.serve_shop_model.setColumnCount(len(headers))
        self.serve_shop_model.setHorizontalHeaderLabels(headers)

        self.serve_shop_view = QtWidgets.QTableView()
        self.serve_shop_view.setModel(self.serve_shop_model)
        self.serve_shop_view.setSortingEnabled(True)
        self.serve_shop_view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        self.serve_shop_view.clicked.connect(self.on_serve_shop_clicked)

        # Restore column widths using utility function
        restore_qtableview_column_widths(
            self.parent_app.settings_manager, 
            self.serve_shop_view, 
            "ServeShopTable"
        )
        # Save column widths on resize using utility function
        self.serve_shop_view.horizontalHeader().sectionResized.connect(
            lambda: save_qtableview_column_widths(
                self.parent_app.settings_manager, 
                self.serve_shop_view, 
                "ServeShopTable"
            )
        )

        vlay.addWidget(self.serve_shop_view)
        container.setLayout(vlay)
        main_tabs_widget.addTab(container, "써브(상가)")

        # Setup and start the timer
        try:
            # 이미 종료 상태인지 확인
            if self.is_shutting_down:
                print("[INFO] ServeShopTab: 이미 종료 중이므로 타이머를 시작하지 않습니다.")
                return
                
            # [자동 타이머 비활성화] 성능 최적화를 위해 자동 리로드 타이머를 비활성화함
            # 사용자가 필요시 수동으로 새로고침하도록 변경
            print("[INFO] ServeShopTab: 자동 리로드 타이머가 성능 최적화를 위해 비활성화되었습니다.")
            
            # self.serve_shop_timer = QtCore.QTimer(self.parent_app)
            # self.serve_shop_timer.setInterval(30 * 1000)  # 30 seconds interval
            
            # # 연결 전에 기존 연결이 있는지 확인하고 해제
            # try:
            #     # 새로 만든 타이머이므로 연결 오류는 없겠지만 안전하게 처리
            #     self.serve_shop_timer.timeout.disconnect()
            # except (TypeError, RuntimeError):
            #     # 기존 연결이 없으면 오류가 발생하므로 무시
            #     pass
                
            # self.serve_shop_timer.timeout.connect(self.auto_reload_serve_shop_data)
            
            # [제거됨] 초기 데이터 로드 - 성능 최적화를 위해 비활성화
            # 필요시 사용자가 주소 선택 시 filter_and_populate()에서 실시간 로드됨
            # self.auto_reload_serve_shop_data() # 비활성화
            # self.serve_shop_timer.start()
        except Exception as e:
            print(f"[ERROR] ServeShopTab 타이머 설정 중 오류 발생: {e}")

    def on_serve_shop_clicked(self, index: QtCore.QModelIndex):
        """ 
        Handles clicks on the serve_shop table.
        - Updates bottom table with selected address (like manager check tab)
        - Opens image slideshow if images are available
        """
        # 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] ServeShopTab: 종료 중이므로 클릭 이벤트를 처리하지 않습니다.")
            return
            
        if not index.isValid():
            return

        # 헤더 기반 안전한 컬럼 접근으로 변경
        from ui_utils import get_item_by_header_cached
        item_clicked = get_item_by_header_cached(self.serve_shop_model, index.row(), "주소")
        if not item_clicked:
            return

        # Extract address text for bottom table update
        address_text = item_clicked.text().strip()
        print(f"[🔄 SERVE-SHOP] ServeShopTab: Selected address: '{address_text}'")
        
        # 🎯 NEW: Update bottom table like manager check tab
        if hasattr(self.parent_app, 'update_selection_from_manager_check') and address_text:
            print(f"[🚨 API CALL] ServeShopTab: Calling update_selection_from_manager_check with: {address_text}")
            try:
                self.parent_app.update_selection_from_manager_check(address_text)
                print(f"[✅ SUCCESS] ServeShopTab: Bottom table updated successfully")
            except Exception as e:
                print(f"[❌ ERROR] ServeShopTab: Failed to update bottom table: {e}")
        else:
            print(f"[⚠️ WARNING] ServeShopTab: update_selection_from_manager_check not available or empty address")

        # 🖼️ EXISTING: Image slideshow functionality (only for first column clicks)
        if index.column() == 0:  # Only for address column
            folder_path = item_clicked.data(QtCore.Qt.UserRole + 10) or ""
            if folder_path and os.path.isdir(folder_path):
                image_files = sorted(
                    glob.glob(os.path.join(folder_path, "*.jpg")) +
                    glob.glob(os.path.join(folder_path, "*.jpeg")) +
                    glob.glob(os.path.join(folder_path, "*.png")) +
                    glob.glob(os.path.join(folder_path, "*.gif"))
                )
                if image_files:
                    # Reuse or create the slideshow window
                    if self.slider_window and self.slider_window.isVisible():
                        self.slider_window.set_image_list(image_files)
                        self.slider_window.activateWindow()
                        self.slider_window.raise_()
                    else:
                        self.slider_window = ImageSlideshowWindow(image_files, parent=self.parent_app)
                        self.slider_window.show()
                else:
                    print(f"[INFO] ServeShopTab: No images found in folder: {folder_path}")
            else:
                print(f"[INFO] ServeShopTab: No valid folder path for address: {address_text}")

    def populate_serve_shop_table(self, rows):
        """ Populates the serve_shop table view with the given rows data. """
        # 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] ServeShopTab: 종료 중이므로 테이블 채우기를 건너뜁니다.")
            return
            
        # 앱이 종료 중인지 확인
        if not self.parent_app or (hasattr(self.parent_app, 'terminating') and self.parent_app.terminating):
            print("[INFO] ServeShopTab: 앱이 종료 중이므로 테이블 채우기를 건너뜁니다.")
            return
            
        # 모델 객체가 유효한지 확인
        if not self.serve_shop_model:
            print("[INFO] ServeShopTab: Model not available, skipping populate_serve_shop_table")
            return
            
        m = self.serve_shop_model
        m.setRowCount(0)
        if not rows: return

        headers = self._get_headers() # Ensure headers are correct
        m.setColumnCount(len(headers))
        m.setHorizontalHeaderLabels(headers)
        m.setRowCount(len(rows))

        for i, r in enumerate(rows):
            # 0) 주소 + 아이콘 + 툴팁 + UserData
            addr_ = (r.get("dong", "") + " " + r.get("jibun", "")).strip()
            folder_path = r.get("photo_path", "") or ""
            rep_img_path = ""
            if os.path.isdir(folder_path):
                files = [f for f in os.listdir(folder_path)
                         if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
                if files:
                    rep_img_path = os.path.join(folder_path, files[0])

            item = QtGui.QStandardItem(addr_)
            if rep_img_path and os.path.isfile(rep_img_path):
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
            item.setData(folder_path, QtCore.Qt.UserRole + 10) # Folder path
            item.setData(rep_img_path, QtCore.Qt.UserRole + 11) # Representative image path
            item.setData("상가", QtCore.Qt.UserRole + 2) # Source identifier
            item.setData(r.get("id", 0), QtCore.Qt.UserRole + 3) # Primary Key (DB ID)
            item.setData(r.get("status_cd", ""), QtCore.Qt.UserRole + 1) # Status code

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
            m.setItem(i, 10, QtGui.QStandardItem(r.get("manager", ""))) # 담당자
            m.setItem(i, 11, QtGui.QStandardItem(r.get("memo", ""))) # 메모
            m.setItem(i, 12, QtGui.QStandardItem(str(r.get("parking", "")))) # 주차
            m.setItem(i, 13, QtGui.QStandardItem(r.get("building_usage", ""))) # 용도
            m.setItem(i, 14, QtGui.QStandardItem(str(r.get("approval_date", "")))) # 사용승인일
            rm_ = r.get("rooms", 0)
            bt_ = r.get("baths", 0)
            m.setItem(i, 15, QtGui.QStandardItem(f"{rm_}/{bt_}")) # 방/화장실
            m.setItem(i, 16, QtGui.QStandardItem(str(r.get("ad_end_date", "")))) # 광고종료일
            m.setItem(i, 17, QtGui.QStandardItem(r.get("photo_path", ""))) # 사진경로
            m.setItem(i, 18, QtGui.QStandardItem(r.get("owner_name", ""))) # 소유자명
            m.setItem(i, 19, QtGui.QStandardItem(r.get("owner_relation", ""))) # 관계

    def filter_serve_shop_by_address(self, address_str):
        """ Filters the table to show only rows matching the address_str. """
        # 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] ServeShopTab: 종료 중이므로 주소별 필터링을 건너뜁니다.")
            return
            
        # 주소 확인
        if not address_str:
            if not self.is_shutting_down:
                self.populate_serve_shop_table([])
            return

        rows_for_addr = self.serve_shop_dict.get(address_str, [])
        
        # 종료 확인 후 테이블 채우기
        if not self.is_shutting_down:
            self.populate_serve_shop_table(rows_for_addr)

    def auto_reload_serve_shop_data(self):
        """ Triggered by the timer to reload data based on parent_app's new_addresses, skipping cached ones. """
        # 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] ServeShopTab: 종료 중이므로 데이터 로드를 건너뜁니다.")
            return
            
        # parent_app이 유효한지 확인
        if not self.parent_app:
            print("[INFO] ServeShopTab: parent_app이 None이므로 데이터 로드를 건너뜁니다.")
            return
            
        # parent_app이 종료 중인지 확인
        if hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
            print("[INFO] ServeShopTab: 앱이 종료 중이므로 데이터 로드를 건너뜁니다.")
            return
            
        # executor가 이미 종료 상태인지 확인
        if (not hasattr(self.parent_app, 'executor') or 
            self.parent_app.executor is None or
            (hasattr(self.parent_app.executor, '_shutdown') and self.parent_app.executor._shutdown)):
            print("[INFO] ServeShopTab: executor가 없거나 이미 종료되어 데이터 로드를 건너뜁니다.")
            return
            
        if not hasattr(self.parent_app, 'new_addresses'):
            print("[WARN] ServeShopTab: Parent app or new_addresses not found, cannot reload.")
            return

        all_new_addresses = list(self.parent_app.new_addresses)
        if not all_new_addresses:
            return

        # Check local cache and filter out addresses that are already loaded
        addresses_to_check = [
            addr for addr in all_new_addresses
            if addr not in self.serve_shop_dict or not self.serve_shop_dict[addr] # Check if key exists and has data
        ]

        if not addresses_to_check:
            return

        print(f"[INFO] ServeShopTab: Found {len(addresses_to_check)} new/uncached addresses to load: {addresses_to_check[:5]}...") # Log only first 5

        future = self.parent_app.executor.submit(
            self._bg_load_shop_data_with_addresses,
            addresses_to_check # Pass only the addresses that need to be fetched
        )
        future.add_done_callback(self._on_shop_data_fetched)

    def _bg_load_shop_data_with_addresses(self, addresses_to_fetch: list):
        """ (Background Thread) Fetches serve_shop data ONLY for the given uncached addresses, using the original endpoint. """
        if not addresses_to_fetch: # Should not happen due to check in auto_reload, but as safety
            print("[WARN] ServeShopTab _bg_load: Received empty list of addresses to fetch.")
            return {"status": "empty", "data": [], "fetched_addresses": []}

        url = f"http://{self.server_host}:{self.server_port}/shop/get_serve_shop_data" # Changed prefix from /serve to /shop
        payload = {"addresses": addresses_to_fetch}
        try:
            # Keep using POST as it likely expects a list of addresses in the body
            resp = requests.post(url, json=payload, timeout=20) # Increased timeout, use POST
            resp.raise_for_status()
            j = resp.json()
            if j.get("status") == "ok":
                # Return fetched data AND the list of addresses that were requested
                return {"status": "ok", "data": j.get("data", []), "fetched_addresses": addresses_to_fetch}
            else:
                print(f"[ERROR] ServeShopTab _bg_load_shop_data: Server error: {j}")
                return {"status": "error", "data": [], "message": j.get("message", "Unknown server error"), "fetched_addresses": []}
        except requests.exceptions.RequestException as ex:
            print(f"[ERROR] ServeShopTab _bg_load_shop_data: Request failed: {ex}")
            return {"status": "exception", "message": str(ex), "data": [], "fetched_addresses": []}
        except Exception as ex:
            print(f"[ERROR] ServeShopTab _bg_load_shop_data: Unexpected error: {ex}")
            return {"status": "exception", "message": str(ex), "data": [], "fetched_addresses": []}


    def _on_shop_data_fetched(self, future):
        """ (Main Thread) Processes fetched shop data, updates cache, removes processed addresses from parent, and populates view. """
        # 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] ServeShopTab: Tab is shutting down, skipping data processing")
            return
            
        # 앱이 종료 중인지 확인
        if not self.parent_app or hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
            print("[INFO] ServeShopTab: Application is terminating, skipping data update")
            return
            
        try:
            result = future.result()
        except Exception as e:
            print(f"[ERROR] ServeShopTab _on_shop_data_fetched: Future error: {e}")
            return

        st = result.get("status")
        if st not in ["ok", "empty"]: # Allow "empty" status if no data was found for requested addresses
            print(f"[WARN] ServeShopTab: Auto-load failed or server error: {result}")
            return

        new_rows = result.get("data", [])
        # Get the list of addresses that were actually fetched in this batch
        fetched_addresses = result.get("fetched_addresses", [])

        if st == "ok" and new_rows:
            print(f"[INFO] ServeShopTab: Auto-refresh successfully loaded {len(new_rows)} shop items for {len(fetched_addresses)} addresses.")
        elif st == "empty" or (st == "ok" and not new_rows):
             print(f"[INFO] ServeShopTab: Auto-refresh completed for {len(fetched_addresses)} addresses, but no new data returned from server.")
        
        addresses_actually_updated = set() # Track addresses for which we received data

        # Update cache incrementally using the new_rows data
        for row in new_rows:
            addr_str = (row.get("dong", "") + " " + row.get("jibun", "")).strip()
            if addr_str:
                # If address not in dict or needs replacement, add/update it
                self.serve_shop_dict.setdefault(addr_str, []).append(row)
                addresses_actually_updated.add(addr_str)

        # Log cache status after update
        cached_addr_count = len(self.serve_shop_dict)

        # --- Remove successfully processed addresses from parent's set ---
        if fetched_addresses and hasattr(self.parent_app, 'new_addresses'):
            self.parent_app.new_addresses.difference_update(fetched_addresses)
        # ---------------------------------------------------------------

        # Emit signal only for addresses that were actually updated with new data
        if addresses_actually_updated and not self.is_shutting_down:
            for addr in addresses_actually_updated:
                self.data_loaded_for_address.emit(addr)

        # Decide whether to filter and populate based on current selection
        if not self.is_shutting_down:
            self.filter_and_populate() # Update view based on current selection state and new cache data

    def filter_and_populate(self):
        """ [변경됨] API 쿼리 기반으로 선택된 주소의 데이터를 실시간 로드합니다. """
        # 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] ServeShopTab: 종료 중이므로 데이터 로드를 건너뜁니다.")
            return
            
        # 앱 상태 확인
        if not self.parent_app:
            print("[INFO] ServeShopTab: parent_app이 None이므로 데이터 로드를 건너뜁니다.")
            return
            
        # 앱이 종료 중인지 확인
        if hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
            print("[INFO] ServeShopTab: 앱이 종료 중이므로 데이터 로드를 건너뜁니다.")
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
            print("[INFO] ServeShopTab: 선택된 주소가 없으므로 빈 테이블을 표시합니다.")
            if not self.is_shutting_down:
                self.populate_serve_shop_table([])
            return

        # API 쿼리로 실시간 데이터 로드
        print(f"[INFO] ServeShopTab: API 쿼리로 데이터 로드 시작 - 주소: {target_addresses}")
        
        # 백그라운드에서 API 호출
        if hasattr(self.parent_app, 'executor') and self.parent_app.executor:
            future = self.parent_app.executor.submit(
                self._bg_load_shop_data_for_addresses,
                target_addresses
            )
            future.add_done_callback(self._on_filter_data_loaded)
        else:
            print("[ERROR] ServeShopTab: 백그라운드 executor를 찾을 수 없습니다.")

    def _bg_load_shop_data_for_addresses(self, addresses_to_fetch: list):
        """ (Background Thread) API 쿼리로 지정된 주소들의 서빙 상가 데이터를 실시간 로드합니다. """
        if not addresses_to_fetch:
            print("[WARN] ServeShopTab _bg_load_shop_data_for_addresses: 빈 주소 리스트를 받았습니다.")
            return {"status": "empty", "data": [], "fetched_addresses": []}

        url = f"http://{self.server_host}:{self.server_port}/shop/get_serve_shop_data"
        payload = {"addresses": addresses_to_fetch}
        
        try:
            print(f"[DEBUG] ServeShopTab: API 요청 시작 - {url}, 주소: {addresses_to_fetch}")
            resp = requests.post(url, json=payload, timeout=20)
            resp.raise_for_status()
            j = resp.json()
            
            if j.get("status") == "ok":
                data = j.get("data", [])
                print(f"[INFO] ServeShopTab: API 응답 성공 - {len(data)}개 항목")
                return {"status": "ok", "data": data, "fetched_addresses": addresses_to_fetch}
            else:
                print(f"[ERROR] ServeShopTab API 응답 오류: {j}")
                return {"status": "error", "data": [], "message": j.get("message", "Unknown server error"), "fetched_addresses": []}
                
        except requests.exceptions.RequestException as ex:
            print(f"[ERROR] ServeShopTab API 요청 실패: {ex}")
            return {"status": "exception", "message": str(ex), "data": [], "fetched_addresses": []}
        except Exception as ex:
            print(f"[ERROR] ServeShopTab 예상치 못한 오류: {ex}")
            return {"status": "exception", "message": str(ex), "data": [], "fetched_addresses": []}

    def _on_filter_data_loaded(self, future):
        """ (Main Thread) API 쿼리 결과를 처리하고 테이블을 업데이트합니다. """
        # 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] ServeShopTab: 종료 중이므로 데이터 처리를 건너뜁니다.")
            return
            
        # 앱이 종료 중인지 확인
        if not self.parent_app or (hasattr(self.parent_app, 'terminating') and self.parent_app.terminating):
            print("[INFO] ServeShopTab: 앱이 종료 중이므로 데이터 업데이트를 건너뜁니다.")
            return
            
        try:
            result = future.result()
        except Exception as e:
            print(f"[ERROR] ServeShopTab _on_filter_data_loaded: Future 오류: {e}")
            if not self.is_shutting_down:
                self.populate_serve_shop_table([])  # 오류 시 빈 테이블
            return

        status = result.get("status")
        data = result.get("data", [])
        fetched_addresses = result.get("fetched_addresses", [])
        
        if status == "ok":
            print(f"[INFO] ServeShopTab: 데이터 로드 완료 - {len(data)}개 항목, 주소: {fetched_addresses}")
            if not self.is_shutting_down:
                # 딕셔너리 업데이트 - AllTab에서 데이터를 가져갈 수 있도록
                for row in data:
                    addr_str = (row.get("dong", "") + " " + row.get("jibun", "")).strip()
                    if addr_str:
                        # 기존 데이터를 새 데이터로 교체
                        self.serve_shop_dict[addr_str] = self.serve_shop_dict.get(addr_str, [])
                        if row not in self.serve_shop_dict[addr_str]:  # 중복 방지
                            self.serve_shop_dict[addr_str].append(row)
                
                self.populate_serve_shop_table(data)
                # 시그널 보내기 - AllTab에서 데이터 로드 완료를 감지할 수 있도록
                for addr in fetched_addresses:
                    if addr:  # 빈 주소가 아닌 경우만
                        self.data_loaded_for_address.emit(addr)
        elif status == "empty":
            print(f"[INFO] ServeShopTab: 주소 {fetched_addresses}에 대한 데이터가 없습니다.")
            if not self.is_shutting_down:
                self.populate_serve_shop_table([])
        else:
            error_msg = result.get("message", "Unknown error")
            print(f"[ERROR] ServeShopTab: 데이터 로드 실패 - {error_msg}")
            if not self.is_shutting_down:
                self.populate_serve_shop_table([])  # 오류 시 빈 테이블


    def load_data_for_specific_address(self, address_str: str):
        """ Loads data specifically for the given address string, ALWAYS using the cache. """
        # 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] ServeShopTab: 종료 중이므로 주소별 데이터 로드를 건너뜁니다.")
            return
            
        if not address_str:
            print("[WARN][ServeShopTab] load_data_for_specific_address called with empty address.")
            if not self.is_shutting_down:
                self.populate_serve_shop_table([]) # 명시적으로 빈 테이블 처리
            return

        print(f"[DEBUG][ServeShopTab] Populating from cache for address: {address_str}")
        # <<< 항상 캐시에서 데이터를 가져오도록 변경 >>>
        if not self.is_shutting_down:
            self.filter_and_populate() # 이 함수 내부에서 캐시를 읽고 테이블을 채움

    def get_data_for_address(self, addr_str: str) -> list:
        """ Returns the list of serve shop items for the given address from the local cache. """
        # 종료 상태 확인
        if self.is_shutting_down:
            print(f"[INFO] ServeShopTab: 종료 중이므로 주소 '{addr_str}'에 대한 데이터 요청을 건너뜁니다.")
            return []
            
        return self.serve_shop_dict.get(addr_str, [])
        
    def _get_headers(self):
        """ Returns the list of headers for the serve_shop tab. """
        return [
            "주소", "호", "층", "보증금/월세", "관리비",
            "권리금", "현업종", "평수", "연락처", "매물번호",
            "담당자", "메모",
            "주차", "용도", "사용승인일", "방/화장실",
            "광고종료일", "사진경로", "소유자명", "관계"
        ] 

    def terminate(self):
        """프로그램 종료 시 호출하여 타이머, 시그널 등의 리소스 정리"""
        print("[INFO] ServeShopTab: Terminating...")
        self.is_shutting_down = True
        
        # 타이머 정지 강화된 예외 처리
        if hasattr(self, 'serve_shop_timer') and self.serve_shop_timer:
            try:
                if self.serve_shop_timer.isActive():
                    self.serve_shop_timer.stop()
                    print("[INFO] ServeShopTab: Timer stopped")
                    
                # 타이머 연결 해제
                try:
                    self.serve_shop_timer.timeout.disconnect()
                    print("[INFO] ServeShopTab: Timer signal disconnected")
                except (TypeError, RuntimeError):
                    # 이미 연결이 끊어졌거나 예외가 발생했을 경우 무시
                    pass
                    
            except Exception as e:
                print(f"[WARN] ServeShopTab: 타이머 정지 중 오류: {e}")
                
        print("[INFO] ServeShopTab: Termination complete") 