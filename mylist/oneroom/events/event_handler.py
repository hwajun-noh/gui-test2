"""
마이리스트 원룸 이벤트 핸들러

원룸 탭의 다양한 이벤트 처리 기능 제공
"""
import logging
from PyQt5.QtCore import QObject, pyqtSignal, QModelIndex, Qt
from PyQt5.QtWidgets import QMenu, QMessageBox, QInputDialog
from PyQt5.QtGui import QStandardItem, QColor

class OneRoomEventHandler(QObject):
    """원룸 탭 이벤트 처리 클래스"""
    
    # 이벤트 시그널
    addressSelected = pyqtSignal(str)  # 주소 선택 시
    dataChanged = pyqtSignal()  # 데이터 변경 시
    
    def __init__(self, model=None, view=None, commands=None, parent=None):
        """
        초기화
        
        Args:
            model: OneRoomModel 인스턴스
            view: QTableView 인스턴스
            commands: OneRoomCommands 인스턴스
            parent: 부모 객체
        """
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.model = model
        self.view = view
        self.commands = commands
        self.pending_color = QColor("#FFF9C4")  # 연한 노란색 (변경 대기 셀)
        
        # 데이터 로딩 플래그
        self.loading = False
        
        # 시그널 연결
        self._connect_signals()
    
    def _connect_signals(self):
        """내부 시그널 연결"""
        if self.model and hasattr(self.model, 'model'):
            self.model.model.itemChanged.connect(self.on_item_changed)
            
    def on_current_changed(self, current, previous):
        """
        현재 선택 셀 변경 이벤트 처리
        
        Args:
            current (QModelIndex): 현재 선택된 인덱스
            previous (QModelIndex): 이전 선택된 인덱스
        """
        if not current.isValid() or self.loading:
            return
            
        # 행이 바뀌었을 때만 처리
        if current.row() != previous.row():
            try:
                # 선택된 행의 주소 가져오기
                address_item = self.model.model.item(current.row(), 0)
                if address_item:
                    address = address_item.text()
                    if address:
                        self.addressSelected.emit(address)
                        self.logger.debug(f"원룸 주소 선택됨: {address}")
            except Exception as e:
                self.logger.error(f"행 선택 이벤트 처리 중 오류: {e}", exc_info=True)
    
    def on_item_changed(self, item: QStandardItem):
        """
        아이템 변경 이벤트 처리
        
        Args:
            item (QStandardItem): 변경된 아이템
        """
        if self.loading:
            return  # 로딩 중에는 무시
            
        try:
            # 변경된 셀의 배경색 설정
            item.setBackground(self.pending_color)
            
            self.dataChanged.emit()
        except Exception as e:
            self.logger.error(f"아이템 변경 이벤트 처리 중 오류: {e}", exc_info=True)
    
    def on_double_clicked(self, index: QModelIndex):
        """
        더블 클릭 이벤트 처리
        
        Args:
            index (QModelIndex): 더블 클릭된 인덱스
        """
        if not index.isValid() or self.loading:
            return
            
        # 로그 기록
        try:
            row = index.row()
            col = index.column()
            data = self.model.get_row_data(row)
            self.logger.debug(f"원룸 셀 더블클릭: 행={row}, 열={col}, 데이터={data}")
        except Exception as e:
            self.logger.error(f"더블 클릭 이벤트 처리 중 오류: {e}", exc_info=True)
    
    def show_context_menu(self, pos):
        """
        우클릭 컨텍스트 메뉴 표시
        
        Args:
            pos: 마우스 클릭 위치
        """
        if not self.view:
            return
            
        try:
            # 클릭된 인덱스
            index = self.view.indexAt(pos)
            if not index.isValid():
                return
                
            # 메뉴 생성
            menu = QMenu(self.view)
            
            # 메뉴 항목 추가
            action_copy = menu.addAction("행 복사")
            action_delete = menu.addAction("행 삭제")
            menu.addSeparator()
            action_change_manager = menu.addAction("담당자 변경")
            
            # 메뉴 실행
            action = menu.exec_(self.view.mapToGlobal(pos))
            
            # 선택된 메뉴 처리
            if action == action_copy:
                self._copy_row(index.row())
            elif action == action_delete:
                self._delete_selected_rows()
            elif action == action_change_manager:
                self._change_manager()
                
        except Exception as e:
            self.logger.error(f"컨텍스트 메뉴 처리 중 오류: {e}", exc_info=True)
    
    def _copy_row(self, row_idx):
        """
        행 복사 기능
        
        Args:
            row_idx (int): 복사할 행 인덱스
        """
        if not self.model or not self.commands:
            return
            
        try:
            # 원본 행 데이터 가져오기
            row_data = self.model.get_row_data(row_idx)
            if not row_data:
                return
                
            # ID 제거 (새 행은 새 ID 필요)
            if "id" in row_data:
                del row_data["id"]
                
            # 새 행 추가
            self.commands.add_row(row_data)
            self.logger.info(f"원룸 행 복사 완료: {row_data}")
            
        except Exception as e:
            self.logger.error(f"행 복사 중 오류: {e}", exc_info=True)
    
    def _delete_selected_rows(self):
        """선택된 행 삭제"""
        if not self.view or not self.commands:
            return
            
        try:
            # 선택된 행 가져오기
            selection_model = self.view.selectionModel()
            if not selection_model:
                return
                
            selected_rows = sorted(set(idx.row() for idx in selection_model.selectedIndexes()))
            if not selected_rows:
                return
                
            # 확인 메시지
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Question)
            msg_box.setWindowTitle("행 삭제")
            msg_box.setText(f"선택한 {len(selected_rows)}개 행을 삭제하시겠습니까?")
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            
            if msg_box.exec_() == QMessageBox.Yes:
                # 삭제 명령 실행
                deleted_count = self.commands.delete_rows(selected_rows)
                self.logger.info(f"원룸 행 {deleted_count}개 삭제 완료")
                
        except Exception as e:
            self.logger.error(f"행 삭제 중 오류: {e}", exc_info=True)
    
    def _change_manager(self):
        """담당자 변경 기능"""
        if not self.view or not self.commands:
            return
            
        try:
            # 선택된 행 가져오기
            selection_model = self.view.selectionModel()
            if not selection_model:
                return
                
            selected_rows = sorted(set(idx.row() for idx in selection_model.selectedIndexes()))
            if not selected_rows:
                QMessageBox.warning(self.view, "담당자 변경", "선택된 행이 없습니다.")
                return
                
            # 담당자 입력 다이얼로그
            new_manager, ok = QInputDialog.getText(
                self.view,
                "담당자 변경",
                f"선택한 {len(selected_rows)}개 행의 새 담당자 이름을 입력하세요:"
            )
            
            if ok and new_manager:
                # 담당자 변경 명령 실행
                updated_count = self.commands.change_manager(selected_rows, new_manager)
                self.logger.info(f"원룸 행 {updated_count}개 담당자 변경 완료: {new_manager}")
                
        except Exception as e:
            self.logger.error(f"담당자 변경 중 오류: {e}", exc_info=True)
    
    def filter_by_address(self, address_str):
        """
        주소 필터링
        
        Args:
            address_str (str): 필터링할 주소
        """
        if not self.model or not self.view:
            return
            
        try:
            # 주소가 없으면 필터 해제
            if not address_str:
                for row in range(self.model.model.rowCount()):
                    self.view.showRow(row)
                return
                
            # 주소로 필터링
            for row in range(self.model.model.rowCount()):
                address_item = self.model.model.item(row, 0)
                if address_item:
                    row_address = address_item.text()
                    if address_str.lower() in row_address.lower():
                        self.view.showRow(row)
                    else:
                        self.view.hideRow(row)
                        
            self.logger.debug(f"원룸 주소 필터링 완료: {address_str}")
            
        except Exception as e:
            self.logger.error(f"주소 필터링 중 오류: {e}", exc_info=True) 