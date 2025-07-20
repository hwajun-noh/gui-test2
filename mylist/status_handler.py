# status_handler.py
import threading
import logging
import requests
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox

class MyListStatusHandler:
    """
    마이리스트 상태 변경 처리를 담당하는 클래스
    - 상태 변경 요청 처리
    - 서버 API 호출
    - 상태 변경 결과 처리
    """
    
    def __init__(self, container):
        """상태 핸들러 초기화"""
        self.container = container
        self.logger = logging.getLogger(__name__)
    
    def submit_status_change_task(self, payload, rows_to_remove_from_ui, tab_type):
        """상태 변경 작업을 백그라운드로 제출하고 콜백을 설정합니다."""
        future = self.container.parent_app.executor.submit(
            self._bg_add_completed_deals, 
            payload
        )
        # 콜백에 필요한 정보를 람다를 통해 전달
        future.add_done_callback(
            lambda f: self._on_status_change_completed(f, rows_to_remove_from_ui, tab_type)
        )
    
    def _bg_add_completed_deals(self, payload: dict):
        """(백그라운드 스레드) 상태 변경/계약완료 추가를 위한 서버 엔드포인트를 호출합니다."""
        url = f"http://{self.container.server_host}:{self.container.server_port}/completed/add_completed_deals"
        self.logger.info(f"Entering _bg_add_completed_deals. Sending payload to {url}")
        
        try:
            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            j = resp.json()
            self.logger.debug(f"Received response from {url}: {j}")
            return j 
            
        except requests.Timeout:
            self.logger.error(f"Request timed out calling {url}.")
            return {"status": "exception", "message": "Request timed out"}
            
        except requests.RequestException as ex:
            self.logger.error(f"RequestException calling {url}: {ex}", exc_info=True)
            return {"status": "exception", "message": str(ex)}
            
        except Exception as ex_other:
            self.logger.error(f"Unexpected error calling {url}: {ex_other}", exc_info=True)
            return {"status": "exception", "message": f"Unexpected error: {ex_other}"}
            
        finally:
            self.logger.info(f"Exiting _bg_add_completed_deals for {url}.")
    
    def _on_status_change_completed(self, future, row_indices_to_remove, tab_type):
        """
        (콜백, 잠재적으로 백그라운드 스레드) 상태 변경 API 호출 결과를 처리하여
        메인 스레드에 시그널을 발생시킵니다. UI 업데이트는 연결된 슬롯에서 처리됩니다.
        """
        current_thread = threading.current_thread()
        self.logger.warning(
            f"Entering _on_status_change_completed (Callback Thread). "
            f"Current Thread: {current_thread.name} (ID: {current_thread.ident}). "
            f"Tab type: {tab_type}, Rows to remove: {row_indices_to_remove}"
        )

        try:
            result = future.result()
            self.logger.debug(
                f"Future result received in status change callback: "
                f"status={result.get('status') if result else 'None'}"
            )
            # 시그널 발생
            self.container.statusChangeCompleteSignal.emit(
                result if result else {}, 
                row_indices_to_remove, 
                tab_type
            )
            self.logger.info("Emitted statusChangeCompleteSignal.")
            
        except Exception as e:
            self.logger.error(
                f"Failed to get future result or emit signal in status change callback: {e}", 
                exc_info=True
            )
            # 오류 발생 시에도 시그널을 발생시켜 메인 스레드에서 처리
            error_result = {"status": "exception", "message": f"콜백 처리 오류: {e}"}
            self.container.statusChangeCompleteSignal.emit(
                error_result, 
                row_indices_to_remove, 
                tab_type
            )
            self.logger.info("Emitted statusChangeCompleteSignal with error state.")

        self.logger.warning(
            f"Exiting _on_status_change_completed (Callback Thread). "
            f"Current Thread: {current_thread.name} (ID: {current_thread.ident})"
        )
    
    def process_status_change(self, result, row_indices_to_remove, tab_type):
        """
        (메인 스레드 처리) 상태 변경 API 호출 결과를 처리합니다.
        메인 GUI 스레드에서 실행되므로 UI를 안전하게 업데이트합니다.
        (행 제거, 새로 고침 트리거, 메시지 표시)
        """
        current_thread = threading.current_thread()
        self.logger.warning(
            f"Entering process_status_change (Main Thread). "
            f"Current Thread: {current_thread.name} (ID: {current_thread.ident}). "
            f"Tab type: {tab_type}, Rows to remove: {row_indices_to_remove}"
        )

        model = None
        view = None
        mark_deletion_func = None  # 호출할 pending_manager 함수

        if tab_type == 'shop': 
            model = self.container.sanga_logic.mylist_shop_model
            view = self.container.sanga_logic.mylist_shop_view
            mark_deletion_func = self.container.pending_manager.mark_shop_row_for_deletion
        elif tab_type == 'oneroom': 
            model = self.container.oneroom_logic.mylist_oneroom_model
            view = self.container.oneroom_logic.mylist_oneroom_view
            mark_deletion_func = self.container.pending_manager.mark_oneroom_row_for_deletion

        if result and result.get("status") == "ok":
            self.logger.info(
                f"[process_status_change] Server reported success for status change "
                f"(tab_type='{tab_type}')."
            )

            if model and view and row_indices_to_remove:
                try:
                    # UI에서 제거하기 전에 pending 상태에서 삭제 표시
                    successfully_marked_ids = []
                    for row_idx in row_indices_to_remove:
                        item0 = model.item(row_idx, 0)
                        if item0:
                            record_id = item0.data(Qt.UserRole + 3)
                            if isinstance(record_id, int) and record_id > 0 and mark_deletion_func:
                                mark_deletion_func(record_id)  # 적절한 함수 사용
                                self.logger.info(
                                    f"[process_status_change] Marked {tab_type} row ID {record_id} "
                                    f"for deletion via pending_manager."
                                )
                                successfully_marked_ids.append(record_id)
                            else:
                                self.logger.warning(
                                    f"[process_status_change] Cannot mark row {row_idx} for deletion: "
                                    f"Invalid/temp ID ({record_id}) or no mark function."
                                )
                        else:
                            self.logger.warning(
                                f"[process_status_change] Cannot mark row {row_idx} for deletion: "
                                f"Item 0 not found."
                            )

                    # UI에서 행 제거
                    row_indices_to_remove.sort(reverse=True)
                    view.setSortingEnabled(False) 
                    removed_count = 0
                    for row_idx in row_indices_to_remove:
                        if 0 <= row_idx < model.rowCount():
                            model.removeRow(row_idx)
                            removed_count += 1
                        else:
                            self.logger.warning(
                                f"[process_status_change] Index {row_idx} out of range for {tab_type} model."
                            )
                    if removed_count > 0: 
                        self.logger.info(
                            f"[process_status_change] Successfully removed {removed_count} rows "
                            f"from {tab_type} model."
                        )
                    view.setSortingEnabled(True)

                except Exception as e_remove:
                    self.logger.error(
                        f"[process_status_change] Error removing rows from {tab_type} model: {e_remove}", 
                        exc_info=True
                    )
            
            # '계약완료' 탭 새로 고침 및 사용자 알림
            try: 
                self.container.completed_logic._auto_reload_mylist_completed_deals_data()
                self.logger.info("Triggered completed deals refresh.")
            except Exception as e_refresh: 
                self.logger.error(f"Error triggering completed deals refresh: {e_refresh}", exc_info=True)
                
            try: 
                self.container.parent_app.statusBar().showMessage(f"{tab_type.capitalize()} 상태 변경 완료.", 3000)
                self.logger.info("Status bar updated.")
            except Exception as e_status: 
                self.logger.error(f"Error setting status bar message: {e_status}", exc_info=True)

        else:
            error_message = result.get("message", "서버 오류 또는 콜백 오류") if result else "결과 없음"
            self.logger.error(f"[process_status_change] Status change failed for {tab_type}: {error_message}")
            try: 
                QMessageBox.warning(
                    self.container.parent_app, 
                    "상태 변경 실패", 
                    f"{tab_type.capitalize()} 상태 변경 중 오류:\n{error_message}"
                )
            except Exception as e_msgbox: 
                self.logger.error(f"Error showing warning message box: {e_msgbox}", exc_info=True)

        self.logger.warning(f"Exiting process_status_change (Main Thread).")