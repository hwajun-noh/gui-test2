"""
마이리스트 계약완료 명령 모듈

계약완료된 매물 정보에 대한 명령(추가, 삭제, 변경 등) 처리 클래스 제공
"""
import logging
from PyQt5.QtCore import QObject, pyqtSignal, Qt
from PyQt5.QtGui import QStandardItem

class CompletedDealCommands(QObject):
    """계약완료 데이터 명령 처리 클래스"""
    
    # 명령 실행 결과 시그널
    commandExecuted = pyqtSignal(str, bool)  # 명령, 성공여부
    
    def __init__(self, model=None, parent=None):
        """
        초기화
        
        Args:
            model: CompletedDealModel 인스턴스
            parent: 부모 객체
        """
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.model = model
        
    def add_row(self, initial_data=None):
        """
        새 행 추가
        
        Args:
            initial_data (dict, optional): 초기 데이터
            
        Returns:
            int: 추가된 행의 인덱스
        """
        if self.model is None:
            self.logger.error("모델이 설정되지 않았습니다.")
            self.commandExecuted.emit("add_row", False)
            return -1
            
        try:
            # 초기 데이터가 있으면 사용, 없으면 기본값 설정
            if initial_data is None:
                initial_data = {
                    "address": "",
                    "price": "",
                    "area": "",
                    "floor": "",
                    "rooms_bath": "방0/0",
                    "manager": "",
                    "contract_date": "",
                    "contract_type": "매매",
                    "client_name": "",
                    "memo": ""
                }
                
            # 행 추가
            row_idx = self.model.append_row(initial_data)
            
            self.commandExecuted.emit("add_row", True)
            return row_idx
            
        except Exception as e:
            self.logger.error(f"행 추가 중 오류 발생: {e}", exc_info=True)
            self.commandExecuted.emit("add_row", False)
            return -1
    
    def delete_rows(self, row_indices):
        """
        행 삭제
        
        Args:
            row_indices (list): 삭제할 행 인덱스 목록
            
        Returns:
            int: 삭제된 행 수
        """
        if self.model is None:
            self.logger.error("모델이 설정되지 않았습니다.")
            self.commandExecuted.emit("delete_rows", False)
            return 0
            
        try:
            deleted_count = 0
            
            # 역순으로 정렬하여 인덱스 변화 방지
            for row_idx in sorted(row_indices, reverse=True):
                self.model.model.removeRow(row_idx)
                deleted_count += 1
                
            self.commandExecuted.emit("delete_rows", deleted_count > 0)
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"행 삭제 중 오류 발생: {e}", exc_info=True)
            self.commandExecuted.emit("delete_rows", False)
            return 0
    
    def update_cell(self, row_idx, col_idx, value):
        """
        셀 값 업데이트
        
        Args:
            row_idx (int): 행 인덱스
            col_idx (int): 열 인덱스
            value (str): 새 값
            
        Returns:
            bool: 성공 여부
        """
        if self.model is None:
            self.logger.error("모델이 설정되지 않았습니다.")
            self.commandExecuted.emit("update_cell", False)
            return False
            
        try:
            # 현재 셀 정보
            model_item = self.model.model.item(row_idx, col_idx)
            if not model_item:
                self.logger.error(f"셀({row_idx}, {col_idx})을 찾을 수 없습니다.")
                return False
                
            old_value = model_item.text()
            if old_value == value:
                self.logger.debug(f"셀({row_idx}, {col_idx}) 값이 변경되지 않았습니다: {value}")
                return True
                
            # 값 업데이트
            model_item.setText(value)
            
            self.commandExecuted.emit("update_cell", True)
            return True
            
        except Exception as e:
            self.logger.error(f"셀 업데이트 중 오류 발생: {e}", exc_info=True)
            self.commandExecuted.emit("update_cell", False)
            return False
            
    def export_data(self, format_type="excel"):
        """
        데이터 내보내기
        
        Args:
            format_type (str): 내보내기 형식 ("excel" 또는 "csv")
            
        Returns:
            bool: 성공 여부
        """
        if self.model is None:
            self.logger.error("모델이 설정되지 않았습니다.")
            self.commandExecuted.emit("export_data", False)
            return False
            
        try:
            # TODO: 데이터 내보내기 구현
            self.logger.info(f"데이터 내보내기 요청: {format_type}")
            
            # 성공 시그널 발생
            self.commandExecuted.emit("export_data", True)
            return True
            
        except Exception as e:
            self.logger.error(f"데이터 내보내기 중 오류 발생: {e}", exc_info=True)
            self.commandExecuted.emit("export_data", False)
            return False 