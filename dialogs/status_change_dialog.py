# dialogs/status_change_dialog.py

from PyQt5 import QtWidgets, QtGui, QtCore

class StatusChangeDialog(QtWidgets.QDialog):
    """
    '계약완료/부재중/광고X' 상태로 변경하기 위한 다이얼로그.
    관리자(admin)일 경우 -> 담당자 콤보에서 선택
    일반매니저(manager)일 경우 -> 담당자 콤보 고정 (비활성)
    상태변경 콤보(계약완료/부재중/광고X)
    확인메모(텍스트박스) - 빈칸 가능
    """
    def __init__(self, current_role: str, current_manager: str, all_managers: list, parent=None):
        """
        :param current_role: 'admin' or 'manager'
        :param current_manager: 현재 로그인 사용자 이름
        :param all_managers: 전체 관리자 목록 (admin일 때 콤보 채우는데 사용)
        """
        super().__init__(parent)
        self.setWindowTitle("상태 변경 / 계약완료 추가")
        self.resize(400, 200)

        self.current_role = current_role
        self.current_manager = current_manager
        self.all_managers = all_managers

        self.selected_manager = current_manager  # 기본값
        self.selected_status = "계약완료"        # 기본값
        self.memo_text = ""

        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # (A) 담당자 콤보
        hlayout_manager = QtWidgets.QHBoxLayout()
        lbl_manager = QtWidgets.QLabel("담당자:", self)
        self.cmb_manager = QtWidgets.QComboBox(self)
        if self.current_role.lower() == "admin":
            # 전체 매니저 목록 all_managers 로 채움
            self.cmb_manager.addItems(self.all_managers)
            self.cmb_manager.setCurrentText(self.current_manager)
        else:
            # 일반매니저 -> 콤보에 현재매니저만
            self.cmb_manager.addItem(self.current_manager)
            self.cmb_manager.setEnabled(False)

        hlayout_manager.addWidget(lbl_manager)
        hlayout_manager.addWidget(self.cmb_manager)
        layout.addLayout(hlayout_manager)

        # (B) 상태변경 콤보 (계약완료, 부재중, 광고X)
        hlayout_status = QtWidgets.QHBoxLayout()
        lbl_status = QtWidgets.QLabel("상태:", self)
        self.cmb_status = QtWidgets.QComboBox(self)
        self.cmb_status.addItems(["계약완료", "부재중", "광고X"])
        hlayout_status.addWidget(lbl_status)
        hlayout_status.addWidget(self.cmb_status)
        layout.addLayout(hlayout_status)

        # (C) 확인메모 (QTextEdit or QLineEdit)
        hlayout_memo = QtWidgets.QHBoxLayout()
        lbl_memo = QtWidgets.QLabel("확인메모:", self)
        self.edit_memo = QtWidgets.QLineEdit(self)
        self.edit_memo.setPlaceholderText("(빈칸 허용)")
        hlayout_memo.addWidget(lbl_memo)
        hlayout_memo.addWidget(self.edit_memo)
        layout.addLayout(hlayout_memo)

        # (D) 버튼박스 (OK/Cancel)
        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            parent=self
        )
        btn_box.accepted.connect(self.on_ok_clicked)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def on_ok_clicked(self):
        # 입력값 저장
        self.selected_manager = self.cmb_manager.currentText().strip()
        self.selected_status  = self.cmb_status.currentText().strip()
        self.memo_text        = self.edit_memo.text().strip()
        self.accept()

    def get_result(self):
        """
        다이얼로그 OK 후,
        {
          "manager": ...,
          "status" : "계약완료" / "부재중" / "광고X"
          "memo"   : ...
        }
        반환
        """
        return {
            "manager": self.selected_manager,
            "status":  self.selected_status,
            "memo":    self.memo_text
        }
