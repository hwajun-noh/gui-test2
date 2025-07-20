"""
마이리스트 상가 선택 관련 이벤트 처리 모듈

이 모듈은 테이블 셀 선택과 관련된 함수들을 제공합니다.
"""

import logging
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItem
from PyQt5.QtWidgets import QTableView

logger = logging.getLogger(__name__)

def select_entire_column(logic_instance, table_view: QTableView, col_index: int):
    """Selects the entire column of the given index."""
    table_view.selectColumn(col_index)

def clear_selected_cells(logic_instance, table_view: QTableView):
    """
    Clears the content of the selected cells.
    Does not modify the first column (address) or certain essential columns.
    """
    if not table_view:
        logger.warning("clear_selected_cells: table_view is None")
        return
        
    indexes = table_view.selectedIndexes()
    if not indexes:
        logger.debug("clear_selected_cells: No cells selected")
        return
    
    model = table_view.model()
    if not model:
        logger.warning("clear_selected_cells: model is None")
        return
        
    protected_columns = [0]  # First column (Address) is protected
    
    # Find indices of protected columns by header text
    for c in range(model.columnCount()):
        header_item = model.horizontalHeaderItem(c)
        if header_item:
            header_text = header_item.text()
            if header_text in ["주소", "재광고"]:  # Add other protected headers if needed
                if c not in protected_columns:
                    protected_columns.append(c)
    
    # Clear cells that are not in protected columns
    cleared_count = 0
    for idx in indexes:
        col = idx.column()
        if col not in protected_columns:
            model.setItem(idx.row(), col, QStandardItem(""))
            cleared_count += 1
    
    logger.info(f"clear_selected_cells: Cleared {cleared_count} cells (skipped {len(indexes) - cleared_count} protected cells)") 