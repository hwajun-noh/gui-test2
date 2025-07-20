"""
마이리스트 원룸 데이터 모델
"""
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtGui import QStandardItemModel, QStandardItem
import logging

class OneRoomModel(QObject):
    """원룸 데이터 모델 클래스"""
    
    dataChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.model = QStandardItemModel()
        
        # 기본 열 헤더 설정
        self.headers = ["주소", "가격", "면적", "층수", "방/화장실", "담당자", "상태", "메모", "등록일"]
        self.model.setColumnCount(len(self.headers))
        self.model.setHorizontalHeaderLabels(self.headers)
        
        # 디스플레이 이름과 DB 필드명 매핑
        self.column_map_display_to_db = {
            "주소": "address",
            "가격": "price",
            "면적": "area",
            "층수": "floor",
            "방/화장실": "rooms_bath",
            "담당자": "manager",
            "상태": "status",
            "메모": "memo",
            "등록일": "reg_date"
        }
        
    def get_model(self):
        """QStandardItemModel 반환"""
        return self.model
    
    def clear_model(self):
        """모델 데이터 초기화"""
        self.model.removeRows(0, self.model.rowCount())
    
    def append_rows(self, rows_data):
        """
        데이터 행 추가
        
        Args:
            rows_data (list): 원룸 데이터 행 목록
        """
        if not rows_data:
            return
            
        self.logger.info(f"원룸 데이터 {len(rows_data)}행 추가 중")
        for row_data in rows_data:
            self.append_row(row_data)
            
        self.dataChanged.emit()
    
    def append_row(self, row_data):
        """
        단일 데이터 행 추가
        
        Args:
            row_data (dict): 원룸 데이터 행
        """
        row_idx = self.model.rowCount()
        self.model.insertRow(row_idx)
        
        for col_idx, header in enumerate(self.headers):
            db_field = self.column_map_display_to_db.get(header)
            value = str(row_data.get(db_field, ""))
            
            item = QStandardItem(value)
            
            # 첫 번째 열에 원본 ID 저장
            if col_idx == 0 and "id" in row_data:
                item.setData(row_data["id"], Qt.UserRole + 3)
                
            self.model.setItem(row_idx, col_idx, item)
    
    def get_row_data(self, row_idx):
        """
        특정 행의 데이터를 사전 형태로 반환
        
        Args:
            row_idx (int): 행 인덱스
            
        Returns:
            dict: 행 데이터
        """
        if row_idx < 0 or row_idx >= self.model.rowCount():
            return {}
            
        row_data = {}
        
        # ID 가져오기
        id_item = self.model.item(row_idx, 0)
        if id_item:
            row_data["id"] = id_item.data(Qt.UserRole + 3)
            
        # 열 데이터 가져오기
        for col_idx, header in enumerate(self.headers):
            item = self.model.item(row_idx, col_idx)
            if item:
                db_field = self.column_map_display_to_db.get(header)
                if db_field:
                    row_data[db_field] = item.text()
                    
        return row_data
        
    def get_known_ids(self):
        """
        모델에 있는 모든 ID 반환
        
        Returns:
            set: ID 집합
        """
        ids = set()
        for row_idx in range(self.model.rowCount()):
            item = self.model.item(row_idx, 0)
            if item:
                item_id = item.data(Qt.UserRole + 3)
                if item_id:
                    ids.add(item_id)
        return ids 