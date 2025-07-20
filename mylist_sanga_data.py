# mylist_sanga_data.py
import time
import requests
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItem, QPixmap, QIcon, QColor, QStandardItemModel
from PyQt5.QtWidgets import QMessageBox, QApplication
import os
from PyQt5.QtCore import QUrl
import logging # 로깅 임포트
from mylist_constants import PENDING_COLOR, RE_AD_BG_COLOR, NEW_AD_BG_COLOR

logger = logging.getLogger(__name__) # 모듈 레벨 로거

def get_api_endpoint(server_host, server_port):
    """Return the API endpoint for fetching mylist_shop data."""
    return f"http://{server_host}:{server_port}/mylist/get_all_mylist_shop_data"

def bg_load_mylist_shop_data(server_host, server_port, manager, role):
    """(Background Thread) Fetches mylist_shop data via GET request."""
    # print(f"[DEBUG] MyListSangaData: Fetching data for manager={manager}, role={role}")
    logger.info(f"bg_load_mylist_shop_data: Fetching for manager='{manager}', role='{role}'") # 로그 수정
    url = get_api_endpoint(server_host, server_port)
    params = {"manager": manager, "role": role}
    try:
        logger.debug(f"bg_load_mylist_shop_data: Sending GET request to {url} with params: {params}") # 로그 추가
        resp = requests.get(url, params=params, timeout=10)
        logger.debug(f"bg_load_mylist_shop_data: Received response status {resp.status_code}") # 로그 추가
        resp.raise_for_status()
        j = resp.json()
        status = j.get('status')
        logger.info(f"bg_load_mylist_shop_data: API response status='{status}'.") # 로그 추가
        if status != "ok":
            # print(f"[ERROR] MyListSangaData Fetch Error: Status={j.get('status')}, Msg={j.get('message')}")
            logger.error(f"bg_load_mylist_shop_data: API error - Status: {status}, Message: {j.get('message')}") # 로그 수정
            return {"status": "error", "data": [], "message": j.get('message')}
        # print(f"[DEBUG] MyListSangaData Fetch: Received {len(j.get('data',[]))} rows.")
        data_len = len(j.get('data', []))
        logger.info(f"bg_load_mylist_shop_data: Successfully fetched {data_len} rows.") # 로그 수정
        return {"status": "ok", "data": j.get("data", [])}
    except requests.Timeout:
        # print("[ERROR] MyListSangaData Fetch Error: Request timed out.")
        logger.error("bg_load_mylist_shop_data: Request timed out.", exc_info=True) # 로그 수정
        return {"status": "exception", "message": "Request timed out", "data": []}
    except requests.RequestException as ex:
        # print(f"[ERROR] MyListSangaData Fetch Error: {ex}")
        logger.error(f"bg_load_mylist_shop_data: RequestException - {ex}", exc_info=True) # 로그 수정
        return {"status": "exception", "message": str(ex), "data": []}
    except Exception as ex_other:
        # print(f"[ERROR] MyListSangaData Fetch Error (Unexpected): {ex_other}")
        logger.error(f"bg_load_mylist_shop_data: Unexpected error - {ex_other}", exc_info=True) # 로그 수정
        return {"status": "exception", "message": f"Unexpected error: {ex_other}", "data": []}

def get_mylist_shop_known_ids(model):
    """
    Returns a set of all real database IDs currently in the shop model.
    More robust version with error handling for multi-threading contexts.
    """
    known_ids = set()
    
    if not model:
        print("[WARN] get_mylist_shop_known_ids called with None model")
        return known_ids
    
    try:
        row_count = model.rowCount()
        for row in range(row_count):
            item0 = model.item(row, 0)
            if not item0:
                continue
                
            record_id = item0.data(Qt.UserRole + 3)
            if record_id is not None and isinstance(record_id, int) and record_id > 0:
                known_ids.add(record_id)
    except Exception as e:
        print(f"[ERROR] Error in get_mylist_shop_known_ids: {e}")
        
    return known_ids

