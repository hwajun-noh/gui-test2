# context_menu_events.py - 컨텍스트 메뉴 이벤트 처리 모듈
import logging
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtWidgets import QMenu, QMessageBox

# 로거 인스턴스
logger = logging.getLogger(__name__)

class SangaContextMenuEvents(QObject):
    """상가 컨텍스트 메뉴 이벤트 핸들러 클래스"""
    
    # 시그널 정의
    menuRequested = pyqtSignal(object)  # QPoint
    actionTriggered = pyqtSignal(str, int)  # 액션 이름, 행 인덱스
    
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
    
    def setup_context_menu(self, view):
        """
        컨텍스트 메뉴 설정
        
        Args:
            view: 컨텍스트 메뉴를 연결할 뷰 객체
        """
        if not view:
            self.logger.error("View is None, cannot setup context menu")
            return
            
        # 시그널 연결
        view.setContextMenuPolicy(Qt.CustomContextMenu)
        view.customContextMenuRequested.connect(self.show_context_menu)
    
    def show_context_menu(self, pos):
        """
        상가 테이블의 컨텍스트 메뉴를 생성하고 표시합니다.
        복사, 삭제, 담당자 변경 등의 옵션을 제공합니다.
        
        Args:
            pos: 메뉴를 표시할 위치 (QPoint)
        """
        view = self.parent.mylist_shop_view
        if not view:
            return
        
        index = view.indexAt(pos)
        if not index.isValid():
            return
        
        menu = QMenu(view)
        act_copy = menu.addAction("복사 후 추가")
        
        # 최소 하나의 셀이 선택된 경우에만 삭제 활성화
        act_delete = menu.addAction("삭제")
        act_delete.setEnabled(len(view.selectedIndexes()) > 0)
        
        menu.addSeparator()
        
        act_change_manager = menu.addAction("담당자 변경")
        act_change_re_ad = menu.addAction("재광고 여부 변경")
        menu.addSeparator()
        
        act_completed = menu.addAction("상태 변경(계약완료)")
        
        # 시그널 발생
        self.menuRequested.emit(pos)
        
        action = menu.exec_(view.viewport().mapToGlobal(pos))
        
        if action == act_copy:
            # 커서 아래 행 복사
            self.copy_row(index.row())
        elif action == act_delete:
            self.delete_selected_rows()
        elif action == act_change_manager:
            self.bulk_change_manager()
        elif action == act_change_re_ad:
            self.bulk_change_re_ad()
        elif action == act_completed:
            self.change_status(pos)
    
    def copy_row(self, row_idx):
        """
        행 복사
        
        Args:
            row_idx: 복사할 행 인덱스
        """
        if hasattr(self.parent, 'copy_mylist_shop_row'):
            self.parent.copy_mylist_shop_row(row_idx)
        else:
            # parent에 함수가 없는 경우 이벤트 핸들러에 직접 구현
            from mylist.sanga.events.item_events import SangaItemEvents
            if isinstance(self.parent.event_handler, SangaItemEvents):
                self.parent.event_handler.copy_row(row_idx)
            else:
                self.logger.warning("Cannot find copy_row implementation")
        
        # 시그널 발생
        self.actionTriggered.emit('copy', row_idx)
        
    def delete_selected_rows(self):
        """
        선택한 행을 '삭제 예정' 상태로 표시하고 pending changes에 기록합니다.
        (실제 행 삭제는 '저장' 시 수행됨)
        """
        if hasattr(self.parent, 'delete_selected_mylist_shop_rows'):
            self.parent.delete_selected_mylist_shop_rows()
            self.actionTriggered.emit('delete', -1)
            return
            
        view = self.parent.mylist_shop_view
        model = self.parent.mylist_shop_model
        pending_manager = self.parent.container.pending_manager
        
        if not view or not model or not pending_manager:
            self.logger.error("delete_selected_rows: View, model, or pending_manager is None.")
            return
        
        # 선택한 인덱스를 가져와서 관련된 고유 행 결정
        selected_indexes = view.selectedIndexes()
        if not selected_indexes: return 
        involved_rows = set(idx.row() for idx in selected_indexes)
        if not involved_rows: return
            
        # 전체 행 삭제 확인
        reply = QMessageBox.question(
            self.parent.parent_app,
            "행 삭제 확인",
            f"선택한 셀이 포함된 {len(involved_rows)}개 행 전체를 삭제 상태로 표시하시겠습니까?", 
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes: return
        
        # 모델 신호 차단 상태에서 모든 처리 수행 (성능 향상)
        model.blockSignals(True)
        try:
            # 행 처리
            rows_to_mark = sorted(list(involved_rows))
            record_ids = []
            
            # 첫 번째 루프: 모든 행의 ID 수집 (ID가 있는 경우)
            for row in rows_to_mark:
                item0 = model.item(row, 0)
                if item0:
                    record_id = item0.data(Qt.UserRole + 3)
                    if record_id is not None:
                        record_ids.append((row, record_id))

            # 두 번째 루프: 모든 행 시각적으로 표시
            self.logger.info(f"마크 시작: {len(rows_to_mark)}개 행 삭제 표시 중...")
            
            # ui_helpers 모듈에서 함수 임포트
            from mylist.sanga.events.ui_helpers import mark_row_as_pending_deletion
            
            for row in rows_to_mark:
                mark_row_as_pending_deletion(model, row)

            # 세 번째 루프: 서버에 삭제 표시할 ID 등록 (pending_manager)
            for row, record_id in record_ids:
                pending_manager.mark_shop_row_for_deletion(record_id)
                self.logger.debug(f"Marked shop row for deletion via pending manager: ID={record_id}")
        
        finally:
            model.blockSignals(False)
            
        marked_count = len(rows_to_mark)
        self.logger.info(f"{marked_count}개 행을 삭제 예정 상태로 표시했습니다.")
        
        # 표시 후 요약 업데이트
        if hasattr(self.parent.container, '_recalculate_manager_summary'):
            self.parent.container._recalculate_manager_summary()
        
        # 시그널 발생
        self.actionTriggered.emit('delete', -1)
            
    def change_status(self, pos):
        """
        상태 변경 대화 상자를 열고 상태 변경을 처리합니다.
        
        Args:
            pos: 메뉴 위치 (QPoint)
        """
        if hasattr(self.parent, 'on_mylist_shop_change_status'):
            self.parent.on_mylist_shop_change_status(pos)
            self.actionTriggered.emit('change_status', -1)
            return
            
        view = self.parent.mylist_shop_view
        model = self.parent.mylist_shop_model
        
        if not view or not model:
            return
        
        # 선택한 행 가져오기 (없으면 커서 아래 행 사용)
        selected_indexes = view.selectedIndexes()
        
        if not selected_indexes:
            index = view.indexAt(pos)
            if index.isValid():
                selected_indexes = [index]
        
        if not selected_indexes:
            QMessageBox.information(self.parent.parent_app, "선택 없음", "상태를 변경할 행을 선택하세요.")
            return
        
        # 선택한 인덱스에서 고유 행 가져오기
        selected_rows = set(idx.row() for idx in selected_indexes)
        
        # 상태 변경을 위한 첫 번째 열이 유효한지 확인
        valid_ids = []
        rows_to_remove = []
        
        for row in selected_rows:
            item0 = model.item(row, 0)
            if not item0:
                continue
            
            record_id = item0.data(Qt.UserRole + 3)
            
            # 임시 행이 아닌 실제 DB 행만 처리 (양수 ID)
            if isinstance(record_id, int) and record_id > 0:
                valid_ids.append(record_id)
                rows_to_remove.append(row)
        
        if not valid_ids:
            QMessageBox.information(
                self.parent.parent_app,
                "대상 없음",
                "상태 변경은 저장된 행에만 적용 가능합니다.\n추가한 행을 먼저 저장해주세요."
            )
            return
        
        # StatusChangeDialog 호출 시 all_managers 전달
        all_managers = []
        if hasattr(self.parent.parent_app, 'manager_list'):
            all_managers = self.parent.parent_app.manager_list
        if not all_managers:
            all_managers = [self.parent.current_manager]  # 목록이 비어 있으면 대체
            self.logger.warning("Could not find manager list in parent_app, using current manager only for StatusChangeDialog.")

        from dialogs import StatusChangeDialog
        dialog = StatusChangeDialog(self.parent.parent_app, "상가", all_managers=all_managers)
        result = dialog.exec_()
        
        if result != QMessageBox.Accepted:
            return
        
        status_data = dialog.get_values()
        
        if not status_data.get("status_value"):
            QMessageBox.warning(self.parent.parent_app, "입력 오류", "상태값이 선택되지 않았습니다.")
            return
        
        # 컨테이너를 통해 상태 변경 작업 제출
        payload = {
            "ids": valid_ids,
            "type": "shop",
            "status": status_data.get("status_value", ""),
            "status_date": status_data.get("selected_date", ""),
            "status_memo": status_data.get("memo", ""),
            "manager": self.parent.current_manager
        }
        
        self.parent.container.submit_status_change_task(payload, rows_to_remove, "shop")
        
        # 시그널 발생
        self.actionTriggered.emit('change_status', -1)
    
    def bulk_change_manager(self):
        """담당자 일괄 변경 대화 상자를 열고 처리합니다."""
        from mylist.sanga.events.bulk_operations import bulk_change_manager_mylist_shop
        bulk_change_manager_mylist_shop(self.parent)
        self.actionTriggered.emit('change_manager', -1)
        
    def bulk_change_re_ad(self):
        """재광고 여부 일괄 변경 대화 상자를 열고 처리합니다."""
        from mylist.sanga.events.bulk_operations import bulk_change_re_ad_mylist_shop
        bulk_change_re_ad_mylist_shop(self.parent)
        self.actionTriggered.emit('change_re_ad', -1)