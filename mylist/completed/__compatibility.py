"""
마이리스트 계약완료 호환성 레이어

기존 MyListCompletedLogic 클래스와 새 모듈식 구조 사이의 호환성 레이어 제공
"""
import logging
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout

# 기존 코드 임포트
from mylist_completed_logic import MyListCompletedLogic

# 새 모듈 임포트
from mylist.completed.data.models import CompletedDealModel
from mylist.completed.data.loaders import CompletedDealLoader
from mylist.completed.events.event_handler import CompletedDealEventHandler
from mylist.completed.ui.components import CompletedDealUI
from mylist.completed.actions.commands import CompletedDealCommands

class CompletedDealBridge:
    """
    기존 MyListCompletedLogic과 새 모듈식 구조 사이의 브릿지
    
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
        self.legacy_logic = MyListCompletedLogic(parent_app, container)
        
        # 새 모듈 컴포넌트 (모듈식)
        self.model = CompletedDealModel()
        self.loader = CompletedDealLoader(self.server_host, self.server_port)
        self.commands = CompletedDealCommands(self.model)
        self.event_handler = CompletedDealEventHandler(self.model, None, self.commands)
        self.ui = CompletedDealUI(self.model, self.event_handler, self.commands)
        
        # 내부 상태
        self.using_legacy = True  # 처음에는 기존 코드 사용
        
        # 호환성을 위한 속성 추가
        self.mylist_completed_model = self.legacy_logic.mylist_completed_model if self.using_legacy else self.model.model
        
        # 시그널 연결
        self._connect_signals()
        
        # 타이머
        self.reload_timer = None
        
    def _connect_signals(self):
        """시그널 연결"""
        # 로더 시그널
        self.loader.dataLoaded.connect(self._on_data_loaded)
        self.loader.loadError.connect(self._on_load_error)
        
        # UI 시그널
        self.ui.buttonClicked.connect(self._on_button_clicked)
        self.ui.dateRangeChanged.connect(self._on_date_range_changed)
        
    def init_ui(self):
        """
        UI 초기화 (기존 MyListCompletedLogic.init_ui와 호환)
        
        Returns:
            QWidget: 계약완료 탭 위젯
        """
        if self.using_legacy:
            return self.legacy_logic.init_ui()
        else:
            # 새 UI 생성 및 설정
            return self.ui.create_ui()
            
    def load_data(self):
        """
        데이터 로드 (기존 MyListCompletedLogic.load_data와 호환)
        """
        if self.using_legacy:
            return self.legacy_logic.load_data()
        else:
            # 현재 관리자와 역할 정보 가져오기
            manager = getattr(self.container, 'current_manager', 'admin')
            role = getattr(self.container, 'current_role', 'admin')
            
            # 로더를 통해 데이터 로드
            self.loader.load_data(manager, role)
            
    def start_timer(self):
        """자동 새로고침 타이머 시작"""
        if self.using_legacy:
            return self.legacy_logic.start_timer()
        else:
            # 타이머가 이미 있으면 중지
            if self.reload_timer and self.reload_timer.isActive():
                self.reload_timer.stop()
                
            # 타이머 생성 및 시작
            self.reload_timer = QTimer()
            self.reload_timer.timeout.connect(self.load_data)
            self.reload_timer.start(60 * 60 * 1000)  # 1시간마다 새로고침
            self.logger.info("계약완료 자동 새로고침 타이머 시작됨 (1시간 간격)")
            
    def stop_timer(self):
        """자동 새로고침 타이머 중지"""
        if self.using_legacy:
            return self.legacy_logic.stop_timer()
        else:
            if self.reload_timer and self.reload_timer.isActive():
                self.reload_timer.stop()
                self.logger.info("계약완료 자동 새로고침 타이머 중지됨")
            
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
        self.mylist_completed_model = self.model.model
        
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
        if button_name == "refresh":
            # 데이터 다시 로드
            self.load_data()
            
    def _on_date_range_changed(self, start_date, end_date):
        """
        날짜 범위 변경 이벤트 처리
        
        Args:
            start_date (str): 시작일
            end_date (str): 종료일
        """
        self.logger.info(f"날짜 범위 변경: {start_date} ~ {end_date}")
        # 데이터 다시 로드
        self.load_data()
            
    def filter_table_by_address(self, address_str):
        """
        주소로 테이블 필터링 (기존 MyListCompletedLogic 호환)
        
        Args:
            address_str (str): 필터링할 주소
        """
        if self.using_legacy:
            return self.legacy_logic.filter_table_by_address(address_str)
        else:
            self.event_handler.filter_by_address(address_str)
            
    def toggle_mode(self):
        """
        레거시 모드와 모듈식 모드 전환 (테스트용)
        
        Returns:
            bool: 현재 모드 (True=레거시, False=모듈식)
        """
        self.using_legacy = not self.using_legacy
        # 모드 전환 시 호환성 속성 업데이트
        self.mylist_completed_model = self.legacy_logic.mylist_completed_model if self.using_legacy else self.model.model
        self.logger.info(f"모드 전환: {'레거시' if self.using_legacy else '모듈식'}")
        return self.using_legacy 