def create_shop_item(header_name, cell_value, db_row_data):
    """Creates a QStandardItem for the shop table with appropriate data and tooltips."""
    item = QStandardItem(str(cell_value)) # Ensure value is string

    # Special handling for '주소' column (icon, tooltip, roles)
    if header_name == "주소":
        folder_path = db_row_data.get("photo_path", "") or ""
        rep_img_path = ""
        if folder_path and os.path.isdir(folder_path):
            try:
                files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
                if files: rep_img_path = os.path.join(folder_path, sorted(files)[0]) # Take first sorted image
            except OSError as e:
                print(f"[WARN] Cannot access folder path '{folder_path}': {e}")

        if rep_img_path and os.path.isfile(rep_img_path):
            try:
                pixmap = QPixmap(rep_img_path).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                if not pixmap.isNull():
                    item.setIcon(QIcon(pixmap))
                    file_url = QUrl.fromLocalFile(rep_img_path).toString()
                    item.setToolTip(f'<img src="{file_url}" width="200">')
                else:
                    print(f"[WARN] Failed to load pixmap for icon: {rep_img_path}")
                    item.setToolTip(cell_value) # Fallback tooltip
            except Exception as img_err:
                print(f"[WARN] Error creating icon/tooltip for {rep_img_path}: {img_err}")
                item.setToolTip(cell_value)
        else:
            item.setToolTip(cell_value)

        item.setData(folder_path, Qt.UserRole + 10)
        item.setData(rep_img_path, Qt.UserRole + 11)
        item.setData(db_row_data.get("status_cd", ""), Qt.UserRole + 1) # Status code
        item.setData(db_row_data.get("id"), Qt.UserRole + 3) # DB Primary Key

    # --- 추가: 기본적인 아이템 플래그 설정 (편집 가능 포함) ---
    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
    # --- 추가 끝 ---

    # 성능 최적화: 디버그 로깅 제거 (대량 데이터 처리 시 성능 저하 방지)
    # 필요시에만 주석 해제하여 사용
    # try:
    #     flags = item.flags()
    #     is_editable = bool(flags & Qt.ItemIsEditable)
    #     logger.debug(f"[create_shop_item] Item created for '{header_name}'. Flags: {flags}, IsEditable: {is_editable}")
    # except Exception as flag_log_err:
    #     logger.warning(f"[create_shop_item] Error logging item flags: {flag_log_err}")

    return item

def update_model_row(model, row_idx, headers, db_row_data, column_map):
    """Helper function to set items for a single row in the shop model based on DB data."""
    item0 = None # Keep track of the first item for setting ID etc.
    for col_idx, header_name in enumerate(headers):
        # Map the header (display) name to the expected DB key
        db_key = column_map.get(header_name, None)
        raw_value = db_row_data.get(db_key) if db_key else None

        # Special handling for combined fields or specific formatting
        if header_name == "주소":
            cell_val = f"{db_row_data.get('dong', '')} {db_row_data.get('jibun', '')}".strip()
        elif header_name == "층":
            cell_val = f"{db_row_data.get('curr_floor', 0)}/{db_row_data.get('total_floor', 0)}"
        elif header_name == "보증금/월세":
            cell_val = f"{db_row_data.get('deposit', 0)}/{db_row_data.get('monthly', 0)}"
        elif header_name == "매물번호":
            cell_val = f"{db_row_data.get('naver_property_no', '')}/{db_row_data.get('serve_property_no', '')}"
        elif header_name == "방/화장실":
            r, b = db_row_data.get("rooms", ""), db_row_data.get("baths", "")
            cell_val = f"방{r}/{b}" if r or b else "" # Changed format slightly
        elif header_name == "재광고":
            cell_val = "재광고" if db_row_data.get("re_ad_yn", "N") == "Y" else "새광고"
        elif header_name == "관리비":
            cell_val = str(raw_value) if raw_value is not None else ""
        elif header_name == "평수":
            cell_val = str(raw_value) if raw_value is not None else ""
        elif header_name == "주차대수":
            cell_val = str(raw_value) if raw_value is not None else ""
        elif header_name == "사용승인일":
            cell_val = str(raw_value) if raw_value is not None else ""
        elif header_name == "광고종료일":
            cell_val = str(raw_value) if raw_value is not None else ""
        else:
            # Default: use the raw value directly (convert None to empty string)
            cell_val = str(raw_value) if raw_value is not None else ""

        item = create_shop_item(header_name, cell_val, db_row_data) # Use helper
        model.setItem(row_idx, col_idx, item)
        if col_idx == 0:
            item0 = item # Store the first item (address item)

    # Set background color based on '재광고' status AFTER all items are set
    re_ad_yn = db_row_data.get("re_ad_yn", "N") == "Y"
    row_bg = RE_AD_BG_COLOR if re_ad_yn else NEW_AD_BG_COLOR
    for c in range(model.columnCount()):
        cell = model.item(row_idx, c)
        if cell:
            cell.setBackground(row_bg)

