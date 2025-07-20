import logging
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt

logger = logging.getLogger(__name__)

class ManagerTableMixin:
    """ManagerCheckTab의 테이블 데이터 관련 메서드를 관리하는 Mixin 클래스"""
    
    def format_type_string(self, type_value, verification_method):
        """
        type과 verification_method를 조합하여 타입 문자열 생성
        
        Args:
            type_value: "상가" 또는 "사무실"
            verification_method: "NDOC1", "OWNER", "SITE" 등
            
        Returns:
            str: 조합된 타입 문자열 (예: "상가 집주인", "사무실 현장", "상가")
        """
        if not type_value:
            return ""
            
        # verification_method 매핑
        verification_map = {
            "NDOC1": "집주인",
            "OWNER": "집주인", 
            "SITE": "현장"
        }
        
        verification_text = verification_map.get(verification_method, "")
        
        if verification_text:
            return f"{type_value} {verification_text}"
        else:
            return type_value
    
    def populate_check_manager_table(self, rows, append=False):
        """Populates the QTableView with data."""
        # Logic from main_app_part5/populate_check_manager_table
        model = self.manager_source_model
        
        # 데이터가 비어있는 경우 처리
        if not rows:
            self.logger.info("populate_check_manager_table: 표시할 데이터가 없습니다.")
            if not append:
                model.setRowCount(0)
            return

        # 디버그 로깅
        self.logger.info(f"populate_check_manager_table 시작: 행 수={len(rows)}, append={append}")
        
        # 로딩 중 플래그 설정
        self.loading_data_flag = True
        
        try:
            if not append:
                model.setRowCount(0)
                
            old_count = model.rowCount() if append else 0
            model.setRowCount(old_count + len(rows))
             
            # 헤더 확인
            headers = []
            try:
                headers = [model.horizontalHeaderItem(j).text() if model.horizontalHeaderItem(j) else f"col_{j}" 
                        for j in range(model.columnCount())]
                self.logger.debug(f"테이블 헤더: {headers}")
            except AttributeError as e:
                self.logger.warning(f"헤더 가져오기 실패: {e}")
                # 기본 헤더 설정 (타입 컬럼 추가)
                headers = ["타입","주소","호","층","보증금/월세","관리비",
                    "권리금","현업종","평수","연락처",
                    "매물번호","제목","매칭업종","확인메모","광고등록일",
                    "주차대수","용도","사용승인일","방/화장실",
                    "사진경로","소유자명","관계"]
                model.setColumnCount(len(headers))
                model.setHorizontalHeaderLabels(headers)
                self.logger.info(f"기본 헤더로 재설정: {len(headers)}개 컬럼")
                 
            # 열 인덱스 확인
            header_map = {text: idx for idx, text in enumerate(headers)} 
            col_type_idx = header_map.get("타입", -1)
            col_addr_idx = header_map.get("주소", 1)
            col_ho_idx = header_map.get("호", -1)
            col_floor_idx = header_map.get("층", -1)
            col_price_idx = header_map.get("보증금/월세", -1)
            col_manage_fee_idx = header_map.get("관리비", -1)
            col_premium_idx = header_map.get("권리금", -1)
            col_current_use_idx = header_map.get("현업종", -1)
            col_area_idx = header_map.get("평수", -1)
            col_contact_idx = header_map.get("연락처", -1)
            col_prop_no_idx = header_map.get("매물번호", -1)
            col_title_idx = header_map.get("제목", -1)
            col_biz_idx = header_map.get("매칭업종", -1)
            col_check_memo_idx = header_map.get("확인메모", -1)
            col_ad_start_idx = header_map.get("광고등록일", -1)
            col_parking_idx = header_map.get("주차대수", -1)
            col_usage_idx = header_map.get("용도", -1)
            col_approval_date_idx = header_map.get("사용승인일", -1)
            col_rooms_idx = header_map.get("방/화장실", -1)
            col_photo_path_idx = header_map.get("사진경로", -1)
            col_owner_name_idx = header_map.get("소유자명", -1)
            col_relation_idx = header_map.get("관계", -1)

            # 배치 크기 설정 (한 번에 처리할 행 수)
            BATCH_SIZE = 300
            total_rows = len(rows)
            batch_count = (total_rows + BATCH_SIZE - 1) // BATCH_SIZE  # 총 배치 수 계산
            
            # 상태바에 진행 상황 표시
            self.parent_app.statusBar().showMessage(f"데이터 처리 중... (0/{total_rows}건)", 0)
            QtWidgets.QApplication.processEvents()  # UI 업데이트
            
            # 배치 단위로 데이터 처리
            for batch_idx in range(batch_count):
                start_idx = batch_idx * BATCH_SIZE
                end_idx = min((batch_idx + 1) * BATCH_SIZE, total_rows)
                
                # 현재 배치의 행 범위
                batch_rows = rows[start_idx:end_idx]
                
                # 상태바 업데이트
                self.parent_app.statusBar().showMessage(f"데이터 처리 중... ({end_idx}/{total_rows}건)", 0)
                
                # 현재 배치의 데이터 처리
                for i, row in enumerate(batch_rows):
                    try:
                        idx = old_count + start_idx + i
                        shop_id = row.get("shop_id", None)
                        lat_ = row.get("lat", "")
                        lng_ = row.get("lng", "")
                        naver_no = row.get("naver_property_no","")
                        serve_no = row.get("serve_property_no","")
                        addr_str = (row.get("dong","") + " " + row.get("jibun","")).strip()
                        
                        # 첫번째와 마지막 행은 디버그 로깅
                        if i == 0 or i == len(batch_rows) - 1:
                            self.logger.debug(f"행 {idx} 데이터: addr={addr_str}, shop_id={shop_id}")
                        
                        # 타입 컬럼 먼저 설정
                        if col_type_idx != -1:
                            type_value = row.get("type", "")
                            verification_method = row.get("verification_method", "")
                            type_string = self.format_type_string(type_value, verification_method)
                            item_type = QtGui.QStandardItem(type_string)
                            model.setItem(idx, col_type_idx, item_type)
                        
                        # 주소 컬럼 설정
                        if col_addr_idx != -1:
                            item_addr = QtGui.QStandardItem(addr_str)
                            item_addr.setData("네이버", QtCore.Qt.UserRole + 2) # Source indication
                            if shop_id is not None: item_addr.setData(shop_id, QtCore.Qt.UserRole + 3) # PK
                            item_addr.setData((lat_, lng_), QtCore.Qt.UserRole + 8) # Geo
                            item_addr.setData({"naver": naver_no, "serve": serve_no}, QtCore.Qt.UserRole + 9) # Prop Nos
                            model.setItem(idx, col_addr_idx, item_addr)
                             
                        # 나머지 열도 있으면 채우기
                        if col_ho_idx != -1: model.setItem(idx, col_ho_idx, QtGui.QStandardItem(row.get("ho", "")))
                        if col_floor_idx != -1: 
                            cf = row.get("curr_floor", 0); tf = row.get("total_floor", 0)
                            model.setItem(idx, col_floor_idx, QtGui.QStandardItem(f"{cf}/{tf}"))
                        if col_price_idx != -1:
                            dep = row.get("deposit", 0); mon = row.get("monthly", 0)
                            model.setItem(idx, col_price_idx, QtGui.QStandardItem(f"{dep}/{mon}"))
                        if col_manage_fee_idx != -1: 
                            manage_fee = row.get("manage_fee", "")
                            manage_fee_str = "" if manage_fee is None else str(manage_fee)
                            model.setItem(idx, col_manage_fee_idx, QtGui.QStandardItem(manage_fee_str))
                        if col_premium_idx != -1: 
                            premium = row.get("premium", "")
                            premium_str = "" if premium is None else str(premium)
                            model.setItem(idx, col_premium_idx, QtGui.QStandardItem(premium_str))
                        if col_current_use_idx != -1: model.setItem(idx, col_current_use_idx, QtGui.QStandardItem(row.get("current_use", "")))
                        if col_area_idx != -1: 
                            area = row.get("area", "")
                            area_str = "" if area is None else str(area)
                            model.setItem(idx, col_area_idx, QtGui.QStandardItem(area_str))
                        if col_contact_idx != -1: model.setItem(idx, col_contact_idx, QtGui.QStandardItem(row.get("owner_phone", "")))
                        
                        # 추가적인 필드 처리
                        if col_prop_no_idx != -1: 
                            prop_no = row.get("naver_property_no", "")
                            prop_no_str = "" if prop_no is None else str(prop_no)
                            model.setItem(idx, col_prop_no_idx, QtGui.QStandardItem(prop_no_str))
                        if col_title_idx != -1: 
                            # title 대신 memo를 사용합니다
                            memo = row.get("memo", "")
                            # None 값 처리
                            memo_str = "" if memo is None else memo
                            model.setItem(idx, col_title_idx, QtGui.QStandardItem(memo_str))
                        
                        # 매칭업종 처리 (리스트에서 변환)
                        if col_biz_idx != -1:
                            biz_manager_list = row.get("biz_manager_list", [])
                            biz_list = [bm.get("biz", "") for bm in biz_manager_list if bm.get("biz", "")]
                            model.setItem(idx, col_biz_idx, QtGui.QStandardItem("; ".join(biz_list)))
                        
                        if col_check_memo_idx != -1: model.setItem(idx, col_check_memo_idx, QtGui.QStandardItem(row.get("check_memo", "")))
                        if col_ad_start_idx != -1: model.setItem(idx, col_ad_start_idx, QtGui.QStandardItem(row.get("ad_start_date", "")))
                        
                        # 추가 데이터 필드들
                        if col_parking_idx != -1: 
                            parking = row.get("parking", "")
                            # 주차대수 None 값을 빈 문자열로 변환
                            parking_str = "" if parking is None else str(parking)
                            model.setItem(idx, col_parking_idx, QtGui.QStandardItem(parking_str))
                            
                        if col_usage_idx != -1: model.setItem(idx, col_usage_idx, QtGui.QStandardItem(row.get("building_usage", "")))
                        if col_approval_date_idx != -1: model.setItem(idx, col_approval_date_idx, QtGui.QStandardItem(row.get("approval_date", "")))
                        
                        # 방/화장실 조합
                        if col_rooms_idx != -1:
                            rooms = row.get("rooms", 0)
                            baths = row.get("baths", 0)
                            # None 값 처리
                            rooms = 0 if rooms is None else rooms
                            baths = 0 if baths is None else baths
                            
                            if rooms or baths:
                                room_bath_str = f"{rooms}/{baths}"
                                model.setItem(idx, col_rooms_idx, QtGui.QStandardItem(room_bath_str))
                        
                        if col_photo_path_idx != -1: model.setItem(idx, col_photo_path_idx, QtGui.QStandardItem(row.get("photo_path", "")))
                        if col_owner_name_idx != -1: model.setItem(idx, col_owner_name_idx, QtGui.QStandardItem(row.get("owner_name", "")))
                        if col_relation_idx != -1: model.setItem(idx, col_relation_idx, QtGui.QStandardItem(row.get("owner_relation", "")))
                    except Exception as e:
                        self.logger.error(f"행 {start_idx + i} 데이터 설정 중 오류: {e}", exc_info=True)
                        # 오류가 발생해도 다음 행 계속 처리
                
                # 각 배치 처리 후 UI 이벤트 처리 허용
                QtWidgets.QApplication.processEvents()

            self.logger.info(f"populate_check_manager_table 완료: {len(rows)}개 행 로드됨")
            
            # 완료 메시지
            self.parent_app.statusBar().showMessage(f"데이터 처리 완료: {len(rows)}건", 3000)
            QtWidgets.QApplication.processEvents()
            
            # 정렬 상태 복원 - 테이블 데이터 채운 후 복원
            if hasattr(self, 'saved_sort_state') and self.check_manager_view:
                sort_column, sort_order = self.saved_sort_state
                self.logger.info(f"저장된 정렬 상태 복원: 열={sort_column}, 순서={sort_order}")
                self.check_manager_view.sortByColumn(sort_column, sort_order)
            # 정렬 상태가 없으면 기본 정렬 안함
            
        except Exception as e:
            self.logger.error(f"테이블 데이터 채우기 전체 오류: {e}", exc_info=True)
        finally:
            self.loading_data_flag = False

    def append_rows_to_manager_table(self, new_rows: list):
        """Appends new rows to the manager table view."""
        # Logic moved from main_app_part8/append_rows_to_manager_table
        model = self.manager_source_model
        old_count = model.rowCount()
        add_cnt = len(new_rows)
        model.setRowCount(old_count + add_cnt)
        
        headers = []
        try:
            headers = [model.horizontalHeaderItem(j).text() if model.horizontalHeaderItem(j) else f"col_{j}" 
                       for j in range(model.columnCount())]
        except AttributeError:
            print("[WARN] ManagerCheckTab: Could not get headers during append.")
            headers = []
            
        header_map = {text: idx for idx, text in enumerate(headers)} 
        col_type_idx = header_map.get("타입", -1)
        col_addr_idx = header_map.get("주소", 1)
        # 다른 열 인덱스 가져오기
        col_ho_idx = header_map.get("호", -1)
        col_floor_idx = header_map.get("층", -1)
        col_price_idx = header_map.get("보증금/월세", -1)
        col_manage_fee_idx = header_map.get("관리비", -1)
        col_premium_idx = header_map.get("권리금", -1)
        col_current_use_idx = header_map.get("현업종", -1)
        col_area_idx = header_map.get("평수", -1)
        col_contact_idx = header_map.get("연락처", -1)
        col_prop_no_idx = header_map.get("매물번호", -1)
        col_title_idx = header_map.get("제목", -1)
        col_biz_idx = header_map.get("매칭업종", -1)
        col_check_memo_idx = header_map.get("확인메모", -1)
        col_ad_start_idx = header_map.get("광고등록일", -1)
        col_parking_idx = header_map.get("주차대수", -1)
        col_usage_idx = header_map.get("용도", -1)
        col_approval_date_idx = header_map.get("사용승인일", -1)
        col_rooms_idx = header_map.get("방/화장실", -1)
        col_photo_path_idx = header_map.get("사진경로", -1)
        col_owner_name_idx = header_map.get("소유자명", -1)
        col_relation_idx = header_map.get("관계", -1)

        for i, row in enumerate(new_rows):
            idx = old_count + i
            shop_id = row.get("shop_id", None)
            lat_ = row.get("lat", "")
            lng_ = row.get("lng", "")
            naver_no = row.get("naver_property_no","")
            serve_no = row.get("serve_property_no","")
            addr_str = (row.get("dong","") + " " + row.get("jibun","")).strip()
            
            # 타입 컬럼 먼저 설정
            if col_type_idx != -1:
                type_value = row.get("type", "")
                verification_method = row.get("verification_method", "")
                type_string = self.format_type_string(type_value, verification_method)
                item_type = QtGui.QStandardItem(type_string)
                model.setItem(idx, col_type_idx, item_type)
            
            # 주소 컬럼 설정
            if col_addr_idx != -1:
                item_addr = QtGui.QStandardItem(addr_str)
                item_addr.setData("네이버", QtCore.Qt.UserRole + 2) # Source indication
                if shop_id is not None: item_addr.setData(shop_id, QtCore.Qt.UserRole + 3) # PK
                item_addr.setData((lat_, lng_), QtCore.Qt.UserRole + 8) # Geo
                item_addr.setData({"naver": naver_no, "serve": serve_no}, QtCore.Qt.UserRole + 9) # Prop Nos
                model.setItem(idx, col_addr_idx, item_addr)
            
            if col_ho_idx != -1: model.setItem(idx, col_ho_idx, QtGui.QStandardItem(row.get("ho", "")))
            if col_floor_idx != -1: 
                cf = row.get("curr_floor", 0); tf = row.get("total_floor", 0)
                model.setItem(idx, col_floor_idx, QtGui.QStandardItem(f"{cf}/{tf}"))
            if col_price_idx != -1:
                dep = row.get("deposit", 0); mon = row.get("monthly", 0)
                model.setItem(idx, col_price_idx, QtGui.QStandardItem(f"{dep}/{mon}"))
            if col_manage_fee_idx != -1: 
                manage_fee = row.get("manage_fee", "")
                manage_fee_str = "" if manage_fee is None else str(manage_fee)
                model.setItem(idx, col_manage_fee_idx, QtGui.QStandardItem(manage_fee_str))
            if col_premium_idx != -1: 
                premium = row.get("premium", "")
                premium_str = "" if premium is None else str(premium)
                model.setItem(idx, col_premium_idx, QtGui.QStandardItem(premium_str))
            if col_current_use_idx != -1: model.setItem(idx, col_current_use_idx, QtGui.QStandardItem(row.get("current_use", "")))
            if col_area_idx != -1: 
                area = row.get("area", "")
                area_str = "" if area is None else str(area)
                model.setItem(idx, col_area_idx, QtGui.QStandardItem(area_str))
            if col_contact_idx != -1: model.setItem(idx, col_contact_idx, QtGui.QStandardItem(row.get("owner_phone", "")))
            
            # 추가적인 필드 처리
            if col_prop_no_idx != -1: 
                prop_no = row.get("naver_property_no", "")
                prop_no_str = "" if prop_no is None else str(prop_no)
                model.setItem(idx, col_prop_no_idx, QtGui.QStandardItem(prop_no_str))
            if col_title_idx != -1: 
                # title 대신 memo를 사용합니다
                memo = row.get("memo", "")
                # None 값 처리
                memo_str = "" if memo is None else memo
                model.setItem(idx, col_title_idx, QtGui.QStandardItem(memo_str))
            
            # 매칭업종 처리 (리스트에서 변환)
            if col_biz_idx != -1:
                biz_manager_list = row.get("biz_manager_list", [])
                biz_list = [bm.get("biz", "") for bm in biz_manager_list if bm.get("biz", "")]
                model.setItem(idx, col_biz_idx, QtGui.QStandardItem("; ".join(biz_list)))
            
            if col_check_memo_idx != -1: model.setItem(idx, col_check_memo_idx, QtGui.QStandardItem(row.get("check_memo", "")))
            if col_ad_start_idx != -1: model.setItem(idx, col_ad_start_idx, QtGui.QStandardItem(row.get("ad_start_date", "")))
            
            # 추가 데이터 필드들
            if col_parking_idx != -1: 
                parking = row.get("parking", "")
                # 주차대수 None 값을 빈 문자열로 변환
                parking_str = "" if parking is None else str(parking)
                model.setItem(idx, col_parking_idx, QtGui.QStandardItem(parking_str))
                
            if col_usage_idx != -1: model.setItem(idx, col_usage_idx, QtGui.QStandardItem(row.get("building_usage", "")))
            if col_approval_date_idx != -1: model.setItem(idx, col_approval_date_idx, QtGui.QStandardItem(row.get("approval_date", "")))
            
            # 방/화장실 조합
            if col_rooms_idx != -1:
                rooms = row.get("rooms", 0)
                baths = row.get("baths", 0)
                # None 값 처리
                rooms = 0 if rooms is None else rooms
                baths = 0 if baths is None else baths
                
                if rooms or baths:
                    room_bath_str = f"{rooms}/{baths}"
                    model.setItem(idx, col_rooms_idx, QtGui.QStandardItem(room_bath_str))
            
            if col_photo_path_idx != -1: model.setItem(idx, col_photo_path_idx, QtGui.QStandardItem(row.get("photo_path", "")))
            if col_owner_name_idx != -1: model.setItem(idx, col_owner_name_idx, QtGui.QStandardItem(row.get("owner_name", "")))
            if col_relation_idx != -1: model.setItem(idx, col_relation_idx, QtGui.QStandardItem(row.get("owner_relation", "")))

    def find_row_by_id(self, pk_id):
         """Finds the row index for a given primary key."""
         # Helper moved from main_app_part9
         model = self.manager_source_model
         row_count = model.rowCount()
         # 헤더에서 주소 컬럼 인덱스 찾기
         headers = [model.horizontalHeaderItem(j).text() if model.horizontalHeaderItem(j) else f"col_{j}" 
                   for j in range(model.columnCount())]
         header_map = {text: idx for idx, text in enumerate(headers)}
         col_addr_idx = header_map.get("주소", 1)  # 주소 컬럼 인덱스
         for r in range(row_count):
             item_0 = model.item(r, col_addr_idx)
             if item_0:
                 stored_id = item_0.data(QtCore.Qt.UserRole+3)
                 if stored_id == pk_id:
                     return r
         return None

    def highlight_by_id(self, pk_id):
        """Highlights a row in the table view by its primary key."""
        # Helper moved from main_app_part9
        model = self.manager_source_model
        view = self.check_manager_view
        row_count = model.rowCount()
        # 헤더에서 주소 컬럼 인덱스 찾기
        headers = [model.horizontalHeaderItem(j).text() if model.horizontalHeaderItem(j) else f"col_{j}" 
                  for j in range(model.columnCount())]
        header_map = {text: idx for idx, text in enumerate(headers)}
        col_addr_idx = header_map.get("주소", 1)  # 주소 컬럼 인덱스
        for r in range(row_count):
            item_0 = model.item(r, col_addr_idx)
            if item_0:
                stored_id = item_0.data(QtCore.Qt.UserRole+3)
                if stored_id == pk_id:
                    index_0 = model.index(r, col_addr_idx)
                    view.setCurrentIndex(index_0)
                    view.selectRow(r)
                    view.scrollTo(index_0, QtWidgets.QAbstractItemView.PositionAtCenter)
                    break

    def update_single_row_by_id(self, pk_id, rowd):
        """Updates a single row in the table view based on primary key."""
        # Logic from main_app_part7/update_single_row_by_id
        row_in_model = self.find_row_by_id(pk_id)
        if row_in_model is None:
            print(f"[WARN] ManagerCheckTab update_single_row_by_id: Can't find row for pk_id={pk_id}")
            return

        model = self.manager_source_model
        headers = [model.horizontalHeaderItem(j).text() if model.horizontalHeaderItem(j) else f"col_{j}" 
                   for j in range(model.columnCount())]
        header_map = {text: idx for idx, text in enumerate(headers)} 

        # Update based on keys in rowd, mapping to column indices
        def set_item_text(col_key, value):
             col_idx = header_map.get(col_key)
             if col_idx is not None and col_idx != -1:
                  existing_item = model.item(row_in_model, col_idx)
                  if existing_item:
                       existing_item.setText(str(value)) # Ensure value is string
                  else:
                       model.setItem(row_in_model, col_idx, QtGui.QStandardItem(str(value)))

        if "floor" in rowd: set_item_text("층", rowd["floor"])
        if "ho" in rowd: set_item_text("호", rowd["ho"])
        if "area" in rowd: set_item_text("평수", rowd["area"])
        if "price" in rowd: set_item_text("보증금/월세", rowd["price"])
        if "manage_fee" in rowd: set_item_text("관리비", rowd["manage_fee"])
        if "premium" in rowd: set_item_text("권리금", rowd["premium"])
        if "current_use" in rowd: set_item_text("현업종", rowd["current_use"])
        if "owner_phone" in rowd: set_item_text("연락처", rowd["owner_phone"])
        if "check_memo" in rowd: set_item_text("확인메모", rowd["check_memo"])
        if "parking" in rowd: set_item_text("주차대수", rowd["parking"])
        if "building_usage" in rowd: set_item_text("용도", rowd["building_usage"])
        if "approval_date" in rowd: set_item_text("사용승인일", rowd["approval_date"])
        # Add other fields as necessary
        
    def table_to_data_list(self):
        """Converts table view data to a list of dictionaries for Selenium/Tk."""
        # Helper moved from main_app_part9
        data_list = []
        model = self.manager_source_model
        row_count = model.rowCount()
        headers = [model.horizontalHeaderItem(j).text() if model.horizontalHeaderItem(j) else f"col_{j}" 
                   for j in range(model.columnCount())]
        header_map = {text: idx for idx, text in enumerate(headers)} 
        col_addr_idx = header_map.get("주소", 1)
        col_area_idx = header_map.get("평수", -1)
        col_price_idx = header_map.get("보증금/월세", -1)
        col_biz_idx = header_map.get("매칭업종", -1)
        col_memo_idx = header_map.get("확인메모", -1)
        col_floor_idx = header_map.get("층", -1)
        col_manage_fee_idx = header_map.get("관리비", -1)
        col_premium_idx = header_map.get("권리금", -1)
        col_current_use_idx = header_map.get("현업종", -1)

        for r in range(row_count):
            item_0 = model.item(r, col_addr_idx if col_addr_idx != -1 else 1) # Base on Address col
            if not item_0: continue

            shop_id = item_0.data(QtCore.Qt.UserRole+3) or None
            lat_lng = item_0.data(QtCore.Qt.UserRole+8) or ("","")
            nav_serve = item_0.data(QtCore.Qt.UserRole+9) or {}
            naver_no = nav_serve.get("naver","")
            address_str = item_0.text() or ""
            
            def get_col_data(row_idx, col_idx):
                 if col_idx == -1: return "" # Return empty if column doesn't exist
                 index = model.index(row_idx, col_idx)
                 return model.data(index) if index.isValid() else ""
                 
            row_dict = {
                "id": shop_id,
                "addr": address_str,
                "area": get_col_data(r, col_area_idx),
                "price": get_col_data(r, col_price_idx),
                "lat": lat_lng[0],
                "lng": lat_lng[1],
                "naver_no": naver_no,
                "매칭업종": get_col_data(r, col_biz_idx), 
                "check_memo": get_col_data(r, col_memo_idx),
                "floor": get_col_data(r, col_floor_idx),
                "manage_fee": get_col_data(r, col_manage_fee_idx),
                "premium": get_col_data(r, col_premium_idx),
                "current_use": get_col_data(r, col_current_use_idx),
            }
            data_list.append(row_dict)
        return data_list 