#customer_tab.py
import requests
from dialogs import CustomerRowEditDialog
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QStandardItem
import json
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QTableView, QHeaderView
from ui_utils import restore_qtableview_column_widths, save_qtableview_column_widths




class CustomerTab:
    def __init__(self, parent_app=None, manager=None, role=None,
                 server_host=None, server_port=None,
                 district_data=None, saved_conditions=None):
        self.parent_app = parent_app
        self.current_manager = manager
        self.current_role = role
        self.server_host = server_host
        self.server_port = server_port

        self.district_data = district_data
        self.saved_conditions = saved_conditions
        self.customer_view = None
        self.customer_model = None
        self.customer_tabs = None
        

        
    def init_customer_data_for_manager_tab(self):
        """
        (새로 추가)
        상가고객 탭을 초기화 + 해당 매니저의 데이터 로딩까지 수행.
        다른 init_* 함수들처럼 프로그램 시작시에 한 번에 불러올 수 있도록 함.
        """

        # 1) 우선 상가고객 전용 TabWidget이 있는지 확인 (없으면 생성)
        #    (만약 기존 코드에서 self.customer_tabs를 이미 만들었으면 생략 가능)
        self.customer_tabs = QtWidgets.QTabWidget()

        container_widget = QtWidgets.QWidget()
        container_layout = QtWidgets.QVBoxLayout(container_widget)

        # (2-A) "고객 등록" 버튼
        new_customer_btn = QtWidgets.QPushButton("고객 등록")
        new_customer_btn.setFixedHeight(40)
        new_customer_btn.clicked.connect(self.on_new_customer)
        container_layout.addWidget(new_customer_btn)



        self.customer_model = QtGui.QStandardItemModel()
        self.customer_view = QtWidgets.QTableView()
        self.customer_view.setModel(self.customer_model)
        self.customer_view.setSortingEnabled(True)
        self.customer_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)

        self.customer_view.doubleClicked.connect(self.on_customer_double_clicked)
        self.customer_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customer_view.customContextMenuRequested.connect(self.on_customer_context_menu)

        # Restore/Save column widths using ui_utils
        restore_qtableview_column_widths(
            self.parent_app.settings_manager, 
            self.customer_view, 
            "CustomerTable"
        )
        self.customer_view.horizontalHeader().sectionResized.connect(
            lambda: save_qtableview_column_widths(
                self.parent_app.settings_manager, 
                self.customer_view, 
                "CustomerTable"
            )
        )

        container_layout.addWidget(self.customer_view)

        self.customer_tabs.addTab(
            container_widget,
            f"상가고객({self.current_manager})"
        )

        self.load_customer_data_for_manager(self.current_manager)

        sel_model_customer = self.customer_view.selectionModel()
        sel_model_customer.currentChanged.connect(self.on_customer_view_current_changed)
        # self.customer_tabs.hide()


    def on_customer_view_current_changed(self, current: QtCore.QModelIndex, previous: QtCore.QModelIndex):
        """ Handles selection changes. Filters local recommend_dict based on '업종' and '담당자' to find matching addresses. """
        # --- ADDED: Log recommend_dict state at the beginning --- 
        recommend_dict_state = "Not found or not dict"
        if hasattr(self.parent_app, 'recommend_dict') and isinstance(self.parent_app.recommend_dict, dict):
             recommend_dict_state = f"Exists, size: {len(self.parent_app.recommend_dict)}, Sample keys: {list(self.parent_app.recommend_dict.keys())[:5]}"
        # --- END ADDED ---

        if not current.isValid() or current.row() == previous.row():
            return

        new_row = current.row()
        model = self.customer_model
        headers = self.customer_headers

        # --- 1. Extract '업종' and '담당자' from the selected row --- 
        try:
            col_upjong = headers.index("업종")
        except ValueError:
            print("[ERR] CustomerTab: '업종' header not found!")
            return
        try:
            col_manager = headers.index("담당자")
        except ValueError:
            col_manager = -1 # 담당자 column might not exist or be relevant

        upjong_item = model.item(new_row, col_upjong)
        upjong_val = upjong_item.text().strip() if upjong_item else ""

        manager_val = self.current_manager # Default to current logged-in manager
        if col_manager >= 0:
            manager_item = model.item(new_row, col_manager)
            row_manager_str = manager_item.text().strip() if manager_item else ""
            if row_manager_str: # Use manager from the row if specified
                manager_val = row_manager_str

        print(f"[INFO] Customer selection changed. Filtering recommend_dict for 업종='{upjong_val}', 담당자='{manager_val}'")

        # --- ADDED: Store selected biz and manager in parent_app ---
        self.parent_app.last_selected_customer_biz = upjong_val
        self.parent_app.last_selected_customer_manager = manager_val
        print(f"[DEBUG][CustomerTab] Stored in parent_app: biz='{upjong_val}', mgr='{manager_val}'") # 디버깅 로그 추가
        # --- END ADDED ---

        # --- 2. Filter local recommend_dict to find matching addresses --- 
        matched_addresses = []
        if hasattr(self.parent_app, 'recommend_dict') and isinstance(self.parent_app.recommend_dict, dict):
            # recommend_dict is { "address_string": [row_dict, row_dict, ...], ... }
            for addr_str, row_list in self.parent_app.recommend_dict.items():
                # Check if any row in the list for this address matches the criteria
                for r_ in row_list:
                    # Assuming recommend_dict rows have 'matching_biz' and 'manager' keys
                    biz_ = r_.get("matching_biz", "") 
                    mgr_ = r_.get("manager", "")
                    if (biz_ == upjong_val) and (mgr_ == manager_val):
                        matched_addresses.append(addr_str)
                        break # Found a match for this address, no need to check other rows for the same address
        else:
            print("[WARN] CustomerTab: parent_app.recommend_dict not found or not a dict.")

        if not matched_addresses:
            print("[INFO] No matching addresses found in recommend_dict. Clearing related tabs.")
            self.parent_app.selected_addresses = [] # Clear selection
        else:
            self.parent_app.selected_addresses = matched_addresses # Set the found addresses

        self.parent_app.from_customer_click = True # Set the flag regardless of matches
        self.parent_app.last_selected_address = None # Clear single address selection if any

        # Trigger AllTab update using the unified method
        if hasattr(self.parent_app, 'all_tab') and hasattr(self.parent_app.all_tab, 'rebuild_and_populate_for_current_selection'):
             self.parent_app.all_tab.rebuild_and_populate_for_current_selection() # Use the unified update method
        else:
             print("[ERR] CustomerTab: all_tab instance or its method rebuild_and_populate_for_current_selection not found!")

        # Trigger other tabs to potentially reload based on the new selection state
        # (They might internally check self.parent_app.selected_addresses)
        # --- MODIFIED: Explicitly call update methods for other tabs --- 
        if hasattr(self.parent_app, 'serve_shop_tab') and hasattr(self.parent_app.serve_shop_tab, 'filter_and_populate'):
            self.parent_app.serve_shop_tab.filter_and_populate()
        else:
            print("[WARN][CustomerTab] ServeShopTab or filter_and_populate method not found.")
            
        if hasattr(self.parent_app, 'check_confirm_tab') and hasattr(self.parent_app.check_confirm_tab, 'filter_and_populate'):
            self.parent_app.check_confirm_tab.filter_and_populate()
        else:
            print("[WARN][CustomerTab] CheckConfirmTab or filter_and_populate method not found.")

        if hasattr(self.parent_app, 'serve_oneroom_tab') and hasattr(self.parent_app.serve_oneroom_tab, 'filter_and_populate'):
            self.parent_app.serve_oneroom_tab.filter_and_populate()
        else:
            print("[WARN][CustomerTab] ServeOneroomTab or filter_and_populate method not found.")
            
        if hasattr(self.parent_app, 'mylist_shop_tab') and hasattr(self.parent_app.mylist_shop_tab, 'filter_and_populate'):
            self.parent_app.mylist_shop_tab.filter_and_populate()
        else:
            print("[WARN][CustomerTab] MyListShopTab or filter_and_populate method not found.")
            
        # --- ADDED: Explicitly trigger RecommendTab update ---
        if hasattr(self.parent_app, 'recommend_tab') and hasattr(self.parent_app.recommend_tab, 'filter_and_populate'):
            self.parent_app.recommend_tab.filter_and_populate()
        else:
            print("[WARN][CustomerTab] RecommendTab or filter_and_populate method not found.")
        # --- END ADDED ---
            
        # Add calls for other tabs like CompletedDealsTab if needed
        print("[DEBUG][CustomerTab] Finished triggering updates for other tabs.")
        # --- END MODIFIED --- 

    def on_customer_context_menu(self, pos):
        """
        고객 테이블 우클릭 시 컨텍스트 메뉴 표시
        """
        try:
            view = self.customer_view
            if not view:
                print("[ERROR] customer_view가 None입니다.")
                return

            # 선택된 행이 있는지 확인
            selection_model = view.selectionModel()
            if not selection_model or not selection_model.hasSelection():
                print("[INFO] 컨텍스트 메뉴: 선택된 행이 없습니다.")
                return

            # 메뉴 생성
            menu = QtWidgets.QMenu(view)
            delete_action = menu.addAction("고객 삭제")
            
            # 메뉴 위치 계산 및 표시
            global_pos = view.viewport().mapToGlobal(pos)
            action = menu.exec_(global_pos)
            
            # 선택된 메뉴 처리
            if action == delete_action:
                try:
                    print("[INFO] 컨텍스트 메뉴: 고객 삭제 액션 선택됨")
                    
                    # 고객 삭제 처리
                    self.handle_customer_delete()
                    
                    # 처리 완료 메시지
                    self.parent_app.statusBar().showMessage("고객 삭제 처리가 완료되었습니다.", 3000)
                    QtWidgets.QApplication.processEvents()  # UI 업데이트
                    
                except Exception as e:
                    error_msg = f"고객 삭제 중 오류: {e}"
                    print(f"[ERROR] {error_msg}")
                    
                    # 로깅
                    if hasattr(self, 'logger') and self.logger:
                        self.logger.error(error_msg)
                        
                    # 사용자에게 알림
                    QtWidgets.QMessageBox.critical(
                        self.parent_app, 
                        "삭제 오류", 
                        f"고객 삭제 중 오류가 발생했습니다:\n{str(e)}"
                    )
        
        except Exception as e:
            error_msg = f"컨텍스트 메뉴 처리 중 오류: {e}"
            print(f"[ERROR] {error_msg}")
            
            # 로깅
            if hasattr(self, 'logger') and self.logger:
                self.logger.error(error_msg)

    def handle_customer_delete(self):
        """고객 정보 삭제 처리"""
        try:
            view = self.customer_view
            if not view:
                print("[ERROR] customer_view가 None입니다.")
                return

            selection_model = view.selectionModel()
            if not selection_model:
                print("[ERROR] selection_model이 None입니다.")
                return

            selected_indexes = selection_model.selectedIndexes()
            if not selected_indexes:
                print("[WARN] 선택된 행이 없습니다.")
                QtWidgets.QMessageBox.warning(self.parent_app, "삭제 실패", "선택된 고객 정보가 없습니다.")
                return

            selected_rows = set(idx.row() for idx in selected_indexes)

            ret = QtWidgets.QMessageBox.question(
                self.parent_app,
                "삭제 확인",
                f"총 {len(selected_rows)}개의 고객 정보를 정말 삭제하시겠습니까?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if ret != QtWidgets.QMessageBox.Yes:
                return

            # 상태바에 삭제 작업 시작을 표시
            self.parent_app.statusBar().showMessage("고객 삭제 처리 중...", 0)
            QtWidgets.QApplication.processEvents()  # UI 업데이트

            # DB + 모델에서 제거
            model = self.customer_model
            rows_sorted_desc = sorted(selected_rows, reverse=True)  # 역순으로 정렬 (인덱스 변동 방지)
            
            deleted_count = 0
            for row in rows_sorted_desc:
                id_item = model.item(row, 0)
                if not id_item:
                    print(f"[WARN] 행 {row}의 ID 아이템이 None입니다.")
                    continue
                
                # UserRole 데이터에서 ID 가져오기
                user_role_data = id_item.data(QtCore.Qt.UserRole)
                if not user_role_data or not isinstance(user_role_data, dict):
                    print(f"[WARN] 행 {row}의 UserRole 데이터가 유효하지 않습니다: {user_role_data}")
                    continue
                
                cust_id = user_role_data.get("id")
                if not cust_id:
                    print(f"[WARN] 행 {row}의 ID 값이 유효하지 않습니다.")
                    continue
                    
                try:
                    # 상태바에 삭제 진행 상태 업데이트
                    self.parent_app.statusBar().showMessage(f"고객 ID {cust_id} 삭제 중...", 0)
                    QtWidgets.QApplication.processEvents()
                    
                    # 서버에서 삭제 시도
                    success = self.delete_customer_row(cust_id)
                    if success:
                        # 로컬 모델에서도 제거 (서버에서 삭제 성공한 경우만)
                        model.removeRow(row)
                        deleted_count += 1
                        print(f"[INFO] 행 {row}, ID={cust_id} 삭제 성공")
                    else:
                        print(f"[ERROR] 고객 ID={cust_id} 삭제 실패")
                except Exception as e:
                    print(f"[ERROR] 고객 삭제 중 예외 발생: {e}")
                    # 개별 고객 삭제 실패해도 계속 진행
                    continue
            
            # 삭제 결과 표시
            self.parent_app.statusBar().showMessage(f"고객 삭제 완료: {deleted_count}건", 3000)
            QtWidgets.QApplication.processEvents()  # UI 업데이트
            
            if deleted_count > 0:
                # 삭제 성공한 항목이 있는 경우에만 처리
                
                # 1. 사용자에게 성공 메시지 표시
                QtWidgets.QMessageBox.information(
                    self.parent_app, 
                    "삭제 완료", 
                    f"선택한 {len(selected_rows)}개 중 {deleted_count}개의 고객 정보가 삭제되었습니다."
                )
                
                # 2. 관련 탭 업데이트 (데이터 변경이 있는 경우에만)
                if hasattr(self.parent_app, 'manager_check_tab') and self.parent_app.manager_check_tab:
                    # 마지막 로드 ID 초기화하여 강제 새로고침 준비
                    if hasattr(self.parent_app, 'last_loaded_id'):
                        self.parent_app.last_loaded_id = 0
                    
                    print("[INFO] 고객 삭제 후 manager_check_tab 업데이트 예약 (1초 후)")
                    self.parent_app.statusBar().showMessage("매니저 체크 탭 업데이트 예약됨", 3000)
                    QtWidgets.QApplication.processEvents()  # UI 업데이트
                    
                    # 업종 목록 즉시 갱신 시도 (다이얼로그 문제 해결용)
                    if hasattr(self.parent_app.manager_check_tab, 'update_real_biz_set'):
                        try:
                            self.parent_app.manager_check_tab.update_real_biz_set()
                            print("[INFO] 고객 삭제 후 업종 목록 즉시 갱신 완료")
                        except Exception as e:
                            print(f"[WARN] 업종 목록 갱신 중 오류 발생: {e}")
                    
                    # 이전에 예약된 타이머가 있다면 중지 (추가 코드)
                    if hasattr(self, '_refresh_timer') and self._refresh_timer:
                        try:
                            self._refresh_timer.stop()
                            print("[INFO] 기존 타이머 중지됨")
                        except Exception as e:
                            print(f"[WARN] 기존 타이머 중지 중 오류: {e}")
                        
                    # 안전하게 새 타이머 생성
                    try:
                        self._refresh_timer = QtCore.QTimer()
                        self._refresh_timer.setSingleShot(True)
                        self._refresh_timer.timeout.connect(self._delayed_manager_check_refresh)
                        self._refresh_timer.start(1000)  # 1초 후 실행
                        print("[INFO] 새 타이머 시작됨 - 1초 후 매니저 체크 탭 업데이트 예정")
                    except Exception as e:
                        print(f"[ERROR] 타이머 설정 중 오류: {e}")
                        # 타이머 설정 실패 시 직접 호출 시도
                        QtCore.QTimer.singleShot(1000, self._delayed_manager_check_refresh)
        
        except Exception as e:
            import traceback
            error_msg = f"고객 삭제 중 오류 발생: {e}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")
            
            # 로깅
            if hasattr(self, 'logger') and self.logger:
                self.logger.error(error_msg)
                
            # 사용자에게 알림
            QtWidgets.QMessageBox.critical(
                self.parent_app, 
                "삭제 오류", 
                f"고객 삭제 중 오류가 발생했습니다:\n{str(e)}"
            )

    def on_customer_double_clicked(self, index: QtCore.QModelIndex):
        """
        QTableView에서 특정 셀을 더블클릭 시 호출되는 함수.
        1) row,col 구하기
        2) 행 전체 데이터를 row_values로 구성
        3) CustomerRowEditDialog 열어서 수정
        4) OK 누르면 UI/DB 갱신
        """
        if not index.isValid():
            return

        model = self.customer_model
        row = index.row()
        col = index.column()

        headers = self.customer_headers
        try:
            region_col = headers.index("지역")
        except ValueError:
            region_col = -1

        memo_col = headers.index("메모") if "메모" in headers else -1

        first_item = model.item(row, 0)
        db_info = {}
        if first_item:
            db_info = first_item.data(QtCore.Qt.UserRole) or {}
        cust_id = db_info.get("id", None)
        db_manager = self.current_manager

        row_values = []
        for c in range(model.columnCount()):
            item = model.item(row, c)
            if not item:
                row_values.append("")
                continue
            cell_text = item.text() or ""

            if c == region_col:
                raw_json = item.data(QtCore.Qt.UserRole + 1)
                if raw_json:
                    row_values.append(raw_json)
                else:
                    row_values.append(cell_text)
            elif c == memo_col:
                memo_json_str = item.data(QtCore.Qt.UserRole + 1)
                if memo_json_str:
                    row_values.append(memo_json_str)
                else:
                    row_values.append(cell_text)
            else:
                row_values.append(cell_text)

        dlg = CustomerRowEditDialog(
            parent=self.parent_app,
            district_data=self.district_data,
            headers=headers,
            row_data=row_values,
            saved_state=self.saved_conditions
        )
        dlg.id = cust_id
        dlg.manager = self.current_manager
        dlg.edit_row = row

        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            if dlg.is_delete_requested():
                model.removeRow(row)
            else:
                new_values = dlg.get_row_data()
                self.saved_conditions = dlg.get_saved_conditions()

                # 변경 감지 로직 추가
                data_changed = self.has_row_data_changed(row_values, new_values)
                
                if data_changed:
                    print("[INFO] 데이터 변경이 감지되어 업데이트를 실행합니다.")
                    # 비동기로 서버 업데이트 처리
                    self.update_customer_sheet_async(
                        row_data=new_values,
                        row_idx=row,
                        cust_id=cust_id,
                        manager=db_manager
                    )

                    # 필요한 탭만 선택적으로 업데이트
                    self.update_tabs_after_customer_edit(row_values, new_values)
                else:
                    print("[INFO] 변경사항이 없어 업데이트를 생략합니다.")
                    # 변경이 없더라도 UI에는 반영 (입력 형식 등이 정규화될 수 있음)
                    self._update_customer_sheet_locally(new_values, row, cust_id, db_manager)
        else:
            print("[INFO] Customer edit cancelled.")

    def on_new_customer(self):
        manager = self.current_manager
        new_id = self.insert_blank_customer_row(manager)
        if new_id is None:
            QtWidgets.QMessageBox.warning(self, "에러", "빈 행 생성 실패!")
            return

        headers = [
            "지역", "보증금", "월세", "평수", "층",
            "권리금", "업종", "연락처", "실보증금/월세",
            "최근연락날짜", "메모","담당자"
        ]
        row_values = [""] * len(headers)
        dlg = CustomerRowEditDialog(
            parent=self.parent_app,
            district_data=self.district_data,
            headers=headers,
            row_data=row_values,
            saved_state=self.saved_conditions
        )
        dlg.id = new_id
        dlg.manager = self.current_manager
        dlg.edit_row = -1

        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            new_values = dlg.get_row_data()
            self.saved_conditions = dlg.get_saved_conditions()

            model = self.customer_model
            if model.columnCount() == 0:
                model.setColumnCount(len(headers))
                model.setHorizontalHeaderLabels(headers)

            old_row_count = model.rowCount()
            new_row_idx = old_row_count
            model.setRowCount(old_row_count + 1)

            # 비동기로 서버 업데이트 처리
            self.update_customer_sheet_async(
                row_data=new_values,
                row_idx=new_row_idx,
                cust_id=new_id,
                manager=manager
            )
            
            # 새로운 고객 데이터가 있는 경우에만 탭 업데이트
            data_exists = any(val.strip() for val in new_values)
            if data_exists:
                # 새 고객 추가의 경우 old_values는 빈 값들이므로 새로운 값과 차이가 있는지 확인하기 위함
                empty_values = [""] * len(new_values)
                self.update_tabs_after_customer_edit(empty_values, new_values)
            else:
                print("[INFO] 새 고객 데이터가 없어 탭 업데이트를 생략합니다.")
        else:
            # 취소 시 서버에서 빈 행 삭제
            print(f"[INFO] 새 고객 추가 취소됨. id={new_id} 삭제 요청")
            if self.delete_customer_row(new_id):
                print(f"[INFO] 취소된 빈 행(id={new_id}) 삭제 성공")
            else:
                print(f"[WARN] 취소된 빈 행(id={new_id}) 삭제 실패")

    def insert_blank_customer_row(self, manager):
        """
        서버에 POST 요청하여 빈 고객 행 생성
        """
        payload = {"manager": manager}

        try:
            # 서버 엔드포인트 예시: POST /customer/create_blank_customer
            # (서버가 이 요청을 받아 DB insert + new_id 반환)
            resp = requests.post(
                f"http://{self.server_host}:{self.server_port}/customer/create_blank_customer",
                json=payload,
                timeout=10  # 타임아웃 10초로 증가
            )
            resp.raise_for_status()

            rj = resp.json()
            if rj.get("status") == "ok":
                new_id = rj.get("new_id")
                return new_id
            else:
                print("[ERROR] create_blank_customer =>", rj)
                return None

        except Exception as e:
            print("[ERR] insert_blank_customer_row =>", e)
            return None

    def delete_customer_row(self, cust_id):
        """
        특정 ID의 고객 행을 서버에서 삭제
        
        Args:
            cust_id: 삭제할 고객 ID
            
        Returns:
            bool: 삭제 성공 여부
        """
        if cust_id is None:
            print("[ERROR] delete_customer_row: cust_id가 None입니다.")
            return False
            
        try:
            # API 경로 확인
            url = f"http://{self.server_host}:{self.server_port}/customer/delete_customer_row"
            
            # 현재 사용자 권한 정보
            manager = self.current_manager  # 예: "홍길동"
            role = self.current_role        # 예: "admin" or "manager"
            
            # 요청 페이로드
            payload = {
                "id": cust_id,
                "manager": manager,
                "role": role
            }
            
            print(f"[INFO] 고객 삭제 요청: id={cust_id}, manager={manager}, role={role}, url={url}")
            
            # 타임아웃 10초 설정으로 요청
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()  # HTTP 오류 발생 시 예외 발생
            
            # 응답 확인
            try:
                rj = resp.json()
                if rj.get("status") != "ok":
                    error_msg = rj.get("message", "알 수 없는 오류")
                    print(f"[ERROR] 고객 ID={cust_id} 삭제 실패: {error_msg}")
                    return False
                    
                print(f"[INFO] 고객 ID={cust_id} 삭제 성공")
                return True
            except ValueError as e:
                # JSON 파싱 오류
                print(f"[ERROR] 응답 JSON 파싱 오류: {e}")
                return False
                
        except requests.exceptions.Timeout:
            print(f"[ERROR] 고객 ID={cust_id} 삭제 중 서버 타임아웃")
            return False
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] 고객 ID={cust_id} 삭제 중 네트워크 오류: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] 고객 ID={cust_id} 삭제 중 예외 발생: {e}")
            return False

    def parse_range(self, range_str: str):
        range_str = (range_str or "").strip()
        if "~" in range_str:
            s, e = range_str.split("~", 1)
            try:
                return (int(s.strip()), int(e.strip()))
            except ValueError:
                return (0, 0)
        else:
            try:
                val = int(range_str) if range_str else 0
                return (val, val)
            except ValueError:
                return (0, 0)
            
    def parse_floor_range(self, floor_str):
        floor_str = (floor_str or "").strip()
        is_top = False
        fmin, fmax = 0, 999

        if not floor_str:
            return (0, 0, False)

        if "지하" in floor_str:
            fmin, fmax = -999, -1
        elif "탑층" in floor_str:
            is_top = True
            fmin, fmax = 0, 0
        elif "이상" in floor_str:
            num_part = floor_str.replace("층이상", "").replace("층", "").strip()
            try:
                fmin = int(num_part)
            except:
                fmin = 2
            fmax = 999
        elif "~" in floor_str:
            range_part = floor_str.replace("층","")
            s,e = range_part.split("~",1)
            try:
                fmin = int(s)
                fmax = int(e)
            except:
                fmin,fmax=0,0
        else:
            num_part = floor_str.replace("층","").strip()
            try:
                val = int(num_part)
                fmin,fmax= val,val
            except:
                fmin,fmax=0,0

        return (fmin,fmax,is_top)

    def find_which_gu(self, dong):
        for gu, dongs in self.district_data.items():
            if dong in dongs:
                return gu
        print(f"[WARN] find_which_gu() 매칭 실패: '{dong}' => district_data에 없음!")
        return "기타"

    def build_region_short_text(self, dongs_list, rects_list):
        if rects_list is None:
            rects_list = []

        gu_map = {}
        for dong in dongs_list:
            gu = self.find_which_gu(dong)
            if gu not in gu_map:
                gu_map[gu] = []
            gu_map[gu].append(dong)

        line_parts = []
        tooltip_lines = []
        for gu, d_list in gu_map.items():
            if gu in self.district_data:
                total_in_gu = len(self.district_data[gu])
            else:
                total_in_gu = 0
            selected_cnt = len(d_list)
            if selected_cnt == total_in_gu and total_in_gu > 0:
                line_parts.append(f"{gu}(전체)")
                tooltip_lines.append(f"{gu}: {', '.join(d_list)}")
            else:
                line_parts.append(f"{gu}({len(d_list)})")
                tooltip_lines.append(f"{gu}: {', '.join(d_list)}")

        rect_count = len(rects_list)
        if rect_count > 0:
            line_parts.append(f"지도({rect_count})")
            for i, rect in enumerate(rects_list):
                tooltip_lines.append(f"지도{i+1}: {rect}")

        short_text = ", ".join(line_parts) if line_parts else ""
        tooltip_text = "\n".join(tooltip_lines)
        return short_text, tooltip_text
    
    def load_customer_data_for_manager(self, manager_name: str):
        params = {
        "manager": manager_name,
        "role": self.current_role
        }
        url = f"http://{self.server_host}:{self.server_port}/customer/get_customer_data"
        resp = requests.get(url,params=params)
        if resp.status_code != 200:
            print("[ERROR] Failed to fetch customer data. status=", resp.status_code)
            return

        json_data = resp.json()
        if "data" not in json_data:
            print("[ERROR] invalid response:", json_data)
            return

        rows = json_data["data"]
        model = self.customer_model
        model.clear()

        self.customer_headers = [
            "지역","보증금","월세","평수","층",
            "권리금","업종","연락처","실보증금/월세","최근연락날짜","메모","담당자"
        ]
        model.setColumnCount(len(self.customer_headers))
        model.setHorizontalHeaderLabels(self.customer_headers)

        if not rows:
            return

        model.setRowCount(len(rows))

        for i, row_data in enumerate(rows):
            row_id = row_data.get("id", None)
            for j, col_name in enumerate(self.customer_headers):
                if col_name == "담당자":
                    cell_val = row_data.get("manager", "")
                else:
                    cell_val = row_data.get(col_name, "")

                if col_name == "지역":
                    try:
                        region_obj = json.loads(cell_val) if cell_val else {}
                        dongs_list = region_obj.get("dong_list", [])
                        rects_list = region_obj.get("rectangles", [])
                        
                        short_txt, tip_txt = self.build_region_short_text(dongs_list, rects_list)

                        item = QStandardItem(short_txt)
                        item.setToolTip(tip_txt)
                        item.setData(cell_val, QtCore.Qt.UserRole+1)

                    except (json.JSONDecodeError, TypeError):
                        item = QStandardItem(str(cell_val))
                elif col_name == "메모":
                    short_txt, tip_txt = self.build_memo_display_text(cell_val)
                    item = QStandardItem(short_txt)
                    item.setToolTip(tip_txt)
                    item.setData(cell_val, QtCore.Qt.UserRole+1)
                else:
                    item = QStandardItem(str(cell_val))

                item.setData({
                    "id": row_id,
                    "manager": manager_name,
                    "column": col_name
                }, QtCore.Qt.UserRole)

                model.setItem(i, j, item)

        print("[INFO] load_customer_data_for_manager =>", len(rows), "rows loaded.")
        
    def build_memo_display_text(self, memo_json_str: str):
        """
        memo_json_str: '[{"date":"고정메모","text":"12345123"}, {"date":"2025-01-05","text":"추가메모"}]'
        => return (short_text, tooltip_text)
        short_text: '고정메모' 항목의 text (ex: "12345123") (없으면 "")
        tooltip_text: 전체 항목 (ex: "고정메모: 12345123\n2025-01-05: 추가메모")
        """

        if not memo_json_str.strip():
            return ("", "")

        try:
            memo_arr = json.loads(memo_json_str)  # [{"date":"고정메모","text":"..."}, ...]
        except (json.JSONDecodeError, TypeError):
            # 파싱 실패 => 그냥 원본 문자열 or 빈 값
            return (memo_json_str, memo_json_str)

        fixed_text = ""       # "고정메모" 항목의 text
        tooltip_lines = []    # 전체 항목
        for mo in memo_arr:
            d_ = mo.get("date","")
            t_ = mo.get("text","")
            # 툴큅 한 줄
            tooltip_lines.append(f"{d_}: {t_}")
            # "고정메모" => short_text
            if d_ == "고정메모":
                fixed_text = t_

        tooltip_str = "\n".join(tooltip_lines)
        return (fixed_text, tooltip_str)

    def update_customer_sheet_async(self, row_data, row_idx, cust_id, manager):
        """
        1) UI(테이블 모델) 즉시 반영
        2) 서버(DB) 갱신은 self.parent_app.executor.submit(...) 로 비동기 처리
        """
        # (A) UI(모델) 즉시 갱신 - 이 부분은 시각적 응답성을 위해 즉시 처리
        self._update_customer_sheet_locally(row_data, row_idx, cust_id, manager)

        # 상태 바에 서버 업데이트 중임을 표시
        self.parent_app.statusBar().showMessage("고객 정보 서버 업데이트 중...", 0)  # 0은 무기한 표시

        # (B) 서버로 보낼 payload 구성은 별도 스레드에서 처리
        future_prepare = self.parent_app.executor.submit(
            self._bg_prepare_payload,
            row_data, cust_id, manager
        )
        future_prepare.add_done_callback(self._on_payload_prepared)

    def _bg_prepare_payload(self, row_data, cust_id, manager):
        """백그라운드에서 페이로드 구성"""
        try:
            return self._build_payload_for_server(row_data, cust_id, manager)
        except Exception as ex:
            import traceback
            return {"error": f"{ex}\n{traceback.format_exc()}"}

    def _on_payload_prepared(self, future):
        """페이로드 구성이 완료되면 서버에 업데이트 요청"""
        try:
            payload = future.result()
            
            # 오류 확인
            if isinstance(payload, dict) and "error" in payload:
                error_msg = payload["error"]
                print(f"[ERROR] 페이로드 구성 실패: {error_msg}")
                self.parent_app.statusBar().showMessage("서버 업데이트 실패: 페이로드 오류", 3000)
                return
                
            # 백그라운드 스레드로 서버 통신 수행
            future_server = self.parent_app.executor.submit(
            self._bg_update_customer_sheet,
            payload
        )
            future_server.add_done_callback(self._on_update_customer_sheet_done)
            
        except Exception as e:
            print(f"[ERROR] 페이로드 처리 중 오류: {e}")
            self.parent_app.statusBar().showMessage("서버 업데이트 준비 실패", 3000)

    def _on_update_customer_sheet_done(self, future):
        """
        (메인 스레드) 백그라운드 작업 완료 시점에 executor가 호출.
        => future.result() 꺼내서 성공/실패 처리 후 UI 반영
        """
        try:
            result = future.result()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self.parent_app, "DB갱신 실패", f"오류발생:\n{e}")
            self.parent_app.statusBar().showMessage("서버 업데이트 실패", 3000)
            return
        
        if not result:
            QtWidgets.QMessageBox.warning(self.parent_app, "DB갱신 실패", "서버 응답이 없습니다.")
            self.parent_app.statusBar().showMessage("서버 응답 없음", 3000)
            return
        
        if result.get("status") == "ok":
            print("[INFO] customer_sheet update => 성공")
            self.parent_app.statusBar().showMessage("고객정보 수정 성공", 3000)
            
            # update_tabs_after_customer_edit 메서드에서 이미 필요한 경우에만 
            # manager_check_tab을 업데이트하므로 여기서는 별도로 업데이트하지 않음
        else:
            err_ = result.get("message", "알 수 없는 오류")
            QtWidgets.QMessageBox.critical(self.parent_app, "DB갱신 실패", f"{err_}")
            self.parent_app.statusBar().showMessage(f"서버 오류: {err_}", 3000)

    def update_tabs_after_customer_edit(self, old_values, new_values):
        """변경된 필드에 따라 필요한 탭만 업데이트"""
        # 데이터 변경 여부 확인
        data_changed = self.has_row_data_changed(old_values, new_values)
        
        if not data_changed:
            print("[INFO] 데이터 변경이 없어 manager_check_tab 업데이트를 생략합니다.")
            return
            
        # 데이터가 변경된 경우에만 manager_check_tab 업데이트
        try:
            # manager_check_tab이 있을 경우에는 상태 초기화
            if hasattr(self.parent_app, 'manager_check_tab'):
                self.parent_app.last_loaded_id = 0  # 강제 새로고침을 위해 ID 리셋
                
                QtCore.QTimer.singleShot(500, lambda: self._delayed_manager_check_refresh())
                print("[INFO] 고객 정보 변경으로 인해 manager_check_tab 업데이트 예약 완료")
            else:
                print("[WARN] manager_check_tab이 초기화되지 않았습니다.")
                
            # 필드별 변경 여부 확인
            update_all_tab = False
            update_recommend_tab = False
            
            if not hasattr(self, 'customer_headers'):
                print("[WARN] customer_headers 속성이 없습니다. 전체 탭을 업데이트합니다.")
                update_all_tab = True
            else:
                try:
                    # 필드별 변경사항 체크
                    for i, h in enumerate(self.customer_headers):
                        if i >= len(old_values) or i >= len(new_values):
                            continue
                        
                        old_val = old_values[i]
                        new_val = new_values[i]
                        
                        if old_val != new_val:
                            print(f"[INFO] 필드 '{h}' 변경됨: {old_val} -> {new_val}")
                            
                            # 중요 필드(지역/평수/층) 변경 시 모든 탭 업데이트
                            if h in ["지역", "평수", "층"]:
                                update_all_tab = True
                                break
                            # 기타 필드 변경 시 recommendation_tab 업데이트
                            elif h in ["보증금", "월세", "권리금", "업종"]:
                                update_recommend_tab = True
                except Exception as ex:
                    print(f"[ERROR] 필드별 변경사항 체크 중 오류: {ex}")
                    update_all_tab = True
            
            # 전체 탭 업데이트
            if update_all_tab:
                print("[INFO] 중요 필드 변경으로 인해 모든 탭 업데이트")
                tabs_to_update = ["all_tabs"]  # 특별 값: 모든 탭 업데이트 요청
            # 권장 탭만 업데이트
            elif update_recommend_tab:
                print("[INFO] 부가 필드 변경으로 인해 recommendation_tab 업데이트")
                tabs_to_update = ["recommendation_tab"]
            else:
                print("[INFO] 일반 필드 변경으로 인해 업데이트 불필요")
                tabs_to_update = []
                
            # 각 탭 업데이트 스케줄링
            for tab_name in tabs_to_update:
                if tab_name == "all_tabs":
                    for t in ["recommendation_tab", "neighborhood_tab", "multi_map_tab"]:
                        QtCore.QTimer.singleShot(1000, lambda tn=t: self._delayed_tab_update(tn))
                else:
                    QtCore.QTimer.singleShot(1000, lambda tn=tab_name: self._delayed_tab_update(tn))
                
        except Exception as ex:
            print(f"[ERROR] update_tabs_after_customer_edit 전체 실행 중 예외 발생: {ex}")
            import traceback
            print(f"[ERROR] 스택 트레이스: {traceback.format_exc()}")
    
    def _delayed_manager_check_refresh(self):
        """매니저 체크 탭 업데이트를 지연 실행하는 방법"""
        try:
            # PyQt5.sip 모듈 임포트 (필요 시 추가)
            try:
                from PyQt5 import sip
                has_sip = True
            except ImportError:
                has_sip = False
                print("[WARN] PyQt5.sip 모듈을 가져올 수 없습니다. 객체 삭제 여부를 확인할 수 없습니다.")
            
            if hasattr(self.parent_app, 'manager_check_tab') and self.parent_app.manager_check_tab:
                # 객체 존재 여부 추가 검사
                if has_sip and sip.isdeleted(self.parent_app.manager_check_tab):
                    print("[INFO] 매니저 체크 탭이 이미 삭제되어 업데이트를 건너뜁니다.")
                    return
                    
                print("[INFO] 매니저 체크 탭 지연 업데이트 시작")
                
                # 상태바 업데이트
                self.parent_app.statusBar().showMessage("매니저 체크 탭 업데이트 시작", 0)
                QtWidgets.QApplication.processEvents()  # UI 업데이트
                
                # 업종 목록 갱신 (고객 추가/삭제로 인한 업종 변경 반영)
                if hasattr(self.parent_app.manager_check_tab, 'update_real_biz_set'):
                    self.parent_app.manager_check_tab.update_real_biz_set()
                    print("[INFO] 매니저 체크 탭 업종 목록 갱신 완료")
                
                # 별도의 스레드를 사용하지 않고 UI 스레드에서 실행하되
                # force_reload=True로 설정하여 완전한 새로고침 수행
                self.parent_app.manager_check_tab.refresh_tab_data(force_reload=True)
                
                # 업데이트 완료 메시지
                self.parent_app.statusBar().showMessage("매니저 체크 탭 업데이트 완료", 3000)
                QtWidgets.QApplication.processEvents()  # UI 업데이트
                
                print("[INFO] 매니저 체크 탭 업데이트 완료")
        except RuntimeError as rt_err:
            # C++ 객체가 이미 삭제된 경우 처리
            if "C++ object" in str(rt_err) and "deleted" in str(rt_err):
                print("[INFO] 매니저 체크 탭이 이미 삭제되어 업데이트를 건너뜁니다.")
            else:
                print(f"[ERROR] 매니저 체크 탭 업데이트 중 런타임 오류: {rt_err}")
        except Exception as e:
            print(f"[ERROR] 매니저 체크 탭 업데이트 중 오류 발생: {e}")
            # 오류 메시지 표시
            if hasattr(self.parent_app, 'statusBar') and callable(self.parent_app.statusBar):
                try:
                    self.parent_app.statusBar().showMessage(f"매니저 체크 탭 업데이트 오류: {e}", 3000)
                    QtWidgets.QApplication.processEvents()  # UI 업데이트
                except Exception:
                    pass  # statusBar 호출 실패 시 무시
            
            import traceback
            print(f"[ERROR] 스택 트레이스: {traceback.format_exc()}")

    def _delayed_tab_update(self, tab_name):
        """탭 업데이트를 지연 실행하는 헬퍼 메소드"""
        try:
            if hasattr(self.parent_app, tab_name):
                tab_obj = getattr(self.parent_app, tab_name)
                if hasattr(tab_obj, 'filter_and_populate'):
                    tab_obj.filter_and_populate()
                    print(f"[INFO] {tab_name} 탭 지연 업데이트 완료")
                elif hasattr(tab_obj, 'rebuild_and_populate_for_current_selection'):
                    tab_obj.rebuild_and_populate_for_current_selection()
                    print(f"[INFO] {tab_name} 탭 리빌드 및 업데이트 완료")
                else:
                    print(f"[WARN] {tab_name}에 업데이트 메서드가 없습니다.")
            else:
                print(f"[WARN] parent_app에 {tab_name} 속성이 없습니다.")
        except Exception as e:
            print(f"[ERROR] {tab_name} 탭 업데이트 중 오류: {e}")
            import traceback
            print(f"[ERROR] 스택 트레이스: {traceback.format_exc()}")
            # 오류가 발생해도 프로그램 전체가 중단되지 않도록 처리

    def build_floor_str(self, fmin, fmax, is_top):
        """
        층 범위 숫자를 사용자가 인식할 수 있는 텍스트로 변환
        (parse_floor_range의 역함수 역할)
        
        입력:
            fmin: 최소 층 (예: 2)
            fmax: 최대 층 (예: 999)
            is_top: 탑층 여부 (True/False)
            
        출력:
            UI에 표시하고 DB에 저장할 형태의 층 문자열 
            (예: "2층이상", "1층", "탑층", "지하층", "3~5층", "2층이상, 탑층" 등)
            
        특별 케이스:
            - 1층 + 2층이상: "1~999층"으로 표시
            - 지하층 + 1층 + 2층이상: "전체층"으로 표시
        """
        # 기본값 설정
        result_parts = []
        has_basement = False
        has_first_floor = False
        has_above_second = False
        
        # 지하층 확인
        if fmin < 0:
            has_basement = True
            result_parts.append("지하층")
        
        # 1층 확인
        if (fmin == 1 and fmax == 1) or (fmin <= 1 and fmax >= 1):
            has_first_floor = True
            if not (fmin < 1 and fmax > 1):  # 범위에 포함된 경우가 아니라 명시적인 경우만
                result_parts.append("1층")
        
        # 2층이상 확인
        if fmin <= 2 and fmax >= 999:
            has_above_second = True
            if not (fmin < 2):  # 범위에 포함된 경우가 아니라 명시적인 경우만
                result_parts.append("2층이상")
        elif fmin >= 2 and fmax >= 999:
            has_above_second = True
            result_parts.append(f"{fmin}층이상")
        elif fmin > 1 and fmax < 999 and fmin == fmax:
            # 단일층 (예: 3층)
            result_parts.append(f"{fmin}층")
        elif fmin > 1 and fmax < 999 and fmin < fmax:
            # 범위 (예: 3~5층)
            result_parts.append(f"{fmin}~{fmax}층")
        
        # 특별 케이스 처리
        result = ""
        
        # 특별 케이스 1: 1층 + 2층이상 = 1~999층
        if has_first_floor and has_above_second and not has_basement:
            result = "1~999층"
        # 특별 케이스 2: 지하층 + 1층 + 2층이상 = 전체층
        elif has_basement and has_first_floor and has_above_second:
            result = "전체층"
        # 일반 케이스: 각 부분을 쉼표로 구분하여 결합
        else:
            result = ", ".join(result_parts)
        
        # 탑층 추가
        if is_top:
            if result:
                result += ", 탑층"
            else:
                result = "탑층"
                
        return result

    def _update_customer_sheet_locally(self, row_data, row_idx, cust_id, manager):
        """
        (기존 update_customer_sheet에서 'UI에 setItem' 부분만 떼어옴)
        """
        model = self.customer_model
        headers = self.customer_headers

        for col_idx, val in enumerate(row_data):
            col_name = headers[col_idx]
            
            if col_name == "지역":
                try:
                    region_obj = json.loads(val) if val.strip() else {}
                    dongs_list = region_obj.get("dong_list", [])
                    rects_list = region_obj.get("rectangles", [])
                    
                    short_txt, tip_txt = self.build_region_short_text(dongs_list, rects_list)
                    new_item = QtGui.QStandardItem(short_txt)
                    new_item.setToolTip(tip_txt)
                    new_item.setData(val, QtCore.Qt.UserRole+1)
                except:
                    new_item = QtGui.QStandardItem(val)
            elif col_name == "메모":
                short_txt, tip_txt = self.build_memo_display_text(val)
                new_item = QtGui.QStandardItem(short_txt)
                new_item.setToolTip(tip_txt)
                new_item.setData(val, QtCore.Qt.UserRole+1)
            else:
                new_item = QtGui.QStandardItem(str(val))

            if col_idx == 0:
                new_item.setData({"id": cust_id, "manager": manager}, QtCore.Qt.UserRole)
            else:
                new_item.setData({"id": cust_id, "manager": manager, "column": col_name}, QtCore.Qt.UserRole)

            model.setItem(row_idx, col_idx, new_item)

    def _build_payload_for_server(self, row_data, cust_id, manager):
        """서버로 전송할 페이로드 구성 - 최적화 버전"""
        # 변경된 필드만 필요한 경우 로직을 간소화하여 불필요한 파싱 작업을 줄임
        payload = {
            "id": cust_id,
            "manager": manager,
        }
        
        # 필드 이름으로 직접 접근하기 위한 인덱스 매핑
        headers = self.customer_headers
        field_indices = {}
        for field in ["지역", "보증금", "월세", "평수", "층", "권리금", "업종", "연락처", "실보증금/월세", "최근연락날짜", "메모"]:
            try:
                field_indices[field] = headers.index(field)
            except ValueError:
                field_indices[field] = -1
        
        # 1. 지역 데이터 처리 (JSON 문자열 그대로 전달)
        region_idx = field_indices.get("지역", -1)
        if region_idx >= 0 and region_idx < len(row_data):
            region_json_str = row_data[region_idx]
            try:
                region_obj = json.loads(region_json_str) if region_json_str.strip() else {}
                payload["gu_list"] = region_obj.get("gu_list", [])
                payload["dong_list"] = region_obj.get("dong_list", [])
                payload["rects_list"] = region_obj.get("rectangles", [])
            except:
                # JSON 파싱 실패 시 빈 객체로 설정
                payload["gu_list"] = []
                payload["dong_list"] = []
                payload["rects_list"] = []
                print(f"[WARN] 지역 JSON 파싱 실패: '{region_json_str}'")
        
        # 2. 보증금/월세/평수 처리
        # 보증금
        idx = field_indices.get("보증금", -1)
        if idx >= 0 and idx < len(row_data):
            deposit_str = row_data[idx]
            if "~" in deposit_str:
                try:
                    d_min, d_max = deposit_str.split("~")
                    payload["deposit_min"] = int(d_min.strip())
                    payload["deposit_max"] = int(d_max.strip())
                except:
                    payload["deposit_min"] = 0
                    payload["deposit_max"] = 0
            else:
                try:
                    val = int(deposit_str) if deposit_str.strip() else 0
                    payload["deposit_min"] = val
                    payload["deposit_max"] = val
                except:
                    payload["deposit_min"] = 0
                    payload["deposit_max"] = 0
        
        # 월세
        idx = field_indices.get("월세", -1)
        if idx >= 0 and idx < len(row_data):
            monthly_str = row_data[idx]
            if "~" in monthly_str:
                try:
                    m_min, m_max = monthly_str.split("~")
                    payload["monthly_min"] = int(m_min.strip())
                    payload["monthly_max"] = int(m_max.strip())
                except:
                    payload["monthly_min"] = 0
                    payload["monthly_max"] = 0
            else:
                try:
                    val = int(monthly_str) if monthly_str.strip() else 0
                    payload["monthly_min"] = val
                    payload["monthly_max"] = val
                except:
                    payload["monthly_min"] = 0
                    payload["monthly_max"] = 0
        
        # 평수
        idx = field_indices.get("평수", -1)
        if idx >= 0 and idx < len(row_data):
            area_str = row_data[idx]
            if "~" in area_str:
                try:
                    a_min, a_max = area_str.split("~")
                    payload["area_min"] = int(a_min.strip())
                    payload["area_max"] = int(a_max.strip())
                except:
                    payload["area_min"] = 0
                    payload["area_max"] = 0
            else:
                try:
                    val = int(area_str) if area_str.strip() else 0
                    payload["area_min"] = val
                    payload["area_max"] = val
                except:
                    payload["area_min"] = 0
                    payload["area_max"] = 0
        
        # 3. 층 데이터 처리
        idx = field_indices.get("층", -1)
        if idx >= 0 and idx < len(row_data):
            floor_str = row_data[idx]
            
            # 기본값 설정
            payload["floor_min"] = 0
            payload["floor_max"] = 0
            payload["is_top_floor"] = 0
            
            try:
                # 특별 케이스: "전체층" 처리
                if "전체층" in floor_str:
                    payload["floor_min"] = -999
                    payload["floor_max"] = 999
                    payload["is_top_floor"] = 1 if "탑층" in floor_str else 0
                    print(f"[DEBUG] 전체층 처리: 범위={payload['floor_min']}~{payload['floor_max']}, 탑층={payload['is_top_floor']}")
                    return payload
                
                # 층 옵션이 콤마로 구분된 경우를 처리하기 위해 분리
                floor_options = [opt.strip() for opt in floor_str.split(',') if opt.strip()]
                
                # 각 옵션 처리 결과를 저장할 변수들 초기화
                final_floor_min = 999  # 가장 낮은 최소값을 찾기 위해 높은 값으로 시작
                final_floor_max = -999  # 가장 높은 최대값을 찾기 위해 낮은 값으로 시작
                is_top = False
                
                # 빈 문자열 처리
                if not floor_options:
                    payload["floor_min"] = 0
                    payload["floor_max"] = 0
                    payload["is_top_floor"] = 0
                else:
                    # 각 옵션 개별 처리
                    for option in floor_options:
                        # 탑층 여부 체크
                        if "탑층" in option:
                            is_top = True
                            continue
                            
                        # 지하층 처리
                        if "지하" in option:
                            final_floor_min = min(final_floor_min, -1)
                            final_floor_max = max(final_floor_max, -1)
                            continue
                        
                        # "1~999층" 특별 케이스 처리
                        if "1~999" in option:
                            final_floor_min = 1
                            final_floor_max = 999
                            continue
                            
                        # 2층이상 처리
                        if "층이상" in option:
                            try:
                                num_part = option.replace("층이상", "").strip()
                                floor_num = int(num_part)
                                final_floor_min = min(final_floor_min, floor_num)
                                final_floor_max = max(final_floor_max, 999)
                            except ValueError:
                                # 숫자 변환 실패 시 기본값 사용
                                if "2층이상" in option:  # 기본 케이스
                                    final_floor_min = min(final_floor_min, 2)
                                    final_floor_max = max(final_floor_max, 999)
                            continue
                            
                        # 범위 처리 (예: 3~5층)
                        if "~" in option:
                            try:
                                range_part = option.replace("층", "").strip()
                                s, e = range_part.split("~", 1)
                                s_val = int(s.strip())
                                e_val = int(e.strip())
                                final_floor_min = min(final_floor_min, s_val)
                                final_floor_max = max(final_floor_max, e_val)
                            except ValueError:
                                # 파싱 실패 시 무시
                                pass
                            continue
                            
                        # 단일 층 처리 (예: 3층, 1층 등)
                        if "층" in option:
                            try:
                                num_part = option.replace("층", "").strip()
                                val = int(num_part)
                                final_floor_min = min(final_floor_min, val)
                                final_floor_max = max(final_floor_max, val)
                            except ValueError:
                                # 파싱 실패 시 무시
                                pass
                    
                    # 최종 결과 설정
                    # 초기화 값이 변경되지 않았다면 기본값으로 설정
                    if final_floor_min == 999 and final_floor_max == -999:
                        final_floor_min = 0
                        final_floor_max = 0
                    
                    payload["floor_min"] = final_floor_min
                    payload["floor_max"] = final_floor_max
                    payload["is_top_floor"] = 1 if is_top else 0
                
            except Exception as e:
                print(f"[ERROR] 층 처리 중 예외 발생: {e}")
                # 예외 발생 시 안전한 기본값 사용
                payload["floor_min"] = 0
                payload["floor_max"] = 0
                payload["is_top_floor"] = 0
            
            # 디버깅 로그
            print(f"[DEBUG] 층 처리 결과: 원본='{floor_str}', 범위={payload['floor_min']}~{payload['floor_max']}, 탑층={payload['is_top_floor']}")
        
        # 4. 나머지 간단한 필드들
        for field, payload_key in [
            ("권리금", "premium"),
            ("업종", "biz_type"),
            ("연락처", "contact"),
            ("실보증금/월세", "real_deposit_monthly"),
            ("최근연락날짜", "last_contact_date"),
            ("메모", "memo_json")
        ]:
            idx = field_indices.get(field, -1)
            if idx >= 0 and idx < len(row_data):
                payload[payload_key] = row_data[idx]
        
        return payload

    def _bg_update_customer_sheet(self, payload):
        """
        (백그라운드 스레드)
        => requests.post(...) 로 서버에 update_customer_sheet 호출
        => 응답 JSON 반환
        """
        import requests
        import traceback
        url = f"http://{self.server_host}:{self.server_port}/customer/update_customer_sheet"
        try:
            # 타임아웃 5초로 설정
            resp = requests.post(url, json=payload, timeout=5)
            resp.raise_for_status()
            return resp.json()  # {"status":"ok", ...} or {"status":"error",...}
        except requests.exceptions.Timeout:
            return {
                "status": "error",
                "message": "서버 요청 시간 초과 (5초). 네트워크 상태를 확인해주세요."
            }
        except requests.exceptions.ConnectionError:
            return {
                "status": "error",
                "message": "서버 연결 오류. 서버가 실행 중인지 확인해주세요."
            }
        except Exception as ex:
            return {
                "status": "exception",
                "message": f"{ex}\n{traceback.format_exc()}"
            }

    def has_row_data_changed(self, old_values, new_values):
        """고객 데이터 변경 여부 확인"""
        if len(old_values) != len(new_values):
            return True
        
        for i, (old, new) in enumerate(zip(old_values, new_values)):
            if i >= len(self.customer_headers):
                continue
            
            header = self.customer_headers[i]
            
            # 지역과 메모는 JSON 비교
            if header in ["지역", "메모"]:
                try:
                    if old and new:  # 둘 다 데이터가 있는 경우
                        old_obj = json.loads(old) if isinstance(old, str) else old
                        new_obj = json.loads(new) if isinstance(new, str) else new
                        if old_obj != new_obj:
                            print(f"[DEBUG] '{header}' 필드 변경 감지")
                            return True
                    elif bool(old) != bool(new):  # 한쪽만 데이터가 있는 경우
                        print(f"[DEBUG] '{header}' 필드 변경 감지 (비어있음 <-> 채워짐)")
                        return True
                except:
                    if old != new:
                        print(f"[DEBUG] '{header}' 필드 변경 감지 (JSON 파싱 실패)")
                        return True
            elif old != new:
                print(f"[DEBUG] '{header}' 필드 변경 감지: '{old}' -> '{new}'")
                return True
        
        return False