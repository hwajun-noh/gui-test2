# mylist_sanga_logic.py
import os
import glob
import requests
import time
from datetime import datetime
import logging # 로깅 임포트

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QModelIndex, QUrl, Q_ARG, pyqtSignal, pyqtSlot # <<< pyqtSignal 추가
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QColor # QColor 임포트 추가
from PyQt5.QtWidgets import (
    QTableView, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, 
    QMessageBox, QAbstractItemView, QHeaderView, QShortcut, QLabel
)

# UI 관련 임포트
from mylist_sanga_ui import init_sanga_ui

# 데이터 관련 임포트
from mylist_sanga_data import (
    bg_load_mylist_shop_data, get_mylist_shop_known_ids, 
    populate_mylist_shop_table, append_mylist_shop_rows,
    update_model_row, parse_mylist_shop_row, build_mylist_shop_rows_for_changes,
    update_mylist_shop_row_id, find_mylist_shop_row_by_id, 
    get_summary_by_manager
)

# 이벤트 처리 관련 임포트
from mylist_sanga_events import (
    on_mylist_shop_item_changed,
    on_mylist_shop_view_double_clicked,
    on_mylist_shop_current_changed, on_shop_header_section_clicked,
    clear_selected_cells, show_search_dialog_for_shop,
    _mylist_shop_context_menu, on_mylist_shop_change_status,
    _bulk_change_manager_mylist_shop, _bulk_change_re_ad_mylist_shop,
    delete_selected_mylist_shop_rows, select_entire_column
)

# 액션 관련 임포트
from mylist_sanga_actions import (
    on_save_mylist_shop_changes, on_naver_search_clicked,
    add_shop_row_with_data, filter_table_by_address,
    copy_mylist_shop_row, export_selected_shop_to_excel,
    on_open_sanga_tk_for_mylist_shop, highlight_mylist_shop_row_by_id
)

from mylist_constants import PENDING_COLOR, RE_AD_BG_COLOR, NEW_AD_BG_COLOR