def append_mylist_shop_rows(model, headers, row_list, column_map, parent_app=None):
    """Appends rows to the provided shop table model with optimized batch processing."""
    if not row_list: return

    if not model:
        logger.error("append_mylist_shop_rows: Cannot append rows, model is None.")
        return

    append_start_time = time.time()
    rows_to_add = len(row_list)
    start_row = model.rowCount()
    
    logger.debug(f"append_mylist_shop_rows: Appending {rows_to_add} rows to model starting at row {start_row}.")

    # 성능 최적화: 모든 시그널 블록하고 배치 업데이트
    model.blockSignals(True)
    
    try:
        # 한 번에 모든 행 삽입
        model.insertRows(start_row, rows_to_add)

        if not headers:
            logger.warning("append_mylist_shop_rows: Cannot append rows effectively, headers not provided.")
            model.blockSignals(False)
            return

        # 배치 단위로 처리하여 UI 응답성 향상
        BATCH_SIZE = 100  # 배치 크기 설정
        
        for batch_start in range(0, rows_to_add, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, rows_to_add)
            
            # 각 배치 처리
            for i in range(batch_start, batch_end):
                db_row_data = row_list[i]
                row_idx = start_row + i
                update_model_row(model, row_idx, headers, db_row_data, column_map)
            
            # 중간 진행상황 로그 (큰 데이터셋의 경우)
            if rows_to_add > 200:
                logger.debug(f"append_mylist_shop_rows: Processed batch {batch_start+1}-{batch_end} of {rows_to_add}")
                
            # 아주 큰 데이터셋의 경우 중간에 이벤트 처리 허용
            if rows_to_add > 500 and i % 200 == 0:
                QApplication.processEvents()

    except Exception as e:
        logger.error(f"append_mylist_shop_rows: Error during row appending: {e}", exc_info=True)
    finally:
        model.blockSignals(False)
        append_duration = time.time() - append_start_time
        logger.info(f"append_mylist_shop_rows: Appended {rows_to_add} rows in {append_duration:.3f} seconds.")
        # Don't recalculate summary on every append chunk, do it after the full fetch

