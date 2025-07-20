"""
마이리스트 원룸 명령 모듈

원룸 데이터에 대한 명령(추가, 삭제, 변경 등) 처리 클래스 제공
"""
import logging
import os
from PyQt5.QtCore import QObject, pyqtSignal, Qt
from PyQt5.QtGui import QStandardItem, QPixmap, QIcon

class OneRoomCommands(QObject):
    """원룸 데이터 명령 처리 클래스"""
    
    # 명령 실행 결과 시그널
    commandExecuted = pyqtSignal(str, bool)  # 명령, 성공여부
    
    def __init__(self, model=None, pending_manager=None, parent=None):
        """
        초기화
        
        Args:
            model: OneRoomModel 인스턴스
            pending_manager: 변경 사항 관리자
            parent: 부모 객체
        """
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.model = model
        self.pending_manager = pending_manager
        
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
            # 임시 ID 생성
            temp_id = self._generate_temp_id() if self.pending_manager else -1
            
            # 초기 데이터가 있으면 사용, 없으면 기본값 설정
            if initial_data is None:
                initial_data = {
                    "address": "",
                    "price": "",
                    "area": "",
                    "floor": "",
                    "rooms_bath": "방0/0",
                    "manager": "",
                    "status": "신규",
                    "memo": "",
                    "reg_date": ""
                }
                
            # temp_id 추가
            if temp_id:
                initial_data["id"] = temp_id
                
            # 행 추가
            row_idx = self.model.append_row(initial_data)
            
            # 변경 관리자에 추가
            if self.pending_manager:
                self.pending_manager.add_pending_oneroom_add(temp_id)
                
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
                # ID 확인
                row_data = self.model.get_row_data(row_idx)
                record_id = row_data.get("id")
                
                # pending_manager에 등록
                if record_id and self.pending_manager:
                    if record_id > 0:  # 실제 DB 행
                        self.pending_manager.mark_oneroom_row_for_deletion(record_id)
                    elif record_id < 0:  # 임시 행
                        self.pending_manager.remove_oneroom_pending_add(record_id)
                
                # 모델에서 행 삭제
                self.model.model.removeRow(row_idx)
                deleted_count += 1
                
            self.commandExecuted.emit("delete_rows", deleted_count > 0)
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"행 삭제 중 오류 발생: {e}", exc_info=True)
            self.commandExecuted.emit("delete_rows", False)
            return 0
    
    def update_model_row(self, model, row_idx, headers, db_row_data):
        """
        모델의 한 행을 업데이트하는 메소드
        
        Args:
            model: 업데이트할 QStandardItemModel
            row_idx: 업데이트할 행 인덱스
            headers: 컬럼 헤더 목록
            db_row_data: 데이터베이스 행 데이터
            
        Returns:
            bool: 성공 여부
        """
        try:
            # 실행 시작 로깅
            self.logger.debug(f"update_model_row 시작: 행={row_idx}, 데이터 키={list(db_row_data.keys() if db_row_data else [])}")
            
            # 기본 확인
            if not model or row_idx < 0 or row_idx >= model.rowCount():
                self.logger.error(f"유효하지 않은 모델 또는 행 인덱스: {row_idx}")
                return False
                
            item0 = None
            # DB 필드명과 UI 필드명 매핑
            column_map = {
                "주소": None,  # 주소는 dong + jibun으로 특별 처리
                "호": "ho",
                "층": None,  # curr_floor + total_floor 조합
                "보증금/월세": None,  # deposit + monthly 조합
                "관리비": "manage_fee",
                "입주가능일": "in_date",
                "비밀번호": "password",
                "방/화장실": None,  # rooms + baths 조합
                "연락처": "owner_phone",
                "매물번호": None,  # naver_property_no + serve_property_no 조합
                "옵션": "options",
                "담당자": "manager",
                "메모": "memo",
                "주차대수": "parking",
                "용도": "building_usage",
                "사용승인일": "approval_date",
                "평수": "area",
                "광고종료일": "ad_end_date",
                "사진경로": "photo_path",
                "소유자명": "owner_name",
                "관계": "owner_relation"
            }
            
            for col_idx, header_name in enumerate(headers):
                # DB 필드명 조회
                db_key = column_map.get(header_name)
                # DB 값 조회
                raw_value = db_row_data.get(db_key) if db_key else None
                
                # 헤더별 특수 처리
                if header_name == "주소":
                    cell_val = f"{db_row_data.get('dong', '')} {db_row_data.get('jibun', '')}".strip()
                elif header_name == "층":
                    cell_val = f"{db_row_data.get('curr_floor', 0)}/{db_row_data.get('total_floor', 0)}"
                elif header_name == "보증금/월세":
                    cell_val = f"{db_row_data.get('deposit', 0)}/{db_row_data.get('monthly', 0)}"
                elif header_name == "방/화장실":
                    cell_val = f"{db_row_data.get('rooms', 0)}/{db_row_data.get('baths', 0)}"
                elif header_name == "매물번호":
                    cell_val = f"{db_row_data.get('naver_property_no', '')}/{db_row_data.get('serve_property_no', '')}"
                else:
                    cell_val = str(raw_value) if raw_value is not None else ""
                
                # 아이템 생성
                item = QStandardItem(str(cell_val))
                
                # 주소 열 추가 처리
                if header_name == "주소":
                    # 사진 경로 처리
                    folder_path = db_row_data.get("photo_path", "") or ""
                    rep_img_path = ""
                    
                    if folder_path and os.path.isdir(folder_path):
                        try:
                            files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
                            if files: 
                                rep_img_path = os.path.join(folder_path, sorted(files)[0])
                        except OSError as e: 
                            self.logger.warning(f"Cannot access folder path '{folder_path}': {e}")
                    
                    # 대표 이미지가 있으면 아이콘 설정
                    if rep_img_path and os.path.isfile(rep_img_path):
                        try:
                            pixmap = QPixmap(rep_img_path).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            if not pixmap.isNull():
                                item.setIcon(QIcon(pixmap))
                                # 백슬래시 문제 해결: f-string 대신 일반 문자열 연결 사용
                                file_url = "file:///" + rep_img_path.replace('\\', '/')
                                item.setToolTip(f'<img src="{file_url}" width="200">')
                            else: 
                                item.setToolTip(cell_val)
                        except Exception as img_err:
                            self.logger.warning(f"Error creating oneroom icon/tooltip for {rep_img_path}: {img_err}")
                            item.setToolTip(cell_val)
                    else: 
                        item.setToolTip(cell_val)
                    
                    # 메타데이터 설정
                    item.setData(folder_path, Qt.UserRole + 10)  # 사진 폴더 경로
                    item.setData(rep_img_path, Qt.UserRole + 11)  # 대표 이미지 경로
                    item.setData(db_row_data.get("status_cd", ""), Qt.UserRole + 1)  # 상태 코드
                    item.setData(db_row_data.get("id"), Qt.UserRole + 3)  # ID
                
                # 아이템 설정
                model.setItem(row_idx, col_idx, item)
                if col_idx == 0: 
                    item0 = item  # 첫 번째 열(주소) 아이템 참조 저장
                    
            # 상태 따라 배경색 설정 등 추가 처리 (필요시)
            # ...
            
            self.logger.debug(f"update_model_row 완료: 행={row_idx}")
            self.commandExecuted.emit("update_model_row", True)
            return True
            
        except Exception as e:
            self.logger.error(f"행 업데이트 중 오류 발생: {e}", exc_info=True)
            self.commandExecuted.emit("update_model_row", False)
            return False
    
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
            
            # 변경사항 등록
            if self.pending_manager:
                row_data = self.model.get_row_data(row_idx)
                record_id = row_data.get("id")
                
                if record_id > 0:  # 실제 DB 행
                    # 변경된 필드 결정
                    header = self.model.headers[col_idx]
                    db_field = self.model.column_map_display_to_db.get(header)
                    
                    if db_field:
                        self.pending_manager.update_oneroom_field(record_id, db_field, value)
                        
            self.commandExecuted.emit("update_cell", True)
            return True
            
        except Exception as e:
            self.logger.error(f"셀 업데이트 중 오류 발생: {e}", exc_info=True)
            self.commandExecuted.emit("update_cell", False)
            return False
    
    def change_manager(self, row_indices, new_manager):
        """
        담당자 변경
        
        Args:
            row_indices (list): 변경할 행 인덱스 목록
            new_manager (str): 새 담당자
            
        Returns:
            int: 변경된 행 수
        """
        if self.model is None:
            self.logger.error("모델이 설정되지 않았습니다.")
            self.commandExecuted.emit("change_manager", False)
            return 0
            
        try:
            # 담당자 열 인덱스 찾기
            manager_col_idx = -1
            for idx, header in enumerate(self.model.headers):
                if header == "담당자":
                    manager_col_idx = idx
                    break
                    
            if manager_col_idx == -1:
                self.logger.error("담당자 열을 찾을 수 없습니다.")
                return 0
                
            # 담당자 변경
            updated_count = 0
            for row_idx in row_indices:
                # 셀 업데이트
                if self.update_cell(row_idx, manager_col_idx, new_manager):
                    updated_count += 1
                    
            self.commandExecuted.emit("change_manager", updated_count > 0)
            return updated_count
            
        except Exception as e:
            self.logger.error(f"담당자 변경 중 오류 발생: {e}", exc_info=True)
            self.commandExecuted.emit("change_manager", False)
            return 0
                
    def _generate_temp_id(self):
        """임시 ID 생성 (pending_manager 사용)"""
        if self.pending_manager and hasattr(self.pending_manager, "generate_temp_id"):
            return self.pending_manager.generate_temp_id()
        # 백업 메서드
        return -int(abs(hash(str(id(self)))) % 100000) 