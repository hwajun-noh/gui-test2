# completed_deals_tab.py
import requests
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QMessageBox, QTableView, QHeaderView
from ui_utils import restore_qtableview_column_widths, save_qtableview_column_widths

class CompletedDealsTab(QObject):
    data_loaded_for_address = pyqtSignal(str)

    def __init__(self, parent_app=None, server_host=None, server_port=None):
        super().__init__()
        self.parent_app = parent_app
        self.server_host = server_host
        self.server_port = server_port

        self.completed_deals_model = None
        self.completed_deals_view = None
        self.completed_deals_dict = {} # Cache for completed deals data by address
        self.completed_deals_timer = None
        self.is_shutting_down = False  # 종료 상태 플래그 추가

    def init_tab(self, main_tabs_widget):
        """
        Initializes the '계약완료' tab UI components.
        """
        container = QtWidgets.QWidget()
        vlay = QtWidgets.QVBoxLayout(container)

        self.completed_deals_model = QtGui.QStandardItemModel()
        headers = self._get_headers()
        self.completed_deals_model.setColumnCount(len(headers))
        self.completed_deals_model.setHorizontalHeaderLabels(headers)

        self.completed_deals_view = QTableView()
        self.completed_deals_view.setModel(self.completed_deals_model)
        self.completed_deals_view.setSortingEnabled(True)
        self.completed_deals_view.horizontalHeader().setStretchLastSection(True)

        # Restore column widths using utility function
        restore_qtableview_column_widths(
            self.parent_app.settings_manager, 
            self.completed_deals_view, 
            "CompletedDealsTable"
        )
        # Save column widths on resize using utility function
        self.completed_deals_view.horizontalHeader().sectionResized.connect(
            lambda: save_qtableview_column_widths(
                self.parent_app.settings_manager, 
                self.completed_deals_view, 
                "CompletedDealsTable"
            )
        )

        vlay.addWidget(self.completed_deals_view)
        container.setLayout(vlay)
        main_tabs_widget.addTab(container, "계약완료")

        # Setup and start the timer
        try:
            # 이미 종료 상태인지 확인
            if self.is_shutting_down:
                print("[INFO] CompletedDealsTab: 이미 종료 중이므로 타이머를 시작하지 않습니다.")
                return
                
            # [자동 타이머 비활성화] 성능 최적화를 위해 자동 리로드 타이머를 비활성화함
            # 사용자가 필요시 수동으로 새로고침하도록 변경
            print("[INFO] CompletedDealsTab: 자동 리로드 타이머가 성능 최적화를 위해 비활성화되었습니다.")
            
            # self.completed_deals_timer = QtCore.QTimer(self.parent_app)
            # self.completed_deals_timer.setInterval(30 * 1000)  # 30 seconds interval
            
            # # 연결 전에 기존 연결이 있는지 확인하고 해제
            # try:
            #     # 새로 만든 타이머이므로 연결 오류는 없겠지만 안전하게 처리
            #     self.completed_deals_timer.timeout.disconnect()
            # except (TypeError, RuntimeError):
            #     # 기존 연결이 없으면 오류가 발생하므로 무시
            #     pass
                
            # self.completed_deals_timer.timeout.connect(self.auto_reload_completed_deals_data)
            
            # [제거됨] 초기 데이터 로드 - 성능 최적화를 위해 비활성화
            # 필요시 사용자가 주소 선택 시 filter_and_populate()에서 실시간 로드됨
            # self.auto_reload_completed_deals_data() # 비활성화
            
            # # 타이머 시작
            # self.completed_deals_timer.start()
            # print("[INFO] CompletedDealsTab: 타이머 시작 완료 (30초 간격)")
        except Exception as e:
            print(f"[ERROR] CompletedDealsTab: 타이머 초기화 중 오류 발생: {e}")
            import traceback
            print(traceback.format_exc())

    def auto_reload_completed_deals_data(self):
        """
        Triggered by the timer to reload completed deals data.
        """
        # 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] CompletedDealsTab: 종료 중이므로 데이터 로드를 건너뜁니다.")
            return
            
        # parent_app이 유효한지 확인
        if not self.parent_app:
            print("[INFO] CompletedDealsTab: parent_app이 None이므로 데이터 로드를 건너뜁니다.")
            return
            
        # parent_app이 종료 중인지 확인
        if hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
            print("[INFO] CompletedDealsTab: 앱이 종료 중이므로 데이터 로드를 건너뜁니다.")
            return
            
        # executor가 이미 종료 상태인지 확인
        if (not hasattr(self.parent_app, 'executor') or 
            self.parent_app.executor is None or
            (hasattr(self.parent_app.executor, '_shutdown') and 
             self.parent_app.executor._shutdown)):
            print("[WARN] CompletedDealsTab: Executor is already shut down, skipping auto reload")
            return
            
        try:
            future = self.parent_app.executor.submit(self._bg_load_completed_deals_data)
            future.add_done_callback(self._on_completed_deals_data_fetched)
        except RuntimeError as e:
            print(f"[WARN] CompletedDealsTab: RuntimeError during executor submit: {e}")
        except Exception as e:
            print(f"[ERROR] CompletedDealsTab: 데이터 로드 요청 중 예외 발생: {e}")
            import traceback
            print(traceback.format_exc())

    def _bg_load_completed_deals_data(self):
        """
        (Background Thread) Fetches completed deals data from the server.
        """
        url = f"http://{self.server_host}:{self.server_port}/completed/get_completed_deals"
        try:
            resp = requests.get(url, timeout=10) # Increased timeout
            resp.raise_for_status()
            j = resp.json()
            if j.get("status") == "ok":
                return {"status": "ok", "data": j.get("data", [])}
            else:
                print(f"[ERROR] CompletedDealsTab _bg_load: Server error: {j}")
                return {"status": "error", "data": [], "message": j.get("message", "Unknown server error")}
        except requests.exceptions.RequestException as ex:
            print(f"[ERROR] CompletedDealsTab _bg_load: Request failed: {ex}")
            return {"status": "exception", "message": str(ex), "data": []}
        except Exception as ex:
             print(f"[ERROR] CompletedDealsTab _bg_load: Unexpected error: {ex}")
             return {"status": "exception", "message": str(ex), "data": []}

    def _on_completed_deals_data_fetched(self, future):
        """
        (Main Thread) Processes fetched data, updates cache, and populates view.
        """
        # 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] CompletedDealsTab: Tab is shutting down, skipping data processing")
            return
            
        # 앱이 종료 중인지 확인
        if not self.parent_app or hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
            print("[INFO] CompletedDealsTab: Application is terminating, skipping data update")
            return
            
        # 모델 객체가 유효한지 확인
        if not hasattr(self, 'completed_deals_model') or not self.completed_deals_model:
            print("[INFO] CompletedDealsTab: Model not available, skipping data update")
            return
            
        try:
            result = future.result()
        except Exception as e:
            print(f"[ERROR] CompletedDealsTab _on_fetched: Future error: {e}")
            return

        st = result.get("status")
        if st != "ok":
            print(f"[WARN] CompletedDealsTab: Auto-load failed: {result}")
            return

        rows = result.get("data", [])
        print(f"[INFO] CompletedDealsTab: Auto-refresh loaded {len(rows)} items.")

        # 종료 중인지 다시 확인
        if self.is_shutting_down:
            print("[INFO] CompletedDealsTab: Tab is shutting down, skipping cache update")
            return
            
        # 모델이 여전히 유효한지 다시 확인
        if not hasattr(self, 'completed_deals_model') or not self.completed_deals_model:
            print("[INFO] CompletedDealsTab: Model no longer exists, skipping update")
            return

        # Update cache
        self.completed_deals_dict.clear()
        loaded_addresses = set()
        for r in rows:
            addr_ = (r.get("dong", "") + " " + r.get("jibun", "")).strip()
            if addr_:
                self.completed_deals_dict.setdefault(addr_, []).append(r)
                loaded_addresses.add(addr_)

        # 종료 중이 아닐 때만 시그널 발생
        if not self.is_shutting_down:
            # Emit signal for each loaded address
            for addr in loaded_addresses:
                self.data_loaded_for_address.emit(addr)

        # 마지막으로 UI 업데이트 전에 다시 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] CompletedDealsTab: Tab is shutting down, skipping UI update")
            return
            
        if not hasattr(self, 'completed_deals_model') or not self.completed_deals_model:
            print("[INFO] CompletedDealsTab: Model no longer exists, skipping filter and populate")
            return
            
        # Filter and populate based on current selection mode
        try:
            self.filter_and_populate()
        except RuntimeError as e:
            print(f"[INFO] CompletedDealsTab: Could not update UI, likely during shutdown: {e}")
            return
        except Exception as e:
            print(f"[ERROR] CompletedDealsTab: filter_and_populate 중 오류 발생: {e}")
            return

    def filter_and_populate(self):
        """ [변경됨] API 쿼리 기반으로 선택된 주소의 계약완료 데이터를 실시간 로드합니다. """
        # 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] CompletedDealsTab: 종료 중이므로 데이터 로드를 건너뜁니다.")
            return
            
        # 앱 상태 확인
        if not self.parent_app:
            print("[INFO] CompletedDealsTab: parent_app이 None이므로 데이터 로드를 건너뜁니다.")
            return
            
        # 앱이 종료 중인지 확인
        if hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
            print("[INFO] CompletedDealsTab: 앱이 종료 중이므로 데이터 로드를 건너뜁니다.")
            return
            
        # 모델 객체가 유효한지 확인
        if not hasattr(self, 'completed_deals_model') or not self.completed_deals_model:
            print("[INFO] CompletedDealsTab: Model not available, skipping filter_and_populate")
            return

        # 선택된 주소 가져오기
        target_addresses = []
        if hasattr(self.parent_app, 'from_customer_click') and self.parent_app.from_customer_click and hasattr(self.parent_app, 'selected_addresses') and self.parent_app.selected_addresses:
            # Multi-address mode from customer tab
            target_addresses = self.parent_app.selected_addresses
        elif hasattr(self.parent_app, 'last_selected_address') and self.parent_app.last_selected_address:
            # Single address mode (likely from manager_check_tab or mylist_shop_tab)
            target_addresses = [self.parent_app.last_selected_address]
        
        if not target_addresses:
            # No address selected, show empty table
            print("[INFO] CompletedDealsTab: 선택된 주소가 없으므로 빈 테이블을 표시합니다.")
            if not self.is_shutting_down:
                self.populate_completed_deals_table([])
            return

        # API 쿼리로 실시간 데이터 로드
        print(f"[INFO] CompletedDealsTab: API 쿼리로 데이터 로드 시작 - 주소: {target_addresses}")
        
        # 백그라운드에서 API 호출
        if hasattr(self.parent_app, 'executor') and self.parent_app.executor:
            future = self.parent_app.executor.submit(
                self._bg_load_completed_data_for_addresses,
                target_addresses
            )
            future.add_done_callback(self._on_filter_data_loaded)
        else:
            print("[ERROR] CompletedDealsTab: 백그라운드 executor를 찾을 수 없습니다.")

    def _bg_load_completed_data_for_addresses(self, addresses_to_fetch: list):
        """ (Background Thread) API 쿼리로 지정된 주소들의 계약완료 데이터를 실시간 로드합니다. """
        if not addresses_to_fetch:
            print("[WARN] CompletedDealsTab _bg_load_completed_data_for_addresses: 빈 주소 리스트를 받았습니다.")
            return {"status": "empty", "data": [], "fetched_addresses": []}

        url = f"http://{self.server_host}:{self.server_port}/completed/get_completed_deals"
        payload = {"addresses": addresses_to_fetch}
        
        try:
            print(f"[DEBUG] CompletedDealsTab: API 요청 시작 - {url}, 주소: {addresses_to_fetch}")
            resp = requests.post(url, json=payload, timeout=20)
            resp.raise_for_status()
            j = resp.json()
            
            if j.get("status") == "ok":
                data = j.get("data", [])
                print(f"[INFO] CompletedDealsTab: API 응답 성공 - {len(data)}개 항목")
                return {"status": "ok", "data": data, "fetched_addresses": addresses_to_fetch}
            else:
                print(f"[ERROR] CompletedDealsTab API 응답 오류: {j}")
                return {"status": "error", "data": [], "message": j.get("message", "Unknown server error"), "fetched_addresses": []}
                
        except requests.exceptions.RequestException as ex:
            print(f"[ERROR] CompletedDealsTab API 요청 실패: {ex}")
            return {"status": "exception", "message": str(ex), "data": [], "fetched_addresses": []}
        except Exception as ex:
            print(f"[ERROR] CompletedDealsTab 예상치 못한 오류: {ex}")
            return {"status": "exception", "message": str(ex), "data": [], "fetched_addresses": []}

    def _on_filter_data_loaded(self, future):
        """ (Main Thread) API 쿼리 결과를 처리하고 테이블을 업데이트합니다. """
        # 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] CompletedDealsTab: 종료 중이므로 데이터 처리를 건너뜁니다.")
            return
            
        # 앱이 종료 중인지 확인
        if not self.parent_app or (hasattr(self.parent_app, 'terminating') and self.parent_app.terminating):
            print("[INFO] CompletedDealsTab: 앱이 종료 중이므로 데이터 업데이트를 건너뜁니다.")
            return
            
        try:
            result = future.result()
        except Exception as e:
            print(f"[ERROR] CompletedDealsTab _on_filter_data_loaded: Future 오류: {e}")
            if not self.is_shutting_down:
                self.populate_completed_deals_table([])  # 오류 시 빈 테이블
            return

        status = result.get("status")
        data = result.get("data", [])
        fetched_addresses = result.get("fetched_addresses", [])
        
        if status == "ok":
            print(f"[INFO] CompletedDealsTab: 데이터 로드 완료 - {len(data)}개 항목, 주소: {fetched_addresses}")
            if not self.is_shutting_down:
                # 딕셔너리 업데이트 - AllTab에서 데이터를 가져갈 수 있도록
                for row in data:
                    addr_str = (row.get("dong", "") + " " + row.get("jibun", "")).strip()
                    if addr_str:
                        # 기존 데이터를 새 데이터로 교체
                        self.completed_deals_dict[addr_str] = self.completed_deals_dict.get(addr_str, [])
                        if row not in self.completed_deals_dict[addr_str]:  # 중복 방지
                            self.completed_deals_dict[addr_str].append(row)
                
                self.populate_completed_deals_table(data)
                # 시그널 보내기 - AllTab에서 데이터 로드 완료를 감지할 수 있도록
                for addr in fetched_addresses:
                    if addr:  # 빈 주소가 아닌 경우만
                        self.data_loaded_for_address.emit(addr)
        elif status == "empty":
            print(f"[INFO] CompletedDealsTab: 주소 {fetched_addresses}에 대한 데이터가 없습니다.")
            if not self.is_shutting_down:
                self.populate_completed_deals_table([])
        else:
            error_msg = result.get("message", "Unknown error")
            print(f"[ERROR] CompletedDealsTab: 데이터 로드 실패 - {error_msg}")
            if not self.is_shutting_down:
                self.populate_completed_deals_table([])  # 오류 시 빈 테이블

    def populate_completed_deals_table(self, rows):
        """ Populates the completed deals table view with the given rows data. """
        # 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] CompletedDealsTab: 종료 중이므로 테이블 채우기를 건너뜁니다.")
            return
            
        # 앱이 종료 중인지 확인
        if not self.parent_app or (hasattr(self.parent_app, 'terminating') and self.parent_app.terminating):
            print("[INFO] CompletedDealsTab: 앱이 종료 중이므로 테이블 채우기를 건너뜁니다.")
            return
            
        # 모델 객체가 유효한지 확인
        if not hasattr(self, 'completed_deals_model') or not self.completed_deals_model:
            print("[INFO] CompletedDealsTab: Model not available, skipping populate_completed_deals_table")
            return
            
        m = self.completed_deals_model
        
        try:
            m.setRowCount(0)
            if not rows: return
            
            headers = self._get_headers()
            m.setColumnCount(len(headers))
            m.setHorizontalHeaderLabels(headers)
            m.setRowCount(len(rows))
        except RuntimeError as e:
            print(f"[WARN] CompletedDealsTab: Model access error in populate_completed_deals_table: {e}")
            return
        except Exception as e:
            print(f"[ERROR] CompletedDealsTab: 테이블 초기화 중 오류 발생: {e}")
            return

        try:
            # 행 데이터 채우기 전에 종료 상태 재확인
            if self.is_shutting_down:
                print("[INFO] CompletedDealsTab: 종료 중이므로 행 데이터 채우기를 건너뜁니다.")
                return
                
            for i, r in enumerate(rows):
                # 주기적으로 종료 상태 확인 (30행마다)
                if i % 30 == 0 and self.is_shutting_down:
                    print(f"[INFO] CompletedDealsTab: 종료 중이므로 {i}행까지만 처리하고 중단합니다.")
                    break
                
                # 0) 주소 + UserData
                addr_ = (r.get("dong", "") + " " + r.get("jibun", "")).strip()
                item = QtGui.QStandardItem(addr_)
                item.setData("계약완료", QtCore.Qt.UserRole + 2) # Source identifier
                item.setData(r.get("id", 0), QtCore.Qt.UserRole + 3) # Primary Key
                m.setItem(i, 0, item)

                # Populate other columns based on headers
                m.setItem(i, 1, QtGui.QStandardItem(r.get("ho", ""))) # 호
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
                m.setItem(i, 10, QtGui.QStandardItem(r.get("memo", ""))) # 메모
                m.setItem(i, 11, QtGui.QStandardItem(r.get("manager", ""))) # 담당자
                m.setItem(i, 12, QtGui.QStandardItem(str(r.get("parking", "")))) # 주차대수
                m.setItem(i, 13, QtGui.QStandardItem(r.get("building_usage", ""))) # 용도
                m.setItem(i, 14, QtGui.QStandardItem(str(r.get("approval_date", "")))) # 사용승인일
                ro_ = r.get("rooms", "")
                bt_ = r.get("baths", "")
                m.setItem(i, 15, QtGui.QStandardItem(f"{ro_}/{bt_}")) # 방/화장실
                m.setItem(i, 16, QtGui.QStandardItem(str(r.get("ad_end_date", "")))) # 광고종료일
                m.setItem(i, 17, QtGui.QStandardItem(r.get("photo_path", ""))) # 사진경로
                m.setItem(i, 18, QtGui.QStandardItem(r.get("owner_name", ""))) # 소유자명
                m.setItem(i, 19, QtGui.QStandardItem(r.get("owner_relation", ""))) # 관계
                m.setItem(i, 20, QtGui.QStandardItem(str(r.get("status_cd", "")))) # 상태코드
                
                # 주기적으로 이벤트 처리 - 더 자주 UI 업데이트와 이벤트 처리 (10행마다)
                if i % 10 == 0:
                    QtWidgets.QApplication.processEvents()
                    
                    # UI 처리 중 앱 종료 상태 확인
                    if self.is_shutting_down:
                        print(f"[INFO] CompletedDealsTab: 이벤트 처리 중 종료 상태 감지, {i}행까지만 처리하고 중단합니다.")
                        break
                        
        except RuntimeError as e:
            print(f"[INFO] CompletedDealsTab: 테이블 행 채우는 중 런타임 오류 (종료 중일 수 있음): {e}")
        except Exception as e:
            print(f"[ERROR] CompletedDealsTab: 테이블 행 채우는 중 예상치 못한 오류: {e}")
            import traceback
            print(traceback.format_exc())

    def filter_completed_deals_by_address(self, address_str: str):
        """ Filters the table to show only rows matching the address_str. """
        # 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] CompletedDealsTab: 종료 중이므로 주소별 필터링을 건너뜁니다.")
            return
            
        # 주소 확인
        if not address_str:
            if not self.is_shutting_down:
                self.populate_completed_deals_table([])
            return

        # 캐시에서 데이터 가져오기
        filtered = self.completed_deals_dict.get(address_str, [])
        
        # 종료 확인 후 테이블 채우기
        if not self.is_shutting_down:
            self.populate_completed_deals_table(filtered)

    def get_data_for_address(self, addr_str: str) -> list:
        """ Returns the list of completed deals for the given address from the local cache. """
        # 종료 상태 또는 주소가 없으면 빈 리스트 반환
        if self.is_shutting_down or not addr_str:
            return []
            
        # 딕셔너리가 없으면 빈 리스트 반환
        if not hasattr(self, 'completed_deals_dict') or not self.completed_deals_dict:
            return []
            
        return self.completed_deals_dict.get(addr_str, [])

    def _get_headers(self):
        """ Returns the list of headers for the completed deals tab. """
        return [
            "주소", "호", "층", "보증금/월세", "관리비",
            "권리금", "현업종", "평수", "연락처",
            "매물번호", "메모", "담당자",
            "주차대수", "용도", "사용승인일", "방/화장실",
            "광고종료일", "사진경로", "소유자명", "관계",
            "상태코드"
        ]

    def add_completed_deals(self, items_arr, manager):
        """Triggers the background task to add completed deals."""
        # 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] CompletedDealsTab: 종료 중이므로 계약완료 추가를 건너뜁니다.")
            return False
            
        # 앱이 종료 중인지 확인
        if not self.parent_app or (hasattr(self.parent_app, 'terminating') and self.parent_app.terminating):
            print("[INFO] CompletedDealsTab: 앱이 종료 중이므로 계약완료 추가를 건너뜁니다.")
            return False
            
        # 입력 데이터 확인
        if not items_arr:
            print("[WARN] CompletedDealsTab: No items provided to add_completed_deals.")
            return False
            
        # API 요청 데이터 구성
        payload = {
            "items": items_arr,
            "manager": manager
        }
        url = f"http://{self.server_host}:{self.server_port}/completed/add_completed_deals"
        
        # parent_app의 executor 상태 확인
        if not hasattr(self.parent_app, 'executor'):
            print("[ERR] CompletedDealsTab: Parent executor not found.")
            if not self.is_shutting_down:  # 종료 중이 아닌 경우에만 메시지 표시
                QMessageBox.critical(self.parent_app, "오류", "백그라운드 작업을 실행할 수 없습니다.")
            return False
            
        # executor가 종료 상태인지 확인
        if (hasattr(self.parent_app.executor, '_shutdown') and 
            self.parent_app.executor._shutdown):
            print("[WARN] CompletedDealsTab: Executor is already shut down, skipping add_completed_deals")
            return False
            
        # 백그라운드 작업 시작
        try:
            future = self.parent_app.executor.submit(self._bg_add_completed_deals, url, payload)
            future.add_done_callback(self._on_completed_deals_done)
            return True
        except RuntimeError as e:
            print(f"[WARN] CompletedDealsTab: RuntimeError during executor submit: {e}")
            return False
        except Exception as e:
            print(f"[ERR] CompletedDealsTab: Error during executor submit: {e}")
            if not self.is_shutting_down:  # 종료 중이 아닌 경우에만 메시지 표시
                QMessageBox.critical(self.parent_app, "오류", f"백그라운드 작업 시작 중 오류: {e}")
            return False

    def _bg_add_completed_deals(self, url, payload):
        """(Background Thread) Sends POST request to add completed deals."""
        # Logic from main_app_part2/_bg_add_completed_deals
        import requests
        try:
            resp = requests.post(url, json=payload, timeout=5)
            resp.raise_for_status()
            return resp.json()
        except Exception as ex:
            return {"status":"exception","message":str(ex)}

    def _on_completed_deals_done(self, future):
        """(Callback) Processes the result of adding completed deals."""
        # 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] CompletedDealsTab: 종료 중이므로 계약완료 결과 처리를 건너뜁니다.")
            return
            
        # 앱이 종료 중인지 확인
        if not self.parent_app or (hasattr(self.parent_app, 'terminating') and self.parent_app.terminating):
            print("[INFO] CompletedDealsTab: 앱이 종료 중이므로 계약완료 결과 처리를 건너뜁니다.")
            return
            
        try:
            result = future.result()
        except Exception as e:
            print(f"[ERROR] CompletedDealsTab: Error getting future result: {e}")
            result = {"status":"exception","message":str(e)}
            
        # 다시 한 번 종료 상태 확인
        if self.is_shutting_down:
            print("[INFO] CompletedDealsTab: 종료 중이므로 UI 업데이트를 건너뜁니다.")
            return
            
        # Use invokeMethod to safely update UI from the main thread
        try:
            QtCore.QMetaObject.invokeMethod(
                self, 
                "_process_completed_deals_result_slot", 
                QtCore.Qt.QueuedConnection, 
                QtCore.Q_ARG(dict, result)
            )
        except RuntimeError as e:
            print(f"[WARN] CompletedDealsTab: RuntimeError during invokeMethod: {e}")
        except Exception as e:
            print(f"[ERROR] CompletedDealsTab: Error invoking result slot: {e}")

    @QtCore.pyqtSlot(dict)
    def _process_completed_deals_result_slot(self, result: dict):
         """(Main Thread Slot) Updates UI based on the result."""
         # 종료 상태 확인
         if self.is_shutting_down:
             print("[INFO] CompletedDealsTab: 종료 중이므로 결과 처리를 건너뜁니다.")
             return
             
         # 앱이 종료 중인지 확인
         if not self.parent_app or (hasattr(self.parent_app, 'terminating') and self.parent_app.terminating):
             print("[INFO] CompletedDealsTab: 앱이 종료 중이므로 결과 처리를 건너뜁니다.")
             return
             
         # 상태 표시줄이 있는지 확인
         if not hasattr(self.parent_app, 'statusBar') or not callable(self.parent_app.statusBar):
             print("[WARN] CompletedDealsTab: Parent app's statusBar not available")
             return
             
         try:
             status_bar = self.parent_app.statusBar() # Get status bar from parent
             
             st = result.get("status")
             if st == "ok":
                 status_bar.showMessage("계약완료 처리 완료!", 3000)
                 # 종료 상태 재확인 후 데이터 다시 로드
                 if not self.is_shutting_down:
                     self.auto_reload_completed_deals_data()
             elif st == "exception":
                 err_ = result.get("message","")
                 status_bar.showMessage(f"[오류/예외] 계약완료 처리: {err_}", 5000)
             else:
                 msg_ = result.get("message","오류 발생")
                 status_bar.showMessage(f"계약완료 처리 실패: {msg_}", 5000)
         except Exception as e:
             print(f"[ERROR] CompletedDealsTab: 결과 처리 중 오류 발생: {e}")
             import traceback
             print(traceback.format_exc())

    def terminate(self):
        """프로그램 종료 시 호출하여 타이머, 시그널 등의 리소스 정리"""
        print("[INFO] CompletedDealsTab: Terminating...")
        self.is_shutting_down = True
        
        # 타이머 정지 강화된 예외 처리
        if hasattr(self, 'completed_deals_timer') and self.completed_deals_timer:
            try:
                if self.completed_deals_timer.isActive():
                    self.completed_deals_timer.stop()
                    print("[INFO] CompletedDealsTab: Timer stopped")
                    
                # 타이머 연결 해제
                try:
                    self.completed_deals_timer.timeout.disconnect()
                    print("[INFO] CompletedDealsTab: Timer signal disconnected")
                except (TypeError, RuntimeError):
                    # 이미 연결이 끊어졌거나 예외가 발생했을 경우 무시
                    pass
                    
                # 타이머 참조 제거
                self.completed_deals_timer = None
                print("[INFO] CompletedDealsTab: Timer reference removed")
            except Exception as e:
                print(f"[WARN] CompletedDealsTab: Error handling timer: {e}")
        
        # 시그널 연결 해제
        try:
            # 모든 시그널 연결 해제 시도
            if hasattr(self, 'data_loaded_for_address'):
                try:
                    self.data_loaded_for_address.disconnect()
                    print("[INFO] CompletedDealsTab: 모든 시그널 연결 해제 완료")
                except (TypeError, RuntimeError):
                    # 연결된 슬롯이 없거나 이미 연결 해제된 경우 조용히 무시
                    pass
        except Exception as e:
            print(f"[WARN] CompletedDealsTab: 시그널 연결 해제 중 오류: {e}")
        
        # 메모리 정리
        if hasattr(self, 'completed_deals_dict'):
            self.completed_deals_dict.clear()
            
        # 모델과 뷰 참조 제거
        self.completed_deals_model = None
        self.completed_deals_view = None
        
        print("[INFO] CompletedDealsTab: Termination complete")
        
    # 이전 cleanup 메서드를 유지하고 terminate 메서드 호출로 변경
    def cleanup(self):
        """이전 버전과의 호환성을 위해 남겨둔 메서드"""
        print("[INFO] CompletedDealsTab: cleanup() called, forwarding to terminate()")
        self.terminate() 