def populate_mylist_shop_table(logic_instance, rows):
    """Populates the shop table model with the given rows by resetting the model with optimizations."""
    logger.info(f"populate_mylist_shop_table: Starting population with {len(rows)} rows by resetting the model.")
    if not logic_instance.mylist_shop_view:
        logger.error("populate_mylist_shop_table: Cannot populate, view is None.")
        if hasattr(logic_instance, 'mylist_shop_loading'):
            logic_instance.mylist_shop_loading = False
        return

    logic_instance.mylist_shop_loading = True
    view = logic_instance.mylist_shop_view

    # 성능 최적화: 뷰 업데이트 비활성화 및 정렬 임시 중단
    view.setUpdatesEnabled(False)
    view_sorting_was_enabled = view.isSortingEnabled()
    view.setSortingEnabled(False)

    # 새 모델 생성
    new_model = QStandardItemModel()
    headers = logic_instance._get_horizontal_headers()
    column_map = getattr(logic_instance.parent_app, 'COLUMN_MAP_MYLIST_SHOP_DISPLAY_TO_DB', {}) 
    parent_app = logic_instance.parent_app

    if headers:
        new_model.setHorizontalHeaderLabels(headers)
    else:
        logger.warning("populate_mylist_shop_table: Could not get headers for new model.")

    try:
        # 새 모델에 행 추가 (수정된 append_mylist_shop_rows 사용)
        if rows:
            logger.debug("populate_mylist_shop_table: Calling append_mylist_shop_rows for the new model.")
            # 수정된 함수 호출: model, headers, row_list, column_map, parent_app 전달
            append_mylist_shop_rows(new_model, headers, rows, column_map, parent_app)
            logger.debug("populate_mylist_shop_table: append_mylist_shop_rows finished for the new model.")
            # === 기존 직접 구현 로직 제거 ===
            # start_row = 0
            # new_model.insertRows(start_row, len(rows))
            # for i, db_row_data in enumerate(rows):
            #     row_idx = start_row + i
            #     update_model_row(new_model, row_idx, headers, db_row_data, 
            #                     logic_instance.parent_app.COLUMN_MAP_MYLIST_SHOP_DISPLAY_TO_DB)
            # logger.debug(f"populate_mylist_shop_table: Appended {len(rows)} rows to the new model.")
            # =================================

        logger.info(f"populate_mylist_shop_table: Setting the new model to the view. New row count: {new_model.rowCount()}")
        # 뷰에 새 모델 설정 -> 이 시점에 뷰가 갱신됨
        logic_instance.mylist_shop_model = new_model # Update logic instance reference first
        view.setModel(new_model) # Set the new model to the view
        
        # <<< 시그널 발생 코드 이동 및 수정 >>>
        try:
            if hasattr(logic_instance, 'model_populated') and logic_instance.model_populated:
                logger.info("populate_mylist_shop_table: Emitting model_populated signal (after setModel).")
                logic_instance.model_populated.emit()
            else:
                logger.warning("populate_mylist_shop_table: logic_instance does not have model_populated signal to emit.")
            
            # Reset loading flag immediately after signal emission related to model change
            if hasattr(logic_instance, 'mylist_shop_loading'):
                logic_instance.mylist_shop_loading = False
                logger.info("populate_mylist_shop_table: Loading flag reset (after setModel and signal emit).")

        except Exception as emit_e:
             logger.error(f"populate_mylist_shop_table: Error emitting signal or resetting flag: {emit_e}", exc_info=True)
        # <<< 코드 이동 및 수정 끝 >>>

        # 모델 변경 후 컬럼 너비 복원 (필요한 경우)
        # restore_qtableview_column_widths(logic_instance.parent_app.settings_manager, view, "MyListShopTable") # ui_utils 필요

    except Exception as e_pop:
        logger.error(f"populate_mylist_shop_table: Error during population: {e_pop}", exc_info=True)
        # Optionally clear the view or show an error message
        # Ensure loading flag is reset even on error
        if hasattr(logic_instance, 'mylist_shop_loading'):
            logic_instance.mylist_shop_loading = False
            logger.warning("populate_mylist_shop_table: Loading flag reset in exception handler.")
    finally:
        logger.debug("populate_mylist_shop_table: Entering finally block.")
        
        # UI 업데이트 및 정렬 재활성화
        view.setUpdatesEnabled(True)
        view.setSortingEnabled(view_sorting_was_enabled)

        # 요약 정보 재계산 (성능 최적화: 백그라운드에서 실행)
        try:
            if hasattr(logic_instance.container, '_recalculate_manager_summary'):
                # 큰 데이터셋의 경우 요약 계산을 약간 지연시켜 UI 응답성 향상
                if hasattr(logic_instance, 'parent_app') and hasattr(logic_instance.parent_app, 'executor'):
                    def delayed_summary():
                        try:
                            logic_instance.container._recalculate_manager_summary()
                        except Exception as summary_err:
                            logger.error(f"Error in delayed summary calculation: {summary_err}")
                    
                    logic_instance.parent_app.executor.submit(delayed_summary)
                    logger.debug("populate_mylist_shop_table: Scheduled manager summary recalculation in background.")
                else:
                    logic_instance.container._recalculate_manager_summary()
                    logger.debug("populate_mylist_shop_table: Triggered manager summary recalculation.")
            else:
                logger.warning("populate_mylist_shop_table: logic_instance.container has no _recalculate_manager_summary method.")
        except Exception as summary_e:
            logger.error(f"populate_mylist_shop_table: Error during summary recalculation: {summary_e}")
            
        logger.info("populate_mylist_shop_table: Finished.")

