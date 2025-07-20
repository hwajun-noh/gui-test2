# dialogs/map_select_dialog.py

import json
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
import os

# 필요한 환경 변수 로드
SERVER_HOST_CONNECT = os.environ.get("SERVER_HOST_CONNECT", "localhost")
SERVER_PORT_DEFAULT = int(os.environ.get("SERVER_PORT_DEFAULT", "8000"))

# widgets 모듈에서 MyWebEnginePage 가져오기 (가정)
# 실제 widgets 모듈의 구조에 따라 경로 수정 필요
# 예시: from ..widgets import MyWebEnginePage 
# 임시로 정의 (실제 사용 시 주석 해제 및 올바른 임포트 필요)
class MyWebEnginePage(QtCore.QObject): # 임시 정의
    def __init__(self, parent=None):
        super().__init__(parent)
    # 실제 MyWebEnginePage 구현 필요
    pass 

class MapSelectDialog(QtWidgets.QDialog):
    """
    지도에서 사각형을 그려 범위를 선택하는 Dialog.
    """
    def __init__(self, parent=None, initial_rectangles=None):
        from widgets import MyWebEnginePage
        super().__init__(parent)
        self.setWindowTitle("지도 선택")
        self.resize(800, 600)

        if initial_rectangles is None:
            initial_rectangles = []
        self.initial_rectangles = initial_rectangles

        self.layout_ = QtWidgets.QVBoxLayout(self)

        self.web_view = QWebEngineView(self)
        custom_page = MyWebEnginePage(self.web_view)
        self.web_view.setPage(custom_page)
        self.layout_.addWidget(self.web_view)

        # HTML 로드
        self.web_view.load(QUrl(f"http://{SERVER_HOST_CONNECT}:{SERVER_PORT_DEFAULT}/static/newindex.html"))
        self.web_view.loadFinished.connect(self.on_load_finished)

        # 버튼
        btn_layout = QtWidgets.QHBoxLayout()
        self.ok_btn = QtWidgets.QPushButton("확인")
        self.ok_btn.clicked.connect(self.on_ok)
        self.cancel_btn = QtWidgets.QPushButton("취소")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        self.layout_.addLayout(btn_layout)

        self.setLayout(self.layout_)
        self.rectangles = []  # 최종 결과

    def on_load_finished(self, ok):
        if not ok:
            QtWidgets.QMessageBox.warning(self, "로드 실패", "지도를 로드하지 못했습니다.")
            return
        else:
            print("지도 html 로드 성공")
            if self.initial_rectangles:
                try:
                    rect_json = json.dumps(self.initial_rectangles)
                    js_code = f"setRectanglesData({rect_json});"
                    self.web_view.page().runJavaScript(js_code)
                except Exception as e:
                    print("초기 사각형 전달 오류:", e)

    def on_ok(self):
        """
        1) getRectanglesData() => [[swLng, swLat, neLng, neLat], ...]
        2) JSON으로 받아 self.rectangles 저장 후 accept()
        """
        js_code = "JSON.stringify(getRectanglesData())"
        self.web_view.page().runJavaScript(js_code, self.handle_rectangles)

    def handle_rectangles(self, rectangles_json):
        if not rectangles_json:
            print("rectangles_json is None or empty")
            return
        try:
            arr = json.loads(rectangles_json)
            self.rectangles = arr

            # 예: 부모가 CustomerRowEditDialog라면, 
            #     그 내부의 self.saved_conditions["map_rectangles"]에 직접 대입
            parent_dlg = self.parent()
            if parent_dlg and hasattr(parent_dlg, "saved_conditions"):
                parent_dlg.saved_conditions["map_rectangles"] = arr
                print("[DEBUG] 지도 사각형 saved_conditions 갱신 완료")

            QtWidgets.QMessageBox.information(
                self, "사각형 좌표", f"불러온 좌표:\n{arr}"
            )
        except Exception as ex:
            print("JS -> Python 좌표 파싱 오류:", ex)
        self.accept()
