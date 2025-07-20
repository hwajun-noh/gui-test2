# mylist_sanga_ui.py

import os
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel
from PyQt5.QtWidgets import (
    QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QMenu,
    QMessageBox, QTableView, QAbstractItemView, QHeaderView, QShortcut, QLabel
)

# Import necessary components from the main logic or other modules if needed
# Example: from .dialogs import SearchDialogForShop (adjust path as necessary)
from ui_utils import restore_qtableview_column_widths, save_qtableview_column_widths

# 🔥 CRITICAL IMPORT: SangaViewEvents for bottom table update
from mylist.sanga.events.view_events import SangaViewEvents


def create_sanga_top_layout(logic_instance):
    """Creates the top horizontal layout with buttons and labels for the Sanga tab."""
    h_layout = QHBoxLayout()

    # Labels (will be updated by container/logic)
    logic_instance.manager_summary_label = QLabel("담당자별 광고 현황: 로딩 중...")
    logic_instance.manager_summary_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px; background-color: #f0f0f0; border-radius: 5px;")
    # Add label to the main vertical layout later in init_sanga_ui

    logic_instance.autosave_status_label = QLabel("자동 저장: 활성화됨")
    logic_instance.autosave_status_label.setStyleSheet("color: green; font-style: italic;")
    # Add label to the main vertical layout later in init_sanga_ui

    # Buttons - Assign all to logic_instance attributes
    logic_instance.naver_search_button = QPushButton("네이버매물검색")
    logic_instance.naver_search_button.setFixedHeight(30)
    logic_instance.naver_search_button.clicked.connect(logic_instance.on_naver_search_clicked) # Connect here
    h_layout.addWidget(logic_instance.naver_search_button)

    logic_instance.add_button = QPushButton("행 추가(상가)")
    logic_instance.add_button.setFixedHeight(30)
    logic_instance.add_button.clicked.connect(logic_instance.container.add_new_shop_row) # Connect here
    h_layout.addWidget(logic_instance.add_button)

    logic_instance.save_button = QPushButton("저장")
    logic_instance.save_button.setFixedHeight(30)
    logic_instance.save_button.clicked.connect(logic_instance.on_save_mylist_shop_changes) # Connect here
    h_layout.addWidget(logic_instance.save_button)

    logic_instance.export_button = QPushButton("엑셀 다운로드")
    logic_instance.export_button.setFixedHeight(30)
    logic_instance.export_button.clicked.connect(logic_instance.export_selected_shop_to_excel) # Connect here
    h_layout.addWidget(logic_instance.export_button)

    logic_instance.inspect_button = QPushButton("네이버부동산 검수")
    logic_instance.inspect_button.setFixedHeight(30)
    logic_instance.inspect_button.clicked.connect(logic_instance.on_open_sanga_tk_for_mylist_shop) # Connect here
    h_layout.addWidget(logic_instance.inspect_button)

    h_layout.addStretch()
    return h_layout

