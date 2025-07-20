# ui_utils.py

import json
from datetime import datetime, date, timedelta  
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QProxyStyle, QStyle, QStyleOptionTab, QTabBar, QTableView, QHeaderView, 
    QAbstractItemView, QTableWidgetItem, QMenu, QComboBox, QApplication, QMessageBox, QWidget 
)
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QPalette
from config.settings_manager import SettingsManager # Assuming settings manager is here



def get_last_run_date_from_db():
    """
    DB의 system_config에서 cfg_key='last_run_date' 를 SELECT하여 date로 반환.
    없거나 오류면 None.
    """
    import mysql.connector as mysql
    conn = mysql.connect(
        host='localhost',
        user='root',
        password='a13030z0!!',
        database='mydb',
        charset='utf8mb4',
        use_unicode=True
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT cfg_value FROM system_config WHERE cfg_key='last_run_date'")
    row = cursor.fetchone()
    conn.close()
    if row and row.get("cfg_value"):
        try:
            return datetime.strptime(row["cfg_value"], "%Y-%m-%d").date()
        except:
            pass
    return None

def set_last_run_date_in_db(date_obj):
    """
    date_obj(파이썬 date)를 'YYYY-MM-DD' 문자열로 변환하여 DB에 저장/업데이트
    """
    import mysql.connector as mysql
    str_val = date_obj.strftime("%Y-%m-%d")

    conn = mysql.connect(
        host='localhost',
        user='root',
        password='a13030z0!!',
        database='mydb',
        charset='utf8mb4',
        use_unicode=True
    )
    cursor = conn.cursor()
    cursor.execute("SELECT cfg_value FROM system_config WHERE cfg_key='last_run_date'")
    row = cursor.fetchone()
    if row:
        # update
        cursor.execute("UPDATE system_config SET cfg_value=%s WHERE cfg_key='last_run_date'", (str_val,))
    else:
        # insert
        cursor.execute("INSERT INTO system_config (cfg_key, cfg_value) VALUES ('last_run_date', %s)", (str_val,))

    conn.commit()
    conn.close()

class MyTabStyle(QProxyStyle):
    def drawControl(self, element, opt, painter, widget=None):
        # (A) 탭 그리기 로직인지 확인
        if element == QStyle.CE_TabBarTab and isinstance(opt, QStyleOptionTab):
            # widget이 QTabBar인지 체크
            if isinstance(widget, QTabBar):
                bar = widget

                # (1) center_pt: 탭의 사각형(rect) 중심 좌표
                center_pt = opt.rect.center()

                # (2) bar.tabAt(…) : 해당 픽셀 좌표가 어느 탭 인덱스인지 반환
                tab_index = bar.tabAt(center_pt)  # -1이면 못 찾음

                # 원하는 인덱스별 색상 지정
                color_map = {
                    0: None,         # (0) "전체"
                    1: "#CCFFCC",    # (1) "매물체크(확인)"
                    2: "#FFFFCC",    # (2) "써브(상가)"
                    3: "#FFCCCC",    # (3) "써브(원룸)"
                    4: "#BBDEFB",    # (4) "추천"
                    5: "#E1BEE7",    # (5) "마이리스트(상가)"
                    6: "#DDDDDD"      # ★ "계약완료" (옅은 회색)
                }
                bg_hex = color_map.get(tab_index)
                if bg_hex and painter.isActive() and opt.rect.isValid():
                    painter.save()
                    painter.fillRect(opt.rect, QColor(bg_hex))
                    painter.restore()

            # 기본 드로잉(테두리, 텍스트)은 부모에 맡김
            super().drawControl(element, opt, painter, widget)
        else:
            super().drawControl(element, opt, painter, widget)


def update_combo_style(combo: QComboBox):
    """
    콤보박스 배경색을 상태별로 변경.
    """
    current_text = combo.currentText()
    if current_text == "확인필요":
        combo.setStyleSheet("QComboBox { background-color: #FF9999; }")
    elif current_text == "부재중":
        combo.setStyleSheet("QComboBox { background-color: #FFF9C4; }")
    elif current_text == "재광고":
        combo.setStyleSheet("QComboBox { background-color: #C8E6C9; }")
    elif current_text == "거래완료":
        combo.setStyleSheet("QComboBox { background-color: #BBDEFB; }")
    elif current_text == "광고X":
        combo.setStyleSheet("QComboBox { background-color: #FFE0B2; }")
    else:
        combo.setStyleSheet("")

def format_biz_list(biz_manager_list):
    """
    Converts biz_manager_list to display string and hidden data.
    biz_manager_list: [{"biz":"치킨집","manager":"김철수"}, ...]
    Returns: (display_str, hidden_data_list)
    """
    display_parts = []
    hidden_data = []
    for item in biz_manager_list:
        b_ = item.get("biz","")
        mgr_full = item.get("manager","")
        mgr_first = mgr_full[:1] if mgr_full else ""
        part = f"{b_}[{mgr_first}]" if mgr_first else b_
        display_parts.append(part)
        hidden_data.append({"biz": b_, "manager_full": mgr_full})
    display_str = ",".join(display_parts)
    return display_str, hidden_data

# Moved from main_app_part1.py
def show_context_menu(parent_widget: QWidget, pos: QPoint, table_view: QTableView, register_callback: callable, copy_callback: callable, status_callback: callable):
    """Shows a common context menu for tables."""
    index = table_view.indexAt(pos)
    if not index.isValid(): return
    
    # 선택된 행 확인
    model = table_view.model()
    row = index.row()
    addr_item = model.item(row, 0) if model and model.item else None  # 주소 컬럼(첫 번째 컬럼)
    addr_text = addr_item.text() if addr_item else "선택된 행"
    
    menu = QMenu(parent_widget) # Parent menu to the widget where context menu was requested
    
    # 추천매물 등록 강화 - 아이콘과 단축키 추가
    action_register = QtWidgets.QAction("⭐ 추천매물 등록", parent_widget)
    action_register.setShortcut("Ctrl+R")
    if hasattr(QtGui, "QIcon") and hasattr(QtGui.QIcon, "fromTheme"):
        action_register.setIcon(QtGui.QIcon.fromTheme("bookmark-new"))
    
    # 스타일 설정 (글꼴 굵게, 배경색 변경)
    font = action_register.font()
    font.setBold(True)
    action_register.setFont(font)
    
    # 나머지 메뉴 항목 생성
    action_copy = QtWidgets.QAction("내 리스트에 복사", parent_widget)
    action_copy.setShortcut("Ctrl+C")
    if hasattr(QtGui, "QIcon") and hasattr(QtGui.QIcon, "fromTheme"):
        action_copy.setIcon(QtGui.QIcon.fromTheme("edit-copy"))
    
    action_status = QtWidgets.QAction("상태 변경(계약완료/부재중/광고X/연락처X)", parent_widget)
    action_status.setShortcut("Ctrl+S")
    if hasattr(QtGui, "QIcon") and hasattr(QtGui.QIcon, "fromTheme"):
        action_status.setIcon(QtGui.QIcon.fromTheme("document-properties"))
    
    # 메뉴에 액션 추가
    menu.addAction(action_register)
    menu.addSeparator()  # 구분선 추가
    menu.addAction(action_copy)
    menu.addAction(action_status)
    
    # 툴팁이나 상태 텍스트 추가
    action_register.setToolTip(f"{addr_text}를 추천매물로 등록합니다")
    action_copy.setToolTip(f"{addr_text}를 내 리스트에 복사합니다")
    action_status.setToolTip(f"{addr_text}의 상태를 변경합니다")
    
    # 메뉴 실행
    action = menu.exec_(table_view.mapToGlobal(pos))
    
    # 선택된 액션 처리
    if action == action_register:
        if register_callback: register_callback(index)
    elif action == action_copy:
        if copy_callback: copy_callback() # copy_callback might not need index
    elif action == action_status:
        if status_callback: status_callback(table_view) # Pass table_view to status handler

# Moved from main_app_part8.py (likely)
def save_qtableview_column_widths(settings_manager: SettingsManager, table_view: QTableView, settings_key: str):
    """Saves the column widths of a QTableView to settings."""
    if not settings_manager or not table_view or not table_view.model():
        print(f"[WARN] save_qtableview_column_widths: Invalid arguments for key '{settings_key}'")
        return
        
    col_count = table_view.model().columnCount()
    widths = []
    for col_idx in range(col_count):
        widths.append(table_view.columnWidth(col_idx))
    settings_manager.save(settings_key, "column_widths", widths)

# Moved from main_app_part8.py (likely)
def restore_qtableview_column_widths(settings_manager: SettingsManager, table_view: QTableView, settings_key: str):
    """Restores the column widths of a QTableView from settings."""
    if not settings_manager or not table_view or not table_view.model():
        print(f"[WARN] restore_qtableview_column_widths: Invalid arguments for key '{settings_key}'")
        return
        
    widths = settings_manager.load(settings_key, "column_widths", None)
    if not widths:
        return
    if isinstance(widths, str):
        import json
        try: widths = json.loads(widths)
        except: 
             print(f"[WARN] Failed to parse column widths string for key '{settings_key}': {widths}")
             return
             
    if not isinstance(widths, (list, tuple)):
         print(f"[WARN] Invalid widths data type for key '{settings_key}': {type(widths)}")
         return

    col_count = table_view.model().columnCount()
    for col_idx, w in enumerate(widths):
        if col_idx < col_count:
            try:
                table_view.setColumnWidth(col_idx, int(w))
            except (ValueError, TypeError):
                 print(f"[WARN] Invalid width value '{w}' for column {col_idx} in {settings_key}")


# ============== 헤더 기반 컬럼 매핑 헬퍼 함수들 ==============
# 인덱스 대신 헤더명으로 컬럼에 접근하는 안전한 방법들

def get_column_index_by_header(model, header_name):
    """
    헤더명으로 컬럼 인덱스를 찾습니다.
    
    Args:
        model: QStandardItemModel 또는 QAbstractItemModel
        header_name: 찾을 헤더 이름 (예: "주소", "담당자")
        
    Returns:
        int: 컬럼 인덱스 (0부터 시작), 없으면 -1
    """
    if not model:
        return -1
        
    for col in range(model.columnCount()):
        header_item = model.horizontalHeaderItem(col)
        if header_item and header_item.text() == header_name:
            return col
    return -1

def get_item_by_header(model, row, header_name):
    """
    헤더명으로 특정 행의 아이템을 가져옵니다.
    
    Args:
        model: QStandardItemModel 또는 QAbstractItemModel
        row: 행 인덱스
        header_name: 헤더 이름
        
    Returns:
        QStandardItem 또는 None
    """
    col = get_column_index_by_header(model, header_name)
    if col >= 0 and model:
        return model.item(row, col)
    return None

def get_text_by_header(model, row, header_name, default=""):
    """
    헤더명으로 특정 행의 텍스트를 가져옵니다.
    
    Args:
        model: QStandardItemModel 또는 QAbstractItemModel
        row: 행 인덱스
        header_name: 헤더 이름
        default: 기본값 (아이템이 없거나 텍스트가 없을 때)
        
    Returns:
        str: 텍스트 값
    """
    item = get_item_by_header(model, row, header_name)
    return item.text() if item else default

def set_text_by_header(model, row, header_name, text):
    """
    헤더명으로 특정 행의 텍스트를 설정합니다.
    
    Args:
        model: QStandardItemModel
        row: 행 인덱스
        header_name: 헤더 이름
        text: 설정할 텍스트
        
    Returns:
        bool: 성공 여부
    """
    item = get_item_by_header(model, row, header_name)
    if item:
        item.setText(str(text))
        return True
    return False

def get_all_headers(model):
    """
    모델의 모든 헤더 이름을 리스트로 반환합니다.
    
    Args:
        model: QStandardItemModel 또는 QAbstractItemModel
        
    Returns:
        list: 헤더 이름들의 리스트
    """
    if not model:
        return []
        
    headers = []
    for col in range(model.columnCount()):
        header_item = model.horizontalHeaderItem(col)
        headers.append(header_item.text() if header_item else f"Column_{col}")
    return headers

# 성능 최적화를 위한 헤더 캐시 클래스
class HeaderCache:
    """헤더-인덱스 매핑을 캐시하여 성능을 향상시킵니다."""
    
    def __init__(self):
        self._cache = {}
        self._model_id = None
        
    def get_column_index(self, model, header_name):
        """캐시된 헤더 인덱스를 반환합니다."""
        model_id = id(model)
        
        # 모델이 변경되었으면 캐시 초기화
        if self._model_id != model_id:
            self._cache.clear()
            self._model_id = model_id
            
        # 캐시에서 찾기
        if header_name in self._cache:
            return self._cache[header_name]
            
        # 캐시에 없으면 검색 후 캐시
        index = get_column_index_by_header(model, header_name)
        self._cache[header_name] = index
        return index
        
    def clear(self):
        """캐시를 초기화합니다."""
        self._cache.clear()
        self._model_id = None

# 전역 헤더 캐시 인스턴스
_global_header_cache = HeaderCache()

def get_column_index_cached(model, header_name):
    """캐시를 사용하여 헤더 인덱스를 빠르게 가져옵니다."""
    return _global_header_cache.get_column_index(model, header_name)

def get_item_by_header_cached(model, row, header_name):
    """캐시를 사용하여 헤더로 아이템을 빠르게 가져옵니다."""
    col = get_column_index_cached(model, header_name)
    if col >= 0 and model:
        return model.item(row, col)
    return None

def get_text_by_header_cached(model, row, header_name, default=""):
    """캐시를 사용하여 헤더로 텍스트를 빠르게 가져옵니다."""
    item = get_item_by_header_cached(model, row, header_name)
    return item.text() if item else default

# ============== 헤더 기반 헬퍼 함수들 끝 ==============