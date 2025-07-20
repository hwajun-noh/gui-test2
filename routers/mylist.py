from fastapi import APIRouter, HTTPException, Query, Body, Request
import mysql.connector as mysql
from settings import get_db_connection, get_supabase_client, logger
from models import CopyToMyListPayload # models.py에서 관련 모델 임포트
from typing import List
import os
from datetime import datetime, date

router = APIRouter()

@router.post("/copy_to_mylist")
def copy_to_mylist(payload: CopyToMyListPayload):
    items = payload.items
    manager = payload.manager
    if not items:
        raise HTTPException(status_code=400, detail="items가 비어있습니다.")

    # 지원하는 출처 테이블 정의
    source_table_map = {
        "원룸": "serve_oneroom_data",
        "상가": "serve_shop_data",
        "확인": "naver_shop_check_confirm",
        "추천": "recommend_data",
        "네이버": "naver_shop"
    }
    # 대상 테이블 정의
    target_table_map = {
        "원룸": "mylist_oneroom",
        "상가": "mylist_shop",
        "확인": "mylist_shop",
        "추천": "mylist_shop",
        "네이버": "mylist_shop"
    }

    conn = None
    cursor = None
    inserted_list = []
    errors = []

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        for obj in items:
            sid = obj.id
            s_ = obj.source
            row_memo = obj.memo or ""

            if s_ not in source_table_map:
                errors.append(f"ID={sid} => 지원하지 않는 출처 '{s_}'")
                continue

            source_table = source_table_map[s_]
            target_table = target_table_map[s_]

            try:
                # 1. 원본 데이터 조회
                sql_sel = f"SELECT * FROM `{source_table}` WHERE id=%s"
                cursor.execute(sql_sel, (sid,))
                row = cursor.fetchone()
                if not row:
                    errors.append(f"ID={sid}, 출처 '{s_}' 원본 없음")
                    continue
                
                # 2. 대상 테이블에 맞게 데이터 준비
                insert_data = dict(row) # 원본 복사
                insert_data['manager'] = manager # 담당자 덮어쓰기
                insert_data['memo'] = row_memo # 메모 덮어쓰기
                insert_data.pop('id', None) # 원본 id 제거
                
                # 추천 데이터일 경우 mylist_shop 테이블에 없는 필드들 제거
                if s_ == "추천":
                    # 제거할 필드 목록
                    fields_to_remove = ["property_id", "check_memo", "matching_biz", "source", "recommend_date"]
                    for field in fields_to_remove:
                        if field in insert_data:
                            logger.debug(f"추천 매물 처리: {field} 필드 제거 (ID={sid})")
                            insert_data.pop(field, None)

                # 테이블별 특수 처리
                if target_table == 'mylist_shop':
                    insert_data['re_ad_yn'] = "Y" if s_ == "상가" else "N"
                    # 네이버 또는 추천 출처일 경우 없는 컬럼 기본값 처리
                    if s_ in ("네이버", "추천"):
                        shop_cols = [
                            "gu", "dong", "jibun", "ho", "curr_floor", "total_floor", 
                            "deposit", "monthly", "manage_fee", "premium", "current_use", 
                            "area", "rooms", "baths", "building_usage", "parking", 
                            "naver_property_no", "serve_property_no", "approval_date", 
                            "memo", "manager", "photo_path", "owner_name", "owner_relation", 
                            "owner_phone", "lessee_phone", "ad_start_date", "ad_end_date", 
                            "lat", "lng", "status_cd", "re_ad_yn"
                        ]
                        for col in shop_cols:
                             if col not in insert_data:
                                 # 타입에 따른 기본값 설정 (예시)
                                 if col in ["curr_floor", "total_floor", "deposit", "monthly"]:
                                     insert_data[col] = 0
                                 elif col in ["area", "lat", "lng"]:
                                      insert_data[col] = 0.0
                                 elif col in ["approval_date", "ad_start_date", "ad_end_date"]:
                                      insert_data[col] = None
                                 else:
                                      insert_data[col] = ""
                                      
                # 3. 대상 테이블에 INSERT 전 None 값 처리 추가
                if target_table == 'mylist_shop': # mylist_shop 테이블에만 해당 컬럼 존재 가정
                    if insert_data.get("naver_property_no") is None:
                        insert_data["naver_property_no"] = ""
                    if insert_data.get("serve_property_no") is None:
                        insert_data["serve_property_no"] = ""
                    # 값이 NULL이거나 빈 문자열인 경우에만 기본값으로 대체
                    if "manage_fee" in insert_data and (insert_data["manage_fee"] is None or insert_data["manage_fee"] == ""):
                        insert_data["manage_fee"] = 0  # 또는 다른 적절한 기본값
                    if "premium" in insert_data and (insert_data["premium"] is None or insert_data["premium"] == ""):
                        insert_data["premium"] = 0  # 또는 다른 적절한 기본값
                # 원룸 테이블에도 관련 필드가 있으면 처리
                elif target_table == 'mylist_oneroom':
                    # 원룸 테이블에서는 manage_fee와 password(권리금) 필드가 있다면 null로 설정
                    if "manage_fee" in insert_data and (insert_data["manage_fee"] is None or insert_data["manage_fee"] == ""):
                        insert_data["manage_fee"] = 0  # 또는 다른 적절한 기본값
                    if "password" in insert_data and (insert_data["password"] is None or insert_data["password"] == ""):  # 원룸에서는 password가 권리금 역할
                        insert_data["password"] = 0  # 또는 다른 적절한 기본값

                cols = insert_data.keys()
                vals = list(insert_data.values()) # .values()는 뷰 객체이므로 리스트로 변환
                
                # 여기서는 모든 키가 대상 테이블에 존재한다고 가정
                cols_str = ",".join([f"`{c}`" for c in cols])
                placeholders = ",".join(["%s"] * len(vals))
                sql_ins = f"INSERT INTO `{target_table}` ({cols_str}) VALUES ({placeholders})"
                
                cursor.execute(sql_ins, tuple(vals))
                new_id = cursor.lastrowid
                inserted_list.append((sid, s_, new_id))
                logger.debug(f"Copied item from {s_}(ID:{sid}) to {target_table}(ID:{new_id}) for manager '{manager}'")

            except mysql.Error as db_err:
                errors.append(f"ID={sid}, 출처 '{s_}' 처리 중 DB 오류: {db_err}")
                conn.rollback() # 개별 항목 오류 시 롤백하고 계속 진행 (선택적)
            except Exception as ex2:
                errors.append(f"ID={sid}, 출처 '{s_}' 처리 중 예외 발생: {ex2}")
                conn.rollback()

        conn.commit() # 모든 항목 처리 후 최종 커밋
        logger.info(f"Copy to mylist completed for manager '{manager}'. Inserted: {len(inserted_list)}, Errors: {len(errors)}")
        return {
            "status": "ok",
            "inserted_list": inserted_list,
            "errors": errors
        }

    except mysql.Error as ex:
        logger.error(f"Copy to mylist main DB error: {ex}")
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {ex}")
    except Exception as ex:
        logger.error(f"Copy to mylist unexpected error: {ex}", exc_info=True)
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Server error: {ex}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# 상단 테이블용: 전체 mylist_shop 데이터 (manager, role 기반)
@router.get("/get_all_mylist_shop_data")
def get_all_mylist_shop_data(
    manager: str = Query("", description="매니저명"),
    role: str = Query("manager", description="admin 또는 manager")
):
    # 환경변수로 MySQL vs Supabase 선택
    use_supabase = os.environ.get("USE_SUPABASE_MYLIST_SHOP", "false").lower() == "true"
    
    # 디버그 로그 추가
    logger.info(f"get_all_mylist_shop_data API 호출 - USE_SUPABASE_MYLIST_SHOP: {use_supabase}")
    
    if use_supabase:
        logger.info("Supabase 경로로 실행")
        return get_all_mylist_shop_data_supabase(manager, role)
    else:
        logger.info("MySQL 경로로 실행")
        return get_all_mylist_shop_data_mysql(manager, role)

