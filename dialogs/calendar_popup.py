# dialogs/calendar_popup.py

import os
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, QUrl, pyqtSignal
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtWebEngineWidgets import QWebEngineView

# 환경 변수 로드
SERVER_HOST_CONNECT = os.environ.get("SERVER_HOST_CONNECT", "localhost")
SERVER_PORT_DEFAULT = int(os.environ.get("SERVER_PORT_DEFAULT", "8000"))

class CalendarPopup(QFrame):
    """
    팝업 형태로 달력(Flatpickr/inline) + '적용' 버튼
    - 날짜 배열을 parent에게 보내려면 pyqtSignal 사용
    """
    dateApplied = pyqtSignal(list)  # (★) 시그널: 날짜 배열(list)을 전달

    def __init__(self, parent=None):
        super().__init__(parent, flags=Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("CalendarPopup")
        self.setFixedSize(350, 350)  # 크기 좀 넉넉히

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # (A) QWebEngineView
        self.web_view = QWebEngineView(self)
        main_layout.addWidget(self.web_view)

        self.web_view.load(QUrl(f"http://{SERVER_HOST_CONNECT}:{SERVER_PORT_DEFAULT}/static/my_calendar.html"))

        # (B) 하단에 버튼 레이아웃
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(5, 5, 5, 5)
        btn_layout.setSpacing(5)
        
        self.btn_reset = QPushButton("초기화", self)
        self.btn_reset.clicked.connect(self.on_reset_clicked)
        btn_layout.addWidget(self.btn_reset)

        self.btn_apply = QPushButton("적용", self)
        self.btn_apply.clicked.connect(self.on_apply_clicked)
        btn_layout.addWidget(self.btn_apply)

        self.btn_close = QPushButton("닫기", self)
        self.btn_close.clicked.connect(self.closePopup)
        btn_layout.addWidget(self.btn_close)

        main_layout.addLayout(btn_layout)

        self.setStyleSheet("""
            QFrame#CalendarPopup {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
        """)

    def on_reset_clicked(self):
        # runJavaScript("setCalendarLast30Days()") -> 최근 30일로 다시 설정
        self.web_view.page().runJavaScript("setCalendarLast30Days()")

    def on_apply_clicked(self):
        # JS -> getSelectedDates() => ["2025-01-01","2025-01-31"] 등
        self.web_view.page().runJavaScript("getSelectedDates()", self.on_js_dates_result)

    def on_js_dates_result(self, date_list):
        if not isinstance(date_list, list):
            date_list = []
        # 시그널을 통해 date_list를 부모에 전달
        self.dateApplied.emit(date_list)
        # 팝업 닫기
        self.close()

    def closePopup(self):
        self.close()
