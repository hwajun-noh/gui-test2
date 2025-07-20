# item_events.py - 아이템 변경 이벤트 모듈
import logging
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtGui import QStandardItem, QColor
from PyQt5.QtWidgets import QLineEdit, QComboBox, QMessageBox

from mylist.constants import PENDING_COLOR, RE_AD_BG_COLOR, NEW_AD_BG_COLOR

# 로거 인스턴스
logger = logging.getLogger(__name__)

class SangaItemEvents(QObject):
    """상가 항목 이벤트 핸들러 클래스"""
    
    # 시그널 정의
    itemChanged = pyqtSignal(QStandardItem)
    itemEditFinished = pyqtSignal(int, int, str, str)  # 행, 열, 이전 값, 새 값
    
    def __init__(self, parent=None):
        """
        초기화
        
        Args:
            parent: 부모 객체 (일반적으로 SangaBridge)
        """
        # parent 인자가 SangaBridge 타입이면 None으로 설정
        QObject.__init__(self, None)
        self.parent = parent
        self.logger = logging.getLogger(__name__)
        self.pending_edits = {}  # 편집 중인 상태 추적: {(row, col): prev_value}
        
    def setup_model_signals(self, model):
        """
        모델 시그널 설정
        
        Args:
            model: 연결할 모델 객체
        """
        if not model:
            self.logger.error("Model is None, cannot setup signals")
            return
            
        # 시그널 연결
        model.itemChanged.connect(self.on_item_changed)
    
    def setup_editor_signals(self, view):
        """
        편집기 시그널 설정
        
        Args:
            view: 연결할 뷰 객체
        """
        if not view:
            self.logger.error("View is None, cannot setup editor signals")
            return
            
        # 편집기 시그널 연결
        if hasattr(view, 'itemDelegate'):
            delegate = view.itemDelegate()
            if delegate and hasattr(delegate, 'commitData'):
                delegate.commitData.connect(self.handle_commit_data)
    
    def on_item_changed(self, item):
        """
        상가 모델의 itemChanged 신호를 처리합니다.
        대기 중인 변경 사항을 등록하고 배경색을 적용합니다.
        또한 새 행에 대한 대기 중인 추가를 업데이트합니다.
        
        Args:
            item: 변경된 아이템
        """
        # 함수 진입 확인 로그
        self.logger.debug(f"********** ENTERED on_item_changed **********")
        
        try:
            # 초기 객체 유효성 검사 로그
            if not item or not isinstance(item, QStandardItem) or not item.model():
                self.logger.warning(f"[itemChanged] Invalid item or model. Exiting.")
                return
            row = item.row()
            col = item.column()
            model = item.model()
            self.logger.info(f"[itemChanged] Item changed at Row={row}, Col={col}. Item text: '{item.text()}'")

            # ID 값 확인 추가 로그
            item0 = model.item(row, 0)  # 0번 열 아이템 가져오기
            if not item0:
                self.logger.warning(f"[itemChanged] Could not get item at Row {row}, Col 0 to check IDs.")
                return
                
            real_id_val = item0.data(Qt.UserRole + 3)
            temp_id_val = item0.data(Qt.UserRole + 99)
            self.logger.info(f"[itemChanged] ID Check for Row {row}: RealID(UR+3)='{real_id_val}' (Type: {type(real_id_val)}), TempID(UR+99)='{temp_id_val}' (Type: {type(temp_id_val)})")
            
            # pending_manager 가져오기
            pending_manager = None
            if hasattr(self.parent, 'pending_manager'):
                pending_manager = self.parent.pending_manager
            elif hasattr(self.parent, 'container') and hasattr(self.parent.container, 'pending_manager'):
                pending_manager = self.parent.container.pending_manager
                
            if not pending_manager:
                self.logger.error(f"[itemChanged] Cannot find pending_manager in parent or container.")
                return
            
            # 행 상태 확인 (실제 행 vs 임시 행)
            
            # 1. 처음 추가된 임시 행 (temp_id가 있고 real_id가 음수)
            if isinstance(real_id_val, int) and real_id_val < 0:
                self.logger.info(f"[itemChanged] Processing TEMPORARY ROW (real_id={real_id_val})")
                # 임시행은 이미 모델에 추가되어 있어야 함
                # pending_adds에 등록할지 확인(이미 있으면 추가 안함)
                pending_manager.ensure_shop_item_in_pending_adds(real_id_val, row)
                self.logger.debug(f"********** FINISHED on_item_changed (Temp Row) for ({row}, {col}) **********")
                return
                
            # 2. 저장된 실제 행 (real_id가 양수)
            elif isinstance(real_id_val, int) and real_id_val > 0:
                self.logger.info(f"[itemChanged] Processing REAL ROW (id={real_id_val})")
                # 셀 변경 사항 등록
                pending_manager.set_shop_pending_update(real_id_val, row, col, item.text())
                
                # 변경된 셀에 노란색 배경 설정
                item.setBackground(PENDING_COLOR)
                self.logger.info(f"[itemChanged] Set PENDING_COLOR for real row {row} (ID: {real_id_val}) at Col: {col}")
                
                # 전체 행 업데이트 필요시 추가 로직
                try:
                    # 행 전체 배경색 업데이트 함수 호출
                    from mylist.sanga.events.ui_helpers import update_row_background_color
                    update_row_background_color(self.parent, row, pending_col=col)
                    self.logger.debug(f"[itemChanged] Called update_row_background_color for row {row}")
                except Exception as bg_err:
                    self.logger.error(f"[itemChanged] Error updating row background: {bg_err}")
                    
                self.logger.debug(f"********** FINISHED on_item_changed (Real Row) for ({row}, {col}) **********")
                return
                
            # 3. 알 수 없는 상태의 행 (디버깅용)
            else:
                self.logger.warning(f"[itemChanged] Row {row} has UNKNOWN ID STATUS. real_id={real_id_val}, temp_id={temp_id_val}")
                self.logger.debug(f"********** FINISHED on_item_changed (Unknown Row) for ({row}, {col}) **********")
                return

        except Exception as e:
            import traceback
            self.logger.error(f"[itemChanged] Unexpected error: {e}\n{traceback.format_exc()}")
            self.logger.debug(f"********** FINISHED on_item_changed (ERROR) **********")
            
        # 시그널 발생
        self.itemChanged.emit(item)

    def handle_commit_data(self, editor_widget):
        """
        아이템 위임자의 commitData 신호를 처리합니다. (직접 셀 편집)
        일관된 처리를 위해 _process_item_change를 사용합니다.
        
        Args:
            editor_widget: 편집기 위젯 객체
        """
        view = self.parent.mylist_shop_view
        model = self.parent.mylist_shop_model

        if not view or not model:
            self.logger.warning("[handle_commit_data] View or model is None.")
            return

        current_index = view.currentIndex()
        if not current_index.isValid():
            # 편집기가 닫힌 후 currentIndex가 유효하지 않을 수 있음
            self.logger.warning("[handle_commit_data] Invalid current index from view after editor closed.")
            return

        self.logger.info(f"[handle_commit_data] CommitData signal received for editor: {type(editor_widget)}. Current index: Row={current_index.row()}, Col={current_index.column()}")

        new_value = ""
        try:
            if isinstance(editor_widget, QLineEdit):
                new_value = editor_widget.text()
            elif isinstance(editor_widget, QComboBox):
                 new_value = editor_widget.currentText()
            else:
                item_fallback = model.itemFromIndex(current_index)
                if item_fallback: new_value = item_fallback.text()
                self.logger.warning(f"Unhandled editor type: {type(editor_widget)}. Falling back to model value.")
            # 가져온 값 로그
            self.logger.info(f"[handle_commit_data] ===> Captured new value: [{repr(new_value)}] <===")
        except Exception as e_get_val:
            self.logger.error(f"Error getting value from editor_widget: {e_get_val}", exc_info=True)
            item_fallback = model.itemFromIndex(current_index)
            if item_fallback: new_value = item_fallback.text()

        item = model.itemFromIndex(current_index)
        if not item:
             self.logger.warning(f"[handle_commit_data] Could not get item from model for index Row={current_index.row()}, Col={current_index.column()}.")
             return

        # 중앙 처리 함수 호출
        self._process_item_change(item, new_value)

        # 처리 후 모델 값 확인 로그
        try:
            current_text_after = item.text()
            self.logger.info(f"[handle_commit_data] ===> Text in model AFTER _process_item_change: [{repr(current_text_after)}] <===")
        except Exception as e_log_after:
            self.logger.error(f"[handle_commit_data] Error logging text after process: {e_log_after}")

        self.logger.info(f"[handle_commit_data] Finished processing for Row={current_index.row()}, Col={current_index.column()}.")
        
        # 시그널 발생
        row, col = current_index.row(), current_index.column()
        prev_value = self.pending_edits.get((row, col), "")
        self.itemEditFinished.emit(row, col, prev_value, new_value)

    def _process_item_change(self, item, new_value):
        """
        아이템 변경을 처리하는 중앙 함수 (직접 편집 또는 대량 작업에서)
        PRD에 따라 대기 중인 변경 사항을 등록하고 배경색을 적용합니다.
        
        Args:
            item: 변경된 아이템
            new_value: 새 값
        """
        model = item.model()
        if not model:
            self.logger.warning("[_process_item_change] Item has no model.")
            return

        row = item.row()
        col = item.column()

        # 컬럼 헤더 및 매핑 딕셔너리 확인 로그
        col_header = "Unknown"
        column_map = {}
        try:
            if col < model.columnCount():
                header_item = model.horizontalHeaderItem(col)
                if header_item:
                     col_header = header_item.text()
            if hasattr(self.parent, 'parent_app') and hasattr(self.parent.parent_app, 'COLUMN_MAP_MYLIST_SHOP_DISPLAY_TO_DB'):
                column_map = self.parent.parent_app.COLUMN_MAP_MYLIST_SHOP_DISPLAY_TO_DB
            self.logger.info(f"[_process_item_change] CHECKING - Row={row}, Col Header='{col_header}', Column Map Contents: {column_map}")
        except Exception as e_check:
            self.logger.error(f"[_process_item_change] Error checking header/map: {e_check}")

        # 로딩 중인지 확인
        if hasattr(self.parent, 'mylist_shop_loading') and self.parent.mylist_shop_loading:
            self.logger.debug("[_process_item_change] Ignored during loading.")
            return

        container = self.parent.container if hasattr(self.parent, 'container') else None
        if not container:
            self.logger.warning("[_process_item_change] Container is None.")
            return

        item0 = model.item(row, 0)
        if not item0:
            self.logger.warning(f"[_process_item_change] Could not get item0 (column 0) for row {row}.")
            return

        record_id = item0.data(Qt.UserRole + 3)
        if record_id is None:
            # 새로 추가된 행(음수 임시 ID) 또는 다른 문제 처리
            temp_id = item0.data(Qt.UserRole + 99)  # 여기에 임시 ID가 저장되어 있다고 가정
            if temp_id and isinstance(temp_id, int) and temp_id < 0:
                 self.logger.debug(f"[_process_item_change] Processing change for new row (Temp ID={temp_id}), Row={row}, Col={col}.")
                 # 새 행은 pending_manager에 의해 다르게 처리됨(add_pending_shop_addition)
                 # 여기서는 배경색만 적용
                 item.setBackground(PENDING_COLOR)
                 
                 # ui_helpers 모듈에서 함수 가져옴 
                 from mylist.sanga.events.ui_helpers import update_row_background_color
                 update_row_background_color(self.parent, row, pending_col=col)
                 return  # 여기서 새 행의 DB 업데이트 등록 건너뜀
            else:
                self.logger.warning(f"[_process_item_change] Record ID is None and not a new row for Row={row}. Cannot process change.")
                return

        self.logger.debug(f"[_process_item_change] Processing change for Row={row}, Col='{col_header}', ID={record_id}. New value: '{new_value}'")

        if isinstance(record_id, int) and record_id > 0:
            pending_manager = container.pending_manager
            if not pending_manager:
                 self.logger.error(f"[_process_item_change] Cannot register pending update for ID {record_id}: pending_manager not found.")
                 return

            db_field = self.parent.parent_app.COLUMN_MAP_MYLIST_SHOP_DISPLAY_TO_DB.get(col_header)
            needs_update = False

            # db_field 확인 로그 (값 포함)
            if col_header == "담당자":
                self.logger.info(f"[_process_item_change] Handling '담당자' column. Looked up DB field for '{col_header}': {db_field}")

            if db_field:
                update_payload = {
                    "id": record_id,
                    db_field: new_value
                }
                # pending_manager 호출 확인 로그 (값 타입 포함)
                payload_repr = repr(update_payload)  # repr 사용으로 타입 명확히
                self.logger.info(f"[_process_item_change] Calling pending_manager.add_pending_shop_update with payload: {payload_repr}")
                pending_manager.add_pending_shop_update(update_payload)
                self.logger.debug(f"[_process_item_change] Registered pending update via manager for ID {record_id}: {{ {db_field}: '{new_value}' }}")
                needs_update = True

            elif col_header == "재광고":
                new_status_value = "Y" if new_value == "재광고" else "N"
                update_payload = {
                     "id": record_id,
                     "re_ad_yn": new_status_value
                }
                # pending_manager 호출 확인 로그 (값 타입 포함)
                payload_repr = repr(update_payload)  # repr 사용
                self.logger.info(f"[_process_item_change] Calling pending_manager.add_pending_shop_update for '재광고' with payload: {payload_repr}")
                pending_manager.add_pending_shop_update(update_payload)
                self.logger.debug(f"[_process_item_change] Registered pending update for 재광고 column: ID={record_id}, Value={new_status_value}")
                needs_update = True

            elif col_header != "주소":  # 주소 열은 보통 직접 수정하지 않음
                 self.logger.warning(f"[_process_item_change] No DB field mapping for header '{col_header}'. Update not registered for ID {record_id}.")

            if needs_update:
                # 1. 변경된 셀에 PENDING_COLOR 설정
                item.setBackground(PENDING_COLOR)
                self.logger.debug(f"[_process_item_change] Set background to PENDING_COLOR for ({row}, {col})")

                # 2. '재광고' 상태에 따라 행의 나머지 부분 배경 업데이트
                from mylist.sanga.events.ui_helpers import update_row_background_color
                update_row_background_color(self.parent, row, pending_col=col)

        elif isinstance(record_id, int) and record_id < 0:  # 임시 ID 처리 (새 행)
            # 새 행 값 변경은 pending_manager의 'additions' 딕셔너리에서 처리
            # 여기서는 배경색만 처리
            item.setBackground(PENDING_COLOR)
            from mylist.sanga.events.ui_helpers import update_row_background_color
            update_row_background_color(self.parent, row, pending_col=col)
            self.logger.debug(f"[_process_item_change] Applied PENDING_COLOR for new row change (Temp ID={record_id}), Row={row}, Col='{col_header}'.")

        else:
            self.logger.warning(f"[_process_item_change] Invalid record_id type ({type(record_id)}) or value for Row={row}. Skipping update registration and coloring.")

        # 함수 완료 확인 로그
        self.logger.info(f"[_process_item_change] ===> Function finished for ({row}, {col}), New Value: '{new_value}' <===")
    
    def copy_row(self, source_row_idx):
        """
        행 복사
        
        Args:
            source_row_idx: 복사할 행 인덱스
            
        Returns:
            int: 새 행 인덱스 (성공 시), -1 (실패 시)
        """
        if hasattr(self.parent, 'copy_mylist_shop_row'):
            return self.parent.copy_mylist_shop_row(source_row_idx)
            
        model = self.parent.mylist_shop_model
        if not model or source_row_idx < 0 or source_row_idx >= model.rowCount():
            self.logger.warning(f"Invalid source row index: {source_row_idx}")
            return -1
        
        # 소스 행 데이터 가져오기
        row_data = {}
        if hasattr(self.parent, 'model') and hasattr(self.parent.model, 'get_row_data'):
            row_data = self.parent.model.get_row_data(source_row_idx)
        else:
            # 헤더 정보 수집
            headers = []
            for c in range(model.columnCount()):
                header_item = model.horizontalHeaderItem(c)
                if header_item:
                    headers.append(header_item.text())
            
            # 행 데이터 수집
            for c in range(min(len(headers), model.columnCount())):
                item = model.item(source_row_idx, c)
                if item:
                    row_data[headers[c]] = item.text()
        
        # 새 행 추가
        if hasattr(self.parent, 'on_add_mylist_shop_row'):
            return self.parent.on_add_mylist_shop_row(row_data)
        elif hasattr(self.parent, 'model') and hasattr(self.parent.model, 'add_row'):
            return self.parent.model.add_row(row_data)
        else:
            # 필요한 메서드가 없는 경우
            self.logger.warning("Cannot find method to add row")
            return -1
    
    def delete_rows(self, row_indices):
        """
        선택 행 삭제
        
        Args:
            row_indices: 삭제할 행 인덱스 목록
        """
        if hasattr(self.parent, 'delete_selected_mylist_shop_rows'):
            self.parent.delete_selected_mylist_shop_rows()
            return
            
        if not row_indices:
            return
            
        # 삭제 확인
        view = self.parent.mylist_shop_view
        if view:
            reply = QMessageBox.question(
                view, 
                "삭제 확인", 
                f"선택한 {len(row_indices)}개 행을 삭제하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        # 행 삭제 처리
        if hasattr(self.parent, 'model') and hasattr(self.parent.model, 'delete_rows'):
            self.parent.model.delete_rows(row_indices)
        else:
            self.logger.warning("Model does not have delete_rows method")
            
        # 편집 추적 정보에서 삭제된 행 관련 항목 제거
        for key in list(self.pending_edits.keys()):
            row, _ = key
            if row in row_indices:
                del self.pending_edits[key]
                
    def clear_edits(self):
        """보류 중인 편집 추적 정보 지우기"""
        self.pending_edits.clear()
        
    def cancel_all_pending_edits(self):
        """모든 보류 중인 편집 취소"""
        model = self.parent.mylist_shop_model
        if not model:
            return
            
        # 보류 중인 모든 편집 복원
        for (row, col), prev_value in self.pending_edits.items():
            if row < model.rowCount() and col < model.columnCount():
                item = model.item(row, col)
                if item:
                    item.setText(prev_value)
                    item.setBackground(Qt.white)  # 배경색 복원
        
        # 추적 정보 지우기
        self.clear_edits()

# 다른 함수들도 마찬가지로 호환성을 위해 유지하지만, 로깅 메시지 추가
def update_model_row(model, row_idx, headers, db_data, column_map=None):
    logger.warning("update_model_row 함수는 모듈 함수로서 더 이상 사용되지 않습니다. SangaModel 클래스를 대신 사용하세요.")
    # 기존 구현 유지...

# 레거시 호환용 함수 추가
def on_mylist_shop_item_changed(logic_instance, item):
    """
    MyListSangaLogic에서 사용하는 item_changed 이벤트 핸들러
    
    Args:
        logic_instance: 로직 인스턴스 (MyListSangaLogic 또는 SangaBridge)
        item: 변경된 아이템
    """
    logger.debug("on_mylist_shop_item_changed 호출됨: 호환성 레이어 경유")
    
    # 인스턴스가 SangaBridge 타입이고 item_events 속성이 있으면 해당 메서드 호출
    if hasattr(logic_instance, 'item_events') and logic_instance.item_events:
        logic_instance.item_events.on_item_changed(item)
    else:
        # 기본 동작: on_item_changed를 직접 호출
        try:
            from mylist.sanga.events.item_events import SangaItemEvents
            events = SangaItemEvents(logic_instance)
            events.on_item_changed(item)
        except Exception as e:
            logger.error(f"item_changed 이벤트 처리 중 오류: {e}", exc_info=True)