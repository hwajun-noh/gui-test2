# mylist_completed_logic.py
import os
import sys
import requests
from datetime import datetime
import json
import logging # 로깅 모듈 추가
import threading # threading 모듈 임포트 추가

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QModelIndex, QTimer, pyqtSignal, QObject, pyqtSlot # pyqtSignal, QObject, pyqtSlot 추가
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QColor
from PyQt5.QtWidgets import (
    QTableView, QWidget, QVBoxLayout, QHeaderView, QMessageBox
)

from ui_utils import restore_qtableview_column_widths, save_qtableview_column_widths

class MyListCompletedLogic(QObject): # QObject 상속 추가
    dataFetched = pyqtSignal(dict) # 데이터를 전달할 사용자 정의 시그널

    def __init__(self, parent_app, container):
        super().__init__() # QObject 초기화 호출 추가
        self.parent_app = parent_app
        self.container = container
        self.server_host = parent_app.server_host
        self.server_port = parent_app.server_port
        self.logger = logging.getLogger(__name__) # 로거 인스턴스 가져오기

        # UI Elements
        self.mylist_completed_view = None
        self.mylist_completed_model = None

        # Data Cache (Potentially move to container if shared access needed)
        self.mylist_completed_dict = {} # Cache: address -> [row_dict, ...]

        # Timer
        self.mylist_completed_timer = None

        # Tab Widget container
        self.tab_widget = None

        # Define column mapping (Display Name -> DB Field Name)
        # Keep this consistent if possible, or map during population
        self.COLUMN_MAP_MYLIST_COMPLETED_DISPLAY_TO_DB = {
             "주소":None, "호":"ho", "층":None, "보증금/월세":None, "관리비":"manage_fee",
             "권리금":"premium", "현업종":"current_use", "평수":"area", "연락처":"owner_phone",
             "매물번호":None, "메모":"memo", "담당자":"manager", "주차대수":"parking",
             "용도":"building_usage", "사용승인일":"approval_date", "방/화장실":None,
             "광고종료일":"ad_end_date", "사진경로":"photo_path", "소유자명":"owner_name",
             "관계":"owner_relation", "상태코드":"status_cd"
         }

        # --- Connect Signal ---
        self.dataFetched.connect(self._process_fetched_data_slot) # 시그널-슬롯 연결

    def init_ui(self):
        """Creates the widget for the '계약완료' tab."""
        container_completed = QWidget()
        vlay_completed = QVBoxLayout(container_completed)

        # Model
        self.mylist_completed_model = QStandardItemModel()
        headers_completed = [
            "주소","호","층","보증금/월세","관리비","권리금","현업종","평수","연락처",
            "매물번호", "메모","담당자", "주차대수","용도","사용승인일","방/화장실",
            "광고종료일","사진경로","소유자명","관계","상태코드"
        ]
        self.mylist_completed_model.setColumnCount(len(headers_completed))
        self.mylist_completed_model.setHorizontalHeaderLabels(headers_completed)

        # View
        self.mylist_completed_view = QTableView()
        self.mylist_completed_view.setModel(self.mylist_completed_model)
        self.mylist_completed_view.setSortingEnabled(True)
        self.mylist_completed_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive) # Allow manual resize
        # self.mylist_completed_view.horizontalHeader().setStretchLastSection(True) # Removed to allow resize

        # Restore/Save column widths
        restore_qtableview_column_widths(
            self.parent_app.settings_manager, self.mylist_completed_view, "MyListCompletedTable"
        )
        self.mylist_completed_view.horizontalHeader().sectionResized.connect(
            lambda: save_qtableview_column_widths(
                self.parent_app.settings_manager, self.mylist_completed_view, "MyListCompletedTable"
            )
        )

        # Add context menu if needed
        # self.mylist_completed_view.setContextMenuPolicy(Qt.CustomContextMenu)
        # self.mylist_completed_view.customContextMenuRequested.connect(self._completed_context_menu)

        vlay_completed.addWidget(self.mylist_completed_view)
        container_completed.setLayout(vlay_completed)

        self.tab_widget = container_completed
        return self.tab_widget

    def start_timer(self):
        """Starts the auto-reload timer."""
        # 메인 스레드에서만 실행되도록 보장
        if QtCore.QThread.currentThread() != QtCore.QCoreApplication.instance().thread():
            self.logger.warning("Timer start attempted from non-main thread. Scheduling for main thread.")
            # 메인 스레드에서 실행되도록 스케줄링
            QtCore.QMetaObject.invokeMethod(self, "start_timer", QtCore.Qt.QueuedConnection)
            return
            
        if not self.mylist_completed_timer:
            self.mylist_completed_timer = QTimer(self.parent_app) # Parent timer to main app
            self.mylist_completed_timer.setInterval(30_000) # 30 seconds
            self.mylist_completed_timer.timeout.connect(self._auto_reload_mylist_completed_deals_data)
            self.logger.debug("Timer created with 30s interval.")
            
        if not self.mylist_completed_timer.isActive():
             self.mylist_completed_timer.start()
             self.logger.debug("Timer started successfully.")
             # Initial load on start
             self._auto_reload_mylist_completed_deals_data()

    def load_data(self):
        """데이터 로딩 메서드 - base_container와의 호환성을 위해 추가"""
        self.logger.info("load_data: 계약완료 데이터 로딩 시작")
        self._auto_reload_mylist_completed_deals_data()

    def stop_timer(self):
         """Stops the auto-reload timer."""
         # 메인 스레드에서만 실행되도록 보장
         if QtCore.QThread.currentThread() != QtCore.QCoreApplication.instance().thread():
             self.logger.warning("Timer stop attempted from non-main thread. Ignoring.")
             return
             
         if self.mylist_completed_timer and self.mylist_completed_timer.isActive():
              self.mylist_completed_timer.stop()
              self.logger.debug("Timer stopped successfully.")

    # --- Data Loading and Processing ---

    def _auto_reload_mylist_completed_deals_data(self):
        """Initiates background loading of completed deals."""
        # 메인 스레드에서만 실행되도록 보장
        if QtCore.QThread.currentThread() != QtCore.QCoreApplication.instance().thread():
            self.logger.warning("Auto-reload attempted from non-main thread. Scheduling for main thread.")
            # 메인 스레드에서 실행되도록 스케줄링
            QtCore.QMetaObject.invokeMethod(self, "_auto_reload_mylist_completed_deals_data", 
                                           QtCore.Qt.QueuedConnection)
            return
            
        self.logger.info("Entering _auto_reload_mylist_completed_deals_data: Submitting background task.")
        
        # ThreadPoolExecutor 상태 확인 및 안전한 작업 예약
        try:
            # 부모 앱이 존재하는지 확인
            if not hasattr(self, 'parent_app') or self.parent_app is None:
                self.logger.error("parent_app이 존재하지 않아 백그라운드 작업을 예약할 수 없습니다.")
                return
                
            # 부모 앱이 종료 중인지 확인
            if hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
                self.logger.warning("애플리케이션이 종료 중이므로 백그라운드 작업을 예약하지 않습니다.")
                return
                
            # executor가 존재하는지 확인
            if not hasattr(self.parent_app, 'executor') or self.parent_app.executor is None:
                self.logger.error("parent_app.executor가 존재하지 않아 백그라운드 작업을 예약할 수 없습니다.")
                return
                
            # executor가 이미 종료되었는지 확인
            if hasattr(self.parent_app.executor, '_shutdown') and self.parent_app.executor._shutdown:
                self.logger.warning("ThreadPoolExecutor가 이미 종료되어 백그라운드 작업을 예약할 수 없습니다.")
                return
                
            # 안전하게 작업 예약
            try:
                future = self.parent_app.executor.submit(self._bg_load_all_mylist_completed_deals_data)
                future.add_done_callback(self._on_mylist_completed_deals_data_fetched)
                self.logger.info("Background task submitted successfully (using parent_app.executor).")
            except RuntimeError as rt_err:
                # 'cannot schedule new futures after shutdown' 오류는 무시하고 로그만 남김
                if "cannot schedule new futures after shutdown" in str(rt_err):
                    self.logger.warning(f"Executor가 shutdown 상태여서 새로운 작업을 예약할 수 없습니다: {rt_err}")
                else:
                    # 다른 RuntimeError는 기록
                    self.logger.error(f"RuntimeError: 백그라운드 작업 예약 중 오류: {rt_err}")
            except Exception as e:
                self.logger.error(f"Error submitting background task for completed deals: {e}", exc_info=True)
        except Exception as outer_err:
            self.logger.error(f"백그라운드 작업 예약 준비 과정에서 예상치 못한 오류 발생: {outer_err}", exc_info=True)

    def _bg_load_all_mylist_completed_deals_data(self):
        """(Background Thread) Fetches all completed deals."""
        self.logger.info("Entering _bg_load_all_mylist_completed_deals_data (Background Thread).")
        url = f"http://{self.server_host}:{self.server_port}/completed/get_completed_deals"
        self.logger.debug(f"Requesting completed deals from URL: {url}")
        try:
            resp = requests.get(url, timeout=10) # Increased timeout
            resp.raise_for_status()
            j = resp.json()
            self.logger.debug(f"Received response: status={j.get('status')}, data_length={len(j.get('data', [])) if j.get('data') is not None else 'None'}")
            if j.get("status") == "ok":
                self.logger.info("Successfully fetched completed deals data.")
                return {"status": "ok", "data": j.get("data", [])}
            else:
                 self.logger.error(f"Server returned non-ok status: Status={j.get('status')}, Msg={j.get('message')}")
                 return {"status": "error", "data": [], "message": j.get("message")}
        except requests.Timeout:
             self.logger.error("Request timed out while fetching completed deals.")
             return {"status": "exception", "message": "Request timed out", "data": []}
        except requests.RequestException as ex:
             self.logger.error(f"RequestException fetching completed deals: {ex}", exc_info=True)
             return {"status": "exception", "message": str(ex), "data": []}
        except Exception as ex_other:
            self.logger.error(f"Unexpected error fetching completed deals: {ex_other}", exc_info=True)
            return {"status": "exception", "message": f"Unexpected error: {ex_other}", "data": []}
        finally:
            self.logger.info("Exiting _bg_load_all_mylist_completed_deals_data (Background Thread).")

    def _on_mylist_completed_deals_data_fetched(self, future):
        """
        (Callback, potentially background thread) Emits signal with fetched data.
        """
        current_thread = threading.current_thread()
        self.logger.warning(f"Entering _on_mylist_completed_deals_data_fetched. Current Thread: {current_thread.name} (ID: {current_thread.ident})")
        try:
            result = future.result()
            # --- 시그널 발생 ---
            self.dataFetched.emit(result if result else {}) # 결과 또는 빈 딕셔너리 전달
            self.logger.info(f"Emitted dataFetched signal with result status: {result.get('status') if result else 'None'}")
            # -----------------
        except Exception as e:
            self.logger.error(f"Failed to get future result or emit signal: {e}", exc_info=True)
            self.dataFetched.emit({"status": "exception", "message": "콜백 처리 오류"}) # 오류 시에도 시그널 발생
        finally:
             self.logger.warning(f"Exiting _on_mylist_completed_deals_data_fetched. Current Thread: {current_thread.name} (ID: {current_thread.ident})")

    # 슬롯 함수: 메인 스레드에서 실행되어 UI 업데이트 담당
    @pyqtSlot(dict)
    def _process_fetched_data_slot(self, result):
        """
        (Main Thread Slot) Processes fetched data and updates UI elements.
        """
        current_thread = threading.current_thread()
        self.logger.warning(f"Entering _process_fetched_data_slot. Current Thread: {current_thread.name} (ID: {current_thread.ident})")

        model = self.mylist_completed_model
        if not model:
            self.logger.error("Model not initialized in _process_fetched_data_slot!")
            return

        status_msg_prefix = "계약완료 목록: "
        final_status_msg = ""

        if result and result.get("status") == "ok":
            rows = result.get("data", [])
            self.logger.info(f"[_process_fetched_data_slot] Successfully received {len(rows)} completed deals rows via signal.")

            # --- Update Cache ---
            self.logger.debug("[_process_fetched_data_slot] Updating internal cache (mylist_completed_dict).")
            self.mylist_completed_dict = {} # Reset cache
            for r in rows:
                addr = f"{r.get('dong','')} {r.get('jibun','')}".strip()
                self.mylist_completed_dict.setdefault(addr, []).append(r)
            self.logger.debug(f"[_process_fetched_data_slot] Cache updated with {len(self.mylist_completed_dict)} addresses.")

            # --- Update Table Model ---
            self.logger.debug("[_process_fetched_data_slot] Checking for new rows to add to the table model.")
            current_known_ids = self._get_mylist_completed_known_ids()
            self.logger.debug(f"[_process_fetched_data_slot] Current known IDs in model: {current_known_ids}")
            rows_to_add = [r for r in rows if r.get("id") is not None and r.get("id") not in current_known_ids]
            self.logger.info(f"[_process_fetched_data_slot] Found {len(rows_to_add)} new rows to append to the model.")

            if rows_to_add:
                # UI 업데이트는 이 슬롯(메인 스레드)에서 안전하게 수행
                self.append_mylist_completed_rows(rows_to_add, model=model)
            else:
                self.logger.info("[_process_fetched_data_slot] No new rows to add to the model.")

            final_status_msg = f"{status_msg_prefix} 로딩 완료 ({len(rows)}건)."

        else:
            # Handle error
            error_message = "알 수 없는 상태"
            if result and result.get("status") != "ok": error_message = result.get("message", "서버 오류")
            elif not result: error_message = "서버 응답 없음 또는 콜백 오류"
            self.logger.error(f"[_process_fetched_data_slot] Failed to load completed deals: {error_message}")
            final_status_msg = f"{status_msg_prefix} 로딩 실패: {error_message}"

        self.logger.debug(f"[_process_fetched_data_slot] Setting status bar message: '{final_status_msg}'")
        try:
            # 상태 표시줄 업데이트도 메인 스레드에서 안전하게 수행
            self.parent_app.statusBar().showMessage(final_status_msg, 3000)
        except Exception as e:
            self.logger.error(f"[_process_fetched_data_slot] Failed to set status bar message: {e}", exc_info=True)

        self.logger.warning(f"Exiting _process_fetched_data_slot. Current Thread: {current_thread.name} (ID: {current_thread.ident})")

    def _get_mylist_completed_known_ids(self) -> set:
        """Returns a set of real DB IDs currently in the completed deals model."""
        self.logger.debug("Entering _get_mylist_completed_known_ids.")
        s = set()
        m = self.mylist_completed_model
        if not m:
             self.logger.warning("Model is None in _get_mylist_completed_known_ids.")
             return s
        try:
            for r in range(m.rowCount()):
                item0 = m.item(r, 0)
                if not item0: continue
                rid = item0.data(QtCore.Qt.UserRole + 3)
                if isinstance(rid, int) and rid > 0:
                    s.add(rid)
            self.logger.debug(f"Found {len(s)} known IDs.")
        except Exception as e:
            self.logger.error(f"Error getting known IDs: {e}", exc_info=True)
        return s

    def append_mylist_completed_rows(self, row_list, model=None):
        """Appends rows to the completed deals table model."""
        self.logger.info(f"Entering append_mylist_completed_rows to add {len(row_list)} rows.")
        if not row_list: return

        m = model if model else self.mylist_completed_model
        if not m:
             self.logger.error("Cannot append rows, model is None.")
             return

        start_row = m.rowCount()
        rows_to_add_count = len(row_list)
        self.logger.debug(f"Model current rowCount: {start_row}. Attempting to insert {rows_to_add_count} rows.")

        try:
            # --- Begin/End Model Reset for Performance ---
            # Consider using beginInsertRows/endInsertRows for large additions
            # model.beginInsertRows(QModelIndex(), start_row, start_row + rows_to_add_count - 1)
            # ---------------------------------------------

            m.insertRows(start_row, rows_to_add_count)
            headers = [m.horizontalHeaderItem(j).text() for j in range(m.columnCount())] if m.columnCount() > 0 else []
            if not headers:
                 self.logger.error("Cannot append, model headers missing.")
                 # model.endInsertRows() # Make sure to call endInsertRows if begin was called
                 return

            self.logger.debug(f"Model headers obtained: {headers}")

            for i, db_row_data in enumerate(row_list):
                 row_idx = start_row + i
                 self.logger.debug(f"Updating model row at index {row_idx} with data ID: {db_row_data.get('id')}")
                 self._update_completed_model_row(m, row_idx, headers, db_row_data) # Use helper

            # --- End Model Reset ---
            # model.endInsertRows()
            # ---------------------
            self.logger.info(f"Successfully appended {rows_to_add_count} rows.")

        except Exception as e:
             self.logger.error(f"Error during append_mylist_completed_rows: {e}", exc_info=True)
             # if model.isSignalConnected(...): # Check if reset was started
             #    model.endInsertRows() # Attempt to end reset on error

    def _update_completed_model_row(self, model, row_idx, headers, db_row_data):
         """ Helper function to set items for a single row in the completed model. """
         # self.logger.debug(f"Entering _update_completed_model_row for row {row_idx}.") # Can be too verbose
         item0 = None
         try:
            for col_idx, header_name in enumerate(headers):
                db_key = self.COLUMN_MAP_MYLIST_COMPLETED_DISPLAY_TO_DB.get(header_name)
                raw_value = db_row_data.get(db_key) if db_key else None

                # Format cell value
                if header_name == "주소": cell_val = f"{db_row_data.get('dong', '')} {db_row_data.get('jibun', '')}".strip()
                elif header_name == "층": cell_val = f"{db_row_data.get('curr_floor', 0)}/{db_row_data.get('total_floor', 0)}"
                elif header_name == "보증금/월세": cell_val = f"{db_row_data.get('deposit', 0)}/{db_row_data.get('monthly', 0)}"
                elif header_name == "매물번호": cell_val = f"{db_row_data.get('naver_property_no', '')}/{db_row_data.get('serve_property_no', '')}"
                elif header_name == "방/화장실": cell_val = f"{db_row_data.get('rooms', '')}/{db_row_data.get('baths', '')}"
                elif header_name == "관리비": cell_val = str(raw_value) if raw_value is not None else ""
                elif header_name == "평수": cell_val = str(raw_value) if raw_value is not None else ""
                elif header_name == "주차대수": cell_val = str(raw_value) if raw_value is not None else ""
                elif header_name == "사용승인일": cell_val = str(raw_value) if raw_value is not None else ""
                elif header_name == "광고종료일": cell_val = str(raw_value) if raw_value is not None else ""
                else: cell_val = str(raw_value) if raw_value is not None else ""

                item = QStandardItem(cell_val)

                if col_idx == 0:
                    item0 = item
                    db_id = db_row_data.get("id")
                    item0.setData(db_id, Qt.UserRole + 3) # Store DB ID
                    # self.logger.debug(f"  Set UserRole+3 (DB ID) = {db_id} for item in row {row_idx}, col 0")

                model.setItem(row_idx, col_idx, item)
         except Exception as e:
            self.logger.error(f"Error updating cell in row {row_idx}, col {col_idx} (Header: {header_name}): {e}", exc_info=True)

         # Set background color for completed rows (e.g., gray)
         row_bg = QColor("#DDDDDD")
         for c in range(model.columnCount()):
             cell = model.item(row_idx, c)
             if cell: cell.setBackground(row_bg)

    def get_data_for_address(self, address_str: str) -> list:
         """Returns cached completed deal data for a specific address."""
         # Ensure cache is populated if needed, or rely on timer
         return self.mylist_completed_dict.get(address_str, [])

    # --- Filtering (if needed for this tab) ---
    def filter_table_by_address(self, address_str: str):
        """Hides or shows rows based on the address string."""
        view = self.mylist_completed_view
        model = self.mylist_completed_model
        if not view or not model: return

        try:
            model.setSortingEnabled(False)
            for row in range(model.rowCount()):
                item = model.item(row, 0) # Address column
                if item:
                    row_addr = item.text().strip()
                    should_hide = bool(address_str) and (row_addr != address_str)
                    view.setRowHidden(row, should_hide)
                else:
                    view.setRowHidden(row, bool(address_str))
        except Exception as e:
             print(f"[ERROR] MyListCompletedLogic: Error during filtering: {e}")
        finally:
             if model: model.setSortingEnabled(True)

    # --- Context Menu (Placeholder) ---
    # def _completed_context_menu(self, pos):
    #     index = self.mylist_completed_view.indexAt(pos)
    #     if not index.isValid(): return
    #     menu = QMenu(self.mylist_completed_view)
    #     # Add actions specific to completed deals if any
    #     # e.g., act_view_details = menu.addAction("상세 정보 보기")
    #     action = menu.exec_(self.mylist_completed_view.mapToGlobal(pos))
    #     # Handle actions... 