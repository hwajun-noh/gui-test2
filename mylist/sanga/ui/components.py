# components.py - 상가 UI 컴포넌트 모듈
import os
import logging
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel
from PyQt5.QtWidgets import (
    QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QMenu,
    QMessageBox, QTableView, QAbstractItemView, QHeaderView, QShortcut, QLabel
)

# 유틸리티 임포트 (경로 조정 필요할 수 있음)
try:
    from ui_utils import restore_qtableview_column_widths, save_qtableview_column_widths
except ImportError:
    # 가져오지 못한 경우 더미 함수 제공
    def restore_qtableview_column_widths(*args, **kwargs): pass
    def save_qtableview_column_widths(*args, **kwargs): pass
    logging.warning("ui_utils 모듈 가져오기 실패: 열 너비 저장/복원 기능 사용 불가")

# 로거 인스턴스
logger = logging.getLogger(__name__)

def create_sanga_top_layout(logic_instance):
    """상가 탭용 상단 수평 레이아웃과 버튼 및 레이블을 생성합니다."""
    h_layout = QHBoxLayout()

    # 요약 레이블 (컨테이너/로직에 의해 업데이트됨)
    logic_instance.manager_summary_label = QLabel("담당자별 광고 현황: 로딩 중...")
    logic_instance.manager_summary_label.setStyleSheet(
        "font-weight: bold; font-size: 14px; padding: 5px; background-color: #f0f0f0; border-radius: 5px;"
    )
    # 나중에 init_sanga_ui에서 메인 수직 레이아웃에 레이블 추가

    logic_instance.autosave_status_label = QLabel("자동 저장: 활성화됨")
    logic_instance.autosave_status_label.setStyleSheet("color: green; font-style: italic;")
    # 나중에 init_sanga_ui에서 메인 수직 레이아웃에 레이블 추가

    # 버튼 - 모든 로직 인스턴스 속성에 할당
    logic_instance.naver_search_button = QPushButton("네이버매물검색")
    logic_instance.naver_search_button.setFixedHeight(30)
    logic_instance.naver_search_button.clicked.connect(logic_instance.on_naver_search_clicked)  # 여기서 연결
    h_layout.addWidget(logic_instance.naver_search_button)

    logic_instance.add_button = QPushButton("행 추가(상가)")
    logic_instance.add_button.setFixedHeight(30)
    logic_instance.add_button.clicked.connect(logic_instance.container.add_new_shop_row)  # 여기서 연결
    h_layout.addWidget(logic_instance.add_button)

    logic_instance.save_button = QPushButton("저장")
    logic_instance.save_button.setFixedHeight(30)
    logic_instance.save_button.clicked.connect(logic_instance.on_save_mylist_shop_changes)  # 여기서 연결
    h_layout.addWidget(logic_instance.save_button)

    logic_instance.export_button = QPushButton("엑셀 다운로드")
    logic_instance.export_button.setFixedHeight(30)
    logic_instance.export_button.clicked.connect(logic_instance.export_selected_shop_to_excel)  # 여기서 연결
    h_layout.addWidget(logic_instance.export_button)

    logic_instance.inspect_button = QPushButton("네이버부동산 검수")
    logic_instance.inspect_button.setFixedHeight(30)
    logic_instance.inspect_button.clicked.connect(logic_instance.on_open_sanga_tk_for_mylist_shop)  # 여기서 연결
    h_layout.addWidget(logic_instance.inspect_button)

    h_layout.addStretch()
    return h_layout

def setup_sanga_model_and_view(logic_instance):
    """상가 탭의 QStandardItemModel 및 QTableView를 설정합니다."""
    # (A) 모델
    logic_instance.mylist_shop_model = QStandardItemModel()
    headers_shop = logic_instance._get_horizontal_headers()  # 로직 인스턴스에서 헤더 가져오기
    logic_instance.mylist_shop_model.setColumnCount(len(headers_shop))
    logic_instance.mylist_shop_model.setHorizontalHeaderLabels(headers_shop)
    # itemChanged 시그널 연결은 이제 _reconnect_view_signals에서 처리

    # (B) 뷰
    logic_instance.mylist_shop_view = QTableView()
    logic_instance.mylist_shop_view.setModel(logic_instance.mylist_shop_model)
    logic_instance.mylist_shop_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
    
    # 상가 탭은 ID 순서 유지를 위해 정렬 기능 완전 비활성화
    logic_instance.mylist_shop_view.setSortingEnabled(False)
    
    # 정렬 기능 비활성화를 위한 추가 설정
    logic_instance.mylist_shop_view.horizontalHeader().setSortIndicatorShown(False)  # 정렬 표시기 숨김
    
    # 사용자 요청에 따라 상가 탭은 ID 순서 유지를 위해 정렬 기능 비활성화
    logic_instance.logger.info("Shop view sorting permanently disabled as requested to maintain ID order")

    # 열 너비 복원/저장
    restore_qtableview_column_widths(
        logic_instance.parent_app.settings_manager,
        logic_instance.mylist_shop_view,
        "MyListShopTable"  # 또는 로직 인스턴스에서 이 키 가져오기
    )
    logic_instance.mylist_shop_view.horizontalHeader().sectionResized.connect(
        lambda: save_qtableview_column_widths(
            logic_instance.parent_app.settings_manager,
            logic_instance.mylist_shop_view,
            "MyListShopTable"
        )
    )

    # 헤더 클릭 설정 및 컨텍스트 메뉴
    logic_instance.mylist_shop_view.setContextMenuPolicy(Qt.CustomContextMenu)
    logic_instance.mylist_shop_view.horizontalHeader().setSectionsClickable(True)  # 열 선택을 위해 클릭 가능하게 유지

    # 선택 모드 설정
    logic_instance.mylist_shop_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
    logic_instance.mylist_shop_view.setSelectionBehavior(QAbstractItemView.SelectItems)

