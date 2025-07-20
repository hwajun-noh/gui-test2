"""
마이리스트 계약완료 데이터 모델

계약완료된 매물 정보 데이터 모델 제공
"""
import logging
from datetime import datetime
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem

class CompletedDealModel:
    """계약완료 데이터 모델 클래스"""
    
    def __init__(self):
        """초기화"""
        self.logger = logging.getLogger(__name__)
        
        # 기본 헤더 설정
        self.headers = [
            "주소", "가격", "면적", "층수", "방수/화장실", "담당자", 
            "계약일자", "계약유형", "고객명", "계약메모"
        ]
        
        # DB 컬럼명과 표시 컬럼명 매핑
        self.column_map_db_to_display = {
            "address": "주소",
            "price": "가격",
            "area": "면적",
            "floor": "층수",
            "rooms_bath": "방수/화장실",
            "manager": "담당자",
            "contract_date": "계약일자",
            "contract_type": "계약유형",
            "client_name": "고객명",
            "memo": "계약메모"
        }
        
        self.column_map_display_to_db = {v: k for k, v in self.column_map_db_to_display.items()}
        
        # 모델 생성
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(self.headers)
        
    def get_model(self):
        """모델 반환"""
        return self.model
        
    def clear(self):
        """모델 데이터 초기화"""
        self.model.removeRows(0, self.model.rowCount())
        
    def append_row(self, data_dict):
        """
        행 추가
        
        Args:
            data_dict (dict): 행 데이터
            
        Returns:
            int: 추가된 행의 인덱스
        """
        try:
            # 새 행 인덱스
            row_idx = self.model.rowCount()
            
            # 각 열에 데이터 추가
            for col_idx, header in enumerate(self.headers):
                # DB 컬럼명
                db_field = self.column_map_display_to_db.get(header)
                
                # 값 가져오기
                value = ""
                if db_field and db_field in data_dict:
                    value = str(data_dict[db_field])
                elif header in data_dict:
                    value = str(data_dict[header])
                
                # 아이템 추가
                item = QStandardItem(value)
                self.model.setItem(row_idx, col_idx, item)
                
            # ID가 있으면 데이터로 저장
            if "id" in data_dict:
                self.model.item(row_idx, 0).setData(data_dict["id"], Qt.UserRole)
                
            return row_idx
            
        except Exception as e:
            self.logger.error(f"행 추가 중 오류 발생: {e}", exc_info=True)
            return -1
            
    def append_rows(self, rows):
        """
        다수 행 추가
        
        Args:
            rows (list): 행 데이터 목록
            
        Returns:
            int: 추가된 행 수
        """
        count = 0
        for row_data in rows:
            if self.append_row(row_data) >= 0:
                count += 1
        return count
        
    def get_row_data(self, row_idx):
        """
        행 데이터 가져오기
        
        Args:
            row_idx (int): 행 인덱스
            
        Returns:
            dict: 행 데이터
        """
        if row_idx < 0 or row_idx >= self.model.rowCount():
            self.logger.error(f"유효하지 않은 행 인덱스: {row_idx}")
            return {}
            
        data = {}
        for col_idx, header in enumerate(self.headers):
            item = self.model.item(row_idx, col_idx)
            if item:
                # 표시 필드
                data[header] = item.text()
                
                # DB 필드
                db_field = self.column_map_display_to_db.get(header)
                if db_field:
                    data[db_field] = item.text()
                    
        # ID 가져오기 (첫 번째 열에 저장됨)
        first_item = self.model.item(row_idx, 0)
        if first_item:
            record_id = first_item.data(Qt.UserRole)
            if record_id:
                data["id"] = record_id
                
        return data
        
    def update_cell(self, row_idx, col_idx, value):
        """
        셀 업데이트
        
        Args:
            row_idx (int): 행 인덱스
            col_idx (int): 열 인덱스
            value (str): 새 값
            
        Returns:
            bool: 성공 여부
        """
        try:
            # 유효성 검사
            if (row_idx < 0 or row_idx >= self.model.rowCount() or 
                col_idx < 0 or col_idx >= self.model.columnCount()):
                self.logger.error(f"유효하지 않은 셀 좌표: ({row_idx}, {col_idx})")
                return False
                
            # 셀 업데이트
            item = self.model.item(row_idx, col_idx)
            if item:
                item.setText(str(value))
                return True
            else:
                # 아이템이 없으면 새로 생성
                self.model.setItem(row_idx, col_idx, QStandardItem(str(value)))
                return True
                
        except Exception as e:
            self.logger.error(f"셀 업데이트 중 오류 발생: {e}", exc_info=True)
            return False 