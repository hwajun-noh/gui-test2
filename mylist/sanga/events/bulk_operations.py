# bulk_operations.py - 대량 작업 관련 모듈
import logging
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItem
from PyQt5.QtWidgets import QMessageBox, QInputDialog

# 로거 인스턴스
logger = logging.getLogger(__name__)

def _bulk_change_manager_mylist_shop(logic_instance):
    """
    여러 선택된 셀의 담당자를 변경하는 대화 상자를 엽니다.
    일관된 처리를 위해 _process_item_change를 사용합니다.
    """
    # 함수 호출 확인 로그
    logger.critical("********** _bulk_change_manager_mylist_shop FUNCTION CALLED! **********")
    
    view = logic_instance.mylist_shop_view
    model = logic_instance.mylist_shop_model

    if not view or not model:
        return

    selected_indexes = view.selectedIndexes()
    selected_rows = set(idx.row() for idx in selected_indexes)

    if not selected_rows:
        QMessageBox.information(logic_instance.parent_app, "선택 없음", "담당자를 변경할 행을 선택하세요.")
        return

    manager_col_index = -1
    try:
        headers = [model.horizontalHeaderItem(c).text() for c in range(model.columnCount())]
        manager_col_index = headers.index("담당자")
    except (ValueError, IndexError):
        QMessageBox.warning(logic_instance.parent_app, "열 오류", "'담당자' 열을 찾을 수 없습니다.")
        return

    # 현재 담당자 이름 가져오기 (가능한 경우 내부 목록 사용, 그렇지 않으면 모델에서 수집)
    manager_names = []
    if hasattr(logic_instance.parent_app, 'manager_dropdown'):
        dropdown = logic_instance.parent_app.manager_dropdown
        manager_names = [dropdown.itemText(i) for i in range(dropdown.count())]
        if manager_names:
            logger.debug(f"Collected {len(manager_names)} managers from parent_app.manager_dropdown.")
        else:
            logger.warning("parent_app.manager_dropdown exists but is empty. Will try collecting from model.")
    else:
        logger.warning("parent_app.manager_dropdown attribute not found. Will try collecting from model.")

    # 대체로 모델에서 수집 시도 (parent_app.manager_dropdown에서 가져오지 못한 경우)
    if not manager_names:
        logger.debug("Collecting manager names from shop model as fallback.")
        # 모델에서 고유한 담당자 이름 수집
        for r in range(model.rowCount()):
            item = model.item(r, manager_col_index)
            if item and item.text():
                manager_name = item.text().strip()
                if manager_name and manager_name not in manager_names:
                    manager_names.append(manager_name)
    
    if not manager_names:
        manager_names = ["관리자"]  # 담당자를 찾을 수 없는 경우 기본값
    
    # 새 담당자 선택을 위한 대화 상자 표시
    new_manager, ok = QInputDialog.getItem(
        logic_instance.parent_app,
        "담당자 변경",
        "새 담당자 선택:",
        manager_names,
        0,
        False
    )
    
    if not ok or not new_manager:
        return
    
    # 중복 호출 방지를 위해 모델 신호 차단 후 일괄 처리
    logic_instance.mylist_shop_model.blockSignals(True)
    try:
        for row in selected_rows:
            item = model.item(row, manager_col_index)
            if item:
                item.setText(new_manager)
                try:
                    # 아이템 변경 이벤트에서 _process_item_change 함수 가져오기
                    from mylist.sanga.events.item_events import _process_item_change
                    _process_item_change(logic_instance, item, new_manager)
                except Exception as e_proc:
                    logger.error(f"_bulk_change_manager_mylist_shop: Error processing item change for row {row}: {e_proc}", exc_info=True)
        updated_count = len(selected_rows)
    finally:
        logic_instance.mylist_shop_model.blockSignals(False)
    
    if updated_count > 0:
        logger.info(f"Processed manager update for {updated_count} rows to '{new_manager}'.")
        QMessageBox.information(
            logic_instance.parent_app,
            "담당자 변경 완료",
            f"선택한 {updated_count}개 행의 담당자를 '{new_manager}'(으)로 변경했습니다.\n"
            f"(변경된 셀은 노란색으로 표시됩니다. 저장 버튼을 눌러 확정하세요)"
        )
        logic_instance.container._recalculate_manager_summary()

def _bulk_change_re_ad_mylist_shop(logic_instance):
    """
    여러 선택된 셀의 "재광고" 상태를 변경하는 대화 상자를 엽니다.
    일관된 처리를 위해 _process_item_change를 사용합니다.
    """
    view = logic_instance.mylist_shop_view
    model = logic_instance.mylist_shop_model

    if not view or not model:
        return

    selected_indexes = view.selectedIndexes()
    selected_rows = set(idx.row() for idx in selected_indexes)

    if not selected_rows:
        QMessageBox.information(logic_instance.parent_app, "선택 없음", "재광고 상태를 변경할 행을 선택하세요.")
        return

    re_ad_col_index = -1
    try:
        headers = [model.horizontalHeaderItem(c).text() for c in range(model.columnCount())]
        re_ad_col_index = headers.index("재광고")
    except (ValueError, IndexError):
        QMessageBox.warning(logic_instance.parent_app, "열 오류", "'재광고' 열을 찾을 수 없습니다.")
        return

    options = ["새광고", "재광고"]
    new_status, ok = QInputDialog.getItem(
        logic_instance.parent_app,
        "재광고 상태 변경",
        "새 상태 선택:",
        options,
        0,
        False
    )

    if not ok or not new_status:
        return

    # 중복 호출 방지를 위해 모델 신호 차단 후 일괄 처리
    logic_instance.mylist_shop_model.blockSignals(True)
    try:
        for row in selected_rows:
            item = model.item(row, re_ad_col_index)
            if item:
                item.setText(new_status)
                try:
                    # 아이템 변경 이벤트에서 _process_item_change 함수 가져오기
                    from mylist.sanga.events.item_events import _process_item_change
                    _process_item_change(logic_instance, item, new_status)
                except Exception as e_proc:
                    logger.error(f"_bulk_change_re_ad_mylist_shop: Error processing item change for row {row}: {e_proc}", exc_info=True)
        updated_count = len(selected_rows)
    finally:
        logic_instance.mylist_shop_model.blockSignals(False)
    
    if updated_count > 0:
        logger.info(f"Processed re_ad status update for {updated_count} rows to '{new_status}'.")
        QMessageBox.information(
            logic_instance.parent_app,
            "재광고 상태 변경 완료",
            f"선택한 {updated_count}개 행의 재광고 상태를 '{new_status}'(으)로 변경했습니다.\n"
            f"(변경된 셀은 노란색으로 표시됩니다. 저장 버튼을 눌러 확정하세요)"
        )
    
    # 재광고 상태가 변경되면 요약 정보 다시 계산
    logic_instance.container._recalculate_manager_summary()