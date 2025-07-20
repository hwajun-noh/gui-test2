"""
마이리스트 원룸 호환성 레이어

기존 MyListOneroomLogic 클래스와 새 모듈식 구조 사이의 호환성 레이어 제공
"""
import logging
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout

# 기존 코드 임포트
from mylist_oneroom_logic import MyListOneroomLogic

# 새 모듈 임포트
from mylist.oneroom.data.models import OneRoomModel
from mylist.oneroom.data.loaders import OneRoomLoader
from mylist.oneroom.events.event_handler import OneRoomEventHandler
from mylist.oneroom.ui.components import OneRoomUI
from mylist.oneroom.actions.commands import OneRoomCommands

class OneRoomBridge:
    """
    기존 MyListOneroomLogic과 새 모듈식 구조 사이의 브릿지
    
    이 클래스는 이행 기간 동안 사용되며, 모듈화가 완료되면 제거될 수 있습니다.
    """
    
    def __init__(self, parent_app=None, container=None):
        """
        초기화
        
        Args:
            parent_app: 부모 애플리케이션
            container: 컨테이너 객체
        """
        self.logger = logging.getLogger(__name__)
        self.parent_app = parent_app
        self.container = container
        
        # 서버 정보
        self.server_host = getattr(container, 'server_host', 'localhost')
        self.server_port = getattr(container, 'server_port', 8000)
        
        # 기존 로직 클래스 (레거시)
        self.legacy_logic = MyListOneroomLogic(parent_app, container)
        
        # 새 모듈 컴포넌트 (모듈식)
        self.model = OneRoomModel()
        self.loader = OneRoomLoader(self.server_host, self.server_port)
        self.commands = OneRoomCommands(self.model, getattr(container, 'pending_manager', None))
        self.event_handler = OneRoomEventHandler(self.model, None, self.commands)
        self.ui = OneRoomUI(self.model, self.event_handler, self.commands)
        
        # 내부 상태
        self.using_legacy = True  # 처음에는 기존 코드 사용
        
        # 호환성을 위한 속성 추가
        self.mylist_oneroom_model = self.legacy_logic.mylist_oneroom_model if self.using_legacy else self.model.model
        self.mylist_oneroom_view = None  # UI 초기화 후 설정됨
        
        # 시그널 연결
        self._connect_signals()
        
    def _connect_signals(self):
        """시그널 연결"""
        # 로더 시그널
        self.loader.dataLoaded.connect(self._on_data_loaded)
        self.loader.loadError.connect(self._on_load_error)
        
        # UI 시그널
        self.ui.buttonClicked.connect(self._on_button_clicked)
        
    def init_ui(self):
        """
        UI 초기화 (기존 MyListOneroomLogic.init_ui와 호환)
        
        Returns:
            QWidget: 원룸 탭 위젯
        """
        if self.using_legacy:
            widget = self.legacy_logic.init_ui()
            self.mylist_oneroom_view = self.legacy_logic.mylist_oneroom_view
            return widget
        else:
            # 새 UI 생성 및 설정
            widget = self.ui.create_ui()
            
            # table_view 속성을 mylist_oneroom_view에 연결
            self.mylist_oneroom_view = self.ui.table_view
            
            # 이벤트 핸들러에 view 설정 (중요: 컨텍스트 메뉴와 이벤트 처리를 위해)
            self.event_handler.view = self.ui.table_view
            
            return widget
            
    def load_data(self):
        """
        데이터 로드 (기존 MyListOneroomLogic.load_data와 호환)
        """
        if self.using_legacy:
            return self.legacy_logic.load_data()
        else:
            # 현재 관리자와 역할 정보 가져오기
            manager = getattr(self.container, 'current_manager', 'admin')
            role = getattr(self.container, 'current_role', 'admin')
            
            # 로더를 통해 데이터 로드
            self.loader.load_data(manager, role)
    
    def _update_oneroom_model_row(self, model, row_idx, headers, db_row_data):
        """
        원룸 모델 행 업데이트 (기존 MyListOneroomLogic._update_oneroom_model_row와 호환)
        
        Args:
            model: 업데이트할 모델
            row_idx: 행 인덱스
            headers: 헤더 목록
            db_row_data: 행 데이터
        """
        if self.using_legacy:
            return self.legacy_logic._update_oneroom_model_row(model, row_idx, headers, db_row_data)
        else:
            # 새 모듈에서는 commands를 통해 처리
            try:
                # 모듈식 구현에서는 직접 모델 업데이트 대신 commands 사용
                self.commands.update_model_row(model, row_idx, headers, db_row_data)
                self.logger.debug(f"모듈식 구현으로 행 {row_idx} 업데이트 완료")
            except Exception as e:
                self.logger.error(f"모듈식 구현에서 행 {row_idx} 업데이트 중 오류: {str(e)}", exc_info=True)
                # 오류 발생 시 기존 방식으로 폴백
                return self.legacy_logic._update_oneroom_model_row(model, row_idx, headers, db_row_data)
            
    def _build_mylist_oneroom_rows_for_changes(self, added_list, updated_list):
        """
        추가 및 업데이트할 원룸 행 데이터 생성 (기존 MyListOneroomLogic._build_mylist_oneroom_rows_for_changes와 호환)
        
        Args:
            added_list: 추가할 행 리스트
            updated_list: 업데이트할 행 리스트
            
        Returns:
            dict: 추가 및 업데이트할 행 데이터
        """
        if self.using_legacy:
            return self.legacy_logic._build_mylist_oneroom_rows_for_changes(added_list, updated_list)
        else:
            # 모듈식 구현에서는 독자적인 방식으로 처리
            try:
                self.logger.debug(f"모듈식 구현에서 원룸 행 데이터 생성: 추가={len(added_list)}, 업데이트={len(updated_list)}")
                
                model = self.mylist_oneroom_model
                if not model:
                    self.logger.error("모델이 설정되지 않았습니다.")
                    return {"added": [], "updated": []}
                
                rowCount = model.rowCount()
                id_to_row = {}
                
                # ID와 해당 행 인덱스 매핑
                for r in range(rowCount):
                    item0 = model.item(r, 0)
                    if item0 and item0.data(Qt.UserRole+3) is not None:
                        id_to_row[item0.data(Qt.UserRole+3)] = r
                
                # 추가할 행 처리
                added_rows_parsed = []
                for add_obj in added_list:
                    temp_id = add_obj.get("temp_id")
                    row_idx = id_to_row.get(temp_id)
                    if row_idx is not None:
                        # 모듈식 구현에서 행 파싱 (데이터 모델 처리)
                        if hasattr(self.model, 'get_row_data'):
                            row_dict = self.model.get_row_data(row_idx)
                            if row_dict:
                                row_dict["temp_id"] = temp_id
                                added_rows_parsed.append(row_dict)
                        else:
                            # 폴백: 레거시 방식으로 파싱
                            self.logger.warning(f"모듈식 구현에서 get_row_data 메소드가 없어 레거시 방식 사용")
                            row_dict = self.legacy_logic._parse_mylist_oneroom_row(row_idx)
                            row_dict["temp_id"] = temp_id
                            added_rows_parsed.append(row_dict)
                
                # 업데이트할 행 처리
                updated_rows_parsed = []
                updated_ids = set(upd_obj.get("id") for upd_obj in updated_list 
                               if isinstance(upd_obj.get("id"), int) and upd_obj.get("id") > 0)
                
                for real_id in updated_ids:
                    row_idx = id_to_row.get(real_id)
                    if row_idx is not None:
                        # 모듈식 구현에서 행 파싱
                        if hasattr(self.model, 'get_row_data'):
                            row_dict = self.model.get_row_data(row_idx)
                            if row_dict:
                                row_dict["id"] = real_id
                                updated_rows_parsed.append(row_dict)
                        else:
                            # 폴백: 레거시 방식으로 파싱
                            self.logger.warning(f"모듈식 구현에서 get_row_data 메소드가 없어 레거시 방식 사용")
                            row_dict = self.legacy_logic._parse_mylist_oneroom_row(row_idx)
                            row_dict["id"] = real_id
                            updated_rows_parsed.append(row_dict)
                
                return {"added": added_rows_parsed, "updated": updated_rows_parsed}
                
            except Exception as e:
                self.logger.error(f"모듈식 구현에서 원룸 행 데이터 생성 중 오류: {str(e)}", exc_info=True)
                # 오류 발생 시 레거시 방식으로 폴백
                self.logger.warning("레거시 방식으로 폴백하여 원룸 행 데이터 생성")
                return self.legacy_logic._build_mylist_oneroom_rows_for_changes(added_list, updated_list)
            
    def _on_data_loaded(self, rows):
        """
        데이터 로드 완료 처리
        
        Args:
            rows (list): 로드된 데이터 행
        """
        # 모델 데이터 설정
        self.model.append_rows(rows)
        self.ui.set_status(f"데이터 로드 완료: {len(rows)}개 행")
        # 모드 전환 시 호환성 속성 업데이트
        self.mylist_oneroom_model = self.model.model
        
    def _on_load_error(self, error_msg):
        """
        데이터 로드 오류 처리
        
        Args:
            error_msg (str): 오류 메시지
        """
        self.logger.error(f"데이터 로드 오류: {error_msg}")
        self.ui.set_status(f"데이터 로드 오류: {error_msg}")
    
    def _on_button_clicked(self, button_name):
        """
        버튼 클릭 이벤트 처리
        
        Args:
            button_name (str): 버튼 이름
        """
        if button_name == "add":
            # 행 추가 처리
            self.on_add_mylist_oneroom_row()
            self.logger.debug("add 버튼으로 행 추가 요청")
        elif button_name == "save":
            # 저장 처리를 container.save_handler로 위임
            if hasattr(self.container, 'save_handler'):
                self.container.save_handler.save_mylist_oneroom_changes()
                self.logger.debug("save 버튼으로 저장 요청")
            else:
                self.ui.set_status("저장 핸들러가 설정되지 않았습니다.")
        elif button_name == "refresh":
            # 데이터 다시 로드
            self.load_data()
            self.logger.debug("refresh 버튼으로 새로고침 요청")
            
    def filter_table_by_address(self, address_str):
        """
        주소로 테이블 필터링 (기존 MyListOneroomLogic 호환)
        
        Args:
            address_str (str): 필터링할 주소
        """
        if self.using_legacy:
            return self.legacy_logic.filter_table_by_address(address_str)
        else:
            self.event_handler.filter_by_address(address_str)
            
    # 추가 호환성 메서드들...
    # 필요에 따라 기존 MyListOneroomLogic의 다른 메서드들도 추가할 수 있습니다.
    
    def toggle_mode(self):
        """
        레거시 모드와 모듈식 모드 전환 (테스트용)
        
        Returns:
            bool: 현재 모드 (True=레거시, False=모듈식)
        """
        self.using_legacy = not self.using_legacy
        
        # 모드 전환 시 호환성 속성 업데이트
        self.mylist_oneroom_model = self.legacy_logic.mylist_oneroom_model if self.using_legacy else self.model.model
        self.mylist_oneroom_view = self.legacy_logic.mylist_oneroom_view if self.using_legacy else self.ui.table_view
        
        # 이벤트 핸들러 view 업데이트 (모듈식 모드인 경우만)
        if not self.using_legacy:
            self.event_handler.view = self.ui.table_view
            
        self.logger.info(f"모드 전환: {'레거시' if self.using_legacy else '모듈식'}")
        return self.using_legacy
    
    def on_add_mylist_oneroom_row(self):
        """
        원룸 탭에 새 행 추가 (기존 MyListOneroomLogic.on_add_mylist_oneroom_row와 호환)
        """
        if self.using_legacy:
            return self.legacy_logic.on_add_mylist_oneroom_row()
        else:
            try:
                # 모듈식 구현에서는 commands를 통해 처리
                self.commands.add_row()
                self.logger.debug("모듈식 구현으로 원룸 행 추가 완료")
            except Exception as e:
                self.logger.error(f"모듈식 구현에서 원룸 행 추가 중 오류: {str(e)}", exc_info=True)
                # 오류 발생 시 기존 방식으로 폴백
                return self.legacy_logic.on_add_mylist_oneroom_row()
    
    def copy_mylist_oneroom_row(self, source_row_idx):
        """
        원룸 행 복사 (기존 MyListOneroomLogic.copy_mylist_oneroom_row와 호환)
        
        Args:
            source_row_idx: 복사할 행 인덱스
        """
        if self.using_legacy:
            return self.legacy_logic.copy_mylist_oneroom_row(source_row_idx)
        else:
            try:
                # 모듈식 구현에서는 소스 행의 데이터를 가져와서 새 행 추가
                model = self.mylist_oneroom_model
                if not model or source_row_idx < 0 or source_row_idx >= model.rowCount():
                    self.logger.warning(f"유효하지 않은 소스 행 인덱스: {source_row_idx}")
                    return
                
                # 소스 행 데이터 수집
                row_data = {}
                if hasattr(self.model, 'get_row_data'):
                    row_data = self.model.get_row_data(source_row_idx)
                else:
                    # 헤더 정보 수집
                    headers = []
                    for c in range(model.columnCount()):
                        header_item = model.horizontalHeaderItem(c)
                        if header_item:
                            headers.append(header_item.text())
                    
                    # 행 데이터 수집
                    for c in range(min(len(headers), model.columnCount())):
                        item = model.item(source_row_idx, c)
                        if item:
                            row_data[headers[c]] = item.text()
                
                # 새 행 추가 (초기 데이터와 함께)
                self.commands.add_row(initial_data=row_data)
                self.logger.debug(f"모듈식 구현으로 행 {source_row_idx} 복사 완료")
            except Exception as e:
                self.logger.error(f"모듈식 구현에서 원룸 행 복사 중 오류: {str(e)}", exc_info=True)
                # 오류 발생 시 기존 방식으로 폴백
                return self.legacy_logic.copy_mylist_oneroom_row(source_row_idx)
                
    def update_mylist_oneroom_row_id(self, old_tid, new_id):
        """
        임시 ID를 실제 DB ID로 업데이트 (기존 MyListOneroomLogic._update_mylist_oneroom_row_id와 호환)
        
        Args:
            old_tid: 기존 임시 ID
            new_id: 새 실제 ID
            
        Returns:
            bool: 성공 여부
        """
        if self.using_legacy:
            return self.legacy_logic._update_mylist_oneroom_row_id(old_tid, new_id)
        else:
            try:
                # 모듈식 구현에서는 모델에서 직접 ID 업데이트
                model = self.mylist_oneroom_model
                if not model:
                    self.logger.error("모델이 설정되지 않았습니다.")
                    return False
                
                # 임시 ID로 행 찾기
                for r in range(model.rowCount()):
                    item0 = model.item(r, 0)
                    if not item0:
                        continue
                    
                    row_id = item0.data(Qt.UserRole + 3)
                    if row_id == old_tid:
                        # ID 업데이트
                        item0.setData(new_id, Qt.UserRole + 3)
                        self.logger.debug(f"모듈식 구현으로 ID 업데이트 완료: {old_tid} → {new_id}")
                        return True
                
                self.logger.warning(f"임시 ID {old_tid}를 가진 행을 찾을 수 없습니다.")
                return False
            except Exception as e:
                self.logger.error(f"모듈식 구현에서 ID 업데이트 중 오류: {str(e)}", exc_info=True)
                # 오류 발생 시 기존 방식으로 폴백
                return self.legacy_logic._update_mylist_oneroom_row_id(old_tid, new_id)
    
    def delete_selected_mylist_oneroom_rows(self):
        """선택된 원룸 행 삭제 (기존 MyListOneroomLogic.delete_selected_mylist_oneroom_rows와 호환)"""
        if self.using_legacy:
            return self.legacy_logic.delete_selected_mylist_oneroom_rows()
        else:
            try:
                # 현재 선택된 행 인덱스 가져오기
                view = self.mylist_oneroom_view
                if not view:
                    self.logger.error("뷰가 설정되지 않았습니다.")
                    return
                
                sel_model = view.selectionModel()
                if not sel_model:
                    self.logger.error("선택 모델이 설정되지 않았습니다.")
                    return
                
                selected_indexes = sel_model.selectedIndexes()
                if not selected_indexes:
                    return
                
                involved_rows = set(idx.row() for idx in selected_indexes)
                if not involved_rows:
                    return
                
                # 삭제 확인 대화상자
                from PyQt5.QtWidgets import QMessageBox
                reply = QMessageBox.question(view, "삭제 확인", 
                    f"선택한 셀이 포함된 {len(involved_rows)}개 행 전체를 삭제 상태로 표시하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    return
                
                # 삭제 처리
                rows_to_mark = sorted(list(involved_rows))
                marked_count = 0
                
                for row_idx in rows_to_mark:
                    # 모듈식 구현에서는 commands.delete_rows를 사용
                    self.commands.delete_rows([row_idx])
                    marked_count += 1
                
                self.logger.info(f"모듈식 구현으로 {marked_count}개 원룸 행 삭제 표시 완료")
                
            except Exception as e:
                self.logger.error(f"모듈식 구현에서 원룸 행 삭제 중 오류: {str(e)}", exc_info=True)
                # 오류 발생 시 기존 방식으로 폴백
                return self.legacy_logic.delete_selected_mylist_oneroom_rows() 