import sys
import os
import json
import logging
from datetime import datetime, date, timedelta
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, QUrl, pyqtSignal, QObject
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QDialog, QTableWidgetItem, QMessageBox, QAbstractItemView, QTableView, QMenu, QAction, QWidget, QVBoxLayout, QComboBox, QPushButton, QLineEdit, QHBoxLayout, QHeaderView, QApplication, QShortcut, QStackedWidget

from ui_utils import format_biz_list, MyTabStyle, update_combo_style, show_context_menu, save_qtableview_column_widths, restore_qtableview_column_widths
from dialogs import StatusChangeDialog, BizSelectDialog, CalendarPopup, MultiGuDongDialog, SearchDialogForShop, RecommendDialog, NaverShopSearchDialog

# 로컬 모듈 임포트
from .data import ManagerDataMixin
from .ui import ManagerUIMixin
from .table import ManagerTableMixin

logger = logging.getLogger(__name__)

# 환경 변수 설정
SERVER_HOST_CONNECT = os.environ.get("SERVER_HOST_CONNECT", "localhost") 
SERVER_PORT_DEFAULT = int(os.environ.get("SERVER_PORT_DEFAULT", "8000"))

class ManagerCheckTab(QObject, ManagerDataMixin, ManagerUIMixin, ManagerTableMixin):
    """네이버 매물 관리자 체크 탭 컴포넌트"""
    
    # 시그널 정의
    tableDataReady = pyqtSignal(object)    # 테이블 데이터가 준비되면 발생하는 시그널
    metadataReady = pyqtSignal(object)     # 메타데이터 처리 완료 시 발생하는 시그널
    loadingStarted = pyqtSignal()          # 로딩 시작 시 발생하는 시그널
    loadingFinished = pyqtSignal(str)      # 로딩 완료 시 발생하는 시그널 (메시지 포함)
    loadingError = pyqtSignal(str)         # 오류 발생 시 시그널 (오류 메시지 포함)
    
    def __init__(self, parent_app, manager, role, server_host, server_port):
        """
        ManagerCheckTab 클래스 초기화
        
        Args:
            parent_app: 부모 애플리케이션 인스턴스
            manager: 현재 매니저 이름
            role: 역할(권한) 정보
            server_host: 서버 호스트 주소
            server_port: 서버 포트 번호
        """
        super().__init__()  # QObject 초기화
        self.parent_app = parent_app # Reference to the main ExcelTableApp instance
        self.current_manager = manager
        self.current_role = role
        self.server_host = server_host
        self.server_port = server_port
        self.logger = logging.getLogger(__name__) # 로거 인스턴스 속성 추가
        
        # UI elements will be initialized in init_tab
        self.container_widget = None
        self.check_manager_view = None
        self.manager_source_model = None
        self.btn_new_refresh_manager = None
        self.btn_naver_inspect = None
        self.lbl_selected_dongs = None
        self.btn_select_dong = None
        self.lbl_selected_biz = None
        self.btn_select_biz = None
        self.lbl_selected_dates = None
        self.btn_select_date = None
        self.manager_check_timer = None
        self.manager_check_search_shortcut = None
        self.popup_calendar = None # For date selection popup
        self.naver_search_dialog = None # 네이버 검색 다이얼로그 인스턴스

        # Data / State (access via self.parent_app if needed, or manage locally)
        self.last_loaded_id = 0
        self.filter_ad_date_value = "" # e.g., "YYYY-MM-DD,YYYY-MM-DD"
        self.selected_biz_types = [] # 선택된 업종 리스트
        self.selected_dongs_by_gu = {} # e.g., { "동구": {"가양동","대동"}, ... }
        self.loading_data_flag = False # To prevent unwanted signal triggers during population
        self._new_manager_data_list = [] # 새 매니저 데이터 리스트 추가

        # 시그널 연결
        self.tableDataReady.connect(self._handle_table_data_ready)
        self.metadataReady.connect(self._handle_metadata_ready)
        self.loadingStarted.connect(self._handle_loading_started)
        self.loadingFinished.connect(self._handle_loading_finished)
        self.loadingError.connect(self._handle_loading_error)

    def init_tab(self, target_stack: QStackedWidget, tab_index: int):
        """
        매니저 체크 탭 UI를 초기화하고 target_stack에 추가합니다.
        
        Args:
            target_stack: 탭을 추가할 대상 QStackedWidget
            tab_index: 탭이 추가될 인덱스
        """
        # 1) container_widget + layout
        self.container_widget = QtWidgets.QWidget()
        main_vlayout = QtWidgets.QVBoxLayout(self.container_widget)

        # 2) 상단 영역 레이아웃 + 버튼들
        combo_layout = QtWidgets.QHBoxLayout()
        combo_layout.setSpacing(5)

        self.manager_check_timer = QtCore.QTimer(self.parent_app) # Parent timer to parent_app
        self.manager_check_timer.setInterval(5 * 60 * 1000)  # 5 minutes
        self.manager_check_timer.timeout.connect(self.check_new_manager_data) # Connect to local method
        self.manager_check_timer.start()

        # 네이버부동산 검수
        self.btn_naver_inspect = QtWidgets.QPushButton("네이버부동산 검수")
        self.btn_naver_inspect.setFixedHeight(30)
        self.btn_naver_inspect.clicked.connect(self.on_open_sanga_tk) # Connect to local method
        combo_layout.addWidget(self.btn_naver_inspect)

        # 네이버 매물 검색 버튼 생성 및 설정 (위치 조정 전)
        self.btn_naver_search_manager = QtWidgets.QPushButton("네이버 매물 검색")
        self.btn_naver_search_manager.setFixedHeight(30) # 첫 버튼과 높이 동일하게 설정
        self.btn_naver_search_manager.clicked.connect(self.on_naver_search_clicked_manager) # 핸들러 연결
        
        # 버튼 위치 조정: 두 번째 위치(index=1)에 삽입
        combo_layout.insertWidget(1, self.btn_naver_search_manager)

        # (동: 라벨/버튼/요약)
        lbl_dong_static = QtWidgets.QLabel("동:")
        combo_layout.addWidget(lbl_dong_static)

        self.lbl_selected_dongs = QtWidgets.QLabel("(없음)")
        self.lbl_selected_dongs.setToolTip("")
        combo_layout.addWidget(self.lbl_selected_dongs)

        self.btn_select_dong = QtWidgets.QPushButton("동선택")
        self.btn_select_dong.clicked.connect(self.on_select_dong_clicked)
        combo_layout.addWidget(self.btn_select_dong)

        # (업종: 라벨/요약/버튼)
        lbl_biz_static = QtWidgets.QLabel("업종:")
        combo_layout.addWidget(lbl_biz_static)

        self.lbl_selected_biz = QtWidgets.QLabel("(없음)")
        self.lbl_selected_biz.setToolTip("")
        combo_layout.addWidget(self.lbl_selected_biz)

        self.btn_select_biz = QtWidgets.QPushButton("업종선택")
        self.btn_select_biz.clicked.connect(self.on_select_biz_clicked)
        combo_layout.addWidget(self.btn_select_biz)

        # (광고날짜)
        self.lbl_selected_dates = QtWidgets.QLabel("날짜: (날짜 선택 없음)")
        self.btn_select_date = QtWidgets.QPushButton("날짜선택(팝업)")
        self.btn_select_date.clicked.connect(self.on_select_date_clicked)
        combo_layout.addWidget(self.lbl_selected_dates)
        combo_layout.addWidget(self.btn_select_date)

        main_vlayout.addLayout(combo_layout)

        # 3) 테이블(Model + View) - UI 간소화: 필요없는 필드 제거
        self.manager_source_model = QtGui.QStandardItemModel()
        # 불필요한 필드 제거 ('호', '현재업종', '용도' 등)
        headers = [
            "주소", "층", "보증금/월세", "관리비",
            "권리금", "평수", "연락처",
            "매물번호", "제목", "매칭업종", "확인메모", "광고등록일",
            "주차대수", "사용승인일", "방/화장실",
            "사진경로", "소유자명", "관계"
        ]
        self.manager_source_model.setColumnCount(len(headers))
        self.manager_source_model.setHorizontalHeaderLabels(headers)

        self.check_manager_view = QtWidgets.QTableView()
        self.check_manager_view.setModel(self.manager_source_model)
        self.check_manager_view.setSortingEnabled(True)

        header = self.check_manager_view.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)

        # Restore column widths using the utility function
        restore_qtableview_column_widths(
            self.parent_app.settings_manager, # Pass settings manager
            self.check_manager_view,
            "CheckManagerView"  # (저장 키)
        )
        # Save column widths on resize using the utility function
        self.check_manager_view.horizontalHeader().sectionResized.connect(
            lambda: save_qtableview_column_widths(
                self.parent_app.settings_manager, # Pass settings manager
                self.check_manager_view, 
                "CheckManagerView"
            )
        )

        main_vlayout.addWidget(self.check_manager_view)
        self.container_widget.setLayout(main_vlayout) # Set layout on container

        # Add the container to the target stacked widget at the specified index
        target_stack.insertWidget(tab_index, self.container_widget)

        # 4) 초기 필터 설정 - 기본 날짜 필터는 한 달로 설정
        today = datetime.now().date()
        one_month_ago = today - timedelta(days=30)
        today_str = today.strftime("%Y-%m-%d")
        month_ago_str = one_month_ago.strftime("%Y-%m-%d")
        
        # 날짜 필터는 한 달, 나머지 필터는 비움
        self.filter_ad_date_value = f"{month_ago_str},{today_str}"
        self.selected_biz_types = []    # 업종 필터 비움
        self.selected_dongs_by_gu = {}  # 동 필터 비움
        
        # 필터 상태 라벨 업데이트
        self.lbl_selected_dates.setText(f"{month_ago_str} ~ {today_str}")
        self.logger.info(f"기본 날짜 필터 설정: {month_ago_str} ~ {today_str} (최근 30일)")
        
        # 5) 시그널들
        self.manager_source_model.itemChanged.connect(self.on_manager_item_changed) 
        self.check_manager_view.doubleClicked.connect(self.on_manager_view_double_clicked)
        
        # 🔍 디버깅: 시그널 연결 상태 확인
        sel_model_check = self.check_manager_view.selectionModel()
        print(f"[DEBUG] ManagerCheckTab init_tab: selectionModel = {sel_model_check}")
        print(f"[DEBUG] ManagerCheckTab init_tab: model row count = {self.manager_source_model.rowCount()}")
        
        if sel_model_check:
            sel_model_check.currentChanged.connect(self.on_check_current_changed)
            print("[DEBUG] ManagerCheckTab init_tab: currentChanged signal connected successfully")
        else:
            print("[ERROR] ManagerCheckTab init_tab: selectionModel is None!")
        
        # 컨텍스트 메뉴 설정 강화 - 우클릭 기능
        self.check_manager_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.check_manager_view.customContextMenuRequested.connect(
             self.on_check_tab_context_menu_requested
        )
        
        # 검색 단축키 설정
        self.manager_check_search_shortcut = QtWidgets.QShortcut(
            QtGui.QKeySequence("Ctrl+F"),
            self.check_manager_view # Parent is the view itself
        )
        self.manager_check_search_shortcut.activated.connect(self.show_manager_check_search_dialog)
        
        # 6) 시작 시 데이터 로드 (한 달 날짜 필터 적용)
        self.logger.info("초기화 완료: 기본 날짜 필터(최근 30일)로 데이터를 로드합니다.")
        self.refresh_tab_data(force_reload=True)  # 전체 데이터 로드 