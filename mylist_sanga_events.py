# mylist_sanga_events.py
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt, QModelIndex
from PyQt5.QtGui import QStandardItem, QColor, QFont
from PyQt5.QtWidgets import QMessageBox, QInputDialog, QTableView, QMenu, QAbstractItemView, QLineEdit, QComboBox
import logging

from dialogs import ImageSlideshowWindow, SearchDialogForShop, StatusChangeDialog
from mylist_constants import PENDING_COLOR, RE_AD_BG_COLOR, NEW_AD_BG_COLOR

def on_mylist_shop_item_changed(logic_instance, item: QStandardItem):
    """
    Handles the itemChanged signal from the shop model.
    Registers pending changes and applies background colors.
    Also updates pending additions for new rows.
    """
    # <<< 로그: 함수 진입 확인 >>>
    logic_instance.logger.critical(f"********** ENTERED on_mylist_shop_item_changed **********")
    logger = logic_instance.logger
    try:
        # <<< 로그: 초기 객체 유효성 검사 >>>
        if not item or not isinstance(item, QStandardItem) or not item.model():
            logger.warning(f"[itemChanged] Invalid item or model. Exiting.")
            return
        row = item.row()
        col = item.column()
        model = item.model()
        logger.info(f"[itemChanged] Item changed at Row={row}, Col={col}. Item text: '{item.text()}'")

        # <<< 추가 로그: ID 값 확인 >>>
        item0 = model.item(row, 0) # 0번 열 아이템 가져오기
        if not item0:
            logger.warning(f"[itemChanged] Could not get item at Row {row}, Col 0 to check IDs.")
            return
            
        real_id_val = item0.data(Qt.UserRole + 3)
        temp_id_val = item0.data(Qt.UserRole + 99)
        logger.info(f"[itemChanged] ID Check for Row {row}: RealID(UR+3)='{real_id_val}' (Type: {type(real_id_val)}), TempID(UR+99)='{temp_id_val}' (Type: {type(temp_id_val)})")
        
        # pending_manager 가져오기
        pending_manager = getattr(logic_instance, "pending_manager", None)
        if not pending_manager:
            pending_manager = getattr(logic_instance.container, "pending_manager", None)
            
        if not pending_manager:
            logger.error(f"[itemChanged] Cannot find pending_manager in logic_instance or container.")
            return
        
        # === 새로운 로직: 행 상태 확인 (실제 행 vs 임시 행) ===
        
        # 1. 처음 추가된 임시 행 (temp_id가 있고 real_id가 음수)
        if isinstance(real_id_val, int) and real_id_val < 0:
            logger.info(f"[itemChanged] Processing TEMPORARY ROW (real_id={real_id_val})")
            # 임시행은 이미 모델에 추가되어 있어야 함
            # pending_adds에 등록할지 확인(이미 있으면 추가 안함)
            pending_manager.ensure_shop_item_in_pending_adds(real_id_val, row)
            # 노란색 배경 설정 필요 없음 (행 추가 시 이미 설정됨)
            logger.critical(f"********** FINISHED on_mylist_shop_item_changed (Temp Row) for ({row}, {col}) **********")
            return
            
        # 2. 저장된 실제 행 (real_id가 양수)
        elif isinstance(real_id_val, int) and real_id_val > 0:
            logger.info(f"[itemChanged] Processing REAL ROW (id={real_id_val})")
            # 셀 변경 사항 등록
            pending_manager.set_shop_pending_update(real_id_val, row, col, item.text())
            
            # 변경된 셀에 노란색 배경 설정
            item.setBackground(PENDING_COLOR)
            logger.info(f"[itemChanged] Set PENDING_COLOR for real row {row} (ID: {real_id_val}) at Col: {col}")
            
            # 전체 행 업데이트 필요시 추가 로직
            try:
                # 행 전체 배경색 업데이트 함수 호출
                from mylist_sanga_events import update_row_background_color
                update_row_background_color(logic_instance, row, pending_col=col)
                logger.debug(f"[itemChanged] Called update_row_background_color for row {row}")
            except Exception as bg_err:
                logger.error(f"[itemChanged] Error updating row background: {bg_err}")
                
            logger.critical(f"********** FINISHED on_mylist_shop_item_changed (Real Row) for ({row}, {col}) **********")
            return
            
        # 3. 알 수 없는 상태의 행 (디버깅용)
        else:
            logger.warning(f"[itemChanged] Row {row} has UNKNOWN ID STATUS. real_id={real_id_val}, temp_id={temp_id_val}")
            logger.critical(f"********** FINISHED on_mylist_shop_item_changed (Unknown Row) for ({row}, {col}) **********")
            return

    except Exception as e:
        import traceback
        logger.error(f"[itemChanged] Unexpected error: {e}\n{traceback.format_exc()}")
        logic_instance.logger.critical(f"********** FINISHED on_mylist_shop_item_changed (ERROR) **********")

