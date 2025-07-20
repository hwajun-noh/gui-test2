from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QScrollArea, QWidget
)

class MultiRowMemoDialog(QDialog):
    """
    선택된 여러 행(주소별) 각각에 대해 별도 메모를 입력받을 수 있는 다이얼로그.
    - addresses: [(id, src, addr), (id, src, addr), ...]
      (id: DB PK, src: "원룸"/"상가"..., addr: "가양동 123-4")
    - is_admin, manager_list 등은 필요 시 추가
    """

    def __init__(self, row_info_list, manager=None, parent=None):
        """
        row_info_list: [ { "id":..., "src":..., "addr":... }, ... ]
        manager: 현재 매니저명 (필요하면 콤보로 바꾸거나)
        """
        super().__init__(parent)
        self.setWindowTitle("내 리스트 복사 - 행별 메모")
        self.resize(600, 400)

        self.row_info_list = row_info_list  # 외부로부터 받은 행 정보
        self.memo_widgets = []  # row별 메모 위젯(Tuple of (id, source, widget))

        main_layout = QVBoxLayout(self)

        # (A) 스크롤 영역 안에 N개의 (주소,메모) 위젯을 배치
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        container = QWidget()
        vlay = QVBoxLayout(container)

        for row_i, info in enumerate(row_info_list):
            # info: {"id":..., "src":..., "addr":...}
            line_wid = QWidget()
            hlayout = QHBoxLayout(line_wid)

            lbl_addr = QLabel(info["addr"])
            lbl_addr.setFixedWidth(200)

            # 메모 입력: 여기서는 QLineEdit 예시 (짧은 텍스트)
            # 만약 장문이라면 QTextEdit 사용 가능
            edit_memo = QLineEdit()
            edit_memo.setPlaceholderText("메모 입력...")

            hlayout.addWidget(lbl_addr)
            hlayout.addWidget(edit_memo)
            line_wid.setLayout(hlayout)

            vlay.addWidget(line_wid)
            # 저장
            self.memo_widgets.append((info["id"], info["src"], edit_memo))

        # 레이아웃 끝
        vlay.addStretch(1)  # 아래쪽 여백
        container.setLayout(vlay)

        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

        # (B) 하단 버튼
        btn_ok = QPushButton("확인")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)

        main_layout.addLayout(btn_layout)

    def get_memo_list(self):
        """
        각 행마다 사용자 입력한 메모를 리턴:
        [ { "id":..., "source":..., "memo":"..." }, ... ]
        """
        result = []
        for (pid, src, w) in self.memo_widgets:
            memo_text = w.text().strip()
            
            # 디버깅 출력 추가
            print(f"[DEBUG] 마이리스트 복사 - 메모 다이얼로그: ID={pid}, 출처={src}, 메모={memo_text}")
            
            result.append({
                "id": pid,
                "source": src,
                "memo": memo_text
            })
        return result 