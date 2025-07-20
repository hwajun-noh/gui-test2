# dialogs/auth_dialogs.py

import requests
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt

# common 모듈에서 서버 주소/포트 가져오기 (필요시)
# from .common import SERVER_HOST_CONNECT, SERVER_PORT_DEFAULT
# 임시로 하드코딩된 값 사용 (common 모듈 완성 후 수정 권장)
SERVER_HOST_CONNECT = "localhost"
SERVER_PORT_DEFAULT = 8000

class SignupDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("회원가입")
        self.resize(300, 280)

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
        self.confirm_pw_edit = QtWidgets.QLineEdit()
        self.confirm_pw_edit.setPlaceholderText("비밀번호 확인")
        self.confirm_pw_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        layout.addWidget(QtWidgets.QLabel("비밀번호 확인:"))
        layout.addWidget(self.confirm_pw_edit)


        layout.addWidget(QtWidgets.QLabel("연락처 (예: 010-0000-0000):"))
        contact_layout = QtWidgets.QHBoxLayout()

        self.contact_edit1 = QtWidgets.QLineEdit()
        self.contact_edit1.setFixedWidth(50)
        self.contact_edit1.setPlaceholderText("010")
        self.contact_edit1.setMaxLength(3)
        self.contact_edit1.setValidator(QtGui.QIntValidator(0, 999, self))

        hyphen_label1 = QtWidgets.QLabel("-")
        hyphen_label1.setFixedWidth(10)
        hyphen_label1.setAlignment(Qt.AlignCenter)

        self.contact_edit2 = QtWidgets.QLineEdit()
        self.contact_edit2.setFixedWidth(60)
        self.contact_edit2.setPlaceholderText("0000")
        self.contact_edit2.setMaxLength(4)
        self.contact_edit2.setValidator(QtGui.QIntValidator(0, 9999, self))

        hyphen_label2 = QtWidgets.QLabel("-")
        hyphen_label2.setFixedWidth(10)
        hyphen_label2.setAlignment(Qt.AlignCenter)

        self.contact_edit3 = QtWidgets.QLineEdit()
        self.contact_edit3.setFixedWidth(60)
        self.contact_edit3.setPlaceholderText("0000")
        self.contact_edit3.setMaxLength(4)
        self.contact_edit3.setValidator(QtGui.QIntValidator(0, 9999, self))

        contact_layout.addWidget(self.contact_edit1)
        contact_layout.addWidget(hyphen_label1)
        contact_layout.addWidget(self.contact_edit2)
        contact_layout.addWidget(hyphen_label2)
        contact_layout.addWidget(self.contact_edit3)
        layout.addLayout(contact_layout)
        
        self.role_combo = QtWidgets.QComboBox()
        self.role_combo.addItem("manager")  # default
        layout.addWidget(QtWidgets.QLabel("권한(역할):"))
        layout.addWidget(self.role_combo)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_signup = QtWidgets.QPushButton("가입하기")
        btn_signup.clicked.connect(self.on_signup)
        btn_layout.addWidget(btn_signup)

        btn_cancel = QtWidgets.QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def on_signup(self):
        name_val = self.name_edit.text().strip()
        pw_val = self.pw_edit.text().strip()
        confirm_pw_val = self.confirm_pw_edit.text().strip()
        role_val = self.role_combo.currentText()

        if not name_val or not pw_val:
            QtWidgets.QMessageBox.warning(self, "오류", "이름/비밀번호를 입력하세요.")
            return
        if pw_val != confirm_pw_val:
            QtWidgets.QMessageBox.warning(self, "오류", "비밀번호가 일치하지 않습니다.")
            return
        part1 = self.contact_edit1.text().strip()
        part2 = self.contact_edit2.text().strip()
        part3 = self.contact_edit3.text().strip()
        if part1 and part2 and part3:
            contact_val = f"{part1}-{part2}-{part3}"
        else:
            contact_val = ""

        payload = {
            "name": name_val,
            "password": pw_val,
            "contact": contact_val,
            "role": role_val
        }
        try:
            # common 모듈 상수 사용하도록 수정
            resp = requests.post(f"http://{SERVER_HOST_CONNECT}:{SERVER_PORT_DEFAULT}/signup", json=payload)
            data = resp.json()
            if data.get("status") != "ok":
                QtWidgets.QMessageBox.warning(self, "회원가입 실패", data.get("message",""))
                return
            QtWidgets.QMessageBox.information(self, "알림", "회원가입이 완료되었습니다.")
            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "서버오류", str(e))

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
            # common 모듈 상수 사용하도록 수정
            resp = requests.post(f"http://{SERVER_HOST_CONNECT}:{SERVER_PORT_DEFAULT}/login", json=payload)
            data = resp.json()
            if data.get("status") != "ok":
                QtWidgets.QMessageBox.warning(self, "로그인 실패", data.get("message",""))
                return
            
            self.user_name = data["name"]
            self.user_role = data["role"]
            self.accept()  # QDialog.Accepted
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "서버오류", str(e))

    def on_open_signup(self):
        dlg = SignupDialog(self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            QtWidgets.QMessageBox.information(self, "알림", "이제 가입한 이름/비밀번호로 로그인하세요.")
