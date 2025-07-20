"""
마이리스트 계약완료 이벤트 핸들러

계약완료 탭의 다양한 이벤트 처리 기능 제공
"""
import logging
from PyQt5.QtCore import QObject, pyqtSignal, QModelIndex, Qt
from PyQt5.QtWidgets import QMenu, QMessageBox, QInputDialog
from PyQt5.QtGui import QStandardItem, QColor

class CompletedDealEventHandler(QObject):
    """계약완료 탭 이벤트 처리 클래스"""
    
    # 이벤트 시그널
    addressSelected = pyqtSignal(str)  # 주소 선택 시
    dataChanged = pyqtSignal()  # 데이터 변경 시
    
    def __init__(self, model=None, view=None, commands=None, parent=None):
        """
        초기화
        
        Args:
            model: CompletedDealModel 인스턴스
            view: QTableView 인스턴스
            commands: CompletedDealCommands 인스턴스
            parent: 부모 객체
        """
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.model = model
        self.view = view
        self.commands = commands
        
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
                        self.logger.debug(f"계약완료 주소 선택됨: {address}")
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
            # 변경 이벤트 발생
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
            self.logger.debug(f"계약완료 셀 더블클릭: 행={row}, 열={col}, 데이터={data}")
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
            action_export = menu.addAction("내보내기")
            menu.addSeparator()
            action_delete = menu.addAction("행 삭제")
            
            # 메뉴 실행
            action = menu.exec_(self.view.mapToGlobal(pos))
            
            # 선택된 메뉴 처리
            if action == action_copy:
                self._copy_row(index.row())
            elif action == action_delete:
                self._delete_selected_rows()
            elif action == action_export:
                self._export_data()
                
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
            self.logger.info(f"계약완료 행 복사 완료: {row_data}")
            
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
                self.logger.info(f"계약완료 행 {deleted_count}개 삭제 완료")
                
        except Exception as e:
            self.logger.error(f"행 삭제 중 오류: {e}", exc_info=True)
    
    def _export_data(self, format_type="excel"):
        """
        데이터 내보내기
        
        Args:
            format_type (str): 내보내기 형식
        """
        if not self.commands:
            return
            
        try:
            # 형식 선택 대화상자
            items = ["Excel (.xlsx)", "CSV (.csv)"]
            selected_format, ok = QInputDialog.getItem(
                self.view,
                "내보내기 형식 선택",
                "형식을 선택하세요:",
                items,
                0,
                False
            )
            
            if ok and selected_format:
                # 형식 결정
                if "Excel" in selected_format:
                    format_type = "excel"
                elif "CSV" in selected_format:
                    format_type = "csv"
                    
                # 내보내기 실행
                success = self.commands.export_data(format_type)
                if success:
                    QMessageBox.information(
                        self.view,
                        "내보내기 완료",
                        f"데이터가 {format_type} 형식으로 내보내기 되었습니다."
                    )
                
        except Exception as e:
            self.logger.error(f"데이터 내보내기 중 오류: {e}", exc_info=True)
            QMessageBox.warning(
                self.view,
                "내보내기 오류",
                f"데이터 내보내기 중 오류가 발생했습니다: {e}"
            )
    
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
                        
            self.logger.debug(f"계약완료 주소 필터링 완료: {address_str}")
            
        except Exception as e:
            self.logger.error(f"주소 필터링 중 오류: {e}", exc_info=True) 