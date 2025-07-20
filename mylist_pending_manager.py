import logging
from PyQt5.QtCore import QObject

class MyListPendingManager(QObject):
    """Handles the pending changes (added, updated, deleted) for MyList tabs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        
        # Shared Pending Changes State
        self.shop_pending = {"added": [], "deleted": [], "updated": []}
        self.oneroom_pending = {"added": [], "deleted": [], "updated": []}

        # Temporary ID Counter
        self._temp_id_counter = 0
        self.logger.info("MyListPendingManager initialized.")

    def generate_temp_id(self):
        """Generates unique negative IDs for temporary rows."""
        self._temp_id_counter -= 1
        self.logger.debug(f"Generated temporary ID: {self._temp_id_counter}")
        return self._temp_id_counter

    def add_pending_shop_add(self, temp_id):
        """Adds a temporary shop row ID to the pending added list."""
        row_data = {"temp_id": temp_id}
        if row_data not in self.shop_pending["added"]:
            self.shop_pending["added"].append(row_data)
            self.logger.debug(f"Added shop item (temp_id={temp_id}) to pending adds.")
        else:
            self.logger.warning(f"Attempted to add duplicate temp_id {temp_id} to shop pending adds.")

    def add_pending_oneroom_add(self, temp_id):
        """Adds a temporary oneroom row ID to the pending added list."""
        row_data = {"temp_id": temp_id}
        if row_data not in self.oneroom_pending["added"]:
            self.oneroom_pending["added"].append(row_data)
            self.logger.debug(f"Added oneroom item (temp_id={temp_id}) to pending adds.")
        else:
             self.logger.warning(f"Attempted to add duplicate temp_id {temp_id} to oneroom pending adds.")

    def add_pending_shop_update(self, update_data):
         """Adds or updates an item in the pending shop update list."""
         record_id = update_data.get("id")
         if not record_id or record_id < 0: # Do not track updates for temp IDs
              return
         
         # Check if already marked for deletion
         if record_id in self.shop_pending["deleted"]:
              self.logger.debug(f"Shop item ID {record_id} is marked for deletion, ignoring update.")
              return

         existing_update = next((item for item in self.shop_pending["updated"] if item.get("id") == record_id), None)
         if existing_update:
             existing_update.update(update_data) # Merge changes
             self.logger.debug(f"Updated existing pending shop update for ID {record_id}.")
         else:
             self.shop_pending["updated"].append(update_data)
             self.logger.debug(f"Added new pending shop update for ID {record_id}.")

    def add_pending_oneroom_update(self, update_data):
         """Adds or updates an item in the pending oneroom update list."""
         record_id = update_data.get("id")
         if not record_id or record_id < 0:
             return

         if record_id in self.oneroom_pending["deleted"]:
             self.logger.debug(f"Oneroom item ID {record_id} is marked for deletion, ignoring update.")
             return
             
         existing_update = next((item for item in self.oneroom_pending["updated"] if item.get("id") == record_id), None)
         if existing_update:
             existing_update.update(update_data)
             self.logger.debug(f"Updated existing pending oneroom update for ID {record_id}.")
         else:
             self.oneroom_pending["updated"].append(update_data)
             self.logger.debug(f"Added new pending oneroom update for ID {record_id}.")

    def mark_shop_row_for_deletion(self, record_id):
        """Marks a shop row ID for deletion in the pending state."""
        if isinstance(record_id, int):
            if record_id > 0: # Real DB ID
                if record_id not in self.shop_pending["deleted"]:
                    self.shop_pending["deleted"].append(record_id)
                    # If it was marked for update, remove it from updates
                    self.shop_pending["updated"] = [upd for upd in self.shop_pending["updated"] if upd.get("id") != record_id]
                    self.logger.debug(f"Marked shop item ID {record_id} for deletion.")
                else:
                    self.logger.debug(f"Shop item ID {record_id} was already marked for deletion.")
            elif record_id < 0: # Temporary ID
                # Remove from pending added list
                original_len = len(self.shop_pending["added"])
                self.shop_pending["added"] = [add for add in self.shop_pending["added"] if add.get("temp_id") != record_id]
                if len(self.shop_pending["added"]) < original_len:
                     self.logger.debug(f"Removed temporary shop item (temp_id={record_id}) from pending adds.")
        else:
             self.logger.warning(f"Invalid record_id type ({type(record_id)}) passed to mark_shop_row_for_deletion.")


    def mark_oneroom_row_for_deletion(self, record_id):
        """Marks an oneroom row ID for deletion in the pending state."""
        if isinstance(record_id, int):
            if record_id > 0:
                if record_id not in self.oneroom_pending["deleted"]:
                    self.oneroom_pending["deleted"].append(record_id)
                    self.oneroom_pending["updated"] = [upd for upd in self.oneroom_pending["updated"] if upd.get("id") != record_id]
                    self.logger.debug(f"Marked oneroom item ID {record_id} for deletion.")
                else:
                     self.logger.debug(f"Oneroom item ID {record_id} was already marked for deletion.")
            elif record_id < 0:
                original_len = len(self.oneroom_pending["added"])
                self.oneroom_pending["added"] = [add for add in self.oneroom_pending["added"] if add.get("temp_id") != record_id]
                if len(self.oneroom_pending["added"]) < original_len:
                     self.logger.debug(f"Removed temporary oneroom item (temp_id={record_id}) from pending adds.")
        else:
             self.logger.warning(f"Invalid record_id type ({type(record_id)}) passed to mark_oneroom_row_for_deletion.")


    def clear_shop_pending_state(self, clear_added=True, clear_updated=True, clear_deleted=True):
        """Clears the specified pending states for the shop tab."""
        cleared = []
        if clear_added: 
            if self.shop_pending["added"]: cleared.append("added")
            self.shop_pending["added"] = []
        if clear_updated: 
            if self.shop_pending["updated"]: cleared.append("updated")
            self.shop_pending["updated"] = []
        if clear_deleted: 
            if self.shop_pending["deleted"]: cleared.append("deleted")
            self.shop_pending["deleted"] = []
        if cleared:
            self.logger.debug(f"Cleared shop pending state for: {', '.join(cleared)}.")

    def clear_oneroom_pending_state(self, clear_added=True, clear_updated=True, clear_deleted=True):
        """Clears the specified pending states for the oneroom tab."""
        cleared = []
        if clear_added: 
            if self.oneroom_pending["added"]: cleared.append("added")
            self.oneroom_pending["added"] = []
        if clear_updated: 
            if self.oneroom_pending["updated"]: cleared.append("updated")
            self.oneroom_pending["updated"] = []
        if clear_deleted: 
            if self.oneroom_pending["deleted"]: cleared.append("deleted")
            self.oneroom_pending["deleted"] = []
        if cleared:
            self.logger.debug(f"Cleared oneroom pending state for: {', '.join(cleared)}.")

    def has_pending_changes(self):
         """Checks if there are any pending changes across all tabs."""
         shop_has_changes = any(self.shop_pending.values())
         oneroom_has_changes = any(self.oneroom_pending.values())
         return shop_has_changes or oneroom_has_changes

    def get_pending_shop_changes(self):
         """Returns the current pending shop changes."""
         return self.shop_pending

    def get_pending_oneroom_changes(self):
         """Returns the current pending oneroom changes."""
         return self.oneroom_pending 

    def set_shop_pending_update(self, record_id, row_index, col_index, value):
        """
        직접 행/열 인덱스와 값을 사용하여 상가 pending updates를 설정합니다.
        행 ID를 키로 사용하여 컬럼 인덱스와 값을 매핑합니다.
        
        Args:
            record_id (int): 데이터베이스 레코드 ID
            row_index (int): UI 모델의 행 인덱스
            col_index (int): UI 모델의 열 인덱스
            value (str): 셀의 새 값
        """
        if not isinstance(record_id, int) or record_id <= 0:
            self.logger.warning(f"Invalid record_id: {record_id} (type: {type(record_id)}). Must be positive integer.")
            return False
            
        # 삭제 예정인 행은 업데이트하지 않음
        if record_id in self.shop_pending["deleted"]:
            self.logger.debug(f"Shop item ID {record_id} is marked for deletion, ignoring update.")
            return False
            
        # 이미 업데이트 목록에 있는지 확인
        existing_update = None
        for item in self.shop_pending["updated"]:
            if item.get("id") == record_id:
                existing_update = item
                break
                
        if not existing_update:
            # 새 업데이트 항목 생성
            existing_update = {"id": record_id, "col_changes": {}}
            self.shop_pending["updated"].append(existing_update)
            
        # 컬럼 변경 사항 기록
        if "col_changes" not in existing_update:
            existing_update["col_changes"] = {}
            
        existing_update["col_changes"][col_index] = value
        self.logger.info(f"Updated pending_updates for shop item ID {record_id}, Col: {col_index}, Value: '{value}'")
        
        return True
        
    def ensure_shop_item_in_pending_adds(self, temp_id, row_index):
        """
        상가 아이템이 pending_adds에 존재하는지 확인하고, 없으면 추가합니다.
        임시 행에 대해서만 작동합니다.
        
        Args:
            temp_id (int): 임시 ID (음수)
            row_index (int): UI 모델의 행 인덱스
        """
        if not isinstance(temp_id, int) or temp_id >= 0:
            self.logger.warning(f"Invalid temp_id: {temp_id} (type: {type(temp_id)}). Must be negative integer.")
            return False
            
        # 이미 추가 목록에 있는지 확인
        for item in self.shop_pending["added"]:
            if item.get("temp_id") == temp_id:
                # 이미 존재함
                self.logger.debug(f"Shop item with temp_id {temp_id} already in pending_adds.")
                return True
                
        # 없으면 추가
        new_item = {"temp_id": temp_id, "row_index": row_index}
        self.shop_pending["added"].append(new_item)
        self.logger.info(f"Added shop item with temp_id {temp_id} to pending_adds.")
        return True 