def on_mylist_shop_view_double_clicked(logic_instance, index: QModelIndex):
    """
    Handles double-click on shop view items.
    Shows a slideshow for the "주소" column, or activates cell editing for other columns.
    """
    model = logic_instance.mylist_shop_model
    view = logic_instance.mylist_shop_view
    
    if not model or not view or not index.isValid():
        return
    
    column = index.column()
    row = index.row()
    
    # Get column header
    col_header = model.horizontalHeaderItem(column).text() if model.horizontalHeaderItem(column) else ""
    
    # Special handling for address column (show slideshow)
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
                    slideshow = ImageSlideshowWindow(image_files, parent=logic_instance.parent_app)
                    slideshow.exec_()
                else:
                    print(f"[WARNING] No image files found in folder: {folder_path}")
                    QMessageBox.information(
                        logic_instance.parent_app,
                        "이미지 없음",
                        f"해당 폴더에 이미지 파일이 없습니다:\n{folder_path}"
                    )
            except Exception as e:
                print(f"[ERROR] Error showing slideshow: {e}")
                QMessageBox.warning(
                    logic_instance.parent_app,
                    "이미지 로딩 오류",
                    f"사진 폴더를 열 수 없습니다: {folder_path}\n오류: {e}",
                )

def on_mylist_shop_current_changed(logic_instance, current: QModelIndex, previous: QModelIndex):
    """
    Handles when the current selected cell changes in the shop view.
    Triggers cross-tab filtering based on the selected address.
    """
    logic_instance.logger.critical("<<<<< on_mylist_shop_current_changed SLOT CALLED! >>>>>") 
    logic_instance.logger.debug(f"on_mylist_shop_current_changed: Current index changed. Row: {current.row()}") # 로그 추가
    if not current.isValid():
        logic_instance.logger.debug("on_mylist_shop_current_changed: Invalid index, returning.") # 로그 추가
        return

    view = logic_instance.mylist_shop_view
    model = logic_instance.mylist_shop_model
    parent_app = logic_instance.parent_app

    if not view or not model or not parent_app:
        logic_instance.logger.warning("on_mylist_shop_current_changed: View, model, or parent_app not available.")
        return

    row = current.row()

    # Find the '주소' column index
    addr_col_idx = -1
    try:
        # 모델 헤더 가져오기 시도 (주의: 모델이 아직 완전히 로드되지 않았을 수 있음)
        if model.columnCount() > 0:
            headers = [model.horizontalHeaderItem(c).text() for c in range(model.columnCount())]
            addr_col_idx = headers.index("주소")
        else:
            logic_instance.logger.warning("on_mylist_shop_current_changed: Model column count is 0, cannot find '주소' column.")
            return # 헤더를 찾을 수 없으면 진행 불가
            
    except (ValueError, AttributeError, Exception) as e: # 더 넓은 범위의 예외 처리
        logic_instance.logger.error(f"on_mylist_shop_current_changed: Error finding '주소' column index: {e}", exc_info=True)
        return

    # Get the address item and text
    addr_item = model.item(row, addr_col_idx)
    if not addr_item:
        logic_instance.logger.warning(f"on_mylist_shop_current_changed: Address item not found for row {row}, column {addr_col_idx}.")
        return

    address_string = addr_item.text()
    logic_instance.logger.info(f"on_mylist_shop_current_changed: Extracted address: '{address_string}'") # 로그 추가

    # Call the main app's update function
    if hasattr(parent_app, 'update_selection_from_manager_check'):
        logic_instance.logger.info(f"on_mylist_shop_current_changed: Calling parent_app.update_selection_from_manager_check.")
        try:
            # 직접 호출 (UI 스레드에서 발생한 시그널이므로 안전할 것으로 예상)
            parent_app.update_selection_from_manager_check(address_string)
            logic_instance.logger.info("on_mylist_shop_current_changed: Call to update_selection_from_manager_check completed.")
        except Exception as call_e:
            logic_instance.logger.error(f"on_mylist_shop_current_changed: Error calling update_selection_from_manager_check: {call_e}", exc_info=True)
    else:
        logic_instance.logger.error("on_mylist_shop_current_changed: parent_app does not have update_selection_from_manager_check method.")

