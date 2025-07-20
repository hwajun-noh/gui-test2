# view_events.py - 뷰 이벤트 처리 모듈
import os
import logging
from PyQt5 import QtCore
from PyQt5.QtCore import Qt, QModelIndex, QObject, pyqtSignal
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QStandardItem

from dialogs import ImageSlideshowWindow

# 로거 인스턴스
logger = logging.getLogger(__name__)

class SangaViewEvents(QObject):
    """상가 뷰 이벤트 핸들러 클래스"""
    
    # 시그널 정의
    viewDoubleClicked = pyqtSignal(QModelIndex)
    currentChanged = pyqtSignal(QModelIndex, QModelIndex)
    headerSectionClicked = pyqtSignal(int)
    
    def __init__(self, parent=None):
        """
        초기화
        
        Args:
            parent: 부모 객체 (일반적으로 SangaBridge)
        """
        # parent 인자가 SangaBridge 타입이면 None으로 설정
        QObject.__init__(self, None)
        self.parent = parent
        self.logger = logging.getLogger(__name__)
        
    def setup_view_signals(self, view):
        """
        뷰 시그널 설정
        
        Args:
            view: 연결할 뷰 객체
        """
        if not view:
            self.logger.error("View is None, cannot setup signals")
            return
            
        # 시그널 연결
        view.doubleClicked.connect(self.on_view_double_clicked)
        view.selectionModel().currentChanged.connect(self.on_current_changed)
        view.horizontalHeader().sectionClicked.connect(self.on_header_section_clicked)
    
    def on_view_double_clicked(self, index: QModelIndex):
        """
        상가 뷰 아이템 더블 클릭 처리.
        "주소" 열은 슬라이드쇼를 표시하고, 다른 열은 셀 편집을 활성화합니다.
        
        Args:
            index: 클릭된 아이템의 인덱스
        """
        model = self.parent.mylist_shop_model
        view = self.parent.mylist_shop_view
        
        if not model or not view or not index.isValid():
            return
        
        column = index.column()
        row = index.row()
        
        # 열 헤더 가져오기
        col_header = model.horizontalHeaderItem(column).text() if model.horizontalHeaderItem(column) else ""
        
        # 주소 열 특수 처리 (슬라이드쇼 표시)
        if col_header == "주소":
            folder_path = ""
            item0 = model.item(row, 0)
            if item0:
                folder_path = item0.data(Qt.UserRole + 10)
            
            if folder_path and isinstance(folder_path, str):
                try:
                    # 폴더에서 이미지 파일 리스트 생성
                    import os
                    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.JPG', '.JPEG', '.PNG', '.GIF', '.BMP')
                    image_files = []
                    
                    if os.path.isdir(folder_path):
                        for filename in os.listdir(folder_path):
                            if filename.endswith(image_extensions):
                                image_files.append(os.path.join(folder_path, filename))
                    
                    if image_files:
                        # 올바른 매개변수 순서: image_paths 먼저, parent 두 번째
                        slideshow = ImageSlideshowWindow(image_files, parent=self.parent.parent_app)
                        slideshow.exec_()
                    else:
                        self.logger.warning(f"No image files found in folder: {folder_path}")
                        QMessageBox.information(
                            self.parent.parent_app,
                            "이미지 없음",
                            f"해당 폴더에 이미지 파일이 없습니다:\n{folder_path}"
                        )
                except Exception as e:
                    self.logger.error(f"Error showing slideshow: {e}")
                    QMessageBox.warning(
                        self.parent.parent_app,
                        "이미지 로딩 오류",
                        f"사진 폴더를 열 수 없습니다: {folder_path}\n오류: {e}",
                    )
        
        # 시그널 발생
        self.viewDoubleClicked.emit(index)

    def on_current_changed(self, current: QModelIndex, previous: QModelIndex):
        """
        상가 뷰에서 현재 선택된 셀이 변경될 때 처리.
        선택한 주소를 기반으로 탭 간 필터링을 트리거합니다.
        
        Args:
            current: 현재 선택된 셀 인덱스
            previous: 이전에 선택된 셀 인덱스
        """
        print(f"🔥🔥🔥 [SANGA SIGNAL] on_current_changed 호출됨! Row: {current.row() if current.isValid() else 'INVALID'}")
        self.logger.critical(f"🔥🔥🔥 [SANGA SIGNAL] on_current_changed 호출됨! Row: {current.row() if current.isValid() else 'INVALID'}")
        
        if not current.isValid():
            print(f"🔥 [SANGA SIGNAL] Invalid index, returning.")
            self.logger.debug("on_current_changed: Invalid index, returning.")
            return

        view = self.parent.mylist_shop_view
        model = self.parent.mylist_shop_model
        parent_app = self.parent.parent_app

        if not view or not model or not parent_app:
            self.logger.warning("on_current_changed: View, model, or parent_app not available.")
            return

        row = current.row()

        # '주소' 열 인덱스 찾기
        addr_col_idx = -1
        try:
            # 모델 헤더 가져오기 시도 (주의: 모델이 아직 완전히 로드되지 않았을 수 있음)
            if model.columnCount() > 0:
                headers = [model.horizontalHeaderItem(c).text() for c in range(model.columnCount())]
                addr_col_idx = headers.index("주소")
            else:
                self.logger.warning("on_current_changed: Model column count is 0, cannot find '주소' column.")
                return  # 헤더를 찾을 수 없으면 진행 불가
                
        except (ValueError, AttributeError, Exception) as e:
            self.logger.error(f"on_current_changed: Error finding '주소' column index: {e}", exc_info=True)
            return

        # 주소 아이템 및 텍스트 가져오기
        addr_item = model.item(row, addr_col_idx)
        if not addr_item:
            self.logger.warning(f"on_current_changed: Address item not found for row {row}, column {addr_col_idx}.")
            return

        address_string = addr_item.text()
        self.logger.info(f"on_current_changed: Extracted address: '{address_string}'")

        # 메인 앱의 업데이트 함수 호출
        if hasattr(parent_app, 'update_selection_from_manager_check'):
            self.logger.info(f"on_current_changed: Calling parent_app.update_selection_from_manager_check.")
            try:
                # 직접 호출 (UI 스레드에서 시그널이 발생했으므로 안전할 것으로 예상)
                parent_app.update_selection_from_manager_check(address_string)
                self.logger.info("on_current_changed: Call to update_selection_from_manager_check completed.")
            except Exception as call_e:
                self.logger.error(f"on_current_changed: Error calling update_selection_from_manager_check: {call_e}", exc_info=True)
        else:
            self.logger.error("on_current_changed: parent_app does not have update_selection_from_manager_check method.")
            
        # 시그널 발생
        self.currentChanged.emit(current, previous)

    def on_header_section_clicked(self, logical_index: int):
        """
        테이블 헤더 클릭 처리.
        항상 전체 열을 선택합니다. 정렬 기능은 비활성화됩니다.
        
        Args:
            logical_index: 클릭된 헤더 섹션의 논리적 인덱스
        """
        view = self.parent.mylist_shop_view
        if not view:
            return
        
        # 항상 전체 열 선택 (Shift 키 상태 무시)
        self.select_entire_column(view, logical_index)
        
        # 정렬 기능 비활성화 상태 유지
        if view.isSortingEnabled():
            view.setSortingEnabled(False)
            self.logger.debug(f"Header section {logical_index} clicked: Sorting disabled to maintain ID order")
        
        # 시그널 발생
        self.headerSectionClicked.emit(logical_index)
    
    def select_entire_column(self, table_view, col_index: int):
        """주어진 인덱스의 전체 열을 선택합니다."""
        table_view.selectColumn(col_index)

    def clear_selected_cells(self, table_view=None):
        """
        선택한 셀의 내용을 지웁니다.
        첫 번째 열(주소) 또는 특정 필수 열은 수정하지 않습니다.
        
        Args:
            table_view: 테이블 뷰 객체 (None인 경우 parent에서 가져옴)
        """
        if table_view is None:
            table_view = self.parent.mylist_shop_view
            
        if not table_view:
            return
            
        indexes = table_view.selectedIndexes()
        if not indexes:
            return
        
        model = table_view.model()
        protected_columns = [0]  # 첫 번째 열(주소)은 보호됨
        
        # 헤더 텍스트로 보호된 열 인덱스 찾기
        for c in range(model.columnCount()):
            header_item = model.horizontalHeaderItem(c)
            if header_item:
                header_text = header_item.text()
                if header_text in ["주소", "재광고"]:  # 필요한 경우 다른 보호된 헤더 추가
                    if c not in protected_columns:
                        protected_columns.append(c)
        
        # 보호된 열에 있지 않은 셀 지우기
        for idx in indexes:
            col = idx.column()
            if col not in protected_columns:
                model.setItem(idx.row(), col, QStandardItem(""))
                
    def filter_by_address(self, address_str):
        """
        주소로 테이블 필터링
        
        Args:
            address_str (str): 필터링할 주소
        """
        view = self.parent.mylist_shop_view
        model = self.parent.mylist_shop_model
        
        if not view or not model:
            self.logger.warning("filter_by_address: View or model not available.")
            return
        
        # 주소 열 인덱스 찾기
        addr_col_idx = -1
        try:
            for c in range(model.columnCount()):
                header_item = model.horizontalHeaderItem(c)
                if header_item and header_item.text() == "주소":
                    addr_col_idx = c
                    break
        except Exception as e:
            self.logger.error(f"filter_by_address: Error finding '주소' column: {e}")
            return
        
        if addr_col_idx == -1:
            self.logger.warning("filter_by_address: '주소' column not found")
            return
        
        # 주소 부분 문자열로 필터링
        address_str_lower = address_str.lower()
        for r in range(model.rowCount()):
            item = model.item(r, addr_col_idx)
            if not item:
                continue
                
            row_addr = item.text().lower()
            
            # 행 숨기기/표시
            if address_str_lower in row_addr:
                view.setRowHidden(r, False)
            else:
                view.setRowHidden(r, True)
        
        self.logger.info(f"filter_by_address: Filtered table by address '{address_str}'")