import time
import requests
import json
import logging
from datetime import datetime

from PyQt5.QtCore import QObject, QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtGui import QColor, QStandardItem

from mylist_constants import PENDING_COLOR, RE_AD_BG_COLOR, NEW_AD_BG_COLOR

class MyListSaveHandler(QObject):
    """Handles auto-saving and manual saving logic for MyList tabs."""

    cleanup_needed = pyqtSignal()

    def __init__(self, parent_app, container, pending_manager, sanga_logic, oneroom_logic, server_info, user_info, parent=None):
        super().__init__(parent)
        self.parent_app = parent_app # MainApplication instance
        self.container = container # MyListContainer instance (for calling summary recalc)
        self.pending_manager = pending_manager
        self.sanga_logic = sanga_logic
        self.oneroom_logic = oneroom_logic
        self.server_host = server_info['host']
        self.server_port = server_info['port']
        self.current_manager = user_info['manager']
        self.current_role = user_info['role']
        
        self.logger = logging.getLogger(__name__)

        # Auto-save related
        self.last_autosave_time = time.time()
        self.auto_save_interval = 30  # seconds
        self.autosave_timer = None
        self.is_saving = False # Flag to prevent concurrent saves
        
        # 수동 저장 후 자동 저장 방지를 위한 시간 설정
        self.last_manual_save_time = 0  # 마지막 수동 저장 시간
        self.manual_save_cooldown = 10  # 수동 저장 후 자동 저장을 건너뛸 시간(초)

        self.logger.info("MyListSaveHandler initialized.")

    def start_auto_save_timer(self):
        """Starts the auto-save timer."""
        if not self.autosave_timer:
            self.logger.info("[Timer] Creating new auto-save timer")
            self.autosave_timer = QTimer(self.parent_app) # Timer needs a parent QObject
            self.autosave_timer.setInterval(self.auto_save_interval * 1000)
            self.autosave_timer.timeout.connect(self._trigger_auto_save)
        if not self.autosave_timer.isActive():
            self.logger.info(f"[Timer] Starting auto-save timer (interval: {self.auto_save_interval}s)")
            self.autosave_timer.start()
            self.logger.debug(f"[Timer] Auto-save timer started: {self.autosave_timer.isActive()}")

    def stop_auto_save_timer(self):
        """Stops the auto-save timer."""
        if self.autosave_timer and self.autosave_timer.isActive():
            self.logger.info("[Timer] Stopping auto-save timer")
            self.autosave_timer.stop()
            self.logger.debug(f"[Timer] Auto-save timer stopped: {not self.autosave_timer.isActive()}")

    # --- Saving Logic ---

    def _trigger_auto_save(self):
         """Called by the QTimer to initiate auto-save if changes exist or UI cleanup is needed."""
         if self.is_saving:
              self.logger.debug("[AutoSave] Previous save/cleanup still in progress, skipping...")
              return
         
         # 수동 저장 후 일정 시간 내에 자동 저장 방지
         current_time = time.time()
         time_since_manual_save = current_time - self.last_manual_save_time
         if time_since_manual_save < self.manual_save_cooldown:
              self.logger.debug(f"[AutoSave] Skipping auto-save - manual save performed {time_since_manual_save:.1f} seconds ago (cooldown: {self.manual_save_cooldown}s)")
              if hasattr(self.sanga_logic, 'autosave_status_label') and self.sanga_logic.autosave_status_label:
                   self.sanga_logic.autosave_status_label.setText(f"자동 저장: 대기 중 (수동 저장 후 {self.manual_save_cooldown - time_since_manual_save:.0f}초)")
                   self.sanga_logic.autosave_status_label.setStyleSheet("color: gray; font-style: italic;")
              return

         has_pending = self.pending_manager.has_pending_changes()
         needs_ui_cleanup = self._ui_has_rows_marked_for_deletion()

         if has_pending:
              self.is_saving = True
              if hasattr(self.sanga_logic, 'autosave_status_label') and self.sanga_logic.autosave_status_label:
                   self.sanga_logic.autosave_status_label.setText("자동 저장: 저장 중...")
                   self.sanga_logic.autosave_status_label.setStyleSheet("color: orange; font-style: italic;")
                   QApplication.processEvents()
              
              self.logger.info("[AutoSave] Starting background save task...")
              future = self.parent_app.executor.submit(self._bg_auto_save_all_changes)
              future.add_done_callback(self._on_auto_save_completed)
         
         elif needs_ui_cleanup: # No pending changes, but UI needs cleanup
              self.is_saving = True # Prevent concurrent cleanup
              self.logger.info("[AutoSave] No server changes, but UI cleanup needed. Starting cleanup...")
              if hasattr(self.sanga_logic, 'autosave_status_label') and self.sanga_logic.autosave_status_label:
                   self.sanga_logic.autosave_status_label.setText("자동 저장: UI 정리 중...")
                   self.sanga_logic.autosave_status_label.setStyleSheet("color: orange; font-style: italic;")
                   QApplication.processEvents()
              
              removed_count = self._cleanup_ui_marked_rows()
              self.logger.info(f"[AutoSave] UI cleanup finished. Removed {removed_count} rows.")
              
              # Update status label after cleanup
              if hasattr(self.sanga_logic, 'autosave_status_label') and self.sanga_logic.autosave_status_label:
                  timestamp = datetime.now().strftime("%H:%M:%S")
                  self.sanga_logic.autosave_status_label.setText(f"자동 저장: UI 정리 완료 ({timestamp})")
                  self.sanga_logic.autosave_status_label.setStyleSheet("color: green; font-style: italic;")
              
              self.is_saving = False # Release flag after cleanup
              self.logger.debug("[AutoSave] is_saving flag set to False after UI cleanup.")
              
         else: # No pending changes and no UI cleanup needed
              self.logger.debug("[AutoSave] No changes to save or UI to clean.")
              if hasattr(self.sanga_logic, 'autosave_status_label') and self.sanga_logic.autosave_status_label:
                  current_time = datetime.now().strftime("%H:%M:%S")
                  self.sanga_logic.autosave_status_label.setText(f"자동 저장: 활성화됨 ({current_time})")
                  self.sanga_logic.autosave_status_label.setStyleSheet("color: green; font-style: italic;")


    def _bg_auto_save_all_changes(self):
         """(Background Thread) Saves both shop and oneroom changes."""
         shop_payload = None
         oneroom_payload = None
         results = {"shop": None, "oneroom": None}

         # Get pending changes from manager
         shop_pending = self.pending_manager.get_pending_shop_changes()
         oneroom_pending = self.pending_manager.get_pending_oneroom_changes()

         shop_added = shop_pending.get("added", [])
         shop_updated = shop_pending.get("updated", [])
         shop_deleted = shop_pending.get("deleted", [])
         
         oneroom_added = oneroom_pending.get("added", [])
         oneroom_updated = oneroom_pending.get("updated", [])
         oneroom_deleted = oneroom_pending.get("deleted", [])

         # --- Prepare Shop Payload ---
         if shop_added or shop_updated or shop_deleted:
             try:
                # 추가: added_list에서 중복된 temp_id 제거
                if shop_added:
                    # temp_id 기준으로 중복 제거
                    temp_ids_seen = set()
                    unique_shop_added = []
                    
                    for item in shop_added:
                        temp_id = item.get("temp_id")
                        if temp_id not in temp_ids_seen:
                            temp_ids_seen.add(temp_id)
                            unique_shop_added.append(item)
                    
                    # 중복이 있었는지 로그
                    if len(unique_shop_added) < len(shop_added):
                        self.logger.warning(f"[AutoSave] Removed {len(shop_added) - len(unique_shop_added)} duplicate items from shop_added before building payload")
                    
                    # 중복 제거된 리스트 사용
                    shop_added = unique_shop_added
                
                # Call sanga_logic's method to build payload data
                add_up_rows_shop = self.sanga_logic._build_mylist_shop_rows_for_changes(shop_added, shop_updated)
                shop_payload = {
                    "manager": self.current_manager, "role": self.current_role,
                    "added_list": add_up_rows_shop["added"],
                    "updated_list": add_up_rows_shop["updated"],
                    "deleted_list": shop_deleted
                }
                self.logger.debug("[AutoSave] Preparing Shop Payload:")
                self.logger.debug(f"  - Added: {len(shop_payload['added_list'])} | Updated: {len(shop_payload['updated_list'])} | Deleted: {len(shop_payload['deleted_list'])}")
             except Exception as e:
                  self.logger.error(f"[AutoSave] Failed to build shop payload: {e}", exc_info=True)
                  results["shop"] = {"status": "error", "message": f"Build payload failed: {e}", "id_map": {}}

         # --- Prepare Oneroom Payload ---
         if oneroom_added or oneroom_updated or oneroom_deleted:
             try:
                 # 추가: added_list에서 중복된 temp_id 제거
                 if oneroom_added:
                     # temp_id 기준으로 중복 제거
                     temp_ids_seen = set()
                     unique_oneroom_added = []
                     
                     for item in oneroom_added:
                         temp_id = item.get("temp_id")
                         if temp_id not in temp_ids_seen:
                             temp_ids_seen.add(temp_id)
                             unique_oneroom_added.append(item)
                     
                     # 중복이 있었는지 로그
                     if len(unique_oneroom_added) < len(oneroom_added):
                         self.logger.warning(f"[AutoSave] Removed {len(oneroom_added) - len(unique_oneroom_added)} duplicate items from oneroom_added before building payload")
                     
                     # 중복 제거된 리스트 사용
                     oneroom_added = unique_oneroom_added
                 
                 # Call oneroom_logic's method to build payload data
                 add_up_rows_oneroom = self.oneroom_logic._build_mylist_oneroom_rows_for_changes(oneroom_added, oneroom_updated)
                 oneroom_payload = {
                     "manager": self.current_manager, 
                     "role": self.current_role,
                     "added_list": add_up_rows_oneroom["added"],
                     "updated_list": add_up_rows_oneroom["updated"],
                     "deleted_list": oneroom_deleted
                 }
                 self.logger.debug("[AutoSave] Preparing Oneroom Payload:")
                 self.logger.debug(f"  - Added: {len(oneroom_payload['added_list'])} | Updated: {len(oneroom_payload['updated_list'])} | Deleted: {len(oneroom_payload['deleted_list'])}")
             except Exception as e:
                  self.logger.error(f"[AutoSave] Failed to build oneroom payload: {e}", exc_info=True)
                  results["oneroom"] = {"status": "error", "message": f"Build payload failed: {e}", "inserted_map": {}}

         # --- Send Requests --- 
         if shop_payload and results["shop"] is None: # Only send if build succeeded
             url_shop = f"http://{self.server_host}:{self.server_port}/mylist/update_mylist_shop_items"
             try:
                 self.logger.debug(f"[AutoSave] Sending Shop request to {url_shop}")
                 shop_payload_json_utf8 = json.dumps(shop_payload, ensure_ascii=False).encode('utf-8')
                 headers = {'Content-Type': 'application/json; charset=utf-8'}
                 resp_shop = requests.post(url_shop, data=shop_payload_json_utf8, headers=headers, timeout=15)
                 resp_shop.raise_for_status()
                 results["shop"] = resp_shop.json()
                 self.logger.debug(f"[AutoSave] Shop response received: status={results['shop'].get('status')}")
             except Exception as e:
                 self.logger.error(f"[AutoSave] Shop request failed: {e}", exc_info=True)
                 results["shop"] = {"status": "error", "message": str(e), "id_map": {}}

         if oneroom_payload and results["oneroom"] is None: # Only send if build succeeded
             url_oneroom = f"http://{self.server_host}:{self.server_port}/mylist/update_mylist_oneroom_items"
             try:
                 self.logger.debug(f"[AutoSave] Sending Oneroom request to {url_oneroom}")
                 # <<< 로그 추가: 전송 직전 페이로드 확인 >>>
                 payload_to_send_repr = repr(oneroom_payload) # repr()로 전체 내용 확인
                 self.logger.info(f"[AutoSave] ===> Payload to send to {url_oneroom}: {payload_to_send_repr} <===")
                 # <<< 로그 추가 끝 >>>
                 resp_oneroom = requests.post(url_oneroom, json=oneroom_payload, timeout=15)
                 resp_oneroom.raise_for_status()
                 results["oneroom"] = resp_oneroom.json()
                 self.logger.debug(f"[AutoSave] Oneroom response received: status={results['oneroom'].get('status')}")
             except Exception as e:
                 self.logger.error(f"[AutoSave] Oneroom request failed: {e}", exc_info=True)
                 results["oneroom"] = {"status": "error", "message": str(e), "inserted_map": {}}

         return results

    def _on_auto_save_completed(self, future):
        """(Main Thread) Processes the results of the auto-save background task."""
        error_messages = []
        shop_save_attempted = False
        oneroom_save_attempted = False
        shop_cleared = True 
        oneroom_cleared = True

        try:
            try:
                results = future.result()
                shop_result = results.get("shop")
                oneroom_result = results.get("oneroom")

                if shop_result:
                    shop_save_attempted = True
                    shop_cleared = False 
                if oneroom_result:
                    oneroom_save_attempted = True
                    oneroom_cleared = False

                # Process Shop Results
                if shop_result:
                    if shop_result.get("status") == "ok":
                        id_map = shop_result.get("id_map", {})
                        shop_pending_before_clear = self.pending_manager.get_pending_shop_changes() # <<< 클리어 전 상태 가져오기
                        if self.sanga_logic.mylist_shop_model:
                            # Update temp IDs to real IDs
                            for temp_id_str, real_id in id_map.items():
                                try:
                                    # 수정: 호환성 레이어의 메서드 직접 호출 
                                    if hasattr(self.sanga_logic, 'update_mylist_shop_row_id'):
                                        # 직접 호환성 레이어의 메서드 호출
                                        success = self.sanga_logic.update_mylist_shop_row_id(temp_id_str, real_id)
                                        if success:
                                            self.logger.info(f"[AutoSave Callback] Successfully updated ID: {temp_id_str} -> {real_id}")
                                        else:
                                            self.logger.warning(f"[AutoSave Callback] Failed to update ID: {temp_id_str} -> {real_id}")
                                    else:
                                        self.logger.error(f"[AutoSave Callback] sanga_logic does not have update_mylist_shop_row_id method")
                                except Exception as e:
                                    self.logger.error(f"[AutoSave Callback] Error updating ID: {e}", exc_info=True)
                            
                            # Remove 'deleted' rows from UI
                            shop_model = self.sanga_logic.mylist_shop_model
                            rows_to_remove_ui = []
                            for r in range(shop_model.rowCount()-1, -1, -1): # Iterate backwards for removal
                                item0 = shop_model.item(r, 0)
                                if item0 and item0.data(Qt.UserRole + 20) == True: # Check deletion flag
                                    rows_to_remove_ui.append(r)
                            
                            if rows_to_remove_ui:
                                self.logger.info(f"[AutoSave Callback] Removing {len(rows_to_remove_ui)} marked-for-deletion rows from Shop UI.")
                                # No need to sort, already iterating backwards
                                for row_idx in rows_to_remove_ui:
                                    shop_model.removeRow(row_idx)
                        
                        # Get model reference first
                        shop_model = None
                        if self.sanga_logic and hasattr(self.sanga_logic, 'mylist_shop_model'):
                            shop_model = self.sanga_logic.mylist_shop_model
                            self.logger.info(f"[AutoSave Callback] Retrieved shop_model: {shop_model}")
                        else:
                            self.logger.error("[AutoSave Callback] Failed to get shop_model: sanga_logic={self.sanga_logic}")
                        
                        if not shop_model:
                            self.logger.error("[AutoSave Callback] shop_model is None or invalid!")
                            # 모델을 얻지 못했을 때 처리
                            shop_model = None
                            # 대체 로직: 배경색 복원 및 ID 업데이트 건너뛰기
                            self.logger.warning("[AutoSave Callback] Skipping background color restoration and ID updates due to missing model")
                        else:
                            # 이전 코드 계속 실행
                            # 저장 전 pending 상태 가져오기 (삭제 전)
                            shop_pending_before_clear = self.pending_manager.get_pending_shop_changes()
                            self.logger.info(f"[AutoSave Callback] Pending state before clear: {shop_pending_before_clear}")

                            # Update temp IDs to real IDs
                            for temp_id_str, real_id in id_map.items():
                                try:
                                    # 수정: 호환성 레이어의 메서드 직접 호출 
                                    if hasattr(self.sanga_logic, 'update_mylist_shop_row_id'):
                                        # 직접 호환성 레이어의 메서드 호출
                                        success = self.sanga_logic.update_mylist_shop_row_id(temp_id_str, real_id)
                                        if success:
                                            self.logger.info(f"[AutoSave Callback] Successfully updated ID: {temp_id_str} -> {real_id}")
                                        else:
                                            self.logger.warning(f"[AutoSave Callback] Failed to update ID: {temp_id_str} -> {real_id}")
                                    else:
                                        self.logger.error(f"[AutoSave Callback] sanga_logic does not have update_mylist_shop_row_id method")
                                except Exception as e:
                                    self.logger.error(f"[AutoSave Callback] Error updating ID: {e}", exc_info=True)
                            
                            # Remove 'deleted' rows from UI
                            rows_to_remove_ui = []
                            for r in range(shop_model.rowCount()-1, -1, -1): # Iterate backwards for removal
                                item0 = shop_model.item(r, 0)
                                if item0 and item0.data(Qt.UserRole + 20) == True: # Check deletion flag
                                    rows_to_remove_ui.append(r)
                            
                            if rows_to_remove_ui:
                                self.logger.info(f"[AutoSave Callback] Removing {len(rows_to_remove_ui)} marked-for-deletion rows from Shop UI.")
                                # No need to sort, already iterating backwards
                                for row_idx in rows_to_remove_ui:
                                    shop_model.removeRow(row_idx)
                        
                        # <<< 배경색 복원 로직 수정 시작 >>>
                        updated_list = shop_pending_before_clear.get("updated", []) if 'shop_pending_before_clear' in locals() else []
                        updated_ids_from_pending = set(item['id'] for item in updated_list if isinstance(item, dict) and 'id' in item)
                        deleted_ids_from_pending = set(shop_pending_before_clear.get("deleted", [])) if 'shop_pending_before_clear' in locals() else set()

                        if updated_ids_from_pending and shop_model:
                            self.logger.info(f"[AutoSave Callback] Restoring background color for {len(updated_ids_from_pending)} updated rows (fetched before clear).")
                            # '재광고' 컬럼 인덱스 찾기
                            re_ad_col_index = -1
                            headers = []
                            try:
                                if shop_model.columnCount() > 0:
                                    headers = [shop_model.horizontalHeaderItem(c).text() for c in range(shop_model.columnCount())]
                                    re_ad_col_index = headers.index("재광고")
                            except (ValueError, AttributeError, Exception) as e_find_col:
                                self.logger.warning(f"[AutoSave Color Restore] Could not find '재광고' column index: {e_find_col}.")
                                
                            for r in range(shop_model.rowCount()):
                                item0 = shop_model.item(r, 0)
                                if not item0: continue
                                record_id = item0.data(Qt.UserRole + 3)
                                
                                # 업데이트된 ID 목록에 있고, 삭제되지 않은 행만 처리
                                if record_id in updated_ids_from_pending and record_id not in deleted_ids_from_pending:
                                    # 행의 최종 '재광고' 상태 확인
                                    is_re_ad_final = False
                                    if re_ad_col_index != -1:
                                        re_ad_item = shop_model.item(r, re_ad_col_index)
                                        if re_ad_item and re_ad_item.text() == "재광고":
                                            is_re_ad_final = True
                                            
                                    target_color = RE_AD_BG_COLOR if is_re_ad_final else NEW_AD_BG_COLOR
                                    
                                    # 행 전체 순회하며 노란색 배경을 찾아서 복원
                                    for c in range(shop_model.columnCount()):
                                        item = shop_model.item(r, c)
                                        if item and item.background() == PENDING_COLOR:
                                            item.setBackground(target_color)
                            self.logger.info("[AutoSave Callback] Finished background color restoration.")
                        elif shop_model is None:
                            self.logger.warning("[AutoSave Callback] Skipping background color restoration due to missing model")
                        # <<< 배경색 복원 로직 수정 끝 >>>

                        # <<< 추가: 새로 추가된 행 배경색 설정 로직 (manual save 콜백에서 가져옴) >>>
                        successfully_added_real_ids_shop = set(id_map.values()) # 새로 추가되어 실제 ID를 받은 상가 행
                        if successfully_added_real_ids_shop and self.sanga_logic and shop_model:
                            self.logger.info(f"[AutoSave Callback] Setting final background color for {len(successfully_added_real_ids_shop)} newly added shop rows (skipping PENDING).")

                            # '재광고' 컬럼 인덱스 재확인 (모델이 변경되었을 수 있음)
                            re_ad_col_index_add = -1
                            headers_add = []
                            try:
                                if shop_model.columnCount() > 0:
                                    headers_add = [shop_model.horizontalHeaderItem(c).text() for c in range(shop_model.columnCount())]
                                    re_ad_col_index_add = headers_add.index("재광고")
                            except (ValueError, AttributeError, Exception) as e_find_col_add:
                                self.logger.warning(f"[AutoSave Added Color] Could not find '재광고' column index: {e_find_col_add}. Defaulting to NEW_AD_BG_COLOR.")

                            # 실제 ID -> 행 인덱스 맵 생성 (ID 업데이트 이후 상태 기준)
                            real_id_to_row_index_shop = {}
                            for r in range(shop_model.rowCount()):
                                item0 = shop_model.item(r, 0)
                                if item0:
                                    current_id = item0.data(Qt.UserRole + 3)
                                    if isinstance(current_id, int) and current_id > 0:
                                        real_id_to_row_index_shop[current_id] = r

                            for real_id in successfully_added_real_ids_shop:
                                row_idx = real_id_to_row_index_shop.get(real_id)
                                if row_idx is not None:
                                    is_re_ad = False
                                    if re_ad_col_index_add != -1:
                                        re_ad_item = shop_model.item(row_idx, re_ad_col_index_add)
                                        if re_ad_item and re_ad_item.text() == "재광고":
                                            is_re_ad = True

                                    target_color = RE_AD_BG_COLOR if is_re_ad else NEW_AD_BG_COLOR
                                    # 행 전체 배경색 설정 (단, 이미 PENDING_COLOR 인 셀은 제외)
                                    for c in range(shop_model.columnCount()):
                                        item = shop_model.item(row_idx, c)
                                        if item:
                                            if item.background().color() != PENDING_COLOR:
                                                item.setBackground(target_color)
                                            # else: PENDING_COLOR 유지
                                else:
                                    self.logger.warning(f"[AutoSave Added Color] Could not find row index for newly added shop real_id: {real_id}")
                            self.logger.info("[AutoSave Callback] Finished setting background color for newly added shop rows.")
                        # <<< 추가 끝 >>>

                        # Clear pending state via manager
                        self.pending_manager.clear_shop_pending_state() # Clear all states on success
                        self.logger.info("[AutoSave Callback] Cleared pending shop changes.")
                        shop_cleared = True
                    else:
                        error_msg = f"상가 저장 실패: {shop_result.get('message', 'Unknown error')}"
                        error_messages.append(error_msg)
                        self.logger.warning(f"[AutoSave] Shop save failed: {error_msg}")
                        shop_cleared = False

                # Process Oneroom Results
                if oneroom_result:
                    if oneroom_result.get("status") == "ok":
                        inserted_map = oneroom_result.get("inserted_map", {})
                        if self.oneroom_logic.mylist_oneroom_model:
                             # Update temp IDs
                             for temp_id_str, real_id in inserted_map.items():
                                 try:
                                     self.oneroom_logic.update_mylist_oneroom_row_id(int(temp_id_str), real_id)
                                 except (ValueError, TypeError):
                                     self.logger.warning(f"[AutoSave Callback] Invalid temp_id_str from oneroom save: {temp_id_str}")
                             
                             # Remove 'deleted' rows from UI
                             oneroom_model = self.oneroom_logic.mylist_oneroom_model
                             rows_to_remove_ui = []
                             for r in range(oneroom_model.rowCount()-1, -1, -1): # Iterate backwards
                                 item0 = oneroom_model.item(r, 0)
                                 if item0 and item0.data(Qt.UserRole + 20) == True: # Check deletion flag
                                     rows_to_remove_ui.append(r)
                             
                             if rows_to_remove_ui:
                                 self.logger.info(f"[AutoSave Callback] Removing {len(rows_to_remove_ui)} marked-for-deletion rows from Oneroom UI.")
                                 for row_idx in rows_to_remove_ui:
                                     oneroom_model.removeRow(row_idx)
                        
                        # <<< 추가: 새로 추가된 원룸 행 배경색 설정 로직 >>>
                        successfully_added_real_ids_or = set(inserted_map.values())
                        if successfully_added_real_ids_or and self.oneroom_logic and oneroom_model:
                            self.logger.info(f"[AutoSave Callback] Setting final background color for {len(successfully_added_real_ids_or)} newly added oneroom rows (skipping PENDING).")
                            target_color_or = NEW_AD_BG_COLOR

                            # 실제 ID -> 행 인덱스 맵 생성 (ID 업데이트 이후 상태 기준)
                            real_id_to_row_index_or = {}
                            for r in range(oneroom_model.rowCount()):
                                item0 = oneroom_model.item(r, 0)
                                if item0:
                                    current_id = item0.data(Qt.UserRole + 3)
                                    if isinstance(current_id, int) and current_id > 0:
                                        real_id_to_row_index_or[current_id] = r

                            for real_id in successfully_added_real_ids_or:
                                row_idx = real_id_to_row_index_or.get(real_id)
                                if row_idx is not None:
                                    # 행 전체 배경색 설정 (단, PENDING_COLOR 는 제외)
                                    for c in range(oneroom_model.columnCount()):
                                        item = oneroom_model.item(row_idx, c)
                                        if item:
                                            if item.background().color() != PENDING_COLOR:
                                                item.setBackground(target_color_or)
                                            # else: PENDING_COLOR 유지
                                else:
                                    self.logger.warning(f"[AutoSave Added Color] Could not find row index for newly added oneroom real_id: {real_id}")
                            self.logger.info("[AutoSave Callback] Finished setting background color for newly added oneroom rows.")
                        # <<< 추가 끝 >>>

                        # Clear pending state via manager
                        self.pending_manager.clear_oneroom_pending_state() # Clear all states on success
                        self.logger.info("[AutoSave Callback] Cleared pending oneroom changes.")
                        oneroom_cleared = True
                    else:
                        error_msg = f"원룸 저장 실패: {oneroom_result.get('message', 'Unknown error')}"
                        error_messages.append(error_msg)
                        self.logger.warning(f"[AutoSave] Oneroom save failed: {error_msg}")
                        oneroom_cleared = False

            except Exception as e:
                error_msg = f"자동 저장 처리 중 오류: {e}"
                self.logger.error(f"[AutoSave Callback] Error processing future result: {e}", exc_info=True)
                error_messages.append(error_msg)
                if shop_save_attempted: shop_cleared = False
                if oneroom_save_attempted: oneroom_cleared = False

            # --- 추가: 저장 성공 여부와 관계없이 최종 UI 정리 시도 --- 
            self.logger.info("[AutoSave Callback] Attempting final UI cleanup for marked rows.")
            self._cleanup_ui_marked_rows()
            # -----------------------------------------------------

            # Update UI Label
            if hasattr(self.sanga_logic, 'autosave_status_label') and self.sanga_logic.autosave_status_label:
                timestamp = datetime.now().strftime("%H:%M:%S")
                pending_shop = self.pending_manager.get_pending_shop_changes()
                pending_oneroom = self.pending_manager.get_pending_oneroom_changes()
                has_remaining_pending = any(pending_shop.values()) or any(pending_oneroom.values())

                if not error_messages and not has_remaining_pending:
                    status_text = f"자동 저장 완료 ({timestamp})"
                    status_color = "green"
                    self.logger.info("[AutoSave Callback] All changes saved and pending lists cleared.")
                elif error_messages or has_remaining_pending:
                     status_text = f"자동 저장 오류 ({timestamp})"
                     if error_messages:
                         status_text += f": {'; '.join(error_messages)}"
                     elif has_remaining_pending:
                         status_text += ": 일부 변경사항 처리 실패. 재시도 예정."
                     status_color = "red"
                     self.logger.error(f"[AutoSave Callback] Errors or remaining pending changes. Errors: {error_messages}, ShopPending: {pending_shop}, OneroomPending: {pending_oneroom}")
                else: # Fallback, should not happen often
                     status_text = f"자동 저장 상태 불명확 ({timestamp})"
                     status_color = "orange"
                     self.logger.warning("[AutoSave Callback] Ambiguous save state.")

                self.sanga_logic.autosave_status_label.setText(status_text)
                self.sanga_logic.autosave_status_label.setStyleSheet(f"color: {status_color}; font-style: italic;")

            # Recalculate summary via container
            if hasattr(self.container, '_recalculate_manager_summary'):
                 self.container._recalculate_manager_summary()

        finally:
            self.is_saving = False
            self.logger.debug("[AutoSave Callback] is_saving flag set to False.")

    # --- UI Cleanup Helpers ---

    def _ui_has_rows_marked_for_deletion(self):
        """Checks if either the shop or oneroom UI model has rows marked for deletion."""
        shop_marked = False
        if self.sanga_logic and self.sanga_logic.mylist_shop_model:
            shop_model = self.sanga_logic.mylist_shop_model
            for r in range(shop_model.rowCount()):
                item0 = shop_model.item(r, 0)
                if item0 and item0.data(Qt.UserRole + 20) == True:
                    shop_marked = True
                    break # Found one, no need to check further in shop model

        oneroom_marked = False
        if self.oneroom_logic and self.oneroom_logic.mylist_oneroom_model:
            oneroom_model = self.oneroom_logic.mylist_oneroom_model
            for r in range(oneroom_model.rowCount()):
                item0 = oneroom_model.item(r, 0)
                if item0 and item0.data(Qt.UserRole + 20) == True:
                    oneroom_marked = True
                    break # Found one

        return shop_marked or oneroom_marked

    def _cleanup_ui_marked_rows(self):
        """Removes rows marked with the deletion flag (UserRole + 20) from UI models. (최적화 버전)"""
        removed_shop_count = 0
        removed_oneroom_count = 0

        # Cleanup Shop UI
        if self.sanga_logic and self.sanga_logic.mylist_shop_model:
            shop_model = self.sanga_logic.mylist_shop_model
            shop_view = getattr(self.sanga_logic, 'mylist_shop_view', None)
            
            # 먼저 정렬 상태 저장 및 비활성화
            was_sorting_enabled = False
            sort_column = -1
            sort_order = Qt.AscendingOrder
            
            if shop_view and shop_view.isSortingEnabled():
                was_sorting_enabled = True
                sort_column = shop_view.horizontalHeader().sortIndicatorSection()
                sort_order = shop_view.horizontalHeader().sortIndicatorOrder()
                shop_view.setSortingEnabled(False)
                self.logger.debug(f"[_cleanup_ui_marked_rows] Shop 탭 정렬 임시 비활성화: col={sort_column}, order={sort_order}")
            
            # 한 번에 삭제할 행들 수집 (역순으로)
            rows_to_remove_ui = []
            
            # 한 번의 루프로 모든 삭제 대상 행 인덱스 수집
            for r in range(shop_model.rowCount()-1, -1, -1):  # 역순으로 순회
                item0 = shop_model.item(r, 0)
                if item0 and item0.data(Qt.UserRole + 20) == True:
                    rows_to_remove_ui.append(r)
            
            if rows_to_remove_ui:
                self.logger.info(f"[_cleanup_ui_marked_rows] Shop 모델에서 {len(rows_to_remove_ui)}개 행 삭제 시작")
                
                # 한 번에 대량 삭제를 위한 시그널 차단
                shop_model.blockSignals(True)
                try:
                    # 연속된 행 그룹으로 처리하여 removeRows()를 최소한으로 호출
                    continuous_segments = []
                    current_segment = []
                    
                    # 연속된 행을 그룹화 (이미 역순 정렬됨)
                    for idx in rows_to_remove_ui:
                        if not current_segment or current_segment[-1] == idx + 1:
                            current_segment.append(idx)
                        else:
                            if current_segment:
                                continuous_segments.append(current_segment)
                            current_segment = [idx]
                    
                    if current_segment:
                        continuous_segments.append(current_segment)
                    
                    # 각 연속 세그먼트에 대해 한 번에 removeRows 호출
                    for segment in continuous_segments:
                        if not segment:
                            continue
                            
                        # 연속 세그먼트는 높은 인덱스부터 낮은 인덱스 순으로 정렬됨
                        # 시작 행 = 가장 낮은 인덱스 (세그먼트의 마지막 요소)
                        # 행 수 = 세그먼트 길이
                        start_row = segment[-1]
                        count = len(segment)
                        
                        self.logger.debug(f"[_cleanup_ui_marked_rows] Shop 연속 세그먼트 제거: start={start_row}, count={count}")
                        shop_model.removeRows(start_row, count)
                        removed_shop_count += count
                        
                except Exception as e:
                    self.logger.error(f"[_cleanup_ui_marked_rows] Shop 행 제거 중 오류: {e}", exc_info=True)
                finally:
                    shop_model.blockSignals(False)
                
                # 상가 탭은 요청에 따라 정렬 안 함 (ID 순서 유지)
                if shop_view:
                    shop_view.setSortingEnabled(False)
                    self.logger.info("[_cleanup_ui_marked_rows] Shop view 정렬 비활성화 완료 (ID 순서 유지)")

        # Cleanup Oneroom UI (will keep sorting functionality)
        if self.oneroom_logic and self.oneroom_logic.mylist_oneroom_model:
            oneroom_model = self.oneroom_logic.mylist_oneroom_model
            oneroom_view = getattr(self.oneroom_logic, 'mylist_oneroom_view', None)
            
            # 먼저 정렬 상태 저장 및 비활성화
            was_sorting_enabled = False
            sort_column = -1
            sort_order = Qt.AscendingOrder
            
            if oneroom_view and oneroom_view.isSortingEnabled():
                was_sorting_enabled = True
                sort_column = oneroom_view.horizontalHeader().sortIndicatorSection()
                sort_order = oneroom_view.horizontalHeader().sortIndicatorOrder()
                oneroom_view.setSortingEnabled(False)
                self.logger.debug(f"[_cleanup_ui_marked_rows] Oneroom 탭 정렬 임시 비활성화: col={sort_column}, order={sort_order}")
            
            # 한 번에 삭제할 행들 수집 (역순으로)
            rows_to_remove_ui = []
            
            # 한 번의 루프로 모든 삭제 대상 행 인덱스 수집
            for r in range(oneroom_model.rowCount()-1, -1, -1):  # 역순으로 순회
                item0 = oneroom_model.item(r, 0)
                if item0 and item0.data(Qt.UserRole + 20) == True:
                    rows_to_remove_ui.append(r)
            
            if rows_to_remove_ui:
                self.logger.info(f"[_cleanup_ui_marked_rows] Oneroom 모델에서 {len(rows_to_remove_ui)}개 행 삭제 시작")
                
                # 한 번에 대량 삭제를 위한 시그널 차단
                oneroom_model.blockSignals(True)
                try:
                    # 연속된 행 그룹으로 처리하여 removeRows()를 최소한으로 호출
                    continuous_segments = []
                    current_segment = []
                    
                    # 연속된 행을 그룹화 (이미 역순 정렬됨)
                    for idx in rows_to_remove_ui:
                        if not current_segment or current_segment[-1] == idx + 1:
                            current_segment.append(idx)
                        else:
                            if current_segment:
                                continuous_segments.append(current_segment)
                            current_segment = [idx]
                    
                    if current_segment:
                        continuous_segments.append(current_segment)
                    
                    # 각 연속 세그먼트에 대해 한 번에 removeRows 호출
                    for segment in continuous_segments:
                        if not segment:
                            continue
                            
                        # 연속 세그먼트는 높은 인덱스부터 낮은 인덱스 순으로 정렬됨
                        # 시작 행 = 가장 낮은 인덱스 (세그먼트의 마지막 요소)
                        # 행 수 = 세그먼트 길이
                        start_row = segment[-1]
                        count = len(segment)
                        
                        self.logger.debug(f"[_cleanup_ui_marked_rows] Oneroom 연속 세그먼트 제거: start={start_row}, count={count}")
                        oneroom_model.removeRows(start_row, count)
                        removed_oneroom_count += count
                        
                except Exception as e:
                    self.logger.error(f"[_cleanup_ui_marked_rows] Oneroom 행 제거 중 오류: {e}", exc_info=True)
                finally:
                    oneroom_model.blockSignals(False)
                
                # 원룸 탭은 정렬 상태 복원
                if oneroom_view and was_sorting_enabled and sort_column >= 0:
                    oneroom_view.setSortingEnabled(True)
                    oneroom_view.horizontalHeader().setSortIndicator(sort_column, sort_order)
                    self.logger.debug(f"[_cleanup_ui_marked_rows] Oneroom 정렬 복원 완료: col={sort_column}, order={sort_order}")

        # 요약 정보 갱신
        if (removed_shop_count > 0 or removed_oneroom_count > 0) and hasattr(self.container, '_recalculate_manager_summary'):
            self.container._recalculate_manager_summary()

        return removed_shop_count + removed_oneroom_count


    # --- Manual Save Methods ---

    def save_pending_shop_changes(self):
         """Manually triggered save for Shop tab or UI cleanup if needed."""
         if self.is_saving:
              # --- 수정: QMessageBox 대신 상태 레이블 사용 ---
              if hasattr(self.sanga_logic, 'autosave_status_label') and self.sanga_logic.autosave_status_label:
                 self.sanga_logic.autosave_status_label.setText("수동 저장: 진행 중인 작업 있음")
                 self.sanga_logic.autosave_status_label.setStyleSheet("color: orange; font-style: italic;")
              else: # Fallback if label doesn't exist
                 QMessageBox.information(self.parent_app, "저장 중", "현재 다른 저장 또는 정리 작업이 진행 중입니다. 잠시 후 다시 시도하세요.")
              # -------------------------------------------
              return

         shop_pending = self.pending_manager.get_pending_shop_changes()
         has_pending = any(shop_pending.values())
         needs_ui_cleanup = self._ui_has_rows_marked_for_deletion() # Check always, even if pending exists

         if not has_pending and not needs_ui_cleanup:
             # --- 수정: QMessageBox 대신 상태 레이블 사용 ---
            timestamp = datetime.now().strftime("%H:%M:%S")
            if hasattr(self.sanga_logic, 'autosave_status_label') and self.sanga_logic.autosave_status_label:
                self.sanga_logic.autosave_status_label.setText(f"수동 저장(상가): 변경 없음 ({timestamp})")
                self.sanga_logic.autosave_status_label.setStyleSheet("color: grey; font-style: italic;") # Or default color
            else:
                QMessageBox.information(self.parent_app, "변경 없음", "마이리스트(상가)에 저장할 변경 사항이나 정리할 UI 항목이 없습니다.")
            # -------------------------------------------
            return

         if has_pending: # Prioritize saving actual changes
            self.is_saving = True
            self.parent_app.statusBar().showMessage("마이리스트(상가) 저장 중...", 0) 
            future = self.parent_app.executor.submit(self._bg_save_shop_changes_manual)
            future.add_done_callback(self._on_manual_save_shop_completed)
         elif needs_ui_cleanup: # Only UI cleanup needed
            self.is_saving = True
            self.parent_app.statusBar().showMessage("마이리스트(상가) UI 정리 중...", 0)
            self.logger.info("[Manual Save Shop] No server changes, performing UI cleanup only.")
            try:
                removed_count = self._cleanup_ui_marked_rows()
                self.logger.info(f"[Manual Save Shop] UI cleanup finished. Removed {removed_count} rows.")
            except Exception as e:
                 self.logger.error(f"[Manual Save Shop] Error during UI cleanup: {e}", exc_info=True)
                 # --- 수정: QMessageBox 대신 상태 레이블 사용 ---
                 timestamp = datetime.now().strftime("%H:%M:%S")
                 if hasattr(self.sanga_logic, 'autosave_status_label') and self.sanga_logic.autosave_status_label:
                     self.sanga_logic.autosave_status_label.setText(f"수동 저장(상가): UI 정리 오류 ({timestamp})")
                     self.sanga_logic.autosave_status_label.setStyleSheet("color: red; font-style: italic;")
                 else:
                     QMessageBox.critical(self.parent_app, "정리 오류", f"UI 정리 중 오류 발생: {e}")
                 # -------------------------------------------
            finally:
                 self.is_saving = False
                 self.parent_app.statusBar().clearMessage()
                 
         # 수동 저장 시간 업데이트
         self.last_manual_save_time = time.time()

    def _bg_save_shop_changes_manual(self):
        """(Background Thread) Prepares and sends ONLY shop changes."""
        shop_payload = None
        shop_pending = self.pending_manager.get_pending_shop_changes()
        shop_added = shop_pending.get("added", [])
        shop_updated = shop_pending.get("updated", [])
        shop_deleted = shop_pending.get("deleted", [])

        if not (shop_added or shop_updated or shop_deleted):
             return {"status": "no_changes"}

        try:
            # 추가: added_list에서 중복된 temp_id 제거
            if shop_added:
                # temp_id 기준으로 중복 제거
                temp_ids_seen = set()
                unique_shop_added = []
                
                for item in shop_added:
                    temp_id = item.get("temp_id")
                    if temp_id not in temp_ids_seen:
                        temp_ids_seen.add(temp_id)
                        unique_shop_added.append(item)
                
                # 중복이 있었는지 로그
                if len(unique_shop_added) < len(shop_added):
                    self.logger.warning(f"[AutoSave] Removed {len(shop_added) - len(unique_shop_added)} duplicate items from shop_added before building payload")
                
                # 중복 제거된 리스트 사용
                shop_added = unique_shop_added
                
            add_up_rows_shop = self.sanga_logic._build_mylist_shop_rows_for_changes(shop_added, shop_updated)
            shop_payload = {
                "manager": self.current_manager, "role": self.current_role,
                "added_list": add_up_rows_shop["added"],
                "updated_list": add_up_rows_shop["updated"],
                "deleted_list": shop_deleted
            }
            self.logger.debug("[Manual Save Shop] Preparing Payload:")
            self.logger.debug(f"  - Added: {len(shop_payload['added_list'])} | Updated: {len(shop_payload['updated_list'])} | Deleted: {len(shop_payload['deleted_list'])}")
        except Exception as e:
            self.logger.error(f"[Manual Save Shop] Failed to build payload: {e}", exc_info=True)
            return {"status": "error", "message": f"Build payload failed: {e}", "id_map": {}}

        self.logger.info("[Manual Save Shop] Sending changes...")
        url_shop = f"http://{self.server_host}:{self.server_port}/mylist/update_mylist_shop_items"
        try:
            # <<< 로그 추가: 전송 직전 페이로드 확인 >>>
            payload_to_send_repr = repr(shop_payload) # repr()로 전체 내용 확인
            self.logger.info(f"[Manual Save Shop] ===> Payload to send to {url_shop}: {payload_to_send_repr} <===")
            # <<< 로그 추가 끝 >>>
            shop_payload_json_utf8 = json.dumps(shop_payload, ensure_ascii=False).encode('utf-8')
            headers = {'Content-Type': 'application/json; charset=utf-8'}
            resp_shop = requests.post(url_shop, data=shop_payload_json_utf8, headers=headers, timeout=15)
            resp_shop.raise_for_status()
            result = resp_shop.json()
            self.logger.debug(f"[Manual Save Shop] Response received: status={result.get('status')}")
            result["counts"] = {"add": len(add_up_rows_shop["added"]), "update": len(add_up_rows_shop["updated"]), "delete": len(shop_deleted)}
            return result
        except Exception as e:
            self.logger.error(f"[Manual Save Shop] Request failed: {e}", exc_info=True)
            return {"status": "error", "message": str(e), "id_map": {}, "counts": {"add": 0, "update": 0, "delete": 0}}


    def _on_manual_save_shop_completed(self, future):
        """(Main Thread) Handles result of manually triggered shop save."""
        success = False
        message = "알 수 없는 오류"
        result = {} # Initialize result dict
        counts = {"add": 0, "update": 0, "delete": 0}
        id_map = {} # Initialize id_map

        try:
            result = future.result()
            self.logger.info(f"[Manual Save Shop Callback] Received result from future: {result}")

            if result.get("status") == "ok":
                success = True
                message = "마이리스트(상가) 변경 사항이 성공적으로 저장되었습니다."
                counts = result.get("counts", counts)
                id_map = result.get("inserted_map", {}) # Get the id_map here (use inserted_map key)
                self.logger.info(f"[Manual Save Shop Callback] Extracted id_map: {id_map} (Type: {type(id_map)})")

                # Get model reference first
                shop_model = None
                if self.sanga_logic and hasattr(self.sanga_logic, 'mylist_shop_model'):
                    shop_model = self.sanga_logic.mylist_shop_model
                    self.logger.info(f"[AutoSave Callback] Retrieved shop_model: {shop_model}")
                else:
                    self.logger.error("[AutoSave Callback] Failed to get shop_model: sanga_logic={self.sanga_logic}")
                
                if not shop_model:
                    self.logger.error("[AutoSave Callback] shop_model is None or invalid!")
                    # 모델을 얻지 못했을 때 처리
                    shop_model = None
                    # 대체 로직: 배경색 복원 및 ID 업데이트 건너뛰기
                    self.logger.warning("[AutoSave Callback] Skipping background color restoration and ID updates due to missing model")
                else:
                    # 이전 코드 계속 실행
                    # 저장 전 pending 상태 가져오기 (삭제 전)
                    shop_pending_before_clear = self.pending_manager.get_pending_shop_changes()
                    self.logger.info(f"[AutoSave Callback] Pending state before clear: {shop_pending_before_clear}")

                    # Update temp IDs to real IDs
                    if id_map: # Check if id_map is not empty
                        self.logger.info(f"[Manual Save Shop Callback] Updating model IDs using map: {id_map}")
                        for temp_id_str, real_id in id_map.items():
                            # <<< 로그 추가: 루프 내부 값 및 객체 확인 >>>
                            self.logger.info(f"[Manual Save Shop Callback] Processing ID update: temp_id_str='{temp_id_str}', real_id={real_id}")
                            
                            # 기존: 직접 외부 모듈 함수 임포트 후 호출
                            # from mylist_sanga_data import update_mylist_shop_row_id
                            
                            try:
                                # 수정: 호환성 레이어의 메서드 직접 호출 
                                if hasattr(self.sanga_logic, 'update_mylist_shop_row_id'):
                                    # 직접 호환성 레이어의 메서드 호출
                                    success = self.sanga_logic.update_mylist_shop_row_id(temp_id_str, real_id)
                                    if success:
                                        self.logger.info(f"[Manual Save Shop Callback] Successfully updated ID: {temp_id_str} -> {real_id}")
                                    else:
                                        self.logger.warning(f"[Manual Save Shop Callback] Failed to update ID: {temp_id_str} -> {real_id}")
                                else:
                                    self.logger.error(f"[Manual Save Shop Callback] sanga_logic does not have update_mylist_shop_row_id method")
                            except Exception as e:
                                self.logger.error(f"[Manual Save Shop Callback] Error updating ID: {e}", exc_info=True)
                    
                    # Remove 'deleted' rows from UI
                    rows_to_remove_ui = []
                    for r in range(shop_model.rowCount()-1, -1, -1): # Iterate backwards for removal
                        item0 = shop_model.item(r, 0)
                        if item0 and item0.data(Qt.UserRole + 20) == True: # Check deletion flag
                            rows_to_remove_ui.append(r)
                    
                    if rows_to_remove_ui:
                        self.logger.info(f"[AutoSave Callback] Removing {len(rows_to_remove_ui)} marked-for-deletion rows from Shop UI.")
                        # No need to sort, already iterating backwards
                        for row_idx in rows_to_remove_ui:
                            shop_model.removeRow(row_idx)
                
                # <<< 배경색 복원 로직 수정 시작 >>>
                updated_list = shop_pending_before_clear.get("updated", []) if 'shop_pending_before_clear' in locals() else []
                updated_ids_from_pending = set(item['id'] for item in updated_list if isinstance(item, dict) and 'id' in item)
                deleted_ids_from_pending = set(shop_pending_before_clear.get("deleted", [])) if 'shop_pending_before_clear' in locals() else set()

                if updated_ids_from_pending and shop_model:
                    self.logger.info(f"[AutoSave Callback] Restoring background color for {len(updated_ids_from_pending)} updated rows (fetched before clear).")
                    # '재광고' 컬럼 인덱스 찾기
                    re_ad_col_index = -1
                    headers = []
                    try:
                        if shop_model.columnCount() > 0:
                            headers = [shop_model.horizontalHeaderItem(c).text() for c in range(shop_model.columnCount())]
                            re_ad_col_index = headers.index("재광고")
                    except (ValueError, AttributeError, Exception) as e_find_col:
                        self.logger.warning(f"[AutoSave Color Restore] Could not find '재광고' column index: {e_find_col}.")
                        
                    for r in range(shop_model.rowCount()):
                        item0 = shop_model.item(r, 0)
                        if not item0: continue
                        record_id = item0.data(Qt.UserRole + 3)
                        
                        # 업데이트된 ID 목록에 있고, 삭제되지 않은 행만 처리
                        if record_id in updated_ids_from_pending and record_id not in deleted_ids_from_pending:
                            # 행의 최종 '재광고' 상태 확인
                            is_re_ad_final = False
                            if re_ad_col_index != -1:
                                re_ad_item = shop_model.item(r, re_ad_col_index)
                                if re_ad_item and re_ad_item.text() == "재광고":
                                    is_re_ad_final = True
                                    
                            target_color = RE_AD_BG_COLOR if is_re_ad_final else NEW_AD_BG_COLOR
                            
                            # 행 전체 순회하며 노란색 배경을 찾아서 복원
                            for c in range(shop_model.columnCount()):
                                item = shop_model.item(r, c)
                                if item and item.background() == PENDING_COLOR:
                                    item.setBackground(target_color)
                    self.logger.info("[AutoSave Callback] Finished background color restoration.")
                elif shop_model is None:
                    self.logger.warning("[AutoSave Callback] Skipping background color restoration due to missing model")
                # <<< 배경색 복원 로직 수정 끝 >>>

                # <<< 추가: 새로 추가된 행 배경색 설정 로직 (manual save 콜백에서 가져옴) >>>
                successfully_added_real_ids_shop = set(id_map.values()) # 새로 추가되어 실제 ID를 받은 상가 행
                if successfully_added_real_ids_shop and self.sanga_logic and shop_model:
                    self.logger.info(f"[AutoSave Callback] Setting final background color for {len(successfully_added_real_ids_shop)} newly added shop rows (skipping PENDING).")

                    # '재광고' 컬럼 인덱스 재확인 (모델이 변경되었을 수 있음)
                    re_ad_col_index_add = -1
                    headers_add = []
                    try:
                        if shop_model.columnCount() > 0:
                            headers_add = [shop_model.horizontalHeaderItem(c).text() for c in range(shop_model.columnCount())]
                            re_ad_col_index_add = headers_add.index("재광고")
                    except (ValueError, AttributeError, Exception) as e_find_col_add:
                        self.logger.warning(f"[AutoSave Added Color] Could not find '재광고' column index: {e_find_col_add}. Defaulting to NEW_AD_BG_COLOR.")

                    # 실제 ID -> 행 인덱스 맵 생성 (ID 업데이트 이후 상태 기준)
                    real_id_to_row_index_shop = {}
                    for r in range(shop_model.rowCount()):
                        item0 = shop_model.item(r, 0)
                        if item0:
                            current_id = item0.data(Qt.UserRole + 3)
                            if isinstance(current_id, int) and current_id > 0:
                                real_id_to_row_index_shop[current_id] = r

                            for real_id in successfully_added_real_ids_shop:
                                row_idx = real_id_to_row_index_shop.get(real_id)
                                if row_idx is not None:
                                    is_re_ad = False
                                    if re_ad_col_index_add != -1:
                                        re_ad_item = shop_model.item(row_idx, re_ad_col_index_add)
                                        if re_ad_item and re_ad_item.text() == "재광고":
                                            is_re_ad = True

                                    target_color = RE_AD_BG_COLOR if is_re_ad else NEW_AD_BG_COLOR
                                    # 행 전체 배경색 설정 (단, 이미 PENDING_COLOR 인 셀은 제외)
                                    for c in range(shop_model.columnCount()):
                                        item = shop_model.item(row_idx, c)
                                        if item:
                                            if item.background().color() != PENDING_COLOR:
                                                item.setBackground(target_color)
                                            # else: PENDING_COLOR 유지
                                else:
                                    self.logger.warning(f"[AutoSave Added Color] Could not find row index for newly added shop real_id: {real_id}")
                            self.logger.info("[AutoSave Callback] Finished setting background color for newly added shop rows.")
                        # <<< 수정 끝 >>>

                        # Clear pending state via manager
                        self.pending_manager.clear_shop_pending_state() # Clear all states on success

            elif result.get("status") == "no_changes":
                message = "저장할 변경 사항이 없습니다."
                self.parent_app.statusBar().showMessage(message, 3000)
                self.is_saving = False
                return # No message box needed, no cleanup signal needed?
            else:
                message = f"저장 실패: {result.get('message', 'Unknown error')}"
                self.logger.warning(f"[Manual Save Shop] Save failed: {message}")

        except Exception as e:
            message = f"저장 중 오류 발생: {e}"
            self.logger.error(f"[Manual Save Shop Callback] Error: {e}", exc_info=True)
        finally:
            self.is_saving = False
            self.parent_app.statusBar().clearMessage()
            
            # 수동 저장 시간 업데이트
            self.last_manual_save_time = time.time()
            
            # --- 수정: QTimer.singleShot으로 UI 정리 예약 ---
            self.logger.info("[Manual Save Shop Callback] Scheduling final UI cleanup via QTimer.singleShot.")
            try:
                # _cleanup_ui_marked_rows() 직접 호출 대신 예약
                QTimer.singleShot(0, self._cleanup_ui_marked_rows)
            except Exception as schedule_e:
                # singleShot 자체에서 오류가 날 가능성은 낮지만 로깅 추가
                self.logger.error(f"[Manual Save Shop Callback] Error scheduling UI cleanup: {schedule_e}", exc_info=True)
            # ------------------------------------------

        # --- 수정: QMessageBox 대신 상태 레이블 사용 ---
        timestamp = datetime.now().strftime("%H:%M:%S")
        status_text = ""
        status_color = "grey"

        if success:
            status_text = f"수동 저장(상가) 완료 ({timestamp}) | 추가: {counts['add']}, 수정: {counts['update']}, 삭제: {counts['delete']}"
            status_color = "green"
            # QMessageBox.information(self.parent_app, "저장 완료", f"{message}\\n추가: {counts['add']}, 수정: {counts['update']}, 삭제: {counts['delete']}")
        elif result and result.get("status") != "no_changes":
            status_text = f"수동 저장(상가) 실패 ({timestamp}): {message}"
            status_color = "red"
            # QMessageBox.critical(self.parent_app, "저장 실패", message)

        if status_text and hasattr(self.sanga_logic, 'autosave_status_label') and self.sanga_logic.autosave_status_label:
            self.sanga_logic.autosave_status_label.setText(status_text)
            self.sanga_logic.autosave_status_label.setStyleSheet(f"color: {status_color}; font-style: italic;")
        # ------------------------------------------

        # Recalculate summary via container
        if hasattr(self.container, '_recalculate_manager_summary'):
            self.container._recalculate_manager_summary()


    def save_pending_oneroom_changes(self):
         """Manually triggered save for Oneroom tab or UI cleanup if needed."""
         if self.is_saving:
             # --- 수정: QMessageBox 대신 상태 레이블 사용 ---
             if hasattr(self.sanga_logic, 'autosave_status_label') and self.sanga_logic.autosave_status_label:
                 self.sanga_logic.autosave_status_label.setText("수동 저장: 진행 중인 작업 있음")
                 self.sanga_logic.autosave_status_label.setStyleSheet("color: orange; font-style: italic;")
             else:
                 QMessageBox.information(self.parent_app, "저장 중", "현재 다른 저장 또는 정리 작업이 진행 중입니다.")
             # -------------------------------------------
             return

         oneroom_pending = self.pending_manager.get_pending_oneroom_changes()
         has_pending = any(oneroom_pending.values())
         needs_ui_cleanup = self._ui_has_rows_marked_for_deletion()

         if not has_pending and not needs_ui_cleanup:
             # --- 수정: QMessageBox 대신 상태 레이블 사용 ---
             timestamp = datetime.now().strftime("%H:%M:%S")
             if hasattr(self.sanga_logic, 'autosave_status_label') and self.sanga_logic.autosave_status_label:
                 self.sanga_logic.autosave_status_label.setText(f"수동 저장(원룸): 변경 없음 ({timestamp})")
                 self.sanga_logic.autosave_status_label.setStyleSheet("color: grey; font-style: italic;")
             else:
                 QMessageBox.information(self.parent_app, "변경 없음", "마이리스트(원룸)에 저장할 변경 사항이나 정리할 UI 항목이 없습니다.")
             # -------------------------------------------
             return

         if has_pending:
            self.is_saving = True
            self.parent_app.statusBar().showMessage("마이리스트(원룸) 저장 중...", 0)
            future = self.parent_app.executor.submit(self._bg_save_oneroom_changes_manual)
            future.add_done_callback(self._on_manual_save_oneroom_completed)
         elif needs_ui_cleanup:
            self.is_saving = True
            self.parent_app.statusBar().showMessage("마이리스트(원룸) UI 정리 중...", 0)
            self.logger.info("[Manual Save Oneroom] No server changes, performing UI cleanup only.")
            try:
                removed_count = self._cleanup_ui_marked_rows()
                self.logger.info(f"[Manual Save Oneroom] UI cleanup finished. Removed {removed_count} rows.")
            except Exception as e:
                 self.logger.error(f"[Manual Save Oneroom] Error during UI cleanup: {e}", exc_info=True)
                 # --- 수정: QMessageBox 대신 상태 레이블 사용 ---
                 timestamp = datetime.now().strftime("%H:%M:%S")
                 if hasattr(self.sanga_logic, 'autosave_status_label') and self.sanga_logic.autosave_status_label:
                     self.sanga_logic.autosave_status_label.setText(f"수동 저장(원룸): UI 정리 오류 ({timestamp})")
                     self.sanga_logic.autosave_status_label.setStyleSheet("color: red; font-style: italic;")
                 else:
                     QMessageBox.critical(self.parent_app, "정리 오류", f"UI 정리 중 오류 발생: {e}")
                 # -------------------------------------------
            finally:
                 self.is_saving = False
                 self.parent_app.statusBar().clearMessage()
                 
         # 수동 저장 시간 업데이트
         self.last_manual_save_time = time.time()

    def _bg_save_oneroom_changes_manual(self):
        """(Background Thread) Prepares and sends ONLY oneroom changes."""
        oneroom_payload = None
        oneroom_pending = self.pending_manager.get_pending_oneroom_changes()
        oneroom_added = oneroom_pending.get("added", [])
        oneroom_updated = oneroom_pending.get("updated", [])
        oneroom_deleted = oneroom_pending.get("deleted", [])

        if not (oneroom_added or oneroom_updated or oneroom_deleted):
            return {"status": "no_changes"}

        try:
            add_up_rows_oneroom = self.oneroom_logic._build_mylist_oneroom_rows_for_changes(oneroom_added, oneroom_updated)
            oneroom_payload = {
                "manager": self.current_manager, 
                "role": self.current_role,
                "added_list": add_up_rows_oneroom["added"],
                "updated_list": add_up_rows_oneroom["updated"],
                "deleted_list": oneroom_deleted
            }
            self.logger.debug("[Manual Save Oneroom] Preparing Payload:")
            self.logger.debug(f"  - Added: {len(oneroom_payload['added_list'])} | Updated: {len(oneroom_payload['updated_list'])} | Deleted: {len(oneroom_payload['deleted_list'])}")
        except Exception as e:
            self.logger.error(f"[Manual Save Oneroom] Failed to build payload: {e}", exc_info=True)
            return {"status": "error", "message": f"Build payload failed: {e}", "inserted_map": {}}

        self.logger.info("[Manual Save Oneroom] Sending changes...")
        url_oneroom = f"http://{self.server_host}:{self.server_port}/mylist/update_mylist_oneroom_items"
        try:
            # <<< 로그 추가: 전송 직전 페이로드 확인 >>>
            payload_to_send_repr = repr(oneroom_payload) # repr()로 전체 내용 확인
            self.logger.info(f"[Manual Save Oneroom] ===> Payload to send to {url_oneroom}: {payload_to_send_repr} <===")
            # <<< 로그 추가 끝 >>>
            resp_oneroom = requests.post(url_oneroom, json=oneroom_payload, timeout=15)
            resp_oneroom.raise_for_status()
            result = resp_oneroom.json()
            self.logger.debug(f"[Manual Save Oneroom] Response received: status={result.get('status')}")
            result["counts"] = {"add": len(add_up_rows_oneroom["added"]), "update": len(add_up_rows_oneroom["updated"]), "delete": len(oneroom_deleted)}
            return result
        except Exception as e:
            self.logger.error(f"[Manual Save Oneroom] Request failed: {e}", exc_info=True)
            return {"status": "error", "message": str(e), "inserted_map": {}, "counts": {"add": 0, "update": 0, "delete": 0}}


    def _on_manual_save_oneroom_completed(self, future):
        """(Main Thread) Handles result of manually triggered oneroom save."""
        success = False
        message = "알 수 없는 오류"
        counts = {"add": 0, "update": 0, "delete": 0}

        try:
            result = future.result()
            if result.get("status") == "ok":
                success = True
                message = "마이리스트(원룸) 변경 사항이 성공적으로 저장되었습니다."
                counts = result.get("counts", counts)
                inserted_map = result.get("inserted_map", {})
                
                # 저장 전 pending 상태 가져오기 (삭제 전)
                oneroom_pending_before_clear = self.pending_manager.get_pending_oneroom_changes()
                self.logger.info(f"[Manual Save Oneroom Callback] Pending state before clear: {oneroom_pending_before_clear}")
                
                if self.oneroom_logic.mylist_oneroom_model:
                     # Update temp IDs
                     if inserted_map:
                         for old_tid_str, new_id in inserted_map.items():
                             try:
                                 self.oneroom_logic.update_mylist_oneroom_row_id(int(old_tid_str), new_id)
                             except (ValueError, TypeError):
                                 self.logger.warning(f"[Manual Save Oneroom Callback] Invalid temp_id_str: {old_tid_str}")

                # <<< 추가: 배경색 복원 로직 시작 (상가용 배경색 복원 로직 참고) >>>
                oneroom_model = self.oneroom_logic.mylist_oneroom_model # 모델 가져오기
                updated_list = oneroom_pending_before_clear.get("updated", [])
                updated_ids_from_pending = set(item['id'] for item in updated_list if isinstance(item, dict) and 'id' in item)
                deleted_ids_from_pending = set(oneroom_pending_before_clear.get("deleted", []))

                if updated_ids_from_pending and oneroom_model:
                    self.logger.info(f"[Manual Save Oneroom Callback] Restoring background color for {len(updated_ids_from_pending)} updated rows.")
                    
                    for r in range(oneroom_model.rowCount()):
                        item0 = oneroom_model.item(r, 0)
                        if not item0: continue
                        record_id = item0.data(Qt.UserRole + 3)
                        
                        # 업데이트된 ID 목록에 있고, 삭제되지 않은 행만 처리
                        if record_id in updated_ids_from_pending and record_id not in deleted_ids_from_pending:                          
                            target_color = NEW_AD_BG_COLOR # 원룸은 NEW_AD_BG_COLOR로 통일
                            
                            # 행 전체 순회하며 노란색 배경을 찾아서 복원
                            for c in range(oneroom_model.columnCount()):
                                item = oneroom_model.item(r, c)
                                if item and item.background() == PENDING_COLOR:
                                    item.setBackground(target_color)
                    self.logger.info("[Manual Save Oneroom Callback] Finished background color restoration.")
                elif oneroom_model is None:
                    self.logger.warning("[Manual Save Oneroom Callback] Skipping background color restoration due to missing model")
                # <<< 배경색 복원 로직 추가 끝 >>>

                # <<< 수정: 새로 추가된 원룸 행 배경색 설정 로직 >>>
                successfully_added_real_ids_or = set(inserted_map.values())
                if successfully_added_real_ids_or and self.oneroom_logic and oneroom_model:
                    self.logger.info(f"[Manual Save Oneroom Callback] Setting final background color for {len(successfully_added_real_ids_or)} newly added oneroom rows (skipping PENDING).")
                    target_color_or = NEW_AD_BG_COLOR

                    # 실제 ID -> 행 인덱스 맵 생성 (ID 업데이트 이후 상태 기준)
                    real_id_to_row_index_or = {}
                    for r in range(oneroom_model.rowCount()):
                        item0 = oneroom_model.item(r, 0)
                        if item0:
                            current_id = item0.data(Qt.UserRole + 3)
                            if isinstance(current_id, int) and current_id > 0:
                                real_id_to_row_index_or[current_id] = r

                            for real_id in successfully_added_real_ids_or:
                                row_idx = real_id_to_row_index_or.get(real_id)
                                if row_idx is not None:
                                    # 행 전체 배경색 설정 (단, PENDING_COLOR 는 제외)
                                    for c in range(oneroom_model.columnCount()):
                                        item = oneroom_model.item(row_idx, c)
                                        if item:
                                            if item.background().color() != PENDING_COLOR:
                                                item.setBackground(target_color_or)
                                            # else: PENDING_COLOR 유지
                                else:
                                    self.logger.warning(f"[Manual Save Oneroom Callback] Could not find row index for newly added oneroom real_id: {real_id}")
                            self.logger.info("[Manual Save Oneroom Callback] Finished setting background color for newly added oneroom rows.")
                        # <<< 수정 끝 >>>

                        # Clear pending state via manager
                    for real_id in successfully_added_real_ids_or:
                        row_idx = real_id_to_row_index_or.get(real_id)
                        if row_idx is not None:
                            # 행 전체 배경색 설정 (단, PENDING_COLOR 는 제외)
                            for c in range(oneroom_model.columnCount()):
                                item = oneroom_model.item(row_idx, c)
                                if item:
                                    if item.background().color() != PENDING_COLOR:
                                        item.setBackground(target_color_or)
                                    # else: PENDING_COLOR 유지
                                else:
                                    self.logger.warning(f"[Manual Save Oneroom Callback] Could not find row index for newly added oneroom real_id: {real_id}")
                            self.logger.info("[Manual Save Oneroom Callback] Finished setting background color for newly added oneroom rows.")
                        # <<< 수정 끝 >>>

                        # Clear pending state via manager
                    self.pending_manager.clear_oneroom_pending_state() # Clear all states on success
                    self.logger.info("[Manual Save Oneroom Callback] Cleared pending oneroom changes.")

            elif result.get("status") == "no_changes":
                message = "저장할 변경 사항이 없습니다."
                self.parent_app.statusBar().showMessage(message, 3000)
                self.is_saving = False
                return # No message box needed
            else:
                message = f"저장 실패: {result.get('message', 'Unknown error')}"
                self.logger.warning(f"[Manual Save Oneroom] Save failed: {message}")

        except Exception as e:
            message = f"저장 중 오류 발생: {e}"
            self.logger.error(f"[Manual Save Oneroom Callback] Error: {e}", exc_info=True)
        finally:
            self.is_saving = False
            self.parent_app.statusBar().clearMessage()
            
            # 수동 저장 시간 업데이트
            self.last_manual_save_time = time.time()
            
            # --- 수정: QTimer.singleShot으로 UI 정리 예약 ---
            self.logger.info("[Manual Save Oneroom Callback] Scheduling final UI cleanup via QTimer.singleShot.")
            try:
                # _cleanup_ui_marked_rows() 직접 호출 대신 예약
                QTimer.singleShot(0, self._cleanup_ui_marked_rows)
            except Exception as schedule_e:
                # singleShot 자체에서 오류가 날 가능성은 낮지만 로깅 추가
                self.logger.error(f"[Manual Save Oneroom Callback] Error scheduling UI cleanup: {schedule_e}", exc_info=True)
            # ------------------------------------------

         # --- 수정: QMessageBox 대신 상태 레이블 사용 ---
        timestamp = datetime.now().strftime("%H:%M:%S")
        status_text = ""
        status_color = "grey"

        if success:
            status_text = f"수동 저장(원룸) 완료 ({timestamp}) | 추가: {counts['add']}, 수정: {counts['update']}, 삭제: {counts['delete']}"
            status_color = "green"
            # QMessageBox.information(self.parent_app, "저장 완료", f"{message}\\n추가: {counts['add']}, 수정: {counts['update']}, 삭제: {counts['delete']}")
        elif result and result.get("status") != "no_changes":
            status_text = f"수동 저장(원룸) 실패 ({timestamp}): {message}"
            status_color = "red"
            # QMessageBox.critical(self.parent_app, "저장 실패", message)

        if status_text and hasattr(self.sanga_logic, 'autosave_status_label') and self.sanga_logic.autosave_status_label:
            self.sanga_logic.autosave_status_label.setText(status_text)
            self.sanga_logic.autosave_status_label.setStyleSheet(f"color: {status_color}; font-style: italic;")
        # ------------------------------------------

        # No summary recalc needed for oneroom currently
        # If needed in future, call container's method:
        # if hasattr(self.container, '_recalculate_oneroom_summary'): 
        #     self.container._recalculate_oneroom_summary() 