def on_shop_header_section_clicked(logic_instance, logical_index: int):
    """
    Handles clicks on the table header.
    Always selects the entire column. Sorting functionality is disabled.
    """
    view = logic_instance.mylist_shop_view
    if not view:
        return
    
    # 항상 전체 열 선택 (Shift 키 상태 무시)
    select_entire_column(logic_instance, view, logical_index)
    
    # 정렬 기능 비활성화 상태 유지
    if view.isSortingEnabled():
        view.setSortingEnabled(False)
        logic_instance.logger.debug(f"Header section {logical_index} clicked: Sorting disabled to maintain ID order")

def select_entire_column(logic_instance, table_view: QTableView, col_index: int):
    """Selects the entire column of the given index."""
    table_view.selectColumn(col_index)

def clear_selected_cells(logic_instance, table_view: QTableView):
    """
    Clears the content of the selected cells.
    Does not modify the first column (address) or certain essential columns.
    """
    indexes = table_view.selectedIndexes()
    if not indexes:
        return
    
    model = table_view.model()
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
    for idx in indexes:
        col = idx.column()
        if col not in protected_columns:
            model.setItem(idx.row(), col, QStandardItem(""))

def show_search_dialog_for_shop(logic_instance):
    """Shows the search dialog for the shop table."""
    dialog = SearchDialogForShop(logic_instance.parent_app, logic_instance.mylist_shop_model, logic_instance.mylist_shop_view)
    dialog.exec_()

def _mylist_shop_context_menu(logic_instance, pos):
    """
    Creates and shows the context menu for the shop table.
    Offers options for copying, deleting, changing manager, etc.
    """
    view = logic_instance.mylist_shop_view
    if not view:
        return
    
    index = view.indexAt(pos)
    if not index.isValid():
        return
    
    menu = QMenu(view)
    act_copy = menu.addAction("복사 후 추가")
    
    # Only enable delete if at least one cell is selected
    act_delete = menu.addAction("삭제")
    act_delete.setEnabled(len(view.selectedIndexes()) > 0)
    
    menu.addSeparator()
    
    act_change_manager = menu.addAction("담당자 변경")
    act_change_re_ad = menu.addAction("재광고 여부 변경")
    menu.addSeparator()
    
    act_completed = menu.addAction("상태 변경(계약완료)")
    
    action = menu.exec_(view.viewport().mapToGlobal(pos))
    
    if action == act_copy:
        # Copy the row under the cursor
        logic_instance.copy_mylist_shop_row(index.row())
    elif action == act_delete:
        logic_instance.delete_selected_mylist_shop_rows()
    elif action == act_change_manager:
        logic_instance._bulk_change_manager_mylist_shop()
    elif action == act_change_re_ad:
        logic_instance._bulk_change_re_ad_mylist_shop()
    elif action == act_completed:
        logic_instance.on_mylist_shop_change_status(pos)

