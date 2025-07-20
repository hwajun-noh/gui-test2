# ui_helpers.py - 상가 UI 이벤트 도우미 모듈
import logging
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush, QStandardItem, QFont

from mylist.constants import PENDING_COLOR, RE_AD_BG_COLOR, NEW_AD_BG_COLOR

# 로거 인스턴스
logger = logging.getLogger(__name__)

def update_row_background_color(logic_instance, row: int, pending_col: int = None):
    """
    '재광고' 상태를 기반으로 행의 배경색을 업데이트합니다.
    pending_col로 지정된 셀은 PENDING_COLOR를 유지합니다.
    """
    model = logic_instance.mylist_shop_model
    if not model: 
        return

    model.blockSignals(True)  # 신호 차단
    try:
        re_ad_col_index = -1
        try:
            headers = [model.horizontalHeaderItem(c).text() for c in range(model.columnCount())]
            re_ad_col_index = headers.index("재광고")
        except (ValueError, IndexError):
            logger.warning("[update_row_background_color] '재광고' column not found.")
            return

        re_ad_item = model.item(row, re_ad_col_index)
        is_re_ad = (re_ad_item.text() == "재광고") if re_ad_item else False
        default_row_bg = RE_AD_BG_COLOR if is_re_ad else NEW_AD_BG_COLOR

        for col in range(model.columnCount()):
            # 방금 변경된 열은 건너뜀 (PENDING_COLOR 유지)
            if col == pending_col:
                continue

            item = model.item(row, col)
            if item:
                # 아이템 자체가 대기 중인지 확인 (예: 직접 변경됨)
                # 해당 셀에 대한 대기 중인 변경 사항을 나타내는 PENDING_COLOR
                current_bg = item.background().color()
                if current_bg != PENDING_COLOR:
                     item.setBackground(default_row_bg)
                # Else: 셀 자체가 수정된 경우 PENDING_COLOR 유지

    finally:
        model.blockSignals(False)  # 신호 차단 해제

    logger.debug(f"[update_row_background_color] Updated background for row {row} (excluding pending col {pending_col}). Base color: {default_row_bg.name()}")

def mark_row_as_pending_deletion(model, row_index):
    """지정된 행의 스타일을 '삭제 예정'으로 변경합니다. (최적화 버전)"""
    if not model: 
        return
        
    # 배경색 및 폰트 스타일 미리 설정
    delete_bg_color = QColor("#DDDDDD")
    delete_font = QFont()
    delete_font.setStrikeOut(True)
    
    # 한 번에 행 전체 처리 (불필요한 루프 제거)
    col_count = model.columnCount()
    for col in range(col_count):
        item = model.item(row_index, col)
        if not item:
            # 아이템이 없는 경우 생성 (예: 빈 셀)
            item = QStandardItem()
            model.setItem(row_index, col, item)
            
        # 배경색, 폰트, 삭제 플래그 한 번에 설정
        item.setBackground(delete_bg_color)
        item.setFont(delete_font)
        item.setData(True, Qt.UserRole + 20)

def restore_row_color_after_save(model, row_indexes, is_re_ad=False):
    """저장 후 행 배경색을 원래 상태로 복원합니다."""
    if not model:
        return
        
    for row in row_indexes:
        if row < 0 or row >= model.rowCount():
            continue
            
        # 행의 '재광고' 상태 확인
        target_color = RE_AD_BG_COLOR if is_re_ad else NEW_AD_BG_COLOR
        
        # 행의 모든 셀 색상 복원
        for col in range(model.columnCount()):
            item = model.item(row, col)
            if item and item.background().color() == PENDING_COLOR:
                item.setBackground(target_color)