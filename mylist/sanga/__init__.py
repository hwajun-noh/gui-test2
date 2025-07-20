"""
MyList Sanga (상가) 모듈

이 패키지는 마이리스트 상가(새광고) 탭에 관련된 모든 컴포넌트를 포함합니다.
"""

from .ui.components import *
from .data.models import *
from .data.loaders import *
from .events.item_events import *
from .events.view_events import *
from .events.selection_events import *
from .events.context_menu_events import *
from .events.bulk_operations import *
from .events.ui_helpers import *
from .actions.commands import * 

# 레거시 호환성 함수를 명시적으로 임포트
from .events.item_events import on_mylist_shop_item_changed

class MyListSangaLogic:
    """
    마이리스트 상가 로직 클래스
    
    이 클래스는 마이리스트 상가 탭의 전체적인 로직을 관리합니다.
    각 기능별 모듈에서 제공하는 함수들을 사용하여 UI 및 데이터 처리를 합니다.
    """
    
    def __init__(self, parent_app, container):
        """
        초기화
        
        Args:
            parent_app: 부모 애플리케이션 인스턴스
            container: MyListContainer 인스턴스
        """
        self.parent_app = parent_app
        self.container = container
        self.logger = logging.getLogger(__name__)
        
        # UI 요소
        self.mylist_shop_model = None
        self.mylist_shop_view = None
        self.manager_summary_label = None
        self.autosave_status_label = None
        self.naver_search_button = None
        self.add_button = None
        self.save_button = None
        self.export_button = None
        self.inspect_button = None
        self.tab_widget = None
        
        # 상태 플래그
        self.mylist_shop_loading = False
        
        # 로깅 정보
        self.logger.info("MyListSangaLogic 인스턴스 생성됨")
        
    def init_ui(self):
        """
        상가 탭 UI를 초기화합니다.
        
        Returns:
            QWidget: 초기화된 탭 위젯
        """
        # ui.components 모듈의 init_sanga_ui 함수 호출
        return init_sanga_ui(self)
    
    def load_data(self, manager=None, filters=None):
        """
        상가 데이터를 로드합니다.
        
        Args:
            manager: 담당자 필터 (없으면 전체)
            filters: 추가 필터 조건
        """
        # 로딩 상태 설정
        self.mylist_shop_loading = True
        
        # data.loaders 모듈의 SangaDataLoader 사용
        loader = SangaDataLoader(self)
        loader.load_data(manager, filters)
        
    def _get_horizontal_headers(self):
        """
        상가 테이블의 수평 헤더를 반환합니다.
        """
        return [
            "주소", "담당자", "매물번호", "호실", "층", "입주가능일", "월세(만원)", "보증금(만원)", 
            "관리비(만원)", "권리금(만원)", "방/화장실", "평수(공급/전용)", "현업종", "업종제한", 
            "주차", "건물종류", "전용출입구", "전화번호", "메모", "추가정보", "승인일자", "재광고"
        ]
        
    def _update_model_row(self, model, row_idx, headers, db_data):
        """
        모델 행을 업데이트합니다.
        """
        # 기존 로직 유지...
        pass
        
    def _reconnect_view_signals(self):
        """
        뷰 시그널을 다시 연결합니다.
        """
        try:
            # 모델 신호 재연결
            if self.mylist_shop_model:
                self.mylist_shop_model.itemChanged.connect(
                    lambda item: on_mylist_shop_item_changed(self, item)
                )
        except Exception as e:
            self.logger.error(f"시그널 재연결 오류: {e}")
            
    def filter_table_by_address(self, address_str):
        """
        주소로 테이블을 필터링합니다.
        """
        # 기존 로직 유지...
        pass

# 필요한 모듈 임포트
import logging