class MyListSangaLogic(QtCore.QObject): # <<< QObject 상속 추가 (시그널 사용 위해)
    model_populated = pyqtSignal() # <<< 모델 업데이트 완료 시그널 추가

    def __init__(self, parent_app, container):
        super().__init__() # <<< QObject 초기화 추가
        self.parent_app = parent_app
        self.container = container  # Reference to the MyListContainer instance
        self.server_host = parent_app.server_host
        self.server_port = parent_app.server_port
        self.current_manager = parent_app.current_manager
        self.current_role = parent_app.current_role
        self.logger = logging.getLogger(__name__) # 로거 인스턴스 생성
        self.logger.setLevel(logging.DEBUG) # <<< 명시적으로 DEBUG 레벨 설정

        # UI Elements
        self.mylist_shop_view = None
        self.mylist_shop_model = None
        self.manager_summary_label = None
        self.autosave_status_label = None
        self.btn_naver_search = None

        # State / Data (Managed by container)
        # self.mylist_shop_pending = container.mylist_shop_pending
        self.mylist_shop_loading = False  # Local loading flag for this tab

        # Keep track of the container widget created by this logic class
        self.tab_widget = None

        # Define column mapping (Display Name -> DB Field Name)
        # Move this to parent_app or a shared config if used elsewhere
        self.parent_app.COLUMN_MAP_MYLIST_SHOP_DISPLAY_TO_DB = {
            "주소": None,  # Handled separately
            "호": "ho",
            "층": None,  # Combined field
            "보증금/월세": None,  # Combined field
            "관리비": "manage_fee",
            "권리금": "premium",
            "현업종": "current_use",
            "평수": "area",
            "연락처": "owner_phone",
            "매물번호": None,  # Combined field
            "담당자": "manager",
            "메모": "memo",
            "주차대수": "parking",
            "용도": "building_usage",
            "사용승인일": "approval_date",
            "방/화장실": None,  # Combined field
            "광고종료일": "ad_end_date",
            "사진경로": "photo_path",
            "소유자명": "owner_name",
            "관계": "owner_relation",
            "재광고": "re_ad_yn"  # Mapped to DB field
        }

        # <<< 시그널 연결 제거 (중복 방지) >>>
        # self.model_populated.connect(self._reconnect_view_signals)
        # 중복 연결 방지: mylist_shop_tab.py에서 currentChanged 시그널 처리

    def init_ui(self):
        """Creates the widget for the '상가(새광고)' tab using the UI module."""
        return init_sanga_ui(self)

    def _get_horizontal_headers(self):
        """Returns the list of column headers for the shop table."""
        return [
            "주소", "호", "층", "보증금/월세", "관리비", "권리금", "현업종", "평수", "연락처",
            "매물번호", "담당자", "메모", "주차대수", "용도", "사용승인일", "방/화장실",
            "광고종료일", "사진경로", "소유자명", "관계", "재광고"
        ]

    # --- Data Loading and Population ---

    def load_data(self):
        """Initiates the background data loading process."""
        self.logger.info("load_data: Initiating background data load process.") # 로그 추가
        self.mylist_shop_loading = True  # Set loading flag
        # print("[DEBUG] MyListSangaLogic: Initiating data load.") # 기존 print 로그 제거 또는 주석 처리
        try: # 예외 처리 추가
            future = self.parent_app.executor.submit(
                self._bg_load_mylist_shop_data,
                self.current_manager,
                self.current_role
            )

            # 결과를 GUI 스레드에서 처리하도록 래핑
            def _handle_future_done(fut):
                try:
                    result_data = fut.result()
                except Exception as exc:
                    # 예외도 GUI 스레드에서 처리
                    result_data = {"status": "exception", "message": str(exc), "data": []}

                # GUI 스레드로 전달
                QtCore.QMetaObject.invokeMethod(
                    self,
                    "_process_fetched_data_slot",
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(object, result_data)
                )

            future.add_done_callback(_handle_future_done)
            self.logger.info("load_data: Background task submitted successfully.") # 로그 추가
        except Exception as e:
            self.logger.error(f"load_data: Failed to submit background task: {e}", exc_info=True)
            self.mylist_shop_loading = False # 에러 발생 시 로딩 플래그 해제
            QMessageBox.warning(self.parent_app, "오류", f"데이터 로딩 작업 시작 중 오류 발생:\n{e}")

    def _bg_load_mylist_shop_data(self, manager, role):
        """(Background Thread) Fetches mylist_shop data via GET request."""
        return bg_load_mylist_shop_data(self.server_host, self.server_port, manager, role)

    def _get_mylist_shop_known_ids(self):
        """Returns a set of all real database IDs currently in the shop model."""
        return get_mylist_shop_known_ids(self.mylist_shop_model)

    @pyqtSlot(object)
    def _process_fetched_data_slot(self, result):
        """
        (Main GUI Thread) Processes fetched data and updates UI.
        """
        self.logger.info("_process_fetched_data_slot: Slot entered.")

        model = self.mylist_shop_model
        if not model:
            self.logger.error("_process_fetched_data_slot: Model not initialized!")
            self.mylist_shop_loading = False
            return

        try:
            if result and result.get("status") == "ok":
                fetched_rows = result.get("data", [])
                self.logger.info(f"_process_fetched_data_slot: Received {len(fetched_rows)} rows. Populating table.")
                
                # 큰 데이터셋의 경우 진행상황 표시
                if len(fetched_rows) > 500:
                    self.parent_app.statusBar().showMessage(f"MyList 데이터 처리 중... ({len(fetched_rows)}개 행)", 0)
                
                try:
                    populate_mylist_shop_table(self, fetched_rows)
                    self.logger.info("_process_fetched_data_slot: Table populated.")
                    
                    # 최종 모델 행 수 확인 (populate 후)
                    final_row_count = self.mylist_shop_model.rowCount() if self.mylist_shop_model else 0
                    status_msg = f"마이리스트(상가) 로딩 완료: {final_row_count}개 행 표시됨."
                    self.parent_app.statusBar().showMessage(status_msg, 5000)
                    
                except Exception as pop_e:
                    self.logger.error(f"_process_fetched_data_slot: populate_mylist_shop_table error: {pop_e}", exc_info=True)
                    QMessageBox.critical(self.parent_app, "테이블 업데이트 오류", f"데이터로 테이블을 채우는 중 오류 발생:\n{pop_e}")
                    self.mylist_shop_loading = False  # 에러 발생 시 즉시 해제
                    return
            else:
                error_msg = result.get("message", "서버 오류") if result else "데이터를 가져오지 못했습니다."
                self.logger.error(f"_process_fetched_data_slot: Data fetch failed - {error_msg}")
                self.parent_app.statusBar().showMessage(f"마이리스트(상가) 로딩 실패: {error_msg}", 5000)
                QMessageBox.warning(self.parent_app, "데이터 로딩 실패", f"마이리스트(상가) 데이터를 가져오는 중 오류 발생:\n{error_msg}")
                self.mylist_shop_loading = False  # 에러 발생 시 즉시 해제
                return
                
        except Exception as e:
            self.logger.error(f"_process_fetched_data_slot: Unexpected error: {e}", exc_info=True)
            self.mylist_shop_loading = False
            return
        
        # 성공적으로 완료된 경우에만 시그널 발생
        # 로딩 플래그는 populate_mylist_shop_table 내부에서 처리됨
        self.logger.info("_process_fetched_data_slot: Emitting model_populated signal.")
        self.model_populated.emit()

    # --- Update Model Methods ---

    def _update_model_row(self, model, row_idx, headers, db_row_data):
        """Updates a single row in the model with data from the DB."""
        update_model_row(model, row_idx, headers, db_row_data, self.parent_app.COLUMN_MAP_MYLIST_SHOP_DISPLAY_TO_DB)

    def _parse_mylist_shop_row(self, row_idx):
        """Parses a row from the model into a DB-ready dictionary."""
        return parse_mylist_shop_row(self, row_idx)

    def _build_mylist_shop_rows_for_changes(self, added_list, updated_list):
        """Builds dictionaries of added and updated rows for saving to the DB."""
        return build_mylist_shop_rows_for_changes(self, added_list, updated_list)

    def _update_mylist_shop_row_id(self, old_tid, new_id):
        """Updates a temporary ID to a real ID after saving to the DB."""
        update_mylist_shop_row_id(self, old_tid, new_id)

    # --- Event Handlers ---

    def on_mylist_shop_item_changed(self, item):
        """Handles changes to items in the shop model."""
        on_mylist_shop_item_changed(self, item)

    def on_mylist_shop_view_double_clicked(self, index):
        """Handles double-clicks on the shop view."""
        on_mylist_shop_view_double_clicked(self, index)

    def on_mylist_shop_current_changed(self, current, previous):
        """Handles changes to the current cell in the shop view."""
        on_mylist_shop_current_changed(self, current, previous)

    def on_shop_header_section_clicked(self, logical_index):
        """Handles clicks on the table header."""
        on_shop_header_section_clicked(self, logical_index)

    def select_entire_column(self, table_view, col_index):
        """Selects an entire column when requested."""
        select_entire_column(self, table_view, col_index)

    def clear_selected_cells(self, table_view):
        """Clears the contents of selected cells."""
        clear_selected_cells(self, table_view)

    def show_search_dialog_for_shop(self):
        """Shows the search dialog for the shop table."""
        show_search_dialog_for_shop(self)

    def _mylist_shop_context_menu(self, pos):
        """Shows the context menu for the shop table."""
        _mylist_shop_context_menu(self, pos)

    def on_mylist_shop_change_status(self, pos):
        """Opens the status change dialog for selected rows."""
        on_mylist_shop_change_status(self, pos)

    def _bulk_change_manager_mylist_shop(self):
        """Opens a dialog to change the manager for multiple rows."""
        _bulk_change_manager_mylist_shop(self)

    def _bulk_change_re_ad_mylist_shop(self):
        """Opens a dialog to change the "재광고" status for multiple rows."""
        _bulk_change_re_ad_mylist_shop(self)

    def delete_selected_mylist_shop_rows(self):
        """Deletes selected rows from the model."""
        delete_selected_mylist_shop_rows(self)

    # --- Action Methods ---

    def on_save_mylist_shop_changes(self):
        """Saves pending changes to the server."""
        on_save_mylist_shop_changes(self)

    def on_naver_search_clicked(self):
        """Opens the Naver property search dialog."""
        on_naver_search_clicked(self)

    def add_shop_row_with_data(self, row_dict_from_naver):
        """Adds a new row with data from Naver search."""
        add_shop_row_with_data(self, row_dict_from_naver)

    def filter_table_by_address(self, address_str):
        """Filters the table to show only rows with matching addresses."""
        filter_table_by_address(self, address_str)
        self._reconnect_view_signals() # <<< 필터링 후 시그널 재연결

    def copy_mylist_shop_row(self, source_row_idx):
        """Copies a row and adds it as a new row."""
        copy_mylist_shop_row(self, source_row_idx)

    def export_selected_shop_to_excel(self):
        """Exports selected rows to an Excel file."""
        export_selected_shop_to_excel(self)

    def on_open_sanga_tk_for_mylist_shop(self):
        """Opens the TKinter window for Naver property inspection."""
        on_open_sanga_tk_for_mylist_shop(self)

    # This must be marked as a slot to be called from another thread
    @pyqtSlot(int)
    def highlight_mylist_shop_row_by_id(self, pk_id):
        """Highlights a row identified by its primary key."""
        self.logger.info(f"highlight_mylist_shop_row_by_id: Called with pk_id={pk_id}")
        row_index = self.find_mylist_shop_row_by_id(pk_id)
        view = self.mylist_shop_view
        
        if row_index is not None and view:
            view.selectRow(row_index)
            view.scrollTo(view.model().index(row_index, 0))
            self.logger.info(f"highlight_mylist_shop_row_by_id: Highlighted row {row_index} with ID {pk_id}")
        else:
            self.logger.warning(f"highlight_mylist_shop_row_by_id: Could not find row with ID {pk_id} to highlight")

    def find_mylist_shop_row_by_id(self, pk_id):
        """Finds a row's index by its primary key."""
        return find_mylist_shop_row_by_id(self, pk_id)

    def get_summary_by_manager(self, manager_name):
        """Gets a summary of properties assigned to a manager."""
        return get_summary_by_manager(self, manager_name)

    # <<< 새 슬롯 메서드 추가 >>>
    @pyqtSlot()
    def _reconnect_view_signals(self):
        """Reconnects signals after the model has been potentially replaced or populated.""" # Docstring 수정
        self.logger.info("_reconnect_view_signals slot called.")
        if not self.mylist_shop_view or not self.mylist_shop_model:
            self.logger.error("_reconnect_view_signals: View or Model is None, cannot reconnect.")
            return
            
        view = self.mylist_shop_view 
        model = self.mylist_shop_model
            
        selection_model = view.selectionModel()
        if selection_model:
            # --- currentChanged 연결 제거 (중복 방지) ---
            # 중복 연결 방지: mylist_shop_tab.py에서 이미 처리되므로 여기서는 연결하지 않음
            self.logger.info("_reconnect_view_signals: currentChanged 시그널 연결을 mylist_shop_tab.py로 위임")
            # --- currentChanged 연결 끝 ---

            # --- itemChanged 연결 (여기서 수행) --- 
            try:
                # 기존 itemChanged 연결 시도 (disconnect 포함)
                try:
                    model.itemChanged.disconnect()
                    self.logger.debug("_reconnect_view_signals: Disconnected all existing itemChanged signals.")
                except TypeError:
                    self.logger.warning("_reconnect_view_signals: Could not disconnect existing itemChanged signal(s).", exc_info=False)
                except Exception as dis_e_item:
                    self.logger.error(f"_reconnect_view_signals: Unexpected error during itemChanged disconnect: {dis_e_item}", exc_info=True)
                
                # <<< 수정: lambda를 사용하여 logic_instance와 item 전달 >>>
                from mylist_sanga_events import on_mylist_shop_item_changed # 핸들러 임포트
                # lambda 함수를 사용하여 self(logic_instance)와 시그널의 item 인자를 함께 전달
                model.itemChanged.connect(lambda item: on_mylist_shop_item_changed(self, item))
                self.logger.info("_reconnect_view_signals: Successfully reconnected itemChanged signal using lambda.")
                # -----------------------------------------------

                # --- 디버깅 강화: 연결 수신기 재확인 --- (필요시 주석 해제)
                # try:
                #     receiver_count_after = model.receivers(model.itemChanged)
                #     self.logger.info(f"[DEBUG] itemChanged signal has {receiver_count_after} receiver(s) immediately after reconnect attempt.")
                #     if receiver_count_after == 0:
                #          self.logger.error("[CRITICAL DEBUG] itemChanged signal has NO receivers immediately after reconnect attempt!")
                # except Exception as e_debug_recheck:
                #     self.logger.error(f"[DEBUG] Error re-checking itemChanged receivers: {e_debug_recheck}")
                # --- 디버깅 강화 끝 ---

            except ImportError as imp_err:
                 self.logger.error(f"_reconnect_view_signals: Failed to import on_mylist_shop_item_changed: {imp_err}", exc_info=True)
            except Exception as e_reconnect_item:
                self.logger.error(f"_reconnect_view_signals: Failed to reconnect itemChanged: {e_reconnect_item}", exc_info=True)
            # --- itemChanged 연결 끝 ---

        else:
            self.logger.error("_reconnect_view_signals: FAILED to get selection model. Cannot reconnect currentChanged.")

    # Ensure necessary event handler methods (like on_mylist_shop_current_changed) are available
    # They are imported from mylist_sanga_events, so they should be accessible via self
    # Example placeholder if needed:
    # def on_mylist_shop_current_changed(self, current, previous):
    #     # Call the imported function or implement directly
    #     from mylist_sanga_events import on_mylist_shop_current_changed as handler
    #     handler(self, current, previous)
    pass # Assuming methods from events are correctly bound or accessible

