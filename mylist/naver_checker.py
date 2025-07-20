# naver_checker.py
import logging
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox

class MyListNaverChecker:
    """
    마이리스트 네이버 부동산 검수 기능을 담당하는 클래스
    - 검수 기능 실행
    - 검수 UI 연동
    - 결과 처리
    """
    
    def __init__(self, container):
        """네이버 검수 객체 초기화"""
        self.container = container
        self.logger = logging.getLogger(__name__)
    
    def get_all_sanga_rows(self):
        """
        상가(새광고) 탭의 모든 데이터를 가져옵니다.
        네이버부동산 검수 기능에서 사용됩니다.
        """
        self.logger.info("get_all_sanga_rows: 상가 전체 데이터 조회")
        
        all_rows = []
        try:
            model = self.container.sanga_logic.mylist_shop_model
            if not model:
                self.logger.warning("상가 모델이 초기화되지 않았습니다.")
                return all_rows
                
            headers = [model.horizontalHeaderItem(j).text() for j in range(model.columnCount())]
            
            for row in range(model.rowCount()):
                row_data = {}
                # 기본 필드 정보
                row_data['id'] = row
                
                # 각 열 데이터 추출
                for col in range(model.columnCount()):
                    item = model.item(row, col)
                    if item:
                        # 원본 헤더 이름 그대로 저장 (한글 헤더명)
                        header = headers[col]
                        row_data[header] = item.text()
                        
                        # 영문 키도 동시에 저장 (호환성 유지)
                        key = header.lower().replace(' ', '_')
                        row_data[key] = item.text()
                        
                        # ID 정보 저장 (실제 DB ID 또는 임시 ID)
                        if col == 0:
                            real_id = item.data(Qt.UserRole + 3)
                            if real_id:
                                row_data['id'] = real_id
                
                # 좌표 데이터 추출 (UserRole에 저장된 값)
                lat_item = model.item(row, 0)
                if lat_item:
                    row_data['lat'] = lat_item.data(Qt.UserRole) or ""
                    row_data['lng'] = lat_item.data(Qt.UserRole + 1) or ""
                
                # 디버그 정보 로깅 (첫 행일 경우)
                if row == 0:
                    self.logger.debug(f"첫 번째 행 데이터 키 목록: {list(row_data.keys())}")
                    sample_values = {k: v for k, v in row_data.items() if k in ["주소", "addr", "lat", "lng", "매물번호", "naver_no"]}
                    self.logger.debug(f"첫 번째 행 샘플 값: {sample_values}")
                
                all_rows.append(row_data)
                
            self.logger.info(f"총 {len(all_rows)}개 행 데이터 조회 완료")
        except Exception as e:
            self.logger.error(f"상가 데이터 조회 중 오류: {e}", exc_info=True)
        
        return all_rows
    
    def launch_naver_check_for_mylist(self):
        """
        마이리스트 탭에서 네이버부동산 검수 기능을 실행합니다.
        선택된 행에서 시작하여 전체 데이터를 보여줍니다.
        """
        self.logger.info("네이버부동산 검수 실행 (마이리스트)")
        
        try:
            # 1. 현재 선택된 행 가져오기
            selected_row_index = -1
            if hasattr(self.container.sanga_logic, 'mylist_shop_view'):
                selected_row_index = self.container.sanga_logic.mylist_shop_view.currentIndex().row()
            
            if selected_row_index < 0:
                QMessageBox.warning(self.container.parent_app, "알림", "선택된 행이 없습니다")
                self.logger.warning("선택된 행이 없습니다.")
                return
            
            # 2. 전체 데이터 가져오기
            all_rows = self.get_all_sanga_rows()
            if not all_rows:
                QMessageBox.warning(self.container.parent_app, "알림", "표시할 데이터가 없습니다")
                self.logger.warning("표시할 데이터가 없습니다.")
                return
            
            # 3. 검수 창 실행
            self.logger.info(f"네이버부동산 검수 시작: 총 {len(all_rows)}개 행, 시작 행: {selected_row_index+1}")
            
            # my_selenium_tk_for_mylist.py의 함수 임포트 및 호출
            try:
                from my_selenium_tk_for_mylist import launch_selenium_tk_for_mylist
                
                # 4. 네이버부동산 검수 창 실행 - 전체 데이터와 시작 인덱스 전달
                updated_data = launch_selenium_tk_for_mylist(
                    data_list=all_rows,  # 중요: 전체 데이터 전달
                    parent_app=self.container.parent_app,
                    row_callback=self.on_naver_check_row_changed,
                    start_index=selected_row_index
                )
                
                self.logger.info("네이버부동산 검수 완료")
                
            except ImportError as e:
                self.logger.error(f"my_selenium_tk_for_mylist 모듈 임포트 실패: {e}", exc_info=True)
                QMessageBox.critical(self.container.parent_app, "오류", f"검수 모듈을 불러올 수 없습니다: {e}")
            except Exception as e:
                self.logger.error(f"네이버부동산 검수 실행 중 오류: {e}", exc_info=True)
                QMessageBox.critical(self.container.parent_app, "오류", f"검수 실행 중 오류가 발생했습니다: {e}")
        
        except Exception as e:
            self.logger.error(f"launch_naver_check_for_mylist 실행 중 오류: {e}", exc_info=True)
            QMessageBox.critical(self.container.parent_app, "오류", f"검수 준비 중 오류가 발생했습니다: {e}")

    def on_naver_check_row_changed(self, pk_id, row_idx):
        """
        네이버부동산 검수 창에서 행이 변경되었을 때 호출되는 콜백
        """
        try:
            # 테이블에서 해당 행 선택
            if hasattr(self.container.sanga_logic, 'mylist_shop_view'):
                self.container.sanga_logic.mylist_shop_view.selectRow(row_idx)
                self.logger.debug(f"행 {row_idx+1}번 선택됨")
        except Exception as e:
            self.logger.error(f"행 선택 중 오류: {e}", exc_info=True)
    
    def _parse_naver_data_to_db_shop(self, naver_row_dict):
        """네이버 검색 결과 딕셔너리를 DB 필드 형식으로 변환합니다."""
        # 예시 - NaverShopSearchDialog 실제 출력에 따라 필드 이름 조정 필요
        return {
            "dong": naver_row_dict.get("dong", ""), 
            "jibun": naver_row_dict.get("jibun", ""),
            "ho": naver_row_dict.get("ho", ""), 
            "curr_floor": naver_row_dict.get("curr_floor", 0),
            "total_floor": naver_row_dict.get("total_floor", 0), 
            "deposit": naver_row_dict.get("deposit", 0),
            "monthly": naver_row_dict.get("monthly", 0), 
            "manage_fee": naver_row_dict.get("manage_fee", ""),
            "premium": naver_row_dict.get("premium", ""), 
            "current_use": naver_row_dict.get("current_use", ""),
            "area": naver_row_dict.get("area", 0.0), 
            "owner_phone": naver_row_dict.get("owner_phone", ""),
            "naver_property_no": naver_row_dict.get("naver_property_no", ""),
            "serve_property_no": naver_row_dict.get("serve_property_no", ""), 
            "manager": naver_row_dict.get("manager", self.container.current_manager),
            "memo": naver_row_dict.get("memo", ""), 
            "parking": naver_row_dict.get("parking", ""),
            "building_usage": naver_row_dict.get("building_usage", ""),
            "approval_date": naver_row_dict.get("approval_date", ""),
            "rooms": naver_row_dict.get("rooms", ""), 
            "baths": naver_row_dict.get("baths", ""),
            "ad_end_date": naver_row_dict.get("ad_end_date", ""), 
            "photo_path": naver_row_dict.get("photo_path", ""),
            "owner_name": naver_row_dict.get("owner_name", ""), 
            "owner_relation": naver_row_dict.get("owner_relation", ""),
            "re_ad_yn": "N", 
            "status_cd": ""
        }