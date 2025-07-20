import requests
import json
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt
import os

# 필요한 환경 변수 로드
SERVER_HOST_CONNECT = os.environ.get("SERVER_HOST_CONNECT", "localhost")
SERVER_PORT_DEFAULT = int(os.environ.get("SERVER_PORT_DEFAULT", "8000"))

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
        # 숫자만 입력받도록
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
        # role을 선택하도록 할 수도 있고, 단순히 manager로 고정할 수도 있음
        # 여기서는 콤보박스로 "manager"만 선택된 상태를 보여주는 예시
        # (admin을 만들고 싶다면 수동으로 DB에서 role=admin으로 바꿔주세요)
        self.role_combo = QtWidgets.QComboBox()
        self.role_combo.addItem("manager")  # default
        # self.role_combo.addItem("admin")   # 만약 필요하면 주석 해제
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
            resp = requests.post(f"http://{SERVER_HOST_CONNECT}:{SERVER_PORT_DEFAULT}/signup", json=payload)
            data = resp.json()
            if data.get("status") != "ok":
                QtWidgets.QMessageBox.warning(self, "회원가입 실패", data.get("message",""))
                return
            # 가입 성공
            QtWidgets.QMessageBox.information(self, "알림", "회원가입이 완료되었습니다.")
            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "서버오류", str(e)) 