def on_mylist_shop_change_status(logic_instance, pos):
    """
    Opens the status change dialog and processes the status change.
    """
    view = logic_instance.mylist_shop_view
    model = logic_instance.mylist_shop_model
    
    if not view or not model:
        return
    
    # Get selected rows (or row under cursor if none explicitly selected)
    selected_indexes = view.selectedIndexes()
    
    if not selected_indexes:
        index = view.indexAt(pos)
        if index.isValid():
            selected_indexes = [index]
    
    if not selected_indexes:
        QMessageBox.information(logic_instance.parent_app, "선택 없음", "상태를 변경할 행을 선택하세요.")
        return
    
    # Get unique rows from selected indexes
    selected_rows = set(idx.row() for idx in selected_indexes)
    
    # Ensure the first column is valid for status change
    valid_ids = []
    rows_to_remove = []
    
    for row in selected_rows:
        item0 = model.item(row, 0)
        if not item0:
            continue
        
        record_id = item0.data(Qt.UserRole + 3)
        
        # Only process real DB rows (positive IDs), not temporary rows
        if isinstance(record_id, int) and record_id > 0:
            valid_ids.append(record_id)
            rows_to_remove.append(row)
    
    if not valid_ids:
        QMessageBox.information(
            logic_instance.parent_app,
            "대상 없음",
            "상태 변경은 저장된 행에만 적용 가능합니다.\n추가한 행을 먼저 저장해주세요."
        )
        return
    
    # --- 변경: StatusChangeDialog 호출 시 all_managers 전달 --- 
    all_managers = []
    if hasattr(logic_instance.parent_app, 'manager_list'):
        all_managers = logic_instance.parent_app.manager_list
    if not all_managers:
        all_managers = [logic_instance.current_manager] # Fallback if list is empty
        logic_instance.logger.warning("Could not find manager list in parent_app, using current manager only for StatusChangeDialog.")

    dialog = StatusChangeDialog(logic_instance.parent_app, "상가", all_managers=all_managers)
    # --- 변경 끝 ---
    result = dialog.exec_()
    
    if result != QMessageBox.Accepted:
        return
    
    status_data = dialog.get_values()
    
    if not status_data.get("status_value"):
        QMessageBox.warning(logic_instance.parent_app, "입력 오류", "상태값이 선택되지 않았습니다.")
        return
    
    # Submit status change task via container
    payload = {
        "ids": valid_ids,
        "type": "shop",
        "status": status_data.get("status_value", ""),
        "status_date": status_data.get("selected_date", ""),
        "status_memo": status_data.get("memo", ""),
        "manager": logic_instance.current_manager
    }
    
    logic_instance.container.submit_status_change_task(payload, rows_to_remove, "shop")

def _bulk_change_manager_mylist_shop(logic_instance):
    """
    Opens a dialog to change the manager for multiple selected cells.
    Uses _process_item_change for consistent handling.
    """
    # <<< 로그 추가: 함수 호출 확인 >>>
    logic_instance.logger.critical("********** _bulk_change_manager_mylist_shop FUNCTION CALLED! **********")
    # <<< 로그 추가 끝 >>>
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

    # Get the current manager names (use internal list if available, otherwise collect from model)
    manager_names = []
    if hasattr(logic_instance.parent_app, 'manager_dropdown'):
        dropdown = logic_instance.parent_app.manager_dropdown
        manager_names = [dropdown.itemText(i) for i in range(dropdown.count())]
        if manager_names:
            logic_instance.logger.debug(f"Collected {len(manager_names)} managers from parent_app.manager_dropdown.")
        else:
            logic_instance.logger.warning("parent_app.manager_dropdown exists but is empty. Will try collecting from model.")
    else:
        logic_instance.logger.warning("parent_app.manager_dropdown attribute not found. Will try collecting from model.")

    # parent_app.manager_dropdown 에서 가져오지 못한 경우 모델에서 수집 시도 (Fallback)
    if not manager_names:
        logic_instance.logger.debug("Collecting manager names from shop model as fallback.")
        # Collect unique manager names from the model
        for r in range(model.rowCount()):
            item = model.item(r, manager_col_index)
            if item and item.text():
                manager_name = item.text().strip()
                if manager_name and manager_name not in manager_names:
                    manager_names.append(manager_name)
    
    if not manager_names:
        manager_names = ["관리자"]  # Default if no managers found
    
    # Show dialog to select new manager
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
    
    # 모델 신호 차단 후 일괄 처리 → 중복 호출 방지
    logic_instance.mylist_shop_model.blockSignals(True)
    try:
        for row in selected_rows:
            item = model.item(row, manager_col_index)
            if item:
                item.setText(new_manager)
                try:
                    _process_item_change(logic_instance, item, new_manager)
                except Exception as e_proc:
                    logic_instance.logger.error(f"_bulk_change_manager_mylist_shop: Error processing item change for row {row}: {e_proc}", exc_info=True)
        updated_count = len(selected_rows)
    finally:
        logic_instance.mylist_shop_model.blockSignals(False)
    
    if updated_count > 0:
        logic_instance.logger.info(f"Processed manager update for {updated_count} rows to '{new_manager}'.")
        QMessageBox.information(
            logic_instance.parent_app,
            "담당자 변경 완료", # 메시지 수정
            f"선택한 {updated_count}개 행의 담당자를 '{new_manager}'(으)로 변경했습니다.\n"
            f"(변경된 셀은 노란색으로 표시됩니다. 저장 버튼을 눌러 확정하세요)"
        )
        logic_instance.container._recalculate_manager_summary()