def connect_sanga_signals_and_shortcuts(logic_instance):
    """상가 탭 UI 요소의 신호 및 단축키를 연결합니다."""
    # 로그 추가: 함수 진입 및 객체 확인
    logic_instance.logger.info(f"[connect_sanga_signals] Entering function. logic_instance: {logic_instance}")
    view = logic_instance.mylist_shop_view
    model = logic_instance.mylist_shop_model
    parent_app = logic_instance.parent_app  # 단축키용
    logic_instance.logger.info(f"[connect_sanga_signals] View: {view}, Model: {model}, ParentApp: {parent_app}")

    if not view or not model or not parent_app:
        logic_instance.logger.error("connect_sanga_signals: View, model, or parent_app is None. Cannot connect.")
        return

    # 위임자/커미트 데이터 시그널(DISABLED)
    delegate = view.itemDelegate()
    if delegate:
        # 위임자의 commitData 신호 연결
        # 참고: '핸들_commit_data' 처리 함수는 정의되어야 함 (예: mylist_sanga_events.py에서)
        # 이것은 로직 인스턴스를 통해 가져오거나 접근할 수 있다고 가정
        try:
            logic_instance.logger.info("Delegate commitData signal connection is now DISABLED.")
        except Exception as e_commit:
             logic_instance.logger.error(f"Error connecting/disconnecting commitData signal: {e_commit}", exc_info=True)
    else:
        logic_instance.logger.error("Could not get item delegate to connect commitData signal.")

    view.setContextMenuPolicy(Qt.CustomContextMenu)
    # 람다를 사용하여 컨텍스트 메뉴 연결
    view.customContextMenuRequested.connect(lambda pos: logic_instance._mylist_shop_context_menu(pos))
    logic_instance.logger.debug("Connected view.customContextMenuRequested to _mylist_shop_context_menu")

    # 람다를 사용하여 더블 클릭 연결
    view.doubleClicked.connect(lambda index: logic_instance.on_mylist_shop_view_double_clicked(index))
    logic_instance.logger.debug("Connected view.doubleClicked to on_mylist_shop_view_double_clicked")

    # 선택 모델에서 직접 currentChanged 연결 (base_container에서 처리하므로 비활성화)
    selection_model = view.selectionModel()
    if selection_model:
        logic_instance.logger.info(f"connect_sanga_signals: Got selection model: {selection_model}")
        # selection_model.currentChanged.connect(logic_instance.on_mylist_shop_current_changed)  # 비활성화
        logic_instance.logger.info("상가 내부 currentChanged 시그널 연결 비활성화됨 - base_container에서 처리")
    else:
        logic_instance.logger.error("connect_sanga_signals: FAILED to get selection model (view.selectionModel() is None). Cannot connect currentChanged signal.")

    # 람다를 사용하여 헤더 클릭 연결
    view.horizontalHeader().sectionClicked.connect(
        lambda logical_index: logic_instance.on_shop_header_section_clicked(logical_index)
    )
    logic_instance.logger.debug("Connected header.sectionClicked to on_shop_header_section_clicked")

    logic_instance.logger.info("Sanga signals and shortcuts connected (Button connections moved to creation).")

def init_sanga_ui(logic_instance):
    """상가 탭의 전체 UI를 초기화합니다."""
    container_shop = QWidget()
    layout_shop = QVBoxLayout(container_shop)

    # 상단 레이아웃 생성 및 추가 (버튼, 레이블은 logic_instance에 생성 및 저장됨)
    top_h_layout = create_sanga_top_layout(logic_instance)

    # create_sanga_top_layout에서 생성된 레이블을 메인 수직 레이아웃에 추가
    if logic_instance.manager_summary_label:
        layout_shop.addWidget(logic_instance.manager_summary_label)
    if logic_instance.autosave_status_label:
        layout_shop.addWidget(logic_instance.autosave_status_label)

    # 버튼 레이아웃 추가
    layout_shop.addLayout(top_h_layout)

    # 모델 및 뷰 설정 (logic_instance에 저장)
    setup_sanga_model_and_view(logic_instance)

    # 뷰를 레이아웃에 추가
    if logic_instance.mylist_shop_view:
        layout_shop.addWidget(logic_instance.mylist_shop_view)

    # 신호 및 단축키 연결
    connect_sanga_signals_and_shortcuts(logic_instance)

    container_shop.setLayout(layout_shop)

    logic_instance.tab_widget = container_shop  # 생성된 위젯을 로직 인스턴스에 저장
    return logic_instance.tab_widget