def parse_mylist_shop_row(logic_instance, row_idx):
    """Parses a single row from the shop model into a dictionary for DB saving."""
    model = logic_instance.mylist_shop_model
    if not model or row_idx >= model.rowCount(): return {}

    # Helper to get text safely
    def get_item_text(r, c):
        item = model.item(r, c)
        return item.text().strip() if item else ""

    # Get values based on column index (ensure headers are correct in init_ui)
    headers = logic_instance._get_horizontal_headers()
    row_dict_parsed = {}

    for c, header in enumerate(headers):
        text_val = get_item_text(row_idx, c)
        db_key = logic_instance.parent_app.COLUMN_MAP_MYLIST_SHOP_DISPLAY_TO_DB.get(header)

        if header == "주소":
            dong_val, jibun_val = text_val.split(" ", 1) if " " in text_val else (text_val, "")
            row_dict_parsed["dong"] = dong_val
            row_dict_parsed["jibun"] = jibun_val
        elif header == "층":
            cf_val, tf_val = 0, 0
            if "/" in text_val:
                c_str, t_str = text_val.split("/", 1)
                cf_val = int(c_str) if c_str.isdigit() else 0
                tf_val = int(t_str) if t_str.isdigit() else 0
            row_dict_parsed["curr_floor"] = cf_val
            row_dict_parsed["total_floor"] = tf_val
        elif header == "보증금/월세":
            dep_val, mon_val = 0, 0
            if "/" in text_val:
                d_str, m_str = text_val.split("/", 1)
                dep_val = int(d_str) if d_str.isdigit() else 0
                mon_val = int(m_str) if m_str.isdigit() else 0
            row_dict_parsed["deposit"] = dep_val
            row_dict_parsed["monthly"] = mon_val
        elif header == "매물번호":
            nav_val, srv_val = text_val.split("/", 1) if "/" in text_val else (text_val, "")
            row_dict_parsed["naver_property_no"] = nav_val.strip()
            row_dict_parsed["serve_property_no"] = srv_val.strip()
        elif header == "방/화장실":
            rm_val, bt_val = "", ""
            if "/" in text_val:
                r_str, b_str = text_val.split("/", 1)
                rm_val = r_str.replace("방", "").strip()
                bt_val = b_str.strip()
            row_dict_parsed["rooms"] = rm_val
            row_dict_parsed["baths"] = bt_val
        elif header == "재광고":
            row_dict_parsed["re_ad_yn"] = "Y" if text_val == "재광고" else "N"
        elif header == "평수":
            ar_val = 0.0
            try: ar_val = float(text_val) if text_val else 0.0
            except ValueError: ar_val = 0.0
            row_dict_parsed["area"] = ar_val
        elif db_key:
            # Direct mapping for simple text fields
            row_dict_parsed[db_key] = text_val

    # Get status code from UserRole+1 of the first item
    status_cd = ""
    item0 = model.item(row_idx, 0)
    if item0: status_cd = item0.data(Qt.UserRole + 1) or ""
    row_dict_parsed["status_cd"] = status_cd

    # Ensure all expected keys exist (even if empty), based on the column map
    for db_key in logic_instance.parent_app.COLUMN_MAP_MYLIST_SHOP_DISPLAY_TO_DB.values():
        if db_key and db_key not in row_dict_parsed:
            # Set default based on expected type? For now, empty string or 0
            if db_key in ["curr_floor", "total_floor", "deposit", "monthly", "area"]:
                row_dict_parsed[db_key] = 0
            else:
                row_dict_parsed[db_key] = ""
    # Ensure composite fields are covered
    if "dong" not in row_dict_parsed: row_dict_parsed["dong"] = ""
    if "jibun" not in row_dict_parsed: row_dict_parsed["jibun"] = ""
    if "naver_property_no" not in row_dict_parsed: row_dict_parsed["naver_property_no"] = ""
    if "serve_property_no" not in row_dict_parsed: row_dict_parsed["serve_property_no"] = ""
    if "rooms" not in row_dict_parsed: row_dict_parsed["rooms"] = ""
    if "baths" not in row_dict_parsed: row_dict_parsed["baths"] = ""
    if "re_ad_yn" not in row_dict_parsed: row_dict_parsed["re_ad_yn"] = "N"
    if "status_cd" not in row_dict_parsed: row_dict_parsed["status_cd"] = ""

    return row_dict_parsed

