# mylist_shop_tab.py
import os
import glob
import requests
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSignal, QObject, Qt
from PyQt5.QtWidgets import (
    QTableView, QWidget, QTableWidget, QTableWidgetItem, QHeaderView, 
    QAbstractItemView, QMenu
)
from dialogs import ImageSlideshowWindow, EditConfirmMemoDialog, StatusChangeDialog, MultiRowMemoDialog
# Import moved utility functions
from ui_utils import restore_qtableview_column_widths, save_qtableview_column_widths
import logging # Add logging import at the top if not present
from mylist_constants import RE_AD_BG_COLOR, NEW_AD_BG_COLOR # 상수 임포트

# Inherit from QObject
class MyListShopTab(QObject):
    # Add the signal definition
    data_loaded_for_address = pyqtSignal(str)
    
    def __init__(self, parent_app=None, server_host=None, server_port=None):
        super().__init__() # Call QObject initializer
        self.parent_app = parent_app
        self.server_host = server_host
        self.server_port = server_port
        self.logger = logging.getLogger(__name__) # Add logger instance

        self.mylist_shop_model = None
        self.mylist_shop_view = None
        self.mylist_shop_dict = {} # Cache for mylist_shop data by address
        self.mylist_shop_timer = None
        self.slider_window = None
        self.is_shutting_down = False  # 종료 상태 플래그 추가

    def init_tab(self, main_tabs_widget):
        """
        Initializes the '마이리스트(상가)' tab UI components.
        """
        container = QtWidgets.QWidget()
        vlay = QtWidgets.QVBoxLayout(container)

        self.mylist_shop_model = QtGui.QStandardItemModel()
        headers = self._get_headers()
        self.mylist_shop_model.setColumnCount(len(headers))
        self.mylist_shop_model.setHorizontalHeaderLabels(headers)

        self.mylist_shop_view = QTableView()
        self.mylist_shop_view.setModel(self.mylist_shop_model)
        self.mylist_shop_view.setSortingEnabled(True)
        self.mylist_shop_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.mylist_shop_view.clicked.connect(self.on_mylist_shop_clicked)
        # Connect selection change signal - currentChanged 시그널 연결을 mylist_shop_tab.py로 위임
        selection_model = self.mylist_shop_view.selectionModel()
        if selection_model:
            self.logger.info(f"MyListShopTab.init_tab: Got selection model: {selection_model}")
            # selection_model.currentChanged.connect(self.on_mylist_current_changed)  # DISABLED
            self.logger.info("MyListShopTab.init_tab: currentChanged 시그널 연결 비활성화 - base_container에서 처리")
        else:
            self.logger.error("MyListShopTab.init_tab: FAILED to get selection model (view.selectionModel() is None). Cannot connect currentChanged.")

        # Restore column widths using utility function
        restore_qtableview_column_widths(
            self.parent_app.settings_manager, 
            self.mylist_shop_view, 
            "MyListShopTableTab" # Use the key from closeEvent
        )
        # Save column widths on resize using utility function
        self.mylist_shop_view.horizontalHeader().sectionResized.connect(
            lambda: save_qtableview_column_widths(
                self.parent_app.settings_manager, 
                self.mylist_shop_view, 
                "MyListShopTableTab" # Use the key from closeEvent
            )
        )

        vlay.addWidget(self.mylist_shop_view)
        container.setLayout(vlay)
        main_tabs_widget.addTab(container, "마이리스트(상가)")

        # Setup and start the timer
        try:
            # 이미 종료 상태인지 확인
            if self.is_shutting_down:
                self.logger.info("MyListShopTab: 이미 종료 중이므로 타이머를 시작하지 않습니다.")
                return
                
            # [자동 타이머 비활성화] 성능 최적화를 위해 자동 리로드 타이머를 비활성화함
            # 사용자가 필요시 수동으로 새로고침하도록 변경
            self.logger.info("MyListShopTab: 자동 리로드 타이머가 성능 최적화를 위해 비활성화되었습니다.")
            
            # self.mylist_shop_timer = QtCore.QTimer(self.parent_app)
            # self.mylist_shop_timer.setInterval(30 * 1000)  # 30 seconds interval
            
            # # 연결 전에 기존 연결이 있는지 확인하고 해제
            # try:
            #     # 새로 만든 타이머이므로 연결 오류는 없겠지만 안전하게 처리
            #     self.mylist_shop_timer.timeout.disconnect()
            # except (TypeError, RuntimeError):
            #     # 기존 연결이 없으면 오류가 발생하므로 무시
            #     pass
                
            # self.mylist_shop_timer.timeout.connect(self.auto_reload_mylist_shop_data)
            
            # [제거됨] 초기 데이터 로드 - 성능 최적화를 위해 비활성화
            # MyList 데이터는 백그라운드에서 지연 로딩됨 (main_app_test.py에서 3초 후)
            # self.auto_reload_mylist_shop_data() # 비활성화
            # print("[INFO] MyListShopTab: 타이머 시작 완료 (30초 간격)")
            # self.mylist_shop_timer.start()
        except Exception as e:
            self.logger.error(f"MyListShopTab: 타이머 초기화 중 오류 발생: {e}", exc_info=True)

    def on_mylist_shop_clicked(self, index: QtCore.QModelIndex):
        """
        Handles clicks on the mylist_shop table, specifically for opening image slideshows.
        Triggered only when the first column (주소) is clicked.
        """
        # 종료 상태 확인
        if self.is_shutting_down:
            self.logger.info("MyListShopTab: 종료 중이므로 클릭 이벤트를 처리하지 않습니다.")
            return
            
        if not index.isValid() or index.column() != 0:
            return

        item_clicked = self.mylist_shop_model.item(index.row(), 0)
        if not item_clicked:
            return

        folder_path = item_clicked.data(QtCore.Qt.UserRole + 10) or ""
        if not folder_path or not os.path.isdir(folder_path):
            # Optionally inform the user if the path is invalid
            # QtWidgets.QMessageBox.warning(self.parent_app, "폴더 오류", f"사진 폴더 경로가 유효하지 않습니다:\n{folder_path}")
            return

        image_files = sorted(
            glob.glob(os.path.join(folder_path, "*.jpg")) +
            glob.glob(os.path.join(folder_path, "*.jpeg")) +
            glob.glob(os.path.join(folder_path, "*.png")) +
            glob.glob(os.path.join(folder_path, "*.gif"))
        )
        if not image_files:
            QtWidgets.QMessageBox.warning(self.parent_app, "이미지 없음", "선택된 매물의 사진 폴더에 이미지가 없습니다.")
            return

        # 앱이 종료 중인지 다시 확인
        if self.is_shutting_down or (hasattr(self.parent_app, 'terminating') and self.parent_app.terminating):
            self.logger.info("MyListShopTab: 이미지 슬라이드쇼를 열기 전 앱이 종료 중임을 감지했습니다.")
            return
            
        # Reuse or create the slideshow window
        if hasattr(self.parent_app, 'slider_window') and self.parent_app.slider_window and self.parent_app.slider_window.isVisible():
             self.parent_app.slider_window.set_image_list(image_files)
             self.parent_app.slider_window.activateWindow()
             self.parent_app.slider_window.raise_()
        else:
             # Make sure ImageSlideshowWindow is imported in the main app or globally accessible
             # Assuming it's imported in parent_app's scope
             self.parent_app.slider_window = ImageSlideshowWindow(image_files, parent=self.parent_app)
             self.parent_app.slider_window.show()

    def populate_mylist_shop_table(self, rows):
        """ Populates the mylist_shop table view with the given rows data. """
        # 종료 상태 확인
        if self.is_shutting_down:
            self.logger.info("MyListShopTab: 종료 중이므로 테이블 채우기를 건너뜁니다.")
            return
            
        # 앱이 종료 중인지 확인
        if not self.parent_app or (hasattr(self.parent_app, 'terminating') and self.parent_app.terminating):
            self.logger.info("MyListShopTab: 앱이 종료 중이므로 테이블 채우기를 건너뜁니다.")
            return
            
        # 모델 객체가 유효한지 확인
        if not self.mylist_shop_model:
            self.logger.info("MyListShopTab: Model not available, skipping populate_mylist_shop_table")
            return
            
        try:
            m = self.mylist_shop_model
            m.setRowCount(0)
            if not rows: return

            headers = self._get_headers()
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

                item0 = QtGui.QStandardItem(addr_)
                if rep_img_path and os.path.isfile(rep_img_path):
                    pixmap = QtGui.QPixmap(rep_img_path).scaled(
                        24, 24, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation
                    )
                    icon = QtGui.QIcon(pixmap)
                    item0.setIcon(icon)
                    file_url = QtCore.QUrl.fromLocalFile(rep_img_path).toString()
                    html_tooltip = f'<img src="{file_url}" width="200">'
                    item0.setToolTip(html_tooltip)
                else:
                    item0.setToolTip("")

                item0.setData(folder_path, QtCore.Qt.UserRole + 10)
                item0.setData(rep_img_path, QtCore.Qt.UserRole + 11)
                item0.setData("마이리스트(상가)", QtCore.Qt.UserRole + 2) # Source identifier
                item0.setData(r.get("id", 0), QtCore.Qt.UserRole + 3) # Primary Key
                item0.setData(r.get("status_cd", ""), QtCore.Qt.UserRole + 1) # Status code
                m.setItem(i, 0, item0)

                # 1) 호
                m.setItem(i, 1, QtGui.QStandardItem(str(r.get("ho", ""))))
                # 2) 층
                cf = r.get("curr_floor", 0)
                tf = r.get("total_floor", 0)
                m.setItem(i, 2, QtGui.QStandardItem(f"{cf}/{tf}"))
                # 3) 보증금/월세
                dp = r.get("deposit", 0)
                mn = r.get("monthly", 0)
                m.setItem(i, 3, QtGui.QStandardItem(f"{dp}/{mn}"))
                # 4) 관리비
                m.setItem(i, 4, QtGui.QStandardItem(str(r.get("manage_fee", ""))))
                # 5) 권리금
                m.setItem(i, 5, QtGui.QStandardItem(str(r.get("premium", ""))))
                # 6) 현업종
                m.setItem(i, 6, QtGui.QStandardItem(r.get("current_use", "")))
                # 7) 평수
                m.setItem(i, 7, QtGui.QStandardItem(str(r.get("area", ""))))
                # 8) 연락처
                m.setItem(i, 8, QtGui.QStandardItem(r.get("owner_phone", "")))
                # 9) 매물번호
                nav = r.get("naver_property_no", "")
                srv = r.get("serve_property_no", "")
                mm_ = f"{nav}/{srv}" if (nav or srv) else ""
                m.setItem(i, 9, QtGui.QStandardItem(mm_))
                # 10) 담당자
                m.setItem(i, 10, QtGui.QStandardItem(r.get("manager", "")))
                # 11) 메모
                m.setItem(i, 11, QtGui.QStandardItem(r.get("memo", "")))
                # 12) 주차대수
                m.setItem(i, 12, QtGui.QStandardItem(str(r.get("parking", ""))))
                # 13) 용도
                m.setItem(i, 13, QtGui.QStandardItem(r.get("building_usage", "")))
                # 14) 사용승인일
                m.setItem(i, 14, QtGui.QStandardItem(str(r.get("approval_date", ""))))
                # 15) 방/화장실
                rm_ = r.get("rooms", "")
                bt_ = r.get("baths", "")
                m.setItem(i, 15, QtGui.QStandardItem(f"{rm_}/{bt_}"))
                # 16) 광고종료일
                m.setItem(i, 16, QtGui.QStandardItem(str(r.get("ad_end_date", ""))))
                # 17) 사진경로
                m.setItem(i, 17, QtGui.QStandardItem(r.get("photo_path", "")))
                # 18) 소유자명
                m.setItem(i, 18, QtGui.QStandardItem(r.get("owner_name", "")))
                # 19) 관계
                m.setItem(i, 19, QtGui.QStandardItem(r.get("owner_relation", "")))

                # 20) 재광고여부
                re_ad_val = (r.get("re_ad_yn", "N") or "N").upper()
                re_ad_str = "재광고" if re_ad_val == "Y" else "새광고"
                item_re = QtGui.QStandardItem(re_ad_str)
                m.setItem(i, 20, item_re)

                # Set background color based on re_ad_yn
                row_bg = RE_AD_BG_COLOR if re_ad_val == "Y" else NEW_AD_BG_COLOR
                for c_i in range(m.columnCount()):
                    cell_item = m.item(i, c_i)
                    if cell_item:
                        cell_item.setBackground(row_bg)
        except Exception as e:
            self.logger.error(f"MyListShopTab: 테이블 채우기 중 오류 발생: {e}", exc_info=True)

    def auto_reload_mylist_shop_data(self):
        """
        Triggered by the timer or other actions to reload mylist shop data.
        """
        # 종료 상태 확인
        if self.is_shutting_down:
            self.logger.info("MyListShopTab: 종료 중이므로 데이터 로드를 건너뜁니다.")
            return
            
        # parent_app이 유효한지 확인
        if not self.parent_app:
            self.logger.info("MyListShopTab: parent_app이 None이므로 데이터 로드를 건너뜁니다.")
            return
            
        # parent_app이 종료 중인지 확인
        if hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
            self.logger.info("MyListShopTab: 앱이 종료 중이므로 데이터 로드를 건너뜁니다.")
            return
            
        # executor가 이미 종료 상태인지 확인
        if (not hasattr(self.parent_app, 'executor') or 
            self.parent_app.executor is None or
            getattr(self.parent_app.executor, '_shutdown', False)):
            self.logger.warning("MyListShopTab: Executor is already shut down, skipping auto reload")
            return
            
        try:
            future = self.parent_app.executor.submit(self._bg_load_all_mylist_shop_data)
            future.add_done_callback(self._on_mylist_shop_data_fetched)
        except RuntimeError as e:
            self.logger.error(f"MyListShopTab: ThreadPoolExecutor 작업 예약 실패: {e}")
        except Exception as e:
            self.logger.error(f"MyListShopTab: 데이터 로드 중 예외 발생: {e}", exc_info=True)

    def _bg_load_all_mylist_shop_data(self):
        """ (Background Thread) Fetches all mylist_shop data for the current manager/role. """
        url = f"http://{self.server_host}:{self.server_port}/mylist/get_all_mylist_shop_data"
        params = {"manager": self.parent_app.current_manager, "role": self.parent_app.current_role}
        try:
            resp = requests.get(url, params=params, timeout=10) # Increased timeout
            resp.raise_for_status()
            j = resp.json()
            return j # Returns the full JSON response which includes status and data
        except requests.exceptions.RequestException as ex:
            print(f"[ERROR] MyListShopTab _bg_load: Request failed: {ex}")
            return {"status": "exception", "message": str(ex), "data": []}
        except Exception as ex:
            print(f"[ERROR] MyListShopTab _bg_load: Unexpected error: {ex}")
            return {"status": "exception", "message": str(ex), "data": []}

    def _on_mylist_shop_data_fetched(self, future):
        """ (Main Thread) Processes fetched data, updates cache, and populates view. """
        # 종료 상태 확인
        if self.is_shutting_down:
            self.logger.info("MyListShopTab: Tab is shutting down, skipping data processing")
            return
            
        # 앱이 종료 중인지 확인
        if not self.parent_app or hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
            self.logger.info("MyListShopTab: Application is terminating, skipping data update")
            return
            
        # 모델 객체가 유효한지 확인
        if not self.mylist_shop_model:
            self.logger.info("MyListShopTab: Model not available, skipping data update")
            return
            
        try:
            result = future.result()
        except Exception as e:
            self.logger.error(f"MyListShopTab _on_fetched: Future error: {e}", exc_info=True)
            return

        if result.get("status") != "ok":
            self.logger.warning(f"MyListShopTab: Auto-load failed: {result}")
            # Optionally show error to user
            return

        new_rows = result.get("data", [])
        print(f"[INFO] MyListShopTab: Auto-refresh loaded {len(new_rows)} items.")

        # Update cache
        self.mylist_shop_dict.clear() # Clear before populating cache
        loaded_addresses_in_batch = set()
        for row in new_rows:
            addr_str = (row.get("dong", "") + " " + row.get("jibun", "")).strip()
            if addr_str:
                self.mylist_shop_dict.setdefault(addr_str, []).append(row)
                loaded_addresses_in_batch.add(addr_str) # Track loaded addresses
                # --- Add address to parent's set for preloading other tabs --- 
                if hasattr(self.parent_app, 'new_addresses'):
                     self.parent_app.new_addresses.add(addr_str)
                # ---------------------------------------------------------------

        # Log cache status
        cached_addr_count = len(self.mylist_shop_dict)
        sample_keys = list(self.mylist_shop_dict.keys())[:10]
        print(f"[DEBUG][MyListShopTab] Cached {cached_addr_count} addresses: {sample_keys}")

        # 앱이 종료 중인지 다시 확인
        if self.is_shutting_down or (hasattr(self.parent_app, 'terminating') and self.parent_app.terminating):
            self.logger.info("MyListShopTab: Application is now terminating, skipping signal emission and UI update")
            return
            
        # Emit signal for addresses loaded in this batch
        for addr in loaded_addresses_in_batch:
            self.data_loaded_for_address.emit(addr)
            
        # Log address count if specific address was selected
        if self.parent_app.last_selected_address in self.mylist_shop_dict:
            count = len(self.mylist_shop_dict[self.parent_app.last_selected_address])
            print(f"[DEBUG][MyListShopTab] Current selected address '{self.parent_app.last_selected_address}' has {count} rows in cache")
        
        # UI 업데이트 전 마지막으로 종료 상태 확인
        if not self.is_shutting_down:
            self.filter_and_populate() # Update view based on current selection


    def filter_and_populate(self):
        """ [변경됨] API 쿼리 기반으로 선택된 주소의 마이리스트 데이터를 실시간 로드합니다. """
        # 종료 상태 확인
        if self.is_shutting_down:
            self.logger.info("MyListShopTab: 종료 중이므로 데이터 로드를 건너뜁니다.")
            return
            
        # 앱 상태 확인
        if not self.parent_app:
            self.logger.info("MyListShopTab: parent_app이 None이므로 데이터 로드를 건너뜁니다.")
            return
            
        # 앱이 종료 중인지 확인
        if hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
            self.logger.info("MyListShopTab: 앱이 종료 중이므로 데이터 로드를 건너뜁니다.")
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
            self.logger.info("MyListShopTab: 선택된 주소가 없으므로 빈 테이블을 표시합니다.")
            if not self.is_shutting_down:
                self.populate_mylist_shop_table([])
            return

        # API 쿼리로 실시간 데이터 로드
        self.logger.info(f"MyListShopTab: API 쿼리로 데이터 로드 시작 - 주소: {target_addresses}")
        
        # 백그라운드에서 API 호출
        if hasattr(self.parent_app, 'executor') and self.parent_app.executor:
            future = self.parent_app.executor.submit(
                self._bg_load_mylist_data_for_addresses,
                target_addresses
            )
            future.add_done_callback(self._on_filter_data_loaded)
        else:
            self.logger.error("MyListShopTab: 백그라운드 executor를 찾을 수 없습니다.")

    def _bg_load_mylist_data_for_addresses(self, addresses_to_fetch: list):
        """ (Background Thread) API 쿼리로 지정된 주소들의 마이리스트 데이터를 실시간 로드합니다. """
        if not addresses_to_fetch:
            print("[WARN] MyListShopTab _bg_load_mylist_data_for_addresses: 빈 주소 리스트를 받았습니다.")
            return {"status": "empty", "data": [], "fetched_addresses": []}

        url = f"http://{self.server_host}:{self.server_port}/mylist/get_mylist_shop_data"
        payload = {"addresses": addresses_to_fetch}
        
        try:
            print(f"[DEBUG] MyListShopTab: API 요청 시작 - {url}, 주소: {addresses_to_fetch}")
            resp = requests.post(url, json=payload, timeout=20)
            resp.raise_for_status()
            j = resp.json()
            
            if j.get("status") == "ok":
                data = j.get("data", [])
                print(f"[INFO] MyListShopTab: API 응답 성공 - {len(data)}개 항목")
                return {"status": "ok", "data": data, "fetched_addresses": addresses_to_fetch}
            else:
                print(f"[ERROR] MyListShopTab API 응답 오류: {j}")
                return {"status": "error", "data": [], "message": j.get("message", "Unknown server error"), "fetched_addresses": []}
                
        except requests.exceptions.RequestException as ex:
            print(f"[ERROR] MyListShopTab API 요청 실패: {ex}")
            return {"status": "exception", "message": str(ex), "data": [], "fetched_addresses": []}
        except Exception as ex:
            print(f"[ERROR] MyListShopTab 예상치 못한 오류: {ex}")
            return {"status": "exception", "message": str(ex), "data": [], "fetched_addresses": []}

    def _on_filter_data_loaded(self, future):
        """ (Main Thread) API 쿼리 결과를 처리하고 테이블을 업데이트합니다. """
        # 종료 상태 확인
        if self.is_shutting_down:
            self.logger.info("MyListShopTab: 종료 중이므로 데이터 처리를 건너뜁니다.")
            return
            
        # 앱이 종료 중인지 확인
        if not self.parent_app or (hasattr(self.parent_app, 'terminating') and self.parent_app.terminating):
            self.logger.info("MyListShopTab: 앱이 종료 중이므로 데이터 업데이트를 건너뜁니다.")
            return
            
        try:
            result = future.result()
        except Exception as e:
            self.logger.error(f"MyListShopTab _on_filter_data_loaded: Future 오류: {e}")
            if not self.is_shutting_down:
                self.populate_mylist_shop_table([])  # 오류 시 빈 테이블
            return

        status = result.get("status")
        data = result.get("data", [])
        fetched_addresses = result.get("fetched_addresses", [])
        
        if status == "ok":
            self.logger.info(f"MyListShopTab: 데이터 로드 완료 - {len(data)}개 항목, 주소: {fetched_addresses}")
            if not self.is_shutting_down:
                # 딕셔너리 업데이트 - AllTab에서 데이터를 가져갈 수 있도록
                for row in data:
                    addr_str = (row.get("dong", "") + " " + row.get("jibun", "")).strip()
                    if addr_str:
                        # 기존 데이터를 새 데이터로 교체
                        self.mylist_shop_dict[addr_str] = self.mylist_shop_dict.get(addr_str, [])
                        if row not in self.mylist_shop_dict[addr_str]:  # 중복 방지
                            self.mylist_shop_dict[addr_str].append(row)
                
                self.populate_mylist_shop_table(data)
                # 시그널 보내기 - AllTab에서 데이터 로드 완료를 감지할 수 있도록
                for addr in fetched_addresses:
                    if addr:  # 빈 주소가 아닌 경우만
                        self.data_loaded_for_address.emit(addr)
        elif status == "empty":
            self.logger.info(f"MyListShopTab: 주소 {fetched_addresses}에 대한 데이터가 없습니다.")
            if not self.is_shutting_down:
                self.populate_mylist_shop_table([])
        else:
            error_msg = result.get("message", "Unknown error")
            self.logger.error(f"MyListShopTab: 데이터 로드 실패 - {error_msg}")
            if not self.is_shutting_down:
                self.populate_mylist_shop_table([])  # 오류 시 빈 테이블

    def filter_mylist_shop_by_address(self, address_str: str):
        """ Filters the table to show only rows matching the address_str. """
        # 종료 상태 확인
        if self.is_shutting_down:
            self.logger.info("MyListShopTab: 종료 중이므로 주소별 필터링을 건너뜁니다.")
            return
            
        # 주소 확인
        if not address_str:
            if not self.is_shutting_down:
                self.populate_mylist_shop_table([])
            return

        rows_for_addr = self.mylist_shop_dict.get(address_str, [])
        
        # 종료 확인 후 테이블 채우기
        if not self.is_shutting_down:
            self.populate_mylist_shop_table(rows_for_addr)

    def terminate(self):
        """프로그램 종료 시 호출하여 타이머, 시그널 등의 리소스 정리"""
        self.logger.info("MyListShopTab: Terminating...")
        self.is_shutting_down = True
        
        # 타이머 정지 강화된 예외 처리
        if hasattr(self, 'mylist_shop_timer') and self.mylist_shop_timer:
            try:
                if self.mylist_shop_timer.isActive():
                    self.mylist_shop_timer.stop()
                    self.logger.info("MyListShopTab: Timer stopped")
                    
                # 타이머 연결 해제
                try:
                    self.mylist_shop_timer.timeout.disconnect()
                    self.logger.info("MyListShopTab: Timer signal disconnected")
                except (TypeError, RuntimeError):
                    # 이미 연결이 끊어졌거나 예외가 발생했을 경우 무시
                    pass
                    
            except Exception as e:
                self.logger.error(f"MyListShopTab: Error stopping timer: {e}", exc_info=True)

        # 모델 데이터 정리
        if hasattr(self, 'mylist_shop_model') and self.mylist_shop_model:
            try:
                self.mylist_shop_model.setRowCount(0)
                self.logger.info("MyListShopTab: Model data cleared")
            except Exception as e:
                self.logger.error(f"MyListShopTab: Error clearing model data: {e}", exc_info=True)

        # 캐시 정리
        self.mylist_shop_dict.clear()
        
        self.logger.info("MyListShopTab: Termination complete")

    def on_mylist_current_changed(self, current: QtCore.QModelIndex, previous: QtCore.QModelIndex):
        """
        Handles selection changes in the mylist_shop table.
        Updates the bottom container with data for the selected address.
        """
        # 종료 상태 확인
        if self.is_shutting_down:
            self.logger.info("MyListShopTab: 종료 중이므로 선택 변경 이벤트를 처리하지 않습니다.")
            return
            
        # 앱이 종료 중인지 확인
        if hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
            self.logger.info("MyListShopTab: 앱이 종료 중이므로 선택 변경 이벤트를 처리하지 않습니다.")
            return
            
        self.logger.critical("<<<<< MyListShopTab.on_mylist_current_changed CALLED! >>>>>")
        if not current.isValid():
            self.logger.debug("MyListShopTab.on_mylist_current_changed: Invalid index, returning.")
            return

        model = self.mylist_shop_model
        row = current.row()

        # Ensure column 0 (Address) exists and get the item
        if model.columnCount() > 0:
            addr_item = model.item(row, 0)
            if addr_item:
                address_string = addr_item.text()
                self.logger.info(f"MyListShopTab: Extracted address: '{address_string}'")

                # Update the mylist container with the selected address
                if hasattr(self.parent_app, 'mylist_tab') and hasattr(self.parent_app.mylist_tab, 'update_selection_from_mylist'):
                    self.logger.debug(f"MyListShopTab: Calling update_selection_from_mylist for: {address_string}")
                    try:
                        self.parent_app.mylist_tab.update_selection_from_mylist(address_string)
                        self.logger.info("MyListShopTab: Successfully called update_selection_from_mylist")
                    except Exception as e:
                        self.logger.error(f"MyListShopTab: Error calling update_selection_from_mylist: {e}", exc_info=True)
                else:
                    self.logger.error("MyListShopTab: parent_app.mylist_tab.update_selection_from_mylist not available!")
            else:
                 self.logger.warning(f"MyListShopTab.on_mylist_current_changed: Address item (col 0) not found for row {row}.")
        else:
            self.logger.warning("MyListShopTab.on_mylist_current_changed: Model column count is 0.")

    def get_data_for_address(self, addr_str: str) -> list:
        """ Returns the list of mylist shop items for the given address from the local cache. """
        # 종료 상태 확인
        if self.is_shutting_down:
            self.logger.info(f"MyListShopTab: 종료 중이므로 주소 '{addr_str}'에 대한 데이터 요청을 건너뜁니다.")
            return []
            
        return self.mylist_shop_dict.get(addr_str, [])

    def _get_headers(self):
        """ Returns the list of headers for the mylist_shop tab. """
        return [
            "주소", "호", "층", "보증금/월세", "관리비",
            "권리금", "현업종", "평수", "연락처", "매물번호",
            "담당자", "메모",
            "주차대수", "용도", "사용승인일", "방/화장실",
            "광고종료일", "사진경로", "소유자명", "관계",
            "재광고여부"
        ] 