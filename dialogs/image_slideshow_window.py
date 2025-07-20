import os
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt

# ClickableLabel 가져오기
from .clickable_label import ClickableLabel

class ImageSlideshowWindow(QtWidgets.QDialog):
    """
    - 스크롤 없이, 창 크기에 맞춰 이미지를 축소/확대 (KeepAspectRatio)
    - 좌우에 "<", ">" 라벨로 이전/다음
    - 이미지 클릭 => 다음
    - 방향키(←/→) => 이전/다음
    - Non-Modal(메인창 조작 가능)
    """
    def __init__(self, image_paths, parent=None):
        super().__init__(parent)

        self.image_paths = image_paths[:]  # 리스트 복사
        self.current_index = 0

        # 창 설정: Non-Modal
        self.setWindowTitle("이미지 슬라이드")
        self.setWindowFlag(QtCore.Qt.Window)       # 독립된 윈도우
        self.setWindowModality(QtCore.Qt.NonModal) # 메인창과 동시 조작
        self.resize(800, 600)

        # (A) 왼쪽/오른쪽 화살표 라벨
        self.lbl_left_arrow = ClickableLabel("<")
        self.lbl_left_arrow.setFixedWidth(40)
        self.lbl_left_arrow.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_left_arrow.setStyleSheet("font-size: 24px; font-weight: bold; color: gray;")
        self.lbl_left_arrow.clicked.connect(self.show_prev_image)

        self.lbl_right_arrow = ClickableLabel(">")
        self.lbl_right_arrow.setFixedWidth(40)
        self.lbl_right_arrow.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_right_arrow.setStyleSheet("font-size: 24px; font-weight: bold; color: gray;")
        self.lbl_right_arrow.clicked.connect(self.show_next_image)

        # (B) 이미지 표시 라벨 (클릭 => 다음)
        self.image_label = ClickableLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.clicked.connect(self.show_next_image)

        # 레이아웃 (수평)
        h_layout = QtWidgets.QHBoxLayout()
        h_layout.addWidget(self.lbl_left_arrow)
        h_layout.addWidget(self.image_label, stretch=1)
        h_layout.addWidget(self.lbl_right_arrow)

        self.setLayout(h_layout)

        # 첫 이미지를 표시
        self.update_image()

    def update_image(self):
        """self.current_index에 해당하는 이미지를 label 크기에 맞춰 scaled 표시"""
        if not self.image_paths:
            self.image_label.clear()
            return

        # 인덱스 범위 체크
        if self.current_index < 0:
            self.current_index = len(self.image_paths) - 1
        elif self.current_index >= len(self.image_paths):
            self.current_index = 0

        img_path = self.image_paths[self.current_index]
        if not os.path.isfile(img_path):
            self.image_label.clear()
            return

        pixmap = QtGui.QPixmap(img_path)
        if pixmap.isNull():
            self.image_label.clear()
            return

        # (1) QLabel 크기에 맞춰서 비율유지 축소/확대
        lab_w = self.image_label.width()
        lab_h = self.image_label.height()
        if lab_w < 10 or lab_h < 10:
            # 아직 레이아웃이 완성안된 경우 등 -> 임시로 가로폭 600
            lab_w, lab_h = 600, 600

        scaled_pix = pixmap.scaled(lab_w, lab_h, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled_pix)

    def show_prev_image(self):
        self.current_index -= 1
        self.update_image()

    def show_next_image(self):
        self.current_index += 1
        self.update_image()

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        """
        방향키 ← => show_prev_image
        방향키 → => show_next_image
        ESC => close
        """
        key = event.key()
        if key == QtCore.Qt.Key_Left:
            self.show_prev_image()
        elif key == QtCore.Qt.Key_Right:
            self.show_next_image()
        elif key == QtCore.Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event: QtGui.QResizeEvent):
        """
        창 크기가 바뀔 때마다 update_image()를 다시 불러
        이미지가 새 사이즈에 맞춰 다시 scaled되도록
        """
        super().resizeEvent(event)
        self.update_image()

    def set_image_list(self, new_paths):
        """
        다른 폴더 클릭 시, 기존 창 그대로 두고
        이미지 목록만 바꾸고 싶다면 사용 가능.
        """
        self.image_paths = new_paths[:]
        self.current_index = 0
        self.update_image() 