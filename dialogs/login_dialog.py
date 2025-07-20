import requests
import json
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt
import os

# 필요한 환경 변수 로드
SERVER_HOST_CONNECT = os.environ.get("SERVER_HOST_CONNECT", "localhost")
SERVER_PORT_DEFAULT = int(os.environ.get("SERVER_PORT_DEFAULT", "8000"))

# SignupDialog 임포트
from .signup_dialog import SignupDialog

class LoginDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("로그인")
        self.resize(300, 220)

        layout = QtWidgets.QVBoxLayout(self)

        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("이름")
        self.pw_edit = QtWidgets.QLineEdit()
        self.pw_edit.setPlaceholderText("비밀번호")
        self.pw_edit.setEchoMode(QtWidgets.QLineEdit.Password)

        layout.addWidget(QtWidgets.QLabel("이름:"))
        layout.addWidget(self.name_edit)
        layout.addWidget(QtWidgets.QLabel("비밀번호:"))
        layout.addWidget(self.pw_edit)

        btn_layout = QtWidgets.QHBoxLayout()

        btn_login = QtWidgets.QPushButton("로그인")
        btn_login.clicked.connect(self.on_login)
        btn_layout.addWidget(btn_login)

        # (★) 회원가입 버튼
        btn_signup = QtWidgets.QPushButton("회원가입")
        btn_signup.clicked.connect(self.on_open_signup)
        btn_layout.addWidget(btn_signup)

        layout.addLayout(btn_layout)

        self.user_name = None
        self.user_role = None

    def on_login(self):
        name_val = self.name_edit.text().strip()
        pw_val = self.pw_edit.text().strip()
        if not name_val or not pw_val:
            QtWidgets.QMessageBox.warning(self, "오류", "이름/비밀번호를 입력하세요.")
            return

        payload = {"name": name_val, "password": pw_val}
        try:
            resp = requests.post(f"http://{SERVER_HOST_CONNECT}:{SERVER_PORT_DEFAULT}/login", json=payload)
            data = resp.json()
            if data.get("status") != "ok":
                QtWidgets.QMessageBox.warning(self, "로그인 실패", data.get("message",""))
                return
            
            # 로그인 성공
            self.user_name = data["name"]
            self.user_role = data["role"]
            self.accept()  # QDialog.Accepted
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "서버오류", str(e))

    def on_open_signup(self):
        """
        회원가입 다이얼로그 띄우기
        """
        dlg = SignupDialog(self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            # 가입 성공 후 -> 안내. (로그인창으로 돌아옴)
            QtWidgets.QMessageBox.information(self, "알림", "이제 가입한 이름/비밀번호로 로그인하세요.") 