def setup_sanga_model_and_view(logic_instance):
    """Sets up the QStandardItemModel and QTableView for the Sanga tab."""
    # (A) 모델
    logic_instance.mylist_shop_model = QStandardItemModel()
    headers_shop = logic_instance._get_horizontal_headers() # Get headers from logic instance
    logic_instance.mylist_shop_model.setColumnCount(len(headers_shop))
    logic_instance.mylist_shop_model.setHorizontalHeaderLabels(headers_shop)
    # logic_instance.mylist_shop_model.itemChanged.connect(logic_instance.on_mylist_shop_item_changed)

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

    # Restore/Save column widths
    restore_qtableview_column_widths(
        logic_instance.parent_app.settings_manager,
        logic_instance.mylist_shop_view,
        "MyListShopTable" # Or get this key from logic_instance
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
    logic_instance.mylist_shop_view.horizontalHeader().setSectionsClickable(True) # 열 선택을 위해 클릭 가능하게 유지

    # 선택 모드 설정
    logic_instance.mylist_shop_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
    logic_instance.mylist_shop_view.setSelectionBehavior(QAbstractItemView.SelectItems)
    # logic_instance.mylist_shop_view.setContextMenuPolicy(Qt.CustomContextMenu) # 중복 제거
    # logic_instance.mylist_shop_view.horizontalHeader().setSectionsClickable(False) # 중복 제거

def connect_sanga_signals_and_shortcuts(logic_instance):
    """Connects signals and shortcuts for the shop tab UI elements."""
    # <<< 로그 추가: 함수 진입 및 객체 확인 >>>
    logic_instance.logger.info(f"[connect_sanga_signals] Entering function. logic_instance: {logic_instance}")
    view = logic_instance.mylist_shop_view
    model = logic_instance.mylist_shop_model
    parent_app = logic_instance.parent_app # For shortcuts
    logic_instance.logger.info(f"[connect_sanga_signals] View: {view}, Model: {model}, ParentApp: {parent_app}")
    # <<< 로그 추가 끝 >>>

    if not view or not model or not parent_app:
        logic_instance.logger.error("connect_sanga_signals: View, model, or parent_app is None. Cannot connect.")
        return

    # --- Connect Model Signals --- 
    # <<< itemChanged 연결 제거: 이제 MyListSangaLogic._reconnect_view_signals 에서 처리 >>>
    # model.itemChanged.connect(lambda item: logic_instance.on_mylist_shop_item_changed(item))
    # logic_instance.logger.info("Attempted to connect model.itemChanged via lambda to logic_instance.on_mylist_shop_item_changed")
    # try:
    #     is_connected = logic_instance.receivers(model.itemChanged) > 0
    #     logic_instance.logger.info(f"[connect_sanga_signals] Verification: model.itemChanged connection status: {is_connected} (Receivers: {logic_instance.receivers(model.itemChanged)})")
    # except Exception as e_verify:
    #      logic_instance.logger.error(f"Error verifying itemChanged connection: {e_verify}")
    # <<< 로그 추가 끝 >>>

    # --- Connect View/Delegate Signals (DISABLED) ---
    # Get the default delegate used by the view
    delegate = view.itemDelegate()
    if delegate:
        # Connect the delegate's commitData signal
        # Note: The handler function 'handle_commit_data' needs to be defined, e.g., in mylist_sanga_events.py
        # We assume it will be imported or accessible via logic_instance
        try:
            # Disconnect first to avoid multiple connections if this runs again
            # try: delegate.commitData.disconnect() # <<< 수정: 연결 해제
            # except TypeError: pass # Ignore if not connected
            # # Import the handler function where it's defined
            # from mylist_sanga_events import handle_commit_data
            # delegate.commitData.connect(lambda editor_widget: handle_commit_data(logic_instance, editor_widget))
            # logic_instance.logger.info("Connected delegate.commitData signal to handle_commit_data")
            logic_instance.logger.info("Delegate commitData signal connection is now DISABLED.") # <<< 수정: 로그 변경
        # except ImportError:
        #      logic_instance.logger.error("Failed to import handle_commit_data from mylist_sanga_events. Check definition and path.")
        except Exception as e_commit:
             logic_instance.logger.error(f"Error connecting/disconnecting commitData signal: {e_commit}", exc_info=True)
    else:
        logic_instance.logger.error("Could not get item delegate to connect commitData signal.")
    # --- End Alternative Approach ---


    view.setContextMenuPolicy(Qt.CustomContextMenu)
    # Connect using lambda for context menu
    view.customContextMenuRequested.connect(lambda pos: logic_instance._mylist_shop_context_menu(pos))
    logic_instance.logger.debug("Connected view.customContextMenuRequested to _mylist_shop_context_menu")

    # Connect using lambda for double click
    view.doubleClicked.connect(lambda index: logic_instance.on_mylist_shop_view_double_clicked(index))
    logic_instance.logger.debug("Connected view.doubleClicked to on_mylist_shop_view_double_clicked")

    # Connect currentChanged directly from the selection model
    selection_model = view.selectionModel()
    if selection_model:
        logic_instance.logger.info(f"connect_sanga_signals: Got selection model: {selection_model}")
        # 🔥 RE-ENABLED: currentChanged 시그널 연결 활성화 (view_events에서 하단 테이블 업데이트 처리)
        try:
            logic_instance.logger.info("🔥 [SIGNAL DEBUG] SangaViewEvents 생성 시작...")
            view_events_handler = SangaViewEvents(logic_instance)
            logic_instance.logger.info(f"🔥 [SIGNAL DEBUG] SangaViewEvents 생성 완료: {view_events_handler}")
            
            logic_instance.logger.info("🔥 [SIGNAL DEBUG] currentChanged 시그널 연결 시작...")
            selection_model.currentChanged.connect(view_events_handler.on_current_changed)
            logic_instance.logger.info("🔥 [SIGNAL DEBUG] currentChanged 시그널 연결 완료!")
            
            # logic_instance에 view_events 속성 추가 (나중에 사용할 수 있도록)
            logic_instance.view_events = view_events_handler
            logic_instance.logger.info("🔥 connect_sanga_signals: currentChanged 시그널이 SangaViewEvents.on_current_changed에 연결됨 (하단 테이블 업데이트 포함)")
            
            # 테스트용 더미 시그널 발생
            logic_instance.logger.info("🔥 [SIGNAL DEBUG] 시그널 연결 테스트를 위해 수동으로 더미 이벤트 시뮬레이션...")
            
        except Exception as e:
            logic_instance.logger.error(f"🔥 [SIGNAL DEBUG] SangaViewEvents 연결 실패: {e}", exc_info=True)
    else:
        logic_instance.logger.error("connect_sanga_signals: FAILED to get selection model (view.selectionModel() is None). Cannot connect currentChanged signal.")

    # Connect using lambda for header click
    view.horizontalHeader().sectionClicked.connect(
        lambda logical_index: logic_instance.on_shop_header_section_clicked(logical_index)
    )
    logic_instance.logger.debug("Connected header.sectionClicked to on_shop_header_section_clicked")

    logic_instance.logger.info("Sanga signals and shortcuts connected (Button connections moved to creation).")

def init_sanga_ui(logic_instance):
    """Initializes the complete UI for the Sanga tab."""
    container_shop = QWidget()
    layout_shop = QVBoxLayout(container_shop)

    # Create and add top layout (buttons, labels are created and stored in logic_instance)
    top_h_layout = create_sanga_top_layout(logic_instance)

    # Add labels created in create_sanga_top_layout to the main vertical layout
    if logic_instance.manager_summary_label:
        layout_shop.addWidget(logic_instance.manager_summary_label)
    if logic_instance.autosave_status_label:
        layout_shop.addWidget(logic_instance.autosave_status_label)

    # Add the button layout
    layout_shop.addLayout(top_h_layout)

    # Setup model and view (stored in logic_instance)
    setup_sanga_model_and_view(logic_instance)

    # Add the view to the layout
    if logic_instance.mylist_shop_view:
        layout_shop.addWidget(logic_instance.mylist_shop_view)

    # Connect signals and shortcuts
    connect_sanga_signals_and_shortcuts(logic_instance)

    container_shop.setLayout(layout_shop)

    logic_instance.tab_widget = container_shop # Store the created widget in the logic instance
    return logic_instance.tab_widget 