import logging
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox, QAbstractItemView, QDialog, QInputDialog

from ui_utils import show_context_menu
from dialogs import MultiGuDongDialog, BizSelectDialog, SearchDialogForShop, NaverShopSearchDialog, CalendarPopup

logger = logging.getLogger(__name__)

class ManagerUIMixin:
    """ManagerCheckTab의 UI 관련 메서드를 관리하는 Mixin 클래스"""
    
    def on_select_dong_clicked(self):
        """Handles the 'Select Dong' button click."""
        # Logic from main_app_part7/on_select_dong_clicked
        # Needs parent_app.district_data
        if not hasattr(self.parent_app, 'district_data') or not self.parent_app.district_data:
            QMessageBox.warning(self.parent_app, "오류", "동 지역 데이터가 없습니다.")
            return
            
        # Use local real_dong_map (built during refresh) and selected_dongs_by_gu
        # Initialize if they don't exist yet
        if not hasattr(self, 'real_dong_map'): self.real_dong_map = {} 
        if not hasattr(self, 'selected_dongs_by_gu'): self.selected_dongs_by_gu = {}
             
        dlg = MultiGuDongDialog(
            real_dong_map=self.real_dong_map, # Use local map
            selected_dongs_by_gu=self.selected_dongs_by_gu, # Use local state
            parent=self.parent_app
        )
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.selected_dongs_by_gu = dlg.get_selected_dongs_by_gu()
            self.update_selected_dongs_label() # Update local label
            self.apply_local_filter_manager_data() # Apply filter locally

    def update_selected_dongs_label(self):
        """Updates the label showing selected dongs."""
        # Logic from main_app_part7/update_selected_dongs_label
        summary_parts = []
        tooltip_lines = []
        if not hasattr(self, 'selected_dongs_by_gu'): self.selected_dongs_by_gu = {}
        for gu_name, dset in self.selected_dongs_by_gu.items():
            if not dset: continue
            summary_parts.append(f"{gu_name}({len(dset)})")
            # Make sure dset is iterable and sortable (should be set or list)
            try: 
                line = f"{gu_name}: {', '.join(sorted(list(dset)))}"
                tooltip_lines.append(line)
            except TypeError:
                 print(f"[WARN] Could not sort dongs for GU: {gu_name}")
                 line = f"{gu_name}: {dset}" # Fallback
                 tooltip_lines.append(line)
                 
        if not summary_parts:
            self.lbl_selected_dongs.setText("(선택된 동 없음)")
            self.lbl_selected_dongs.setToolTip("")
        else:
            short_str = ", ".join(summary_parts)
            tip_str   = "\n".join(tooltip_lines)
            # Ensure labels exist before setting text
            if hasattr(self, 'lbl_selected_dongs') and self.lbl_selected_dongs:
                 self.lbl_selected_dongs.setText(short_str)
                 self.lbl_selected_dongs.setToolTip(tip_str)

    def on_select_biz_clicked(self):
        """Handles the 'Select Biz' button click."""
        # 다이얼로그를 열기 전에 무조건 업종 목록 갱신 (상가고객 추가/삭제 반영)
        if hasattr(self, 'cached_manager_data_1month') and self.cached_manager_data_1month:
            self.logger.info("업종 선택 다이얼로그 열기 전에 업종 목록을 갱신합니다.")
            old_count = len(self.real_biz_set) if hasattr(self, 'real_biz_set') else 0
            self.real_biz_set = self.build_real_biz_set(self.cached_manager_data_1month)
            new_count = len(self.real_biz_set)
            self.logger.info(f"업종 목록 갱신 결과: {old_count}개 → {new_count}개")
            
            # 선택된 업종 중 더 이상 존재하지 않는 업종이 있는지 확인
            if hasattr(self, 'selected_biz_types') and self.selected_biz_types:
                valid_selected_biz = [biz for biz in self.selected_biz_types if biz in self.real_biz_set]
                if len(valid_selected_biz) != len(self.selected_biz_types):
                    self.logger.info(f"선택된 업종 중 {len(self.selected_biz_types) - len(valid_selected_biz)}개가 더 이상 존재하지 않아 제거합니다.")
                    self.selected_biz_types = valid_selected_biz
                    # 필터 레이블 업데이트
                    display_text = "; ".join(valid_selected_biz)
                    if hasattr(self, 'lbl_selected_biz') and self.lbl_selected_biz:
                        self.lbl_selected_biz.setText(display_text if display_text else "(없음)")
                        self.lbl_selected_biz.setToolTip(display_text)
        else:
            # 캐시된 데이터가 없으면 초기 업종 세트 생성
            if not hasattr(self, 'real_biz_set'):
                self.real_biz_set = set()
                self.logger.warning("캐시된 데이터가 없어 빈 업종 목록을 사용합니다.")
             
        # already_selected = [x.strip() for x in self.filter_biz_value.split(",") if x.strip()] if self.filter_biz_value else [] # 삭제
        already_selected = self.selected_biz_types # 리스트 직접 사용
        all_biz = sorted(list(self.real_biz_set))

        dlg = BizSelectDialog(biz_list=all_biz, pre_selected=already_selected, parent=self.parent_app)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            chosen_list = dlg.get_selected_biz() # 올바른 메소드 이름으로 수정
            # joined = ",".join(chosen_list) # 삭제
            # self.filter_biz_value = joined # 삭제
            self.selected_biz_types = chosen_list # 리스트로 저장
            # Update local label only if it exists
            display_text = "; ".join(chosen_list) # 라벨 구분자를 세미콜론+공백으로 변경
            if hasattr(self, 'lbl_selected_biz') and self.lbl_selected_biz:
                 self.lbl_selected_biz.setText(display_text if display_text else "(없음)") 
                 self.lbl_selected_biz.setToolTip(display_text)
            self.apply_local_filter_manager_data() # Apply filter locally

    def on_select_date_clicked(self):
        """Handles the 'Select Date' button click."""
        # Logic from main_app_part7/on_select_date_clicked
        if self.popup_calendar is None:
            # Parent dialog to main window for better positioning/modality
            self.popup_calendar = CalendarPopup(self.parent_app) 
            self.popup_calendar.dateApplied.connect(self.on_date_applied)

        # Ensure btn_select_date exists before mapping coordinates
        if not hasattr(self, 'btn_select_date') or not self.btn_select_date: return
        
        btn_global_pos = self.btn_select_date.mapToGlobal(QtCore.QPoint(0, 0))
        x = btn_global_pos.x(); y = btn_global_pos.y() + self.btn_select_date.height()
        self.popup_calendar.show(); self.popup_calendar.adjustSize()
        popup_width = self.popup_calendar.width()
        x_aligned = x + self.btn_select_date.width() - popup_width
        if x_aligned < 0: x_aligned = 0
        self.popup_calendar.move(x_aligned, y)
        self.popup_calendar.activateWindow() # Bring to front

    def on_date_applied(self, date_list):
        """Callback when dates are selected from the calendar popup."""
        # Logic from main_app_part7/on_date_applied
        if not date_list:
            self.filter_ad_date_value = "" # Update local state
            # Update local label only if it exists
            if hasattr(self, 'lbl_selected_dates') and self.lbl_selected_dates:
                 self.lbl_selected_dates.setText("(날짜 선택 없음)")
        else:
            self.filter_ad_date_value = ",".join(date_list) # Update local state
            # Update local label only if it exists
            if hasattr(self, 'lbl_selected_dates') and self.lbl_selected_dates:
                 self.lbl_selected_dates.setText(f"{date_list[0]} ~ {date_list[-1]}")
        self.reload_manager_data_with_filter() # Reload or filter based on new dates

    def show_manager_check_search_dialog(self):
        """Shows the search dialog for the manager check table."""
        # Logic from main_app_part7/show_manager_check_search_dialog
        # Assuming SearchDialogForShop works with QTableView/QStandardItemModel
        dlg = SearchDialogForShop(self.check_manager_view, parent=self.parent_app)
        dlg.exec_()

    def on_check_current_changed(self, current: QtCore.QModelIndex, previous: QtCore.QModelIndex):
        """Handles row changes in the manager check table."""
        import time
        timestamp = time.time()
        
        # 🔍 디버깅: 시그널 호출 확인
        print(f"[DEBUG] on_check_current_changed CALLED! current.isValid()={current.isValid()}")
        print(f"[🕒 TIMING] on_check_current_changed 호출 시각: {timestamp}")
        
        # Logic from main_app_part9/on_check_current_changed
        if not current.isValid(): 
            print("[DEBUG] on_check_current_changed: current index is not valid")
            return
        new_row = current.row()
        old_row = previous.row()
        print(f"[DEBUG] on_check_current_changed: new_row={new_row}, old_row={old_row}")
        
        if new_row == old_row: 
            print("[DEBUG] on_check_current_changed: same row selected, skipping")
            return 

        selection_model = self.check_manager_view.selectionModel()
        selected_rows = set(idx.row() for idx in selection_model.selectedIndexes())
        selected_indexes_info = [f"row={idx.row()}, col={idx.column()}" for idx in selection_model.selectedIndexes()]
        print(f"[DEBUG] on_check_current_changed: selected_rows={selected_rows}")
        print(f"[DEBUG] on_check_current_changed: selected_indexes={selected_indexes_info}")
        
        if len(selected_rows) > 1:
            print("[INFO] ManagerCheckTab: multiple rows selected -> skip dependent tab reload")
            if hasattr(self.parent_app, 'clear_last_selected_address'):
                 self.parent_app.clear_last_selected_address()
            return
            
        idx_addr = self.manager_source_model.index(new_row, 0) # Assuming address is col 0
        addr_str = self.manager_source_model.data(idx_addr, QtCore.Qt.DisplayRole) or ""

        # 🚫 중복 요청 방지: 최근 요청한 주소와 동일한 경우 스킵
        if hasattr(self, '_last_requested_address') and self._last_requested_address == addr_str:
            print(f"[DEBUG] on_check_current_changed: 중복 요청 방지 - 이미 요청한 주소: {addr_str}")
            print(f"[🕒 TIMING] 중복 요청 차단 시각: {timestamp}")
            return
        
        # 현재 주소 저장
        self._last_requested_address = addr_str
        print(f"[🔄 STATE] _last_requested_address 업데이트: '{addr_str}'")

        print(f"[INFO] ManagerCheckTab on_check_current_changed => address={addr_str}")
        print(f"[🕒 TIMING] API 요청 시작 예정 시각: {timestamp}")
        
        # Notify parent app about the selected address
        if hasattr(self.parent_app, 'update_selection_from_manager_check'):
             print(f"[DEBUG] Calling update_selection_from_manager_check with address: {addr_str}")
             self.parent_app.update_selection_from_manager_check(addr_str)
        else:
             print("[ERROR] parent_app does not have update_selection_from_manager_check method!")

    def on_check_tab_context_menu_requested(self, pos):
        """Handles context menu requests on the manager check table."""
        # Logic from main_app_part2/on_check_tab_context_menu_requested
        # Needs to call parent_app.show_context_menu with correct callbacks (local methods)
        # Call the utility function instead
        show_context_menu(
            parent_widget=self.check_manager_view, # Pass the view as parent
            pos=pos,
            table_view=self.check_manager_view,
            register_callback=self.on_register_recommend_check_tab, # Local method
            copy_callback=self.on_copy_rows_to_mylist_manager, # Local method
            status_callback=self.parent_app.on_set_completed_status # Use parent app's status handler
        )

    def on_register_recommend_check_tab(self, index: QtCore.QModelIndex):
        """Callback for 'Register Recommend' context menu action. Calls parent app's common handler."""
        # Logic from main_app_part2/on_register_recommend_check_tab - Now delegates to parent
        if not index.isValid():
            logger.warning("ManagerCheckTab: on_register_recommend_check_tab called with invalid index.")
            return

        # Call the parent app's unified recommend registration method
        if hasattr(self.parent_app, 'do_register_recommend'):
            self.parent_app.do_register_recommend(
                index=index, 
                table_model=self.manager_source_model, # Pass this tab's model
                calling_tab_name="ManagerCheckTab"     # Identify the calling tab
            )
        else:
            logger.error("ManagerCheckTab: parent_app does not have do_register_recommend method.")
            QMessageBox.warning(self.parent_app, "오류", "추천 등록 기능을 실행할 수 없습니다.")

    def on_copy_rows_to_mylist_manager(self):
        """Callback for 'Copy to My List' context menu action."""
        # Logic from main_app_part2/on_copy_rows_to_mylist
        if hasattr(self.parent_app, 'do_copy_rows_to_mylist'):
            is_admin_ = (self.current_role == "admin")
            self.parent_app.do_copy_rows_to_mylist(
                table_view  = self.check_manager_view,
                table_model = self.manager_source_model,
                is_admin    = is_admin_
            )

    def on_manager_item_changed(self, item: QtGui.QStandardItem):
        """Handles item changes in the model (e.g., edits)."""
        # Logic potentially from main_app_part8
        if self.loading_data_flag: return 
        
        row = item.row(); col = item.column()
        item_0 = self.manager_source_model.item(row, 0)
        if not item_0: return
        pk_id = item_0.data(QtCore.Qt.UserRole + 3)
        if not pk_id: return
        
        header_item = self.manager_source_model.horizontalHeaderItem(col)
        if not header_item: return
        header_text = header_item.text()
        new_value = item.text()
        
        # if pk_id not in self.manager_pending_updates: self.manager_pending_updates[pk_id] = {}
        # self.manager_pending_updates[pk_id][header_text] = new_value
        # # Activate save timer
        # if hasattr(self, 'manager_batch_timer'): self.manager_batch_timer.start()

    def on_manager_view_double_clicked(self, index: QtCore.QModelIndex):
        """Handles double clicks, potentially for editing specific columns."""
        # Logic potentially from main_app_part8
        if not index.isValid(): return
        col = index.column(); row = index.row()
        model = self.manager_source_model
        header_item = model.horizontalHeaderItem(col)
        if not header_item: return
        header_text = header_item.text()

        if header_text == "확인메모":
             item_0 = model.item(row, 0)
             pk_id = item_0.data(QtCore.Qt.UserRole + 3) if item_0 else None
             if not pk_id: return
             current_memo = model.data(index, QtCore.Qt.DisplayRole) or ""
             new_memo, ok = QtWidgets.QInputDialog.getMultiLineText(self.parent_app, f"확인메모 수정 (ID: {pk_id})", "메모 입력:", current_memo)
             if ok and new_memo != current_memo:
                 # Update model (this will trigger on_manager_item_changed -> adds to pending_updates)
                 model.setData(index, new_memo)
                 # Ensure save timer is started
                 # if hasattr(self, 'manager_batch_timer'): self.manager_batch_timer.start()

    def on_open_sanga_tk(self):
        """Handles the 'Naver Real Estate Check' button click."""
        # Logic from main_app_part9/on_open_sanga_tk
        data_list = self.table_to_data_list() 
        if not data_list:
            QMessageBox.warning(self.parent_app, "오류", "표에 데이터가 없습니다.")
            return
        
        current_index = self.check_manager_view.currentIndex()
        current_row = current_index.row() if current_index.isValid() else 0
        
        def row_callback(pk_id, new_index):
            try:
                # 애플리케이션이 종료 중인지 확인
                if hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
                    self.logger.warning("애플리케이션이 종료 중이므로 콜백 무시")
                    return
                    
                # executor가 이미 종료되었는지 확인
                if (hasattr(self.parent_app, 'executor') and 
                    hasattr(self.parent_app.executor, '_shutdown') and 
                    self.parent_app.executor._shutdown):
                    self.logger.warning("ThreadPoolExecutor가 이미 종료되어 콜백을 처리할 수 없습니다.")
                    return
                
                # 종료 상태가 아니면 하이라이트 처리
                self.highlight_by_id(pk_id)
            except Exception as e:
                # 콜백 처리 중 오류가 발생해도 애플리케이션이 종료되지 않도록 처리
                self.logger.error(f"Sanga TK 콜백 처리 중 오류: {e}", exc_info=True)
        
        try: from my_selenium_tk import launch_selenium_tk 
        except ImportError:
             QMessageBox.critical(self.parent_app, "오류", "Selenium/Tk 모듈을 찾을 수 없습니다.")
             return
             
        # 종료 시 안전하게 처리하기 위한 플래그 설정
        if not hasattr(self.parent_app, 'tk_windows_open'):
            self.parent_app.tk_windows_open = 0
            
        self.parent_app.tk_windows_open += 1
        
        # TK 창 종료 시 호출될 추가 콜백 정의
        def on_tk_window_closed():
            try:
                if hasattr(self.parent_app, 'tk_windows_open'):
                    self.parent_app.tk_windows_open -= 1
                    self.logger.info(f"TK 창 종료됨. 남은 창 수: {self.parent_app.tk_windows_open}")
            except Exception as e:
                self.logger.error(f"TK 창 종료 콜백 처리 중 오류: {e}", exc_info=True)
             
        launch_selenium_tk(
            data_list,
            parent_app=self.parent_app,
            row_callback=row_callback,
            start_index=current_row,
            on_close_callback=on_tk_window_closed  # 종료 콜백 추가
        )

    def on_naver_search_clicked_manager(self):
        """Handles the 'Naver Property Search' button click in ManagerCheckTab."""
        self.logger.info("ManagerCheckTab: 'Naver Property Search' button clicked.")

        # --- 다이얼로그 재사용 또는 새로 생성 ---
        # ManagerCheckTab 인스턴스에 다이얼로그 참조 저장 확인
        if hasattr(self, 'naver_search_dialog') and self.naver_search_dialog and self.naver_search_dialog.isVisible():
            self.logger.info("Existing Naver Search Dialog found for ManagerCheckTab. Activating.")
            self.naver_search_dialog.activateWindow()
            self.naver_search_dialog.raise_()
            return # 이미 열려있으면 새로 생성하지 않음
        # ------------------------------------

        # MyListContainer 참조 가져오기 (parent_app에 mylist_tab 속성이 있다고 가정)
        mylist_container = getattr(self.parent_app, 'mylist_tab', None)
        if not mylist_container:
            self.logger.error("Cannot open Naver Search Dialog: MyListContainer reference not found in parent_app (expected 'mylist_tab').")
            QMessageBox.warning(self.parent_app, "오류", "마이리스트 탭(MyListContainer) 참조를 찾을 수 없습니다.")
            return
            
        # NaverShopSearchDialog 생성 및 실행
        try:
            # dialogs 모듈 임포트 확인 (파일 상단에 추가 필요할 수 있음)
            from dialogs import NaverShopSearchDialog 
            
            # --- 다이얼로그 인스턴스를 self 속성으로 저장 ---
            self.naver_search_dialog = NaverShopSearchDialog(
                parent_app=self.parent_app,
                mylist_tab=mylist_container, # MyListContainer 참조 전달
                server_host=self.server_host, # 서버 정보 전달 (필요시)
                server_port=self.server_port  # 서버 정보 전달 (필요시)
            )
            # -----------------------------------------

            # <<< 시그널 연결 추가 >>>
            if hasattr(self.parent_app, 'all_tab') and hasattr(self.parent_app.all_tab, 'search_by_address'):
                 # --- 수정: 메인 앱의 중앙 핸들러에 연결 ---
                 if hasattr(self.parent_app, 'handle_address_selection_from_dialog'):
                     self.naver_search_dialog.addressClicked.connect(self.parent_app.handle_address_selection_from_dialog)
                     self.logger.info("Connected NaverShopSearchDialog.addressClicked to main_app.handle_address_selection_from_dialog")
                 else:
                     self.logger.warning("Could not connect addressClicked signal: main_app.handle_address_selection_from_dialog slot not found.")
                 # self.naver_search_dialog.addressClicked.connect(self.parent_app.all_tab.search_by_address) # 이전 연결 주석 처리
                 # self.logger.info("Connected NaverShopSearchDialog.addressClicked to AllTab.search_by_address") # 이전 로그 주석 처리
                 # ------------------------------------
            else:
                 self.logger.warning("Could not connect addressClicked signal: all_tab or search_by_address slot not found.")
            # <<< --- >>>

            self.naver_search_dialog.show() # 모달리스로 실행
            self.logger.info("Naver Search Dialog shown (modeless).") # 로그 메시지 수정
            
        except ImportError:
            self.logger.error("Failed to import NaverShopSearchDialog.")
            QMessageBox.critical(self.parent_app, "오류", "네이버 검색 다이얼로그를 로드할 수 없습니다.")
        except Exception as e:
            self.logger.error(f"Error opening Naver Search Dialog: {e}", exc_info=True)
            QMessageBox.critical(self.parent_app, "오류", f"네이버 검색 다이얼로그 실행 중 오류 발생:\n{e}")
            
    def on_new_manager_shop_refresh(self):
        """Handles the refresh button click for new manager data."""
        # Logic from main_app_part8/on_new_manager_shop_refresh
        # Needs access to local _new_manager_data_list
        if not hasattr(self, '_new_manager_data_list') or not self._new_manager_data_list:
            QMessageBox.information(self.parent_app, "새 매물", "추가할 매물이 없습니다.")
            # Assume button is managed here or reference it if needed
            # if hasattr(self, 'btn_new_refresh_manager'): self.btn_new_refresh_manager.hide()
            return

        new_rows = self._new_manager_data_list[:]
        self._new_manager_data_list.clear()

        # Call local method to append rows
        self.append_rows_to_manager_table(new_rows) # Assuming this method exists
        
        # Notify parent about new addresses if necessary 
        new_addresses = set()
        for row in new_rows:
            d_ = row.get("dong",""); j_ = row.get("jibun","")
            if d_ or j_: addr = (d_ + " " + j_).strip()
            if addr: new_addresses.add(addr)
        if new_addresses and hasattr(self.parent_app, 'notify_new_addresses_loaded'):
            self.parent_app.notify_new_addresses_loaded(new_addresses)
                
        # Update/hide the button (assuming it's part of this tab UI)
        if hasattr(self, 'btn_new_refresh_manager') and self.btn_new_refresh_manager:
            self.btn_new_refresh_manager.setText("새로고침(0)")
            self.btn_new_refresh_manager.hide()

        QMessageBox.information(self.parent_app, "추가 완료", f"{len(new_rows)}개 매물을 추가했습니다.")
        
    def process_recommend_from_tk(self, row_data, upjong_memo_list):
        """
        TK 창에서 호출하는 추천매물 등록 처리 메서드
        
        Args:
            row_data (dict): 행 데이터 (주소, ID, 출처, lat, lng 등)
            upjong_memo_list (list): 업종별 메모 리스트 (e.g. [{"biz": "카페", "memo": "추천예정"}, ...])
            
        Returns:
            bool: 성공 여부
        """
        try:
            self.logger.info(f"TK 창에서 추천매물 등록 요청: 주소={row_data.get('주소', '')}, 업종 수={len(upjong_memo_list)}")
            
            # 애플리케이션이 종료 중인지 확인
            if hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
                self.logger.warning("애플리케이션이 종료 중이므로 추천매물 등록 요청을 무시합니다.")
                return False
                
            # ThreadPoolExecutor 상태 확인 - 종료 중이면 작업 취소
            if (hasattr(self.parent_app, 'executor') and 
                (not hasattr(self.parent_app, 'executor') or
                 hasattr(self.parent_app.executor, '_shutdown') and self.parent_app.executor._shutdown)):
                self.logger.warning("ThreadPoolExecutor가 이미 종료되어 추천매물 등록을 처리할 수 없습니다.")
                return False
                
            # 전역 종료 상태 확인
            if 'APP_SHUTTING_DOWN' in globals() and globals().get('APP_SHUTTING_DOWN', False):
                self.logger.warning("글로벌 종료 플래그가 설정되어 있어 추천매물 등록 요청을 무시합니다.")
                return False
                
            # 업종별 메모 목록이 비어있는지 확인
            if not upjong_memo_list:
                self.logger.warning("업종별 메모 목록이 비어있어 추천매물 등록을 진행할 수 없습니다.")
                return False
                
            # 부모 앱의 추천매물 등록 기능 호출
            if hasattr(self.parent_app, 'do_register_recommend'):
                # 현재 테이블의 모델에서 행 인덱스 찾기
                row_idx = self.find_row_by_id(row_data.get('id'))
                if row_idx is None:
                    self.logger.warning(f"ID {row_data.get('id')}에 해당하는 행을 찾을 수 없습니다.")
                    
                    # 애플리케이션이 종료 중인지 한번 더 확인
                    if hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
                        self.logger.warning("애플리케이션이 종료 중이므로 새 행 추가를 취소합니다.")
                        return False
                    
                    # executor 상태 한번 더 확인
                    if (hasattr(self.parent_app, 'executor') and 
                        hasattr(self.parent_app.executor, '_shutdown') and 
                        self.parent_app.executor._shutdown):
                        self.logger.warning("ThreadPoolExecutor가 이미 종료되어 새 행 추가를 취소합니다.")
                        return False
                    
                    # 임시 인덱스 생성
                    temp_index = QtCore.QModelIndex()
                    
                    # 새로운 행 데이터를 테이블에 추가해야 하는 경우
                    new_rows = [{
                        "shop_id": row_data.get('id'),
                        "dong": row_data.get('주소', '').split(' ')[0] if ' ' in row_data.get('주소', '') else '',
                        "jibun": ' '.join(row_data.get('주소', '').split(' ')[1:]) if ' ' in row_data.get('주소', '') else row_data.get('주소', ''),
                        "lat": row_data.get('lat', ''),
                        "lng": row_data.get('lng', ''),
                        "biz_manager_list": [{"biz": item.get("biz", "")} for item in upjong_memo_list]
                    }]
                    
                    try:
                        # 테이블에 새 행 추가
                        self.append_rows_to_manager_table(new_rows)
                        
                        # 다시 행 찾기
                        row_idx = self.find_row_by_id(row_data.get('id'))
                        if row_idx is None:
                            self.logger.error("행 추가 후에도 해당 ID의 행을 찾을 수 없습니다.")
                            return False
                    except Exception as e:
                        self.logger.error(f"새 행 추가 중 오류: {e}")
                        return False
                        
                # RecommendDialog에 전달할 업종 목록 구성
                biz_list = []
                if hasattr(self.parent_app, 'cached_manager_data_1month'):
                    # 업종 관리자 데이터로부터 추천 다이얼로그용 리스트 구성
                    biz_to_manager = {}
                    for r_ in self.parent_app.cached_manager_data_1month:
                        for bm_item in r_.get("biz_manager_list", []):
                            b_ = bm_item.get("biz","").strip(); m_ = bm_item.get("manager","").strip()
                            if b_ and b_ not in biz_to_manager: biz_to_manager[b_] = m_
                            
                    biz_list = [{"biz": b, "manager": biz_to_manager.get(b, "")} for b in sorted(biz_to_manager.keys())]
                
                # 업종 목록이 비어있는 경우
                if not biz_list:
                    # TK에서 전달받은 업종 목록 사용
                    biz_list = [{"biz": item.get("biz", ""), "manager": ""} for item in upjong_memo_list]
                
                # 선택된 업종 항목 구성 (TK에서 전달받은 메모 사용)
                selected_items = []
                for item in upjong_memo_list:
                    if item.get("biz") and item.get("memo"):
                        selected_items.append({
                            "biz": item.get("biz"),
                            "manager": self.current_manager,  # 현재 관리자 사용
                            "memo": item.get("memo")
                        })
                
                if not selected_items:
                    self.logger.warning("선택된 업종 항목이 없어 추천매물 등록을 진행할 수 없습니다.")
                    return False
                
                self.logger.info(f"추천매물 처리 시작: {len(selected_items)}개 업종")
                
                # 애플리케이션이 종료 중인지 한번 더 확인
                if hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
                    self.logger.warning("애플리케이션이 종료 중이므로 백그라운드 작업 실행을 취소합니다.")
                    return False

                # 직접 API 호출 시도 - 로컬 방식 우선
                try:
                    # 서버 상태 먼저 확인
                    server_available = False
                    try:
                        import requests
                        resp = requests.get(f"http://{self.server_host}:{self.server_port}/health", timeout=3)
                        if resp.status_code == 200:
                            server_available = True
                    except:
                        self.logger.warning("서버에 연결할 수 없어 로컬 저장 방식으로 진행합니다.")
                    
                    # 서버를 사용할 수 없으면 로컬에 바로 저장
                    if not server_available:
                        return self.save_recommend_data_locally(row_data, selected_items)

                    # 출처에 따른 source_table 변환
                    source = row_data.get('출처', '')
                    source_table = row_data.get("source_table", "")
                    
                    # 소스 테이블 설정
                    if not source_table:
                        if source == '확인':
                            source_table = 'naver_shop_check_confirm'
                        elif source == '상가':
                            source_table = 'serve_shop_data'
                        elif source == '네이버':
                            source_table = 'naver_shop'
                        else:
                            source_table = 'naver_shop_check_confirm'  # 기본값
                    
                    # ID 확인
                    source_id = row_data.get("id")
                    if not source_id:
                        self.logger.warning("유효한 source_id가 없습니다.")
                        return False
                    
                    # 서버가 사용 가능하면 API 연동 시도
                    if server_available:
                        import requests
                        
                        # 가장 가능성 높은 엔드포인트 먼저 시도
                        url = f"http://{self.server_host}:{self.server_port}/recommend/register_recommend_data"
                        
                        # API 요청 데이터 구성
                        api_data = {
                            "source_id": source_id,
                            "source_table": source_table,
                            "selected_items": selected_items
                        }
                        
                        try:
                            # API 호출
                            resp = requests.post(url, json=api_data, timeout=5)
                            
                            if resp.status_code == 200:
                                result = resp.json()
                                if result.get("status") == "ok":
                                    self.logger.info(f"추천매물 등록 성공: {result.get('message', '성공')}")
                                    
                                    # 성공 메시지 표시
                                    QMessageBox.information(self.parent_app, "성공", 
                                        f"추천매물로 등록되었습니다. ({len(selected_items)}개 업종)")
                                    
                                    # 추천 탭 새로고침 시도
                                    if hasattr(self.parent_app, 'refresh_recommend_tab'):
                                        try:
                                            # Executor가 여전히 사용 가능한지 확인
                                            if (hasattr(self.parent_app, 'executor') and 
                                                not getattr(self.parent_app.executor, '_shutdown', False)):
                                                self.parent_app.refresh_recommend_tab()
                                        except Exception as refresh_err:
                                            self.logger.error(f"추천 탭 새로고침 중 오류: {refresh_err}")
                                    
                                    return True
                                else:
                                    error_msg = result.get("message", "알 수 없는 오류가 발생했습니다.")
                                    self.logger.error(f"추천매물 등록 실패 (API 오류): {error_msg}")
                                    # 로컬 저장으로 폴백
                                    return self.save_recommend_data_locally(row_data, selected_items)
                            else:
                                self.logger.error(f"API 호출 실패: HTTP {resp.status_code}")
                                # 로컬 저장으로 폴백
                                return self.save_recommend_data_locally(row_data, selected_items)
                                
                        except Exception as api_err:
                            self.logger.warning(f"API 호출 실패: {api_err}")
                            # 로컬 저장으로 폴백
                            return self.save_recommend_data_locally(row_data, selected_items)
                    else:
                        # 서버를 사용할 수 없으면 로컬에 저장
                        return self.save_recommend_data_locally(row_data, selected_items)
                    
                except Exception as direct_api_err:
                    self.logger.error(f"직접 API 호출 중 오류: {direct_api_err}", exc_info=True)
                    # 로컬 저장으로 폴백
                    return self.save_recommend_data_locally(row_data, selected_items)
                
            else:
                self.logger.error("parent_app에 do_register_recommend 메서드가 없습니다.")
                return False
                
            
        except Exception as e:
            self.logger.error(f"TK 추천매물 등록 처리 중 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
            
    def save_recommend_data_locally(self, row_data, selected_items):
        """
        추천 데이터를 로컬에 저장하는 메서드
        
        Args:
            row_data (dict): 행 데이터
            selected_items (list): 선택된 업종 항목 리스트
            
        Returns:
            bool: 성공 여부
        """
        try:
            # recommend_data_list에 저장
            if not hasattr(self.parent_app, 'recommend_data_list'):
                self.parent_app.recommend_data_list = []
                
            # 출처에 따른 source_table 변환
            source = row_data.get('출처', '')
            source_table = row_data.get("source_table", "")
            
            # 소스 테이블 설정
            if not source_table:
                if source == '확인':
                    source_table = 'naver_shop_check_confirm'
                elif source == '상가':
                    source_table = 'serve_shop_data'
                elif source == '네이버':
                    source_table = 'naver_shop'
                else:
                    source_table = 'naver_shop_check_confirm'  # 기본값
                    
            # 추천 데이터 구성
            recommend_item = {
                "id": row_data.get("id"),
                "addr": row_data.get("주소", ""),
                "source_table": source_table,
                "lat": row_data.get("lat", ""),
                "lng": row_data.get("lng", ""),
                "selected_items": selected_items,
                "local_only": True  # 로컬에만 저장된 항목임을 표시
            }
            
            # 중복 항목 확인
            is_duplicate = False
            for idx, item in enumerate(self.parent_app.recommend_data_list):
                if item.get("id") == recommend_item["id"] and item.get("addr") == recommend_item["addr"]:
                    is_duplicate = True
                    # 기존 항목 업데이트
                    self.parent_app.recommend_data_list[idx] = recommend_item
                    self.logger.info(f"로컬에 이미 존재하는 추천매물 데이터 업데이트: {row_data.get('주소', '')}")
                    break
                    
            # 중복이 아니면 새로 추가
            if not is_duplicate:
                self.parent_app.recommend_data_list.append(recommend_item)
                self.logger.info(f"로컬에 추천매물 데이터 저장 완료: {row_data.get('주소', '')}")
            
            # 메시지 표시
            QMessageBox.information(self.parent_app, "안내", 
                "서버에 추천매물을 등록할 수 없어 로컬에 임시 저장되었습니다.\n추천 탭에서 확인해주세요.")
            
            # 추천 탭 새로고침 시도
            if hasattr(self.parent_app, 'refresh_recommend_tab'):
                try:
                    # Executor 상태 확인
                    if (hasattr(self.parent_app, 'executor') and 
                        not getattr(self.parent_app.executor, '_shutdown', False)):
                        self.parent_app.refresh_recommend_tab()
                except Exception as refresh_err:
                    self.logger.error(f"추천 탭 새로고침 중 오류: {refresh_err}")
            
            return True
        except Exception as local_err:
            self.logger.error(f"로컬에 추천매물 데이터 저장 중 오류: {local_err}")
            return False 