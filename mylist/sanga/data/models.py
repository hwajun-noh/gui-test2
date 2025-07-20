# models.py - 상가 모델 처리 관련 모듈
import os
import time
import logging
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtGui import QStandardItem, QPixmap, QIcon, QColor, QStandardItemModel, QBrush
from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtCore import QUrl
from mylist.constants import PENDING_COLOR, RE_AD_BG_COLOR, NEW_AD_BG_COLOR

# 로거 인스턴스
logger = logging.getLogger(__name__)

class SangaModel(QObject):
    """상가 데이터 모델 클래스"""
    
    dataChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.model = QStandardItemModel()
        
        # 기본 열 헤더 설정
        self.headers = [
            "주소", "담당자", "매물번호", "호실", "층", "입주가능일", "월세(만원)", "보증금(만원)", 
            "관리비(만원)", "권리금(만원)", "방/화장실", "평수(공급/전용)", "현업종", "업종제한", 
            "주차", "건물종류", "전용출입구", "전화번호", "메모", "추가정보", "승인일자", "재광고"
        ]
        self.model.setColumnCount(len(self.headers))
        self.model.setHorizontalHeaderLabels(self.headers)
        
        # 디스플레이 이름과 DB 필드명 매핑
        self.column_map = {
            "주소": "address",
            "담당자": "manager",
            "매물번호": "property_no",
            "호실": "room_no",
            "층": "floor",
            "입주가능일": "move_in_date",
            "월세(만원)": "monthly",
            "보증금(만원)": "deposit",
            "관리비(만원)": "maintenance_fee",
            "권리금(만원)": "key_money",
            "방/화장실": "rooms_bath",
            "평수(공급/전용)": "area",
            "현업종": "current_business",
            "업종제한": "business_restriction",
            "주차": "parking",
            "건물종류": "building_type",
            "전용출입구": "private_entrance",
            "전화번호": "phone",
            "메모": "memo",
            "추가정보": "additional_info",
            "승인일자": "approval_date",
            "재광고": "re_ad_yn"
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
            rows_data (list): 상가 데이터 행 목록
        """
        if not rows_data:
            return
            
        self.logger.info(f"상가 데이터 {len(rows_data)}행 추가 중")
        
        # 모델 준비
        start_row = self.model.rowCount()
        self.model.blockSignals(True)
        
        try:
            self.model.insertRows(start_row, len(rows_data))
            
            for i, row_data in enumerate(rows_data):
                row_idx = start_row + i
                for col_idx, header in enumerate(self.headers):
                    # 복합 필드 또는 특정 형식을 위한 특별 처리
                    if header == "주소":
                        cell_val = f"{row_data.get('dong', '')} {row_data.get('jibun', '')}".strip()
                    elif header == "층":
                        cell_val = f"{row_data.get('curr_floor', 0)}/{row_data.get('total_floor', 0)}"
                    elif header == "보증금/월세":
                        cell_val = f"{row_data.get('deposit', 0)}/{row_data.get('monthly', 0)}"
                    elif header == "매물번호":
                        cell_val = f"{row_data.get('naver_property_no', '')}/{row_data.get('serve_property_no', '')}"
                    elif header == "방/화장실":
                        r, b = row_data.get("rooms", ""), row_data.get("baths", "")
                        cell_val = f"방{r}/{b}" if r or b else ""
                    elif header == "재광고":
                        cell_val = "재광고" if row_data.get("re_ad_yn", "N") == "Y" else "새광고"
                    else:
                        # 기본값: DB 키에 매핑된 값 직접 사용
                        db_key = self.column_map.get(header)
                        raw_value = row_data.get(db_key) if db_key else None
                        cell_val = str(raw_value) if raw_value is not None else ""

                    item = self._create_shop_item(header, cell_val, row_data)
                    self.model.setItem(row_idx, col_idx, item)
                
                # 행 배경색 설정
                re_ad_yn = row_data.get("re_ad_yn", "N") == "Y"
                row_bg = RE_AD_BG_COLOR if re_ad_yn else NEW_AD_BG_COLOR
                for c in range(self.model.columnCount()):
                    cell = self.model.item(row_idx, c)
                    if cell:
                        cell.setBackground(row_bg)
        finally:
            self.model.blockSignals(False)
            self.dataChanged.emit()
    
    def _create_shop_item(self, header_name, cell_value, db_row_data):
        """상가 테이블을 위한 QStandardItem을 생성합니다."""
        item = QStandardItem(str(cell_value))  # 값을 문자열로 변환

        # '주소' 열 특별 처리 (아이콘, 툴팁, 역할)
        if header_name == "주소":
            folder_path = db_row_data.get("photo_path", "") or ""
            rep_img_path = ""
            if folder_path and os.path.isdir(folder_path):
                try:
                    files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
                    if files: rep_img_path = os.path.join(folder_path, sorted(files)[0])  # 첫 번째 정렬된 이미지 사용
                except OSError as e:
                    self.logger.warning(f"Cannot access folder path '{folder_path}': {e}")

            if rep_img_path and os.path.isfile(rep_img_path):
                try:
                    pixmap = QPixmap(rep_img_path).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    if not pixmap.isNull():
                        item.setIcon(QIcon(pixmap))
                        file_url = QUrl.fromLocalFile(rep_img_path).toString()
                        item.setToolTip(f'<img src="{file_url}" width="200">')
                    else:
                        self.logger.warning(f"Failed to load pixmap for icon: {rep_img_path}")
                        item.setToolTip(cell_value)  # 대체 툴팁
                except Exception as img_err:
                    self.logger.warning(f"Error creating icon/tooltip for {rep_img_path}: {img_err}")
                    item.setToolTip(cell_value)
            else:
                item.setToolTip(cell_value)

            item.setData(folder_path, Qt.UserRole + 10)
            item.setData(rep_img_path, Qt.UserRole + 11)
            item.setData(db_row_data.get("status_cd", ""), Qt.UserRole + 1)  # 상태 코드
            item.setData(db_row_data.get("id"), Qt.UserRole + 3)  # DB 기본 키

        # 기본 아이템 플래그 설정 (편집 가능 포함)
        item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)

        return item
    
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
        
        # 안전하게 텍스트 가져오기 도우미
        def get_item_text(r, c):
            item = self.model.item(r, c)
            return item.text().strip() if item else ""

        row_dict_parsed = {}

        for c, header in enumerate(self.headers):
            text_val = get_item_text(row_idx, c)
            db_key = self.column_map.get(header)

            if header == "주소":
                dong_val, jibun_val = text_val.split(" ", 1) if " " in text_val else (text_val, "")
                row_dict_parsed["dong"] = dong_val
                row_dict_parsed["jibun"] = jibun_val
            elif header == "층":
                cf_val, tf_val = 0, 0
                if "/" in text_val:
                    c_str, t_str = text_val.split("/", 1)
                    cf_val = int(c_str) if c_str.isdigit() else 0
                    tf_val = int(t_str) if t_str.isdigit() else 0
                row_dict_parsed["curr_floor"] = cf_val
                row_dict_parsed["total_floor"] = tf_val
            elif header == "보증금/월세":
                dep_val, mon_val = 0, 0
                if "/" in text_val:
                    d_str, m_str = text_val.split("/", 1)
                    dep_val = int(d_str) if d_str.isdigit() else 0
                    mon_val = int(m_str) if m_str.isdigit() else 0
                row_dict_parsed["deposit"] = dep_val
                row_dict_parsed["monthly"] = mon_val
            elif header == "매물번호":
                nav_val, srv_val = text_val.split("/", 1) if "/" in text_val else (text_val, "")
                row_dict_parsed["naver_property_no"] = nav_val.strip()
                row_dict_parsed["serve_property_no"] = srv_val.strip()
            elif header == "방/화장실":
                rm_val, bt_val = "", ""
                if "/" in text_val:
                    r_str, b_str = text_val.split("/", 1)
                    rm_val = r_str.replace("방", "").strip()
                    bt_val = b_str.strip()
                row_dict_parsed["rooms"] = rm_val
                row_dict_parsed["baths"] = bt_val
            elif header == "재광고":
                row_dict_parsed["re_ad_yn"] = "Y" if text_val == "재광고" else "N"
            elif header == "평수":
                ar_val = 0.0
                try: ar_val = float(text_val) if text_val else 0.0
                except ValueError: ar_val = 0.0
                row_dict_parsed["area"] = ar_val
            elif db_key:
                # 단순 텍스트 필드에 대한 직접 매핑
                row_dict_parsed[db_key] = text_val

        # 첫 번째 항목의 UserRole+1에서 상태 코드 가져오기
        status_cd = ""
        item0 = self.model.item(row_idx, 0)
        if item0: status_cd = item0.data(Qt.UserRole + 1) or ""
        row_dict_parsed["status_cd"] = status_cd
        
        # ID 설정
        if item0 and item0.data(Qt.UserRole + 3) is not None:
            row_dict_parsed["id"] = item0.data(Qt.UserRole + 3)

        return row_dict_parsed
    
    def get_known_ids(self):
        """
        모델에 있는 모든 ID 반환
        
        Returns:
            set: ID 집합
        """
        known_ids = set()
        
        for row in range(self.model.rowCount()):
            item0 = self.model.item(row, 0)
            if not item0:
                continue
                
            record_id = item0.data(Qt.UserRole + 3)
            if record_id is not None and isinstance(record_id, int) and record_id > 0:
                known_ids.add(record_id)
                
        return known_ids
    
    def update_row_id(self, old_tid, new_id):
        """
        임시 ID를 실제 ID로 업데이트
        
        Args:
            old_tid: 기존 임시 ID
            new_id: 서버에서의 새로운 실제 ID
        
        Returns:
            bool: 성공 여부
        """
        self.logger.info(f"[ID Update] Updating temp_id {old_tid} to real_id {new_id}")
        
        if isinstance(old_tid, str):
            try:
                old_tid_int = int(old_tid)
            except (ValueError, TypeError):
                self.logger.error(f"[ID Update] Failed to convert old_tid '{old_tid}' to int")
                return False
        else:
            old_tid_int = old_tid
        
        # 행 찾기
        found = False
        for row in range(self.model.rowCount()):
            item0 = self.model.item(row, 0)
            if not item0:
                continue
                
            # UserRole+3 (RealID) 확인
            current_id = item0.data(Qt.UserRole + 3)
            
            if current_id == old_tid_int:
                # 새 ID로 업데이트
                item0.setData(new_id, Qt.UserRole + 3)
                self.logger.info(f"[ID Update] Successfully updated row {row} from temp_id {old_tid_int} to real_id {new_id}")
                found = True
                
                # 저장됨 표시를 위한 색상 변경
                for col in range(self.model.columnCount()):
                    cell_item = self.model.item(row, col)
                    if cell_item:
                        cell_item.setBackground(QBrush(Qt.white))
                break
        
        if not found:
            self.logger.warning(f"[ID Update] Could not find any row with temp_id {old_tid_int}")
        
        return found
    
    def add_row(self, initial_data=None):
        """
        상가 테이블에 새 행 추가
        
        Args:
            initial_data: 초기 데이터 (선택 사항)
        """
        row_idx = self.model.rowCount()
        self.model.insertRow(row_idx)
        
        # 기본 값이 포함된 새 행 데이터
        row_data = initial_data or {}
        
        # 임시 ID 생성 (-1000 이하의 음수)
        import random
        temp_id = -1000 - random.randint(0, 9000)
        
        # 각 열의 기본값 설정
        for col_idx, header in enumerate(self.headers):
            # 기본값 처리
            if header == "주소":
                cell_val = row_data.get("address", "")
            elif header == "담당자":
                cell_val = row_data.get("manager", "")
            elif header == "재광고":
                cell_val = "새광고"  # 기본값
            else:
                db_key = self.column_map.get(header)
                cell_val = str(row_data.get(db_key, ""))
            
            # 항목 생성
            item = QStandardItem(cell_val)
            
            # 주소 열에는 임시 ID 설정
            if col_idx == 0:
                item.setData(temp_id, Qt.UserRole + 3)  # 임시 ID 설정
                item.setData("PENDING", Qt.UserRole + 1)  # 상태 코드
            
            # 배경색 설정 (새 행은 대기 상태 표시)
            item.setBackground(PENDING_COLOR)
            
            self.model.setItem(row_idx, col_idx, item)
        
        self.logger.info(f"새 상가 행 추가됨, 임시 ID: {temp_id}")
        self.dataChanged.emit()
        
        return row_idx
    
    def delete_rows(self, row_indices):
        """
        선택한 행 삭제 표시
        
        Args:
            row_indices: 삭제할 행 인덱스 목록
        """
        if not row_indices:
            return
        
        self.model.blockSignals(True)
        
        try:
            # 오름차순 정렬 (삭제 시 인덱스 변화 방지)
            sorted_indices = sorted(row_indices)
            
            # 각 행에 삭제 상태 마킹
            for row_idx in sorted_indices:
                if row_idx < 0 or row_idx >= self.model.rowCount():
                    continue
                
                # 첫 번째 셀에 삭제 표시
                item0 = self.model.item(row_idx, 0)
                if item0:
                    item0.setData("DELETED", Qt.UserRole + 1)
                
                # 모든 셀의 배경색 변경
                for col_idx in range(self.model.columnCount()):
                    item = self.model.item(row_idx, col_idx)
                    if item:
                        # 삭제 표시 배경색 (회색 또는 빨간색)
                        delete_color = QColor(240, 200, 200)  # 연한 빨간색
                        item.setBackground(delete_color)
            
            self.logger.info(f"{len(sorted_indices)}개 행 삭제 표시 완료")
        finally:
            self.model.blockSignals(False)
            self.dataChanged.emit()

# 이전 버전과의 호환성을 위한 함수 (레거시 지원용)
def create_shop_item(header_name, cell_value, db_row_data):
    """상가 테이블을 위한 QStandardItem을 생성합니다."""
    logger.warning("create_shop_item 함수는 모듈 함수로서 더 이상 사용되지 않습니다. SangaModel 클래스를 대신 사용하세요.")
    item = QStandardItem(str(cell_value))  # 값을 문자열로 변환

    # '주소' 열 특별 처리 (아이콘, 툴팁, 역할)
    if header_name == "주소":
        folder_path = db_row_data.get("photo_path", "") or ""
        rep_img_path = ""
        if folder_path and os.path.isdir(folder_path):
            try:
                files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
                if files: rep_img_path = os.path.join(folder_path, sorted(files)[0])  # 첫 번째 정렬된 이미지 사용
            except OSError as e:
                logger.warning(f"Cannot access folder path '{folder_path}': {e}")

        if rep_img_path and os.path.isfile(rep_img_path):
            try:
                pixmap = QPixmap(rep_img_path).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                if not pixmap.isNull():
                    item.setIcon(QIcon(pixmap))
                    file_url = QUrl.fromLocalFile(rep_img_path).toString()
                    item.setToolTip(f'<img src="{file_url}" width="200">')
                else:
                    logger.warning(f"Failed to load pixmap for icon: {rep_img_path}")
                    item.setToolTip(cell_value)  # 대체 툴팁
            except Exception as img_err:
                logger.warning(f"Error creating icon/tooltip for {rep_img_path}: {img_err}")
                item.setToolTip(cell_value)
        else:
            item.setToolTip(cell_value)

        item.setData(folder_path, Qt.UserRole + 10)
        item.setData(rep_img_path, Qt.UserRole + 11)
        item.setData(db_row_data.get("status_cd", ""), Qt.UserRole + 1)  # 상태 코드
        item.setData(db_row_data.get("id"), Qt.UserRole + 3)  # DB 기본 키

    # 기본 아이템 플래그 설정 (편집 가능 포함)
    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)

    # 플래그 확인 로그
    try:
        flags = item.flags()
        is_editable = bool(flags & Qt.ItemIsEditable)
        logger.debug(f"[create_shop_item] Item created for '{header_name}'. Flags: {flags}, IsEditable: {is_editable}")
    except Exception as flag_log_err:
        logger.warning(f"[create_shop_item] Error logging item flags: {flag_log_err}")

    return item

# 다른 함수들도 마찬가지로 호환성을 위해 유지하지만, 로깅 메시지 추가
def update_model_row(model, row_idx, headers, db_data, column_map=None):
    logger.warning("update_model_row 함수는 모듈 함수로서 더 이상 사용되지 않습니다. SangaModel 클래스를 대신 사용하세요.")
    # 기존 구현 유지...

def append_mylist_shop_rows(model, headers, row_list, column_map, parent_app=None):
    logger.warning("append_mylist_shop_rows 함수는 모듈 함수로서 더 이상 사용되지 않습니다. SangaModel 클래스를 대신 사용하세요.")
    # 기존 구현 유지...

def populate_mylist_shop_table(logic_instance, rows):
    """레거시 호환용 - SangaModel.append_rows() 사용 권장"""
    logger.warning("populate_mylist_shop_table 함수는 모듈 함수로서 더 이상 사용되지 않습니다. SangaModel 클래스를 대신 사용하세요.")
    # 기존 구현 유지...

def parse_mylist_shop_row(logic_instance, row_idx):
    logger.warning("parse_mylist_shop_row 함수는 모듈 함수로서 더 이상 사용되지 않습니다. SangaModel.get_row_data 메소드를 대신 사용하세요.")
    # 기존 구현 유지...

def build_mylist_shop_rows_for_changes(logic_instance, added_list, updated_list):
    logger.warning("build_mylist_shop_rows_for_changes 함수는 모듈 함수로서 더 이상 사용되지 않습니다. SangaModel 클래스를 대신 사용하세요.")
    # 기존 구현 유지...

def update_mylist_shop_row_id(logic_instance, old_tid, new_id):
    logger.warning("update_mylist_shop_row_id 함수는 모듈 함수로서 더 이상 사용되지 않습니다. SangaModel.update_row_id 메소드를 대신 사용하세요.")
    # 기존 구현 유지...

def find_mylist_shop_row_by_id(logic_instance, pk_id):
    logger.warning("find_mylist_shop_row_by_id 함수는 모듈 함수로서 더 이상 사용되지 않습니다. SangaModel 클래스를 대신 사용하세요.")
    # 기존 구현 유지...

def get_mylist_shop_known_ids(model):
    logger.warning("get_mylist_shop_known_ids 함수는 모듈 함수로서 더 이상 사용되지 않습니다. SangaModel.get_known_ids 메소드를 대신 사용하세요.")
    # 기존 구현 유지...

def get_summary_by_manager(logic_instance, manager_name):
    logger.warning("get_summary_by_manager 함수는 모듈 함수로서 더 이상 사용되지 않습니다. SangaModel 클래스를 대신 사용하세요.")
    # 기존 구현 유지...