def get_all_mylist_shop_data_mysql(
    manager: str = "",
    role: str = "manager"
):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        sql = "SELECT * FROM mylist_shop"
        params = []
        
        if role.lower() != "admin":
            if not manager:
                return {"status": "ok", "data": []}
            sql += " WHERE manager = %s"
            params.append(manager)
            
        sql += " ORDER BY id ASC"
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
        logger.debug(f"Fetched {len(rows)} mylist_shop items for manager '{manager if role != 'admin' else '(Admin)'}'")
        return {"status": "ok", "data": rows}

    except mysql.Error as e:
        logger.error(f"Get all mylist_shop data DB error (manager: {manager}, role: {role}): {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        logger.error(f"Get all mylist_shop data unexpected error (manager: {manager}, role: {role}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# 하단 테이블용: 주소별 필터링된 mylist_shop 데이터
@router.post("/get_mylist_shop_data")
async def get_mylist_shop_data(request: Request):
    # 환경변수로 MySQL vs Supabase 선택
    use_supabase = os.environ.get("USE_SUPABASE_MYLIST_SHOP", "false").lower() == "true"
    
    # 디버그 로그 추가
    logger.info(f"get_mylist_shop_data POST API 호출 - USE_SUPABASE_MYLIST_SHOP: {use_supabase}")
    
    if use_supabase:
        logger.info("Supabase 경로로 실행")
        return await get_mylist_shop_data_supabase_post(request)
    else:
        logger.info("MySQL 경로로 실행")
        return await get_mylist_shop_data_mysql_post(request)

async def get_mylist_shop_data_mysql_post(request: Request):
    body = await request.json()
    address_list = body.get("addresses", [])
    if not address_list:
        return {"status": "ok", "data": []}
        
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        placeholders = ",".join(["%s"] * len(address_list))
        sql = f"SELECT * FROM mylist_shop WHERE CONCAT(dong, ' ', jibun) IN ({placeholders}) ORDER BY id ASC"
        cursor.execute(sql, tuple(address_list))
        rows = cursor.fetchall()
        logger.debug(f"Fetched {len(rows)} mylist_shop items for {len(address_list)} addresses")
        return {"status": "ok", "data": rows}

    except mysql.Error as e:
        logger.error(f"Get mylist_shop data DB error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        logger.error(f"Get mylist_shop data unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@router.get("/get_mylist_oneroom_data")
def get_mylist_oneroom_data(
    manager: str = Query("", description="매니저명"),
    role: str = Query("manager", description="admin 또는 manager")
):
    # 환경변수로 MySQL vs Supabase 선택
    use_supabase = os.environ.get("USE_SUPABASE_MYLIST_ONEROOM", "false").lower() == "true"
    
    # 디버그 로그 추가
    logger.info(f"get_mylist_oneroom_data API 호출 - USE_SUPABASE_MYLIST_ONEROOM: {use_supabase}")
    
    if use_supabase:
        logger.info("Supabase 경로로 실행")
        return get_mylist_oneroom_data_supabase(manager, role)
    else:
        logger.info("MySQL 경로로 실행")
        return get_mylist_oneroom_data_mysql(manager, role)

def get_mylist_oneroom_data_mysql(
    manager: str = "",
    role: str = "manager"
):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        sql = "SELECT * FROM mylist_oneroom"
        params = []
        
        if role.lower() != "admin":
            if not manager:
                 return {"status":"ok","data":[]}
            sql += " WHERE manager = %s"
            params.append(manager)
            
        sql += " ORDER BY id ASC"
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
        logger.debug(f"Fetched {len(rows)} mylist_oneroom items for manager '{manager if role != 'admin' else '(Admin)'}'")
        return {"status":"ok","data":rows}

    except mysql.Error as e:
        logger.error(f"Get mylist_oneroom data DB error (manager: {manager}, role: {role}): {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        logger.error(f"Get mylist_oneroom data unexpected error (manager: {manager}, role: {role}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# update_mylist_oneroom_items 와 update_mylist_shop_items 는 
# payload 구조가 복잡하고 역할(role) 기반 처리가 필요하므로 여기에 포함합니다.

@router.post("/update_mylist_oneroom_items")
def update_mylist_oneroom_items(payload: dict = Body(...)):
    manager = payload.get("manager", "")
    role = payload.get("role", "manager") # 역할 정보 추가
    if not manager and role != 'admin': # Admin이 아니면 manager 필수
        raise HTTPException(status_code=400, detail="manager 필드는 필수입니다.")

    added_list   = payload.get("added", [])
    deleted_list = payload.get("deleted", [])
    updated_list = payload.get("updated", [])

    conn = None
    cursor = None
    inserted_map = {}
    deleted_count = 0
    updated_count = 0

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # (A) added 처리 (manager 필드 사용)
        if added_list:
            sql_insert = """
            INSERT INTO mylist_oneroom (
              gu, dong, jibun, ho, curr_floor, total_floor, deposit, monthly, manage_fee,
              in_date, `password`, rooms, baths, `options`, owner_phone, building_usage,
              naver_property_no, serve_property_no, approval_date, memo, manager,
              photo_path, owner_name, owner_relation, ad_end_date, lat, lng,
              parking, area, status_cd
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """
            for row_ in added_list:
                temp_id = row_.get("temp_id")
                if temp_id is None: continue
                # ... (기존 값 추출 및 타입 변환 로직) ...
                gu_val=row_.get("gu","");dong=row_.get("dong","");jibun=row_.get("jibun","");ho=row_.get("ho","");
                mf=row_.get("manage_fee","");ind=row_.get("in_date","");pwd=row_.get("password","");rms=row_.get("rooms","");bth=row_.get("baths","");
                opts=row_.get("options","");oph=row_.get("owner_phone","");bus=row_.get("building_usage","");nav=row_.get("naver_property_no","");
                srv=row_.get("serve_property_no","");memo=row_.get("memo","");pp=row_.get("photo_path","");onm=row_.get("owner_name","");
                orel=row_.get("owner_relation","");pk=row_.get("parking","");scd=row_.get("status_cd","");
                cf=int(row_.get("curr_floor",0));tf=int(row_.get("total_floor",0));dep=int(row_.get("deposit",0));mon=int(row_.get("monthly",0));
                lat=float(row_.get("lat",0.0));lng=float(row_.get("lng",0.0));area=float(row_.get("area",0.0));
                adp=row_.get("approval_date","").strip();adp_d=adp if adp else None;
                ade=row_.get("ad_end_date","").strip();ade_d=ade if ade else None;
                
                vals = (
                    gu_val,dong,jibun,ho,cf,tf,dep,mon,mf,ind,pwd,rms,bth,opts,oph,bus,nav,srv,
                    adp_d,memo,manager,pp,onm,orel,ade_d,lat,lng,pk,area,scd
                )
                try:
                    cursor.execute(sql_insert, vals)
                    new_id = cursor.lastrowid
                    inserted_map[str(temp_id)] = new_id
                except mysql.Error as insert_err:
                     logger.error(f"Error inserting added mylist_oneroom (temp_id={temp_id}): {insert_err}")
                     conn.rollback()
                     raise HTTPException(status_code=500, detail=f"추가 중 오류: {insert_err}")

        # (B) deleted 처리 (역할 기반)
        if deleted_list:
            real_ids = [d for d in deleted_list if isinstance(d, int) and d > 0]
            if real_ids:
                placeholders = ",".join(["%s"] * len(real_ids))
                sql_del = f"DELETE FROM mylist_oneroom WHERE id IN ({placeholders})"
                params = list(real_ids)
                if role != 'admin':
                    sql_del += " AND manager = %s"
                    params.append(manager)
                try:
                    cursor.execute(sql_del, tuple(params))
                    deleted_count = cursor.rowcount
                except mysql.Error as del_err:
                     logger.error(f"Error deleting mylist_oneroom items (role={role}, manager={manager}): {del_err}")
                     conn.rollback()
                     raise HTTPException(status_code=500, detail=f"삭제 중 오류: {del_err}")

        # (C) updated 처리 (역할 기반)
        if updated_list:
            updatable_cols = [
                "gu","dong","jibun","ho","curr_floor","total_floor","deposit","monthly","manage_fee",
                "in_date","password","rooms","baths","options","owner_phone","building_usage",
                "naver_property_no","serve_property_no","approval_date","memo","photo_path",
                "owner_name","owner_relation","ad_end_date","lat","lng","parking","area","status_cd"
            ]
            for upd in updated_list:
                row_id = upd.get("id")
                if not row_id or not isinstance(row_id, int) or row_id <= 0: continue
                set_clauses = []
                set_values  = []
                for col in updatable_cols:
                    if col in upd:
                        val = upd[col]
                        final_val = str(val).strip() if col in ["approval_date", "ad_end_date"] else val
                        set_clauses.append(f"`{col}`=%s")
                        set_values.append(None if final_val == '' and col in ["approval_date", "ad_end_date"] else final_val)
                if not set_clauses: continue

                sql_update = f"UPDATE mylist_oneroom SET {','.join(set_clauses)} WHERE id=%s"
                params = list(set_values) + [row_id]
                if role != 'admin':
                    sql_update += " AND manager = %s"
                    params.append(manager)
                
                try:
                    cursor.execute(sql_update, tuple(params))
                    if cursor.rowcount > 0: updated_count += 1
                except mysql.Error as upd_err:
                     logger.error(f"Error updating mylist_oneroom item ID={row_id} (role={role}, manager={manager}): {upd_err}")
                     conn.rollback()
                     raise HTTPException(status_code=500, detail=f"수정 중 오류: {upd_err}")

        conn.commit()
        logger.info(f"Updated mylist_oneroom: Inserted={len(inserted_map)}, Deleted={deleted_count}, Updated={updated_count} by Manager='{manager}' (Role: {role})")
        return {
            "status": "ok",
            "inserted_map": inserted_map,
            "deleted_count": deleted_count,
            "updated_count": updated_count
        }

    except Exception as ex:
        logger.error(f"Update mylist_oneroom items unexpected error: {ex}", exc_info=True)
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=str(ex))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@router.post("/update_mylist_shop_items")
def update_mylist_shop_items(payload: dict = Body(...)):
    manager    = payload.get("manager","")
    role      = payload.get("role", "manager")
    added_list = payload.get("added_list", [])
    deleted_list = payload.get("deleted_list", [])
    updated_list = payload.get("updated_list", [])

    if not manager and role != 'admin':
        logger.error(f"Update mylist_shop failed: manager field is required for role '{role}'. Payload: {payload}")
        raise HTTPException(status_code=400, detail=f"manager 필드는 필수입니다 (role: {role})")

    conn = None
    cursor = None
    inserted_map = {}
    deleted_count = 0
    updated_count = 0
    operation_successful = True

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        logger.debug(f"Start update_mylist_shop - Manager: '{manager}', Role: '{role}', Added: {len(added_list)}, Deleted: {len(deleted_list)}, Updated: {len(updated_list)}")

        # (A) added 처리
        if added_list:
            sql_insert = """
            INSERT INTO mylist_shop (
              gu, dong, jibun, ho, curr_floor, total_floor, deposit, monthly, manage_fee,
              premium, current_use, area, rooms, baths, building_usage, parking,
              naver_property_no, serve_property_no, approval_date, memo, manager,
              photo_path, owner_name, owner_relation, owner_phone, lessee_phone,
              ad_end_date, lat, lng, status_cd, re_ad_yn
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """
            for row_ in added_list:
                temp_id = row_.get("temp_id", -99)
                gu=row_.get("gu","");dn=row_.get("dong","");jb=row_.get("jibun","");ho=row_.get("ho","");
                cf=int(row_.get("curr_floor",0));tf=int(row_.get("total_floor",0));dp=int(row_.get("deposit",0));mn=int(row_.get("monthly",0));
                mf=row_.get("manage_fee","");pm=row_.get("premium","");cu=row_.get("current_use","");ar=float(row_.get("area",0.0));
                rms=row_.get("rooms","");bts=row_.get("baths","");bu=row_.get("building_usage","");pk=row_.get("parking","");
                nav=row_.get("naver_property_no","");srv=row_.get("serve_property_no","");mm=row_.get("memo","");
                pp=row_.get("photo_path","");onm=row_.get("owner_name","");orl=row_.get("owner_relation","");oph=row_.get("owner_phone","");
                lph=row_.get("lessee_phone","");lat=float(row_.get("lat",0.0));lng=float(row_.get("lng",0.0));
                scd=row_.get("status_cd","");ryn=row_.get("re_ad_yn","");
                apd_s=row_.get("approval_date","").strip();apd=apd_s if apd_s else None;
                ade_s=row_.get("ad_end_date","").strip();ade=ade_s if ade_s else None;
                
                vals = (
                    gu,dn,jb,ho,cf,tf,dp,mn,mf,pm,cu,ar,rms,bts,bu,pk,nav,srv,apd,mm,manager,pp,
                    onm,orl,oph,lph,ade,lat,lng,scd,ryn
                )
                try:
                    cursor.execute(sql_insert, vals)
                    new_id = cursor.lastrowid
                    inserted_map[str(temp_id)] = new_id
                    logger.debug(f"Inserted mylist_shop temp_id={temp_id} as new_id={new_id}")
                except mysql.Error as insert_err:
                     logger.error(f"Error inserting added mylist_shop (temp_id={temp_id}): {insert_err}")
                     operation_successful = False
                     conn.rollback()
                     break
                except Exception as insert_ex:
                    logger.error(f"Unexpected error inserting added mylist_shop (temp_id={temp_id}): {insert_ex}", exc_info=True)
                    operation_successful = False
                    conn.rollback()
                    break

        # (B) deleted 처리 (역할 기반)
        if deleted_list and operation_successful:
            real_ids = [r for r in deleted_list if isinstance(r, int) and r > 0]
            if real_ids:
                placeholders = ",".join(["%s"] * len(real_ids))
                sql_del = f"DELETE FROM mylist_shop WHERE id IN ({placeholders})"
                params = list(real_ids)
                if role != 'admin':
                    sql_del += " AND manager = %s"
                    params.append(manager)
                    logger.debug(f"Preparing DELETE query (manager check): {sql_del}, Params: {params}")
                else:
                    logger.debug(f"Preparing DELETE query (admin): {sql_del}, Params: {params}")

                try:
                    logger.debug(f"Executing DELETE query...")
                    cursor.execute(sql_del, tuple(params))
                    deleted_count = cursor.rowcount
                    logger.info(f"Executed DELETE on mylist_shop (role={role}, manager={manager or '(Admin)'}) for IDs: {real_ids}. Affected rows: {deleted_count}")
                except mysql.Error as del_err:
                     logger.error(f"Error deleting mylist_shop items (role={role}, manager={manager}): {del_err}")
                     operation_successful = False
                     conn.rollback()
                except Exception as del_ex:
                    logger.error(f"Unexpected error deleting mylist_shop items (role={role}, manager={manager}): {del_ex}", exc_info=True)
                    operation_successful = False
                    conn.rollback()

        # (C) updated 처리 (역할 기반)
        if updated_list and operation_successful:
            updatable_cols = [
                "gu", "dong", "jibun", "ho", "curr_floor", "total_floor", "deposit", "monthly", "manage_fee",
                "premium", "current_use", "area", "rooms", "baths", "building_usage", "parking",
                "naver_property_no", "serve_property_no", "approval_date", "memo", "photo_path",
                "owner_name", "owner_relation", "owner_phone", "lessee_phone", "ad_end_date",
                "lat", "lng", "status_cd", "re_ad_yn", "manager"
            ]
            for row_ in updated_list:
                rid = row_.get("id")
                if not rid or not isinstance(rid, int) or rid <= 0: continue
                set_clauses = []
                set_vals    = []
                for c_ in updatable_cols:
                    if c_ in row_:
                        val = row_[c_]
                        final_val = str(val).strip() if c_ in ["approval_date", "ad_end_date"] else val
                        set_clauses.append(f"`{c_}`=%s")
                        set_vals.append(None if final_val == '' and c_ in ["approval_date", "ad_end_date"] else final_val)
                if not set_clauses: continue

                sql_up = f"UPDATE mylist_shop SET {','.join(set_clauses)} WHERE id=%s"
                params = list(set_vals) + [rid]
                if role != 'admin':
                    sql_up += " AND manager = %s"
                    params.append(manager)
                
                try:
                    cursor.execute(sql_up, tuple(params))
                    if cursor.rowcount > 0:
                        updated_count += 1
                        logger.debug(f"Updated mylist_shop ID={rid} (role={role}, manager={manager or '(Admin)'}). Affected: {cursor.rowcount}")
                except mysql.Error as upd_err:
                     logger.error(f"Error updating mylist_shop item ID={rid} (role={role}, manager={manager}): {upd_err}")
                     operation_successful = False
                     conn.rollback()
                     break
                except Exception as upd_ex:
                    logger.error(f"Unexpected error updating mylist_shop item ID={rid} (role={role}, manager={manager}): {upd_ex}", exc_info=True)
                    operation_successful = False
                    conn.rollback()
                    break

        # --- 최종 커밋 또는 롤백 ---
        if operation_successful:
            logger.info(f"All operations successful for Manager='{manager}'. Attempting commit.")
            conn.commit()
            logger.info(f"Finished update_mylist_shop (Success): Inserted={len(inserted_map)}, Deleted={deleted_count}, Updated={updated_count} by Manager='{manager}' (Role: {role})")
            return {
                "status": "ok",
                "inserted_map": inserted_map,
                "deleted_count": deleted_count,
                "updated_count": updated_count
            }
        else:
            logger.warning(f"One or more operations failed for Manager='{manager}'. Rolling back potentially partial changes.")
            logger.info(f"Finished update_mylist_shop (Failed): Rolled back. Inserted(pre-rollback)={len(inserted_map)}, Deleted=0, Updated=0 by Manager='{manager}' (Role: {role})")
            return {
                "status": "error",
                "message": "One or more database operations failed. See server logs for details.",
                "inserted_map": inserted_map,
                "deleted_count": 0,
                "updated_count": 0
            }

    except mysql.Error as db_err:
        logger.error(f"Update mylist_shop items DB error outside operation blocks: {db_err}", exc_info=True)
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {db_err}")
    except Exception as ex:
        logger.error(f"Update mylist_shop items unexpected error: {ex}", exc_info=True)
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {ex}")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected():
            logger.debug("Closing DB connection.")
            conn.close() 

# ==== SUPABASE 버전 함수들 ====

def get_mylist_oneroom_data_supabase(manager: str = "", role: str = "manager"):
    """Supabase 버전: 원룸 마이리스트 데이터 조회"""
    try:
        supabase = get_supabase_client()
        
        # 기본 쿼리
        query = supabase.table('mylist_oneroom').select('*')
        
        # 권한 확인: admin이 아니면 manager 필터 적용
        if role.lower() != "admin":
            if not manager:
                logger.info("비 admin 사용자이지만 manager가 없어 빈 데이터 반환")
                return {"status": "ok", "data": []}
            query = query.eq('manager', manager)
        
        # 정렬: ID 순
        query = query.order('id', desc=False)
        
        # 쿼리 실행
        result = query.execute()
        
        logger.debug(f"Supabase에서 {len(result.data)}개 mylist_oneroom 항목 조회 완료 (manager: '{manager if role != 'admin' else '(Admin)'}')")
        return {"status": "ok", "data": result.data}
        
    except Exception as e:
        logger.error(f"Supabase mylist_oneroom 데이터 조회 오류 (manager: {manager}, role: {role}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Supabase error: {e}")

def get_mylist_shop_data_supabase(addresses: list = None):
    """Supabase 버전: 상가 마이리스트 데이터 조회 (주소별 필터링)"""
    try:
        supabase = get_supabase_client()
        
        if not addresses:
            return {"status": "ok", "data": []}
        
        # 주소별 필터링을 위한 조건 생성
        query = supabase.table('mylist_shop').select('*')
        
        # CONCAT(dong, ' ', jibun) IN (addresses) 와 동일한 필터링
        # Supabase에서는 여러 조건을 OR로 연결
        address_conditions = []
        for addr in addresses:
            # "동 지번" 형태로 검색
            query = query.or_(f"dong.eq.{addr.split()[0]},jibun.eq.{' '.join(addr.split()[1:])}")
        
        # 정렬: ID 순
        query = query.order('id', desc=False)
        
        # 쿼리 실행
        result = query.execute()
        
        logger.debug(f"Supabase에서 {len(result.data)}개 mylist_shop 항목 조회 완료 ({len(addresses)}개 주소)")
        return {"status": "ok", "data": result.data}
        
    except Exception as e:
        logger.error(f"Supabase mylist_shop 데이터 조회 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Supabase error: {e}")

def get_all_mylist_shop_data_supabase(manager: str = "", role: str = "manager"):
    """Supabase 버전: 전체 상가 마이리스트 데이터 조회"""
    try:
        supabase = get_supabase_client()
        
        # 기본 쿼리
        query = supabase.table('mylist_shop').select('*')
        
        # 권한 확인: admin이 아니면 manager 필터 적용
        if role.lower() != "admin":
            if not manager:
                logger.info("비 admin 사용자이지만 manager가 없어 빈 데이터 반환")
                return {"status": "ok", "data": []}
            query = query.eq('manager', manager)
        
        # 정렬: ID 순
        query = query.order('id', desc=False)
        
        # 쿼리 실행
        result = query.execute()
        
        logger.debug(f"Supabase에서 {len(result.data)}개 mylist_shop 항목 조회 완료 (manager: '{manager if role != 'admin' else '(Admin)'}')")
        return {"status": "ok", "data": result.data}
        
    except Exception as e:
        logger.error(f"Supabase 전체 mylist_shop 데이터 조회 오류 (manager: {manager}, role: {role}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Supabase error: {e}")

async def get_mylist_shop_data_supabase_post(request: Request):
    """Supabase 버전: POST 방식 상가 마이리스트 데이터 조회 (주소별 필터링)"""
    try:
        body = await request.json()
        address_list = body.get("addresses", [])
        
        if not address_list:
            return {"status": "ok", "data": []}
        
        supabase = get_supabase_client()
        
        # 주소별 필터링 - 동과 지번 조합으로 검색
        all_results = []
        
        for addr in address_list:
            try:
                # "동 지번" 형태를 분리
                parts = addr.split(' ', 1)
                if len(parts) >= 2:
                    dong = parts[0]
                    jibun = parts[1]
                    
                    # 동과 지번이 모두 일치하는 것을 찾기
                    query = supabase.table('mylist_shop').select('*').eq('dong', dong).eq('jibun', jibun)
                    result = query.execute()
                    all_results.extend(result.data)
                else:
                    # 동만 있는 경우
                    query = supabase.table('mylist_shop').select('*').eq('dong', addr)
                    result = query.execute()
                    all_results.extend(result.data)
                    
            except Exception as addr_e:
                logger.warning(f"주소 '{addr}' 처리 중 오류: {addr_e}")
                continue
        
        # ID로 정렬하여 중복 제거
        unique_results = []
        seen_ids = set()
        for item in all_results:
            if item['id'] not in seen_ids:
                unique_results.append(item)
                seen_ids.add(item['id'])
        
        # ID 순으로 정렬
        unique_results.sort(key=lambda x: x['id'])
        
        logger.debug(f"Supabase에서 {len(unique_results)}개 mylist_shop 항목 조회 완료 ({len(address_list)}개 주소)")
        return {"status": "ok", "data": unique_results}
        
    except Exception as e:
        logger.error(f"Supabase POST mylist_shop 데이터 조회 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Supabase error: {e}") 