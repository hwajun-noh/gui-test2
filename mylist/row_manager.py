# row_manager.py
import time
import logging
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItem

from mylist_constants import RE_AD_BG_COLOR, NEW_AD_BG_COLOR

class MyListRowManager:
    """
    마이리스트 행 관리를 담당하는 클래스
    - 새 행 추가
    - 행 색상 관리
    - 행 데이터 요약 계산
    """
    
    def __init__(self, container):
        """행 매니저 초기화"""
        self.container = container
        self.logger = logging.getLogger(__name__)
    
    def add_new_shop_row(self, initial_data=None, parse_naver_format=False):
        """상가 모델에 새 행을 추가하고 pending manager에 알립니다."""
        # 디버깅을 위한 상세 정보 로깅
        self.logger.info("====== 행 추가 시작 =====")
        self.logger.info(f"container 존재 여부: {self.container is not None}")
        
        if hasattr(self.container, 'sanga_logic'):
            self.logger.info(f"sanga_logic 존재: {self.container.sanga_logic is not None}")
            self.logger.info(f"sanga_logic 타입: {type(self.container.sanga_logic)}")
            
            # SangaBridge 타입 확인
            if hasattr(self.container.sanga_logic, 'using_legacy'):
                self.logger.info(f"SangaBridge 레거시 모드: {self.container.sanga_logic.using_legacy}")
            
            # 모델 정보 확인
            if hasattr(self.container.sanga_logic, 'mylist_shop_model'):
                model_value = self.container.sanga_logic.mylist_shop_model
                self.logger.info(f"mylist_shop_model 존재: {model_value is not None}")
                self.logger.info(f"mylist_shop_model 타입: {type(model_value) if model_value else 'None'}")
            else:
                self.logger.error("sanga_logic에 mylist_shop_model 속성이 없습니다.")
        else:
            self.logger.error("container에 sanga_logic 속성이 없습니다.")
        
        # 안전하게 모델 참조 가져오기
        model = None
        if hasattr(self.container, 'sanga_logic') and self.container.sanga_logic:
            if hasattr(self.container.sanga_logic, 'mylist_shop_model'):
                model = self.container.sanga_logic.mylist_shop_model
                
        if not model: 
            self.logger.error("상가 행 추가 실패: 모델을 찾을 수 없습니다.")
            return

        old_count = model.rowCount()
        model.insertRow(old_count)
        new_row_idx = old_count
        
        # pending_manager에서 임시 ID 얻기
        temp_id = self.container.pending_manager.generate_temp_id()

        headers = [model.horizontalHeaderItem(j).text() for j in range(model.columnCount())]
        
        # 기본값 설정 (담당자, 방/화장실)
        try: 
            rooms_baths_col = headers.index("방/화장실")
            model.setItem(new_row_idx, rooms_baths_col, QStandardItem("방0/0"))
        except ValueError: 
            pass
            
        try: 
            manager_col = headers.index("담당자")
            model.setItem(new_row_idx, manager_col, QStandardItem(self.container.current_manager))
        except ValueError: 
            pass
        
        db_data_from_initial = {}
        copied_row = False
        
        if initial_data:
            if parse_naver_format:
                 # 네이버 데이터 포맷 파싱
                 db_data_from_initial = initial_data 
            elif isinstance(initial_data, list) and len(initial_data) == len(headers):
                 copied_row = True
                 for c, val_str in enumerate(initial_data):
                     new_item = QStandardItem(val_str)
                     if c == 0: 
                         new_item.setData(temp_id, Qt.UserRole + 3)
                     model.setItem(new_row_idx, c, new_item)
                 try:
                    re_ad_col_idx = headers.index("재광고")
                    is_re_ad = (initial_data[re_ad_col_idx] == "재광고")
                    row_bg = RE_AD_BG_COLOR if is_re_ad else NEW_AD_BG_COLOR
                    for c in range(len(headers)): 
                        model.item(new_row_idx, c).setBackground(row_bg)
                 except (ValueError, IndexError): 
                     pass
            else:
                 db_data_from_initial = initial_data

        if not copied_row:
            # 모델 행 업데이트 메서드 안전하게 호출
            try:
                # _update_model_row 메서드 유무 확인 및 상세 로깅
                if hasattr(self.container.sanga_logic, '_update_model_row'):
                    self.logger.info("_update_model_row 메서드 존재")
                    self.container.sanga_logic._update_model_row(model, new_row_idx, headers, db_data_from_initial)
                    self.logger.debug(f"_update_model_row 호출 성공: {new_row_idx}행")
                else:
                    # update_model_row (언더스코어 없는 버전) 시도
                    if hasattr(self.container.sanga_logic, 'update_model_row'):
                        self.logger.info("언더스코어 없는 update_model_row 시도")
                        self.container.sanga_logic.update_model_row(model, new_row_idx, headers, db_data_from_initial)
                    else:
                        self.logger.error("_update_model_row 또는 update_model_row 메서드가 없습니다.")
                        # 레거시 로직에서 직접 메서드 호출 시도
                        if hasattr(self.container.sanga_logic, 'legacy_logic') and hasattr(self.container.sanga_logic.legacy_logic, '_update_model_row'):
                            self.logger.info("레거시 로직에서 직접 _update_model_row 시도")
                            self.container.sanga_logic.legacy_logic._update_model_row(model, new_row_idx, headers, db_data_from_initial)
                        else:
                            self.logger.error("레거시 로직에서도 _update_model_row 메서드를 찾을 수 없습니다.")
                            return
                    
                item0 = model.item(new_row_idx, 0)
                if item0: 
                    item0.setData(temp_id, Qt.UserRole + 3)
            except Exception as e:
                self.logger.error(f"모델 행 업데이트 중 오류: {e}", exc_info=True)
                return
            
            # 초기 배경색 설정 (네이버 포맷일 경우)
            if parse_naver_format:
                try:
                    for c in range(len(headers)):
                        item = model.item(new_row_idx, c)
                        if item:
                            item.setBackground(NEW_AD_BG_COLOR)  # 새 광고 색상 적용
                    self.logger.info(f"Set initial background color for new row {new_row_idx} from Naver search.")
                except Exception as e_bg:
                    self.logger.error(f"Error setting initial background for row {new_row_idx}: {e_bg}")

        # pending manager에 알림 - 중복 방지 로직 추가
        try:
            existing_temp_ids = [item.get("temp_id") for item in self.container.pending_manager.shop_pending["added"]]
            if temp_id not in existing_temp_ids:
                self.container.pending_manager.add_pending_shop_add(temp_id)
                self.logger.info(f"Added new temp_id {temp_id} to pending_adds")
            else:
                self.logger.warning(f"Skipped adding duplicate temp_id {temp_id} to pending_adds")
        except Exception as e_pending:
            self.logger.error(f"pending_manager 작업 중 오류: {e_pending}", exc_info=True)
            
        self.logger.info("====== 행 추가 완료 =====")
        return True  # 행 추가 성공 시 True 반환
    
    def add_new_oneroom_row(self, initial_data=None):
        """원룸 모델에 새 행을 추가하고 pending manager에 알립니다."""
        # 안전하게 모델 참조 가져오기
        model = None
        if hasattr(self.container, 'oneroom_logic') and self.container.oneroom_logic:
            if hasattr(self.container.oneroom_logic, 'mylist_oneroom_model'):
                model = self.container.oneroom_logic.mylist_oneroom_model
                
        if not model: 
            self.logger.error("원룸 행 추가 실패: 모델을 찾을 수 없습니다.")
            return

        old_count = model.rowCount()
        model.insertRow(old_count)
        new_row_idx = old_count

        temp_id = self.container.pending_manager.generate_temp_id()
        headers = [model.horizontalHeaderItem(j).text() for j in range(model.columnCount())]

        db_data_from_initial = {}
        copied_row = False
        
        if isinstance(initial_data, list) and len(initial_data) == len(headers):
             copied_row = True
             for c, val_str in enumerate(initial_data):
                 new_item = QStandardItem(val_str)
                 if c == 0: 
                     new_item.setData(temp_id, Qt.UserRole + 3)
                 model.setItem(new_row_idx, c, new_item)
        elif isinstance(initial_data, dict):
             db_data_from_initial = initial_data

        if not copied_row:
             # 안전하게 업데이트 메서드 호출
             try:
                 if hasattr(self.container.oneroom_logic, '_update_oneroom_model_row'):
                     self.container.oneroom_logic._update_oneroom_model_row(model, new_row_idx, headers, db_data_from_initial)
                     self.logger.debug(f"_update_oneroom_model_row 호출 성공: {new_row_idx}행")
                 else:
                     self.logger.error("_update_oneroom_model_row 메서드가 없습니다.")
                     return
                     
                 item0 = model.item(new_row_idx, 0)
                 if item0: 
                     item0.setData(temp_id, Qt.UserRole + 3)
             except Exception as e:
                 self.logger.error(f"원룸 모델 행 업데이트 중 오류: {e}", exc_info=True)
                 return

        # pending manager에 알림
        try:
            self.container.pending_manager.add_pending_oneroom_add(temp_id)
            self.logger.info(f"Added new temp_id {temp_id} to pending_oneroom_adds")
        except Exception as e_pending:
            self.logger.error(f"pending_manager 작업 중 오류 (원룸): {e_pending}", exc_info=True)
    
    def recalculate_manager_summary(self):
        """
        담당자 요약 정보(상가 새광고/재광고 수)를 계산하고 레이블을 업데이트합니다.
        메인 스레드에서 호출해야 합니다.
        """
        start_time = time.time()
        self.logger.debug("Entering recalculate_manager_summary (Shop New/Re-Ad logic).")
        
        # 모델 및 레이블 참조 안전하게 가져오기
        model = None
        label = None

        # 상가 로직 존재 여부 확인
        if hasattr(self.container, 'sanga_logic') and self.container.sanga_logic:
            # 모델 참조 안전하게 가져오기
            if hasattr(self.container.sanga_logic, 'mylist_shop_model'):
                model = self.container.sanga_logic.mylist_shop_model
            # 레이블 참조 안전하게 가져오기
            if hasattr(self.container.sanga_logic, 'manager_summary_label'):
                label = self.container.sanga_logic.manager_summary_label
        
        if not model or not label:
            self.logger.warning("Cannot recalculate summary: model or label missing.")
            if label: 
                label.setText("요약: 모델 또는 레이블 없음")
            return
            
        summary_dict = {}
        row_count = model.rowCount()
        manager_col_index = -1
        re_ad_col_index = -1
        
        try:
            headers = [model.horizontalHeaderItem(j).text() for j in range(model.columnCount())]
            manager_col_index = headers.index("담당자")
            re_ad_col_index = headers.index("재광고")
        except (ValueError, AttributeError):
            self.logger.error("Cannot find required columns ('담당자', '재광고') for summary.", exc_info=True)
            label.setText("담당자별 광고 현황: 열 오류")
            return
            
        for r in range(row_count):
            mgr_item = model.item(r, manager_col_index)
            manager_name = mgr_item.text().strip() if mgr_item else "미지정"
            if not manager_name: 
                manager_name = "미지정"
                
            re_item = model.item(r, re_ad_col_index)
            re_text = re_item.text().strip() if re_item else "새광고"
            re_flag = "Y" if re_text == "재광고" else "N"
            
            if manager_name not in summary_dict: 
                summary_dict[manager_name] = {"Y": 0, "N": 0}
            summary_dict[manager_name][re_flag] += 1
            
        summary_text = "담당자별 광고 현황: "
        summary_parts = []
        total_new = 0
        total_re = 0
        
        for manager_name, counts in sorted(summary_dict.items()):
            summary_parts.append(f"{manager_name}(새:{counts['N']},재:{counts['Y']})")
            total_new += counts['N']
            total_re += counts['Y']
            
        summary_text += " | ".join(summary_parts)
        summary_text += f" | [총합] 새:{total_new}, 재:{total_re}"
        
        self.logger.debug(f"Calculated summary: {summary_text}")
        
        try:
            label.setText(summary_text)
            self.logger.debug("Summary label updated via self.sanga_logic.manager_summary_label.")
        except Exception as e_summary:
            self.logger.error(f"Error updating summary label: {e_summary}", exc_info=True)
            
        if hasattr(self.container, 'parent_app') and hasattr(self.container.parent_app, 'update_manager_summary_tab'):
            self.container.parent_app.update_manager_summary_tab(summary_dict)
            self.logger.debug("Called parent_app.update_manager_summary_tab.")
            
        end_time = time.time()
        self.logger.info(f"recalculate_manager_summary finished in {end_time - start_time:.4f} seconds.")