def build_mylist_shop_rows_for_changes(logic_instance, added_list, updated_list):
    """
    Parses rows from the model based on pending added/updated IDs.
    Returns dict: {"added": [parsed_added_rows], "updated": [parsed_updated_rows]}
    """
    model = logic_instance.mylist_shop_model
    if not model: return {"added": [], "updated": []}

    rowCount = model.rowCount()
    # Create map of ID -> row index for faster lookup
    id_to_row = {}
    for r in range(rowCount):
        item0 = model.item(r, 0)
        if item0:
            item_id = item0.data(Qt.UserRole+3)
            if item_id is not None:
                id_to_row[item_id] = r

    # 중복 제거를 위한 처리된 temp_id 추적
    processed_temp_ids = set()
    added_rows_parsed = []
    for add_obj in added_list: # add_obj is like {"temp_id": -1}
        temp_id = add_obj.get("temp_id")
        
        # 이미 처리된 temp_id면 건너뛰기
        if temp_id in processed_temp_ids:
            logger.warning(f"[build_for_changes] Skipping duplicate temp_id: {temp_id}")
            continue
            
        row_idx = id_to_row.get(temp_id)
        if row_idx is not None:
            try:
                row_dict = parse_mylist_shop_row(logic_instance, row_idx)
                row_dict["temp_id"] = temp_id # Pass temp_id back to server
                added_rows_parsed.append(row_dict)
                # 처리된 temp_id 기록
                processed_temp_ids.add(temp_id)
            except Exception as parse_err:
                logger.error(f"Failed to parse added row {row_idx} (temp_id {temp_id}): {parse_err}", exc_info=True)

    updated_rows_parsed = []
    # updated_list is like [{'id': 123, '담당자': 'NewMgr'}, ...]
    # We need the IDs that were marked for update.
    updated_ids = set(upd_obj.get("id") for upd_obj in updated_list if isinstance(upd_obj.get("id"), int) and upd_obj.get("id") > 0)

    for real_id in updated_ids:
        row_idx = id_to_row.get(real_id)
        if row_idx is not None:
            try:
                row_dict = parse_mylist_shop_row(logic_instance, row_idx)
                row_dict["id"] = real_id # Ensure real ID is set
                updated_rows_parsed.append(row_dict)
            except Exception as parse_err:
                logger.error(f"Failed to parse updated row {row_idx} (id {real_id}): {parse_err}", exc_info=True)

    # 결과 로깅
    if len(added_list) != len(added_rows_parsed):
        logger.info(f"[build_for_changes] Removed {len(added_list) - len(added_rows_parsed)} duplicate temp_ids from added_list")

    return {"added": added_rows_parsed, "updated": updated_rows_parsed}