def _bulk_change_re_ad_mylist_shop(logic_instance):
    """
    Opens a dialog to change the "재광고" status for multiple selected cells.
    Uses _process_item_change for consistent handling.
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

    # 모델 신호 차단 후 일괄 처리 → 중복 호출 방지
    logic_instance.mylist_shop_model.blockSignals(True)
    try:
        for row in selected_rows:
            item = model.item(row, re_ad_col_index)
            if item:
                item.setText(new_status)
                try:
                    _process_item_change(logic_instance, item, new_status)
                except Exception as e_proc:
                    logic_instance.logger.error(f"_bulk_change_re_ad_mylist_shop: Error processing item change for row {row}: {e_proc}", exc_info=True)
        updated_count = len(selected_rows)
    finally:
        logic_instance.mylist_shop_model.blockSignals(False)
    
    if updated_count > 0:
        logic_instance.logger.info(f"Processed re_ad status update for {updated_count} rows to '{new_status}'.")
        QMessageBox.information(
            logic_instance.parent_app,
            "재광고 상태 변경 완료", # 메시지 수정
            f"선택한 {updated_count}개 행의 재광고 상태를 '{new_status}'(으)로 변경했습니다.\n"
            f"(변경된 셀은 노란색으로 표시됩니다. 저장 버튼을 눌러 확정하세요)"
        )

def mark_row_as_pending_deletion(model, row_index):
    """지정된 행의 스타일을 '삭제 예정'으로 변경합니다 (최적화 버전)."""
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

def delete_selected_mylist_shop_rows(logic_instance):
    """
    선택된 행을 '삭제 예정' 상태로 표시하고, pending changes에 기록합니다.
    (실제 행 삭제는 '저장' 시 수행됨) - 최적화 버전
    """
    view = logic_instance.mylist_shop_view
    model = logic_instance.mylist_shop_model
    pending_manager = logic_instance.container.pending_manager
    
    if not view or not model or not pending_manager:
        logic_instance.logger.error("delete_selected_mylist_shop_rows: View, model, or pending_manager is None.")
        return
    
    # Get selected indexes and determine unique rows involved
    selected_indexes = view.selectedIndexes()
    if not selected_indexes: return 
    involved_rows = set(idx.row() for idx in selected_indexes)
    if not involved_rows: return
        
    # Full row deletion confirmation
    reply = QMessageBox.question(
        logic_instance.parent_app,
        "행 삭제 확인",
        f"선택한 셀이 포함된 {len(involved_rows)}개 행 전체를 삭제 상태로 표시하시겠습니까?", 
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No
    )
    if reply != QMessageBox.Yes: return
    
    # 모든 처리를 모델 시그널 차단 상태에서 수행 (성능 개선)
    model.blockSignals(True)
    try:
        # Process rows 
        rows_to_mark = sorted(list(involved_rows))
        record_ids = []
        
        # 첫 번째 루프: 모든 행의 ID 수집 (ID가 있는 경우)
        for row in rows_to_mark:
            item0 = model.item(row, 0)
            if item0:
                record_id = item0.data(Qt.UserRole + 3)
                if record_id is not None:
                    record_ids.append((row, record_id))

        # 두 번째 루프: 모든 행 시각적으로 표시
        logic_instance.logger.info(f"마크 시작: {len(rows_to_mark)}개 행 삭제 표시 중...")
        for row in rows_to_mark:
            mark_row_as_pending_deletion(model, row)

        # 세 번째 루프: 서버에 삭제 표시할 ID 등록 (pending_manager)
        for row, record_id in record_ids:
            pending_manager.mark_shop_row_for_deletion(record_id)
            logic_instance.logger.debug(f"Marked shop row for deletion via pending manager: ID={record_id}")
    
    finally:
        model.blockSignals(False)
        
    marked_count = len(rows_to_mark)
    logic_instance.logger.info(f"{marked_count}개 행을 삭제 예정 상태로 표시했습니다.")
    logic_instance.container._recalculate_manager_summary() # Update summary after marking

def handle_commit_data(logic_instance, editor_widget):
    """
    Handles the commitData signal from the item delegate (direct cell editing).
    Uses _process_item_change for consistent handling.
    """
    logger = logic_instance.logger
    view = logic_instance.mylist_shop_view
    model = logic_instance.mylist_shop_model

    if not view or not model:
        logger.warning("[handle_commit_data] View or model is None.")
        return

    current_index = view.currentIndex()
    if not current_index.isValid():
        # 편집기가 닫힌 후 currentIndex가 유효하지 않은 경우가 간혹 발생 가능
        # 이 경우, editor_widget 에서 model index를 직접 얻어오는 시도 필요
        logger.warning("[handle_commit_data] Invalid current index from view after editor closed.")
        # TODO: editor_widget에서 인덱스를 얻어오는 로직 추가 (필요시)
        return

    logger.info(f"[handle_commit_data] CommitData signal received for editor: {type(editor_widget)}. Current index: Row={current_index.row()}, Col={current_index.column()}")

    new_value = ""
    try:
        if isinstance(editor_widget, QLineEdit):
            new_value = editor_widget.text()
        elif isinstance(editor_widget, QComboBox):
             new_value = editor_widget.currentText()
        else:
            item_fallback = model.itemFromIndex(current_index)
            if item_fallback: new_value = item_fallback.text()
            logger.warning(f"Unhandled editor type: {type(editor_widget)}. Falling back to model value.")
        # <<< 로그 추가: 가져온 값 명확히 확인 >>>
        logger.info(f"[handle_commit_data] ===> Captured new value: [{repr(new_value)}] <===") # repr() 사용
        # <<< 로그 추가 끝 >>>
    except Exception as e_get_val:
        logger.error(f"Error getting value from editor_widget: {e_get_val}", exc_info=True)
        item_fallback = model.itemFromIndex(current_index)
        if item_fallback: new_value = item_fallback.text()

    item = model.itemFromIndex(current_index)
    if not item:
         logger.warning(f"[handle_commit_data] Could not get item from model for index Row={current_index.row()}, Col={current_index.column()}.")
         return

    # <<< 수정: 중앙 처리 함수 호출 >>>
    # _process_item_change(logic_instance, item, new_value)

    # <<< 로그 추가: 처리 후 모델 값 확인 >>>
    try:
        current_text_after = item.text()
        logger.info(f"[handle_commit_data] ===> Text in model AFTER _process_item_change: [{repr(current_text_after)}] <===") # repr() 사용
    except Exception as e_log_after:
        logger.error(f"[handle_commit_data] Error logging text after process: {e_log_after}")
    # <<< 로그 추가 끝 >>>

    logger.info(f"[handle_commit_data] Finished processing for Row={current_index.row()}, Col={current_index.column()}.")

def _process_item_change(logic_instance, item: QStandardItem, new_value: str):
    """
    Central function to handle item changes (from direct edit or bulk actions).
    Registers pending changes and applies background colors according to PRD.
    """
    logger = logic_instance.logger
    model = item.model()
    if not model:
        logger.warning("[_process_item_change] Item has no model.")
        return

    row = item.row()
    col = item.column()

    # <<< 로그 추가: 컬럼 헤더 및 매핑 딕셔너리 확인 >>>
    col_header = "Unknown"
    column_map = {}
    try:
        if col < model.columnCount():
            header_item = model.horizontalHeaderItem(col)
            if header_item:
                 col_header = header_item.text()
        if hasattr(logic_instance.parent_app, 'COLUMN_MAP_MYLIST_SHOP_DISPLAY_TO_DB'):
            column_map = logic_instance.parent_app.COLUMN_MAP_MYLIST_SHOP_DISPLAY_TO_DB
        logger.info(f"[_process_item_change] CHECKING - Row={row}, Col Header='{col_header}', Column Map Contents: {column_map}")
    except Exception as e_check:
        logger.error(f"[_process_item_change] Error checking header/map: {e_check}")
    # <<< 로그 추가 끝 >>>

    if logic_instance.mylist_shop_loading:
        logger.debug("[_process_item_change] Ignored during loading.")
        return

    container = logic_instance.container
    if not container:
        logger.warning("[_process_item_change] Container is None.")
        return

    item0 = model.item(row, 0)
    if not item0:
        logger.warning(f"[_process_item_change] Could not get item0 (column 0) for row {row}.")
        return

    record_id = item0.data(Qt.UserRole + 3)
    if record_id is None:
        # Handle newly added rows (negative temp ID) or other issues
        temp_id = item0.data(Qt.UserRole + 99) # Assuming temp ID is stored here
        if temp_id and isinstance(temp_id, int) and temp_id < 0:
             logger.debug(f"[_process_item_change] Processing change for new row (Temp ID={temp_id}), Row={row}, Col={col}.")
             # New rows are handled differently by pending_manager (add_pending_shop_addition)
             # We might need separate logic here, or rely on pending_manager internal handling
             # For now, just apply background color
             item.setBackground(PENDING_COLOR)
             update_row_background_color(logic_instance, row, pending_col=col)
             return # Skip DB update registration for new rows here
        else:
            logger.warning(f"[_process_item_change] Record ID is None and not a new row for Row={row}. Cannot process change.")
            return

    logger.debug(f"[_process_item_change] Processing change for Row={row}, Col='{col_header}', ID={record_id}. New value: '{new_value}'")

    if isinstance(record_id, int) and record_id > 0:
        pending_manager = logic_instance.container.pending_manager
        if not pending_manager:
             logger.error(f"[_process_item_change] Cannot register pending update for ID {record_id}: pending_manager not found.")
             return

        db_field = logic_instance.parent_app.COLUMN_MAP_MYLIST_SHOP_DISPLAY_TO_DB.get(col_header)
        needs_update = False

        # <<< 로그 추가: db_field 확인 (값 포함) >>>
        if col_header == "담당자":
            logger.info(f"[_process_item_change] Handling '담당자' column. Looked up DB field for '{col_header}': {db_field}")
        # <<< 로그 추가 끝 >>>

        if db_field:
            update_payload = {
                "id": record_id,
                db_field: new_value
            }
            # <<< 로그 강화: pending_manager 호출 확인 (값 타입 포함) >>>
            payload_repr = repr(update_payload) # repr 사용으로 타입 명확히
            logger.info(f"[_process_item_change] Calling pending_manager.add_pending_shop_update with payload: {payload_repr}")
            # <<< 로그 강화 끝 >>>
            pending_manager.add_pending_shop_update(update_payload)
            logger.debug(f"[_process_item_change] Registered pending update via manager for ID {record_id}: {{ {db_field}: '{new_value}' }}")
            needs_update = True

        elif col_header == "재광고":
            new_status_value = "Y" if new_value == "재광고" else "N"
            update_payload = {
                 "id": record_id,
                 "re_ad_yn": new_status_value
            }
            # <<< 로그 강화: pending_manager 호출 확인 (값 타입 포함) >>>
            payload_repr = repr(update_payload) # repr 사용
            logger.info(f"[_process_item_change] Calling pending_manager.add_pending_shop_update for '재광고' with payload: {payload_repr}")
            # <<< 로그 강화 끝 >>>
            pending_manager.add_pending_shop_update(update_payload)
            logger.debug(f"[_process_item_change] Registered pending update for 재광고 column: ID={record_id}, Value={new_status_value}")
            needs_update = True

        elif col_header != "주소": # 주소 컬럼은 보통 직접 수정하지 않음
             logger.warning(f"[_process_item_change] No DB field mapping for header '{col_header}'. Update not registered for ID {record_id}.")

        if needs_update:
            # 1. Set PENDING_COLOR for the changed cell
            item.setBackground(PENDING_COLOR)
            logger.debug(f"[_process_item_change] Set background to PENDING_COLOR for ({row}, {col})")

            # 2. Update the rest of the row's background based on '재광고' status
            update_row_background_color(logic_instance, row, pending_col=col) # <<< 행 전체 배경색 업데이트 호출

    elif isinstance(record_id, int) and record_id < 0: # 임시 ID 처리 (새 행)
        # 새 행의 값 변경은 pending_manager의 'additions' 딕셔너리에서 처리되어야 함
        # 여기서는 배경색만 처리
        item.setBackground(PENDING_COLOR)
        update_row_background_color(logic_instance, row, pending_col=col)
        logger.debug(f"[_process_item_change] Applied PENDING_COLOR for new row change (Temp ID={record_id}), Row={row}, Col='{col_header}'.")

    else:
        logger.warning(f"[_process_item_change] Invalid record_id type ({type(record_id)}) or value for Row={row}. Skipping update registration and coloring.")

    # <<< 로그 추가: 함수 완료 확인 >>>
    logger.info(f"[_process_item_change] ===> Function finished for ({row}, {col}), New Value: '{new_value}' <===")
    # <<< 로그 추가 끝 >>>

# <<< 수정: 행 배경색 업데이트 헬퍼 함수 >>>
def update_row_background_color(logic_instance, row: int, pending_col: int = None):
    """
    Updates the background color of a row based on the '재광고' status.
    The cell specified by pending_col keeps its PENDING_COLOR.
    """
    model = logic_instance.mylist_shop_model
    if not model: return

    model.blockSignals(True)  # <<< 시그널 차단
    try:
        re_ad_col_index = -1
        try:
            headers = [model.horizontalHeaderItem(c).text() for c in range(model.columnCount())]
            re_ad_col_index = headers.index("재광고")
        except (ValueError, IndexError):
            logic_instance.logger.warning("[update_row_background_color] '재광고' column not found.")
            return

        re_ad_item = model.item(row, re_ad_col_index)
        is_re_ad = (re_ad_item.text() == "재광고") if re_ad_item else False
        default_row_bg = RE_AD_BG_COLOR if is_re_ad else NEW_AD_BG_COLOR

        for col in range(model.columnCount()):
            # Skip the column that was just changed (it should remain PENDING_COLOR)
            if col == pending_col:
                continue

            item = model.item(row, col)
            if item:
                # Check if the item itself is pending (e.g., changed directly)
                # Assuming PENDING_COLOR indicates a pending change for that specific cell
                current_bg = item.background().color()
                if current_bg != PENDING_COLOR:
                     item.setBackground(default_row_bg)
                # Else: Keep the PENDING_COLOR if the cell itself was modified

    finally:
        model.blockSignals(False) # <<< 시그널 차단 해제

    logic_instance.logger.debug(f"[update_row_background_color] Updated background for row {row} (excluding pending col {pending_col}). Base color: {default_row_bg.name()}")
# <<< 추가 끝 >>>