"""
마이리스트 원룸 UI 컴포넌트

원룸 탭의 UI 레이아웃 및 컴포넌트 관리
"""
import logging
from PyQt5.QtCore import QObject, pyqtSignal, Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                           QTableView, QHeaderView, QAbstractItemView, QLabel,
                           QShortcut)
from PyQt5.QtGui import QKeySequence

class OneRoomUI(QObject):
    """원룸 탭 UI 컴포넌트 클래스"""
    
    # UI 이벤트 시그널
    buttonClicked = pyqtSignal(str)  # 버튼 클릭 시 (버튼명)
    
    def __init__(self, model=None, event_handler=None, commands=None, parent=None):
        """
        초기화
        
        Args:
            model: OneRoomModel 인스턴스
            event_handler: OneRoomEventHandler 인스턴스
            commands: OneRoomCommands 인스턴스
            parent: 부모 객체
        """
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.model = model
        self.event_handler = event_handler
        self.commands = commands
        
        # UI 객체
        self.widget = None
        self.table_view = None
        self.label_status = None
        self.delete_shortcut = None
        
    def create_ui(self):
        """
        UI 생성
        
        Returns:
            QWidget: 원룸 탭 위젯
        """
        # 메인 위젯 및 레이아웃
        self.widget = QWidget()
        main_layout = QVBoxLayout(self.widget)
        
        # 상단 버튼 영역
        top_layout = QHBoxLayout()
        
        # 버튼 생성
        btn_add = QPushButton("행 추가")
        btn_add.clicked.connect(lambda: self._on_button_clicked("add"))
        
        btn_save = QPushButton("저장")
        btn_save.clicked.connect(lambda: self._on_button_clicked("save"))
        
        btn_refresh = QPushButton("새로고침")
        btn_refresh.clicked.connect(lambda: self._on_button_clicked("refresh"))
        
        # 레이아웃에 버튼 추가
        top_layout.addWidget(btn_add)
        top_layout.addWidget(btn_save)
        top_layout.addWidget(btn_refresh)
        top_layout.addStretch(1)  # 오른쪽 정렬을 위한 공간
        
        # 테이블 뷰 설정
        self.table_view = QTableView()
        if self.model:
            self.table_view.setModel(self.model.get_model())
        
        # 테이블 뷰 속성 설정
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.setSortingEnabled(True)
        self.table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        
        # 이벤트 핸들러 연결
        if self.event_handler:
            # 시그널 연결
            selection_model = self.table_view.selectionModel()
            if selection_model:
                selection_model.currentChanged.connect(self.event_handler.on_current_changed)
                
            self.table_view.doubleClicked.connect(self.event_handler.on_double_clicked)
            self.table_view.customContextMenuRequested.connect(self.event_handler.show_context_menu)
        
        # 단축키 설정
        self.delete_shortcut = QShortcut(QKeySequence("Delete"), self.table_view)
        self.delete_shortcut.activated.connect(self._on_delete_shortcut)
        
        # 상태 레이블
        self.label_status = QLabel("준비됨")
        
        # 레이아웃에 컴포넌트 추가
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.table_view)
        main_layout.addWidget(self.label_status)
        
        self.logger.info("원룸 UI 생성 완료")
        return self.widget
    
    def _on_button_clicked(self, button_name):
        """
        버튼 클릭 이벤트 처리
        
        Args:
            button_name (str): 버튼 이름
        """
        self.logger.debug(f"원룸 버튼 클릭: {button_name}")
        
        # 버튼별 처리
        if button_name == "add" and self.commands:
            self.commands.add_row()
        
        # 버튼 클릭 시그널 발생
        self.buttonClicked.emit(button_name)
    
    def _on_delete_shortcut(self):
        """Delete 키 단축키 처리"""
        if self.event_handler:
            self.event_handler._delete_selected_rows()
    
    def set_status(self, message):
        """
        상태 메시지 설정
        
        Args:
            message (str): 상태 메시지
        """
        if self.label_status:
            self.label_status.setText(message)
            
    def update_column_widths(self, width_settings):
        """
        열 너비 업데이트
        
        Args:
            width_settings (dict): 열 인덱스별 너비 설정
        """
        if not self.table_view:
            return
            
        try:
            for col_idx, width in width_settings.items():
                self.table_view.setColumnWidth(int(col_idx), width)
        except Exception as e:
            self.logger.error(f"열 너비 업데이트 중 오류: {e}", exc_info=True)
    
    def get_column_widths(self):
        """
        현재 열 너비 가져오기
        
        Returns:
            dict: 열 인덱스별 너비 설정
        """
        if not self.table_view or not self.model:
            return {}
            
        try:
            widths = {}
            for col_idx in range(self.model.model.columnCount()):
                widths[col_idx] = self.table_view.columnWidth(col_idx)
            return widths
        except Exception as e:
            self.logger.error(f"열 너비 가져오기 중 오류: {e}", exc_info=True)
            return {} 