def update_mylist_shop_row_id(logic_instance, old_tid, new_id):
    """
    Updates a temporary ID to a real ID after saving.
    
    Args:
        logic_instance: The MyListSangaLogic instance
        old_tid: The old temporary ID (string or int)
        new_id: The new real ID from the server (int)
    """
    logger = logic_instance.logger
    logger.info(f"[ID Update] Updating temp_id {old_tid} to real_id {new_id}")
    
    model = logic_instance.mylist_shop_model
    if not model:
        logger.error("[ID Update] Model not found.")
        return False
    
    # 서버에서 받은 temp_id가 문자열일 수 있으므로 안전하게 처리
    try:
        if isinstance(old_tid, str):
            old_tid_int = int(old_tid)
        else:
            old_tid_int = old_tid
        logger.debug(f"[ID Update] Converted old_tid '{old_tid}' to int: {old_tid_int}")
    except (ValueError, TypeError) as e:
        logger.error(f"[ID Update] Failed to convert old_tid '{old_tid}' to int: {e}")
        return False
    
    # 정수로 변환된 old_tid로 행 찾기
    found = False
    
    for row in range(model.rowCount()):
        item0 = model.item(row, 0)
        if not item0:
            continue
            
        # Check both UserRole+3 (RealID) and UserRole+99 (TempID)
        current_id = item0.data(Qt.UserRole + 3)
        temp_id = item0.data(Qt.UserRole + 99)
        
        logger.debug(f"[ID Update] Row {row}: RealID={current_id}, TempID={temp_id}, Looking for={old_tid_int}")
        
        # Match if either RealID or TempID matches the old temporary ID
        if current_id == old_tid_int or temp_id == old_tid_int:
            # Update the RealID to the new ID from server
            item0.setData(new_id, Qt.UserRole + 3)
            # Clear the temporary ID
            item0.setData(None, Qt.UserRole + 99)
            logger.info(f"[ID Update] Successfully updated row {row} from temp_id {old_tid_int} to real_id {new_id}")
            found = True
            
            # Update all cells in this row to mark them as having a real ID
            for col in range(model.columnCount()):
                cell_item = model.item(row, col)
                if cell_item:
                    # Apply white background to indicate saved state
                    cell_item.setBackground(QColor(255, 255, 255))
            break
    
    if not found:
        logger.warning(f"[ID Update] Could not find any row with temp_id {old_tid_int}")
    
    return found

def find_mylist_shop_row_by_id(logic_instance, pk_id):
    """Finds the row index corresponding to the given real DB ID."""
    m = logic_instance.mylist_shop_model
    if not m: return None
    for r in range(m.rowCount()):
        item0 = m.item(r, 0)
        if not item0: continue
        rid = item0.data(Qt.UserRole+3)
        if isinstance(rid, int) and rid == pk_id:
            return r
    return None

def get_summary_by_manager(logic_instance, manager_name):
    """Calculates the count of listings assigned to a specific manager."""
    count = 0
    model = logic_instance.mylist_shop_model
    if not model:
        print("[WARN] SangaData: Model not available for summary calculation.")
        return {"assigned": 0}

    manager_col_index = -1
    try:
        headers = logic_instance._get_horizontal_headers()
        manager_col_index = headers.index("담당자")
    except (ValueError, AttributeError):
        print("[WARN] SangaData: Cannot find '담당자' column for summary.")
        return {"assigned": 0} # Indicate error or inability to calculate

    for r in range(model.rowCount()):
        item = model.item(r, manager_col_index)
        if item and item.text().strip() == manager_name:
            count += 1

    return {"assigned": count} 