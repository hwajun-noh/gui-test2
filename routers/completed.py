from fastapi import APIRouter, HTTPException, Query, Body, Request
import mysql.connector as mysql
from settings import get_db_connection, logger
from models import CompletedDealsPayload # models.py에서 관련 모델 임포트
from datetime import date

router = APIRouter()

@router.get("/get_completed_deals")
async def get_completed_deals_get():
    """GET 방식으로 모든 계약완료 데이터 조회 (405 에러 해결)"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 모든 계약완료 데이터 조회
        sql = """
        SELECT
          id, gu, dong, jibun, ho, curr_floor, total_floor, deposit, monthly,
          manage_fee, premium, current_use, area, rooms, baths, building_usage,
          parking, naver_property_no, serve_property_no, approval_date, memo,
          manager, photo_path, owner_name, owner_relation, owner_phone,
          lessee_phone, ad_start_date, ad_end_date, lat, lng, status_cd
        FROM completed_deals
        ORDER BY ad_end_date DESC, id DESC
        """
        cursor.execute(sql)
        rows = cursor.fetchall()
        logger.debug(f"GET: Fetched {len(rows)} completed deals.")
        return {"status": "ok", "data": rows}

    except mysql.Error as e:
        logger.error(f"GET completed deals DB error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        logger.error(f"GET completed deals error: {e}")
        raise HTTPException(status_code=500, detail=f"Server error: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# completed_deals 테이블의 실제 컬럼 목록 (get_completed_deals 쿼리 참고)
# 'id'는 자동 증가이므로 INSERT 시 명시적으로 포함하지 않음.
COMPLETED_DEALS_COLUMNS = {
    "gu", "dong", "jibun", "ho", "curr_floor", "total_floor", "deposit", "monthly",
    "manage_fee", "premium", "current_use", "area", "rooms", "baths", "building_usage",
    "parking", "naver_property_no", "serve_property_no", "approval_date", "memo",
    "manager", "photo_path", "owner_name", "owner_relation", "owner_phone",
    "lessee_phone", "ad_start_date", "ad_end_date", "lat", "lng", "status_cd"
}

@router.post("/get_completed_deals")
async def get_completed_deals(request: Request):
    body = await request.json()
    address_list = body.get("addresses", [])
    if not address_list:
        return {"status": "ok", "data": []}
        
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        placeholders = ",".join(["%s"] * len(address_list))
        # 컬럼 목록 명시적 지정 및 정렬 순서 확인
        sql = f"""
        SELECT
          id, gu, dong, jibun, ho, curr_floor, total_floor, deposit, monthly,
          manage_fee, premium, current_use, area, rooms, baths, building_usage,
          parking, naver_property_no, serve_property_no, approval_date, memo,
          manager, photo_path, owner_name, owner_relation, owner_phone,
          lessee_phone, ad_start_date, ad_end_date, lat, lng, status_cd
        FROM completed_deals
        WHERE CONCAT(dong, ' ', jibun) IN ({placeholders})
        ORDER BY ad_end_date DESC, id DESC # 계약 완료일(ad_end_date) 기준 내림차순 정렬
        """
        cursor.execute(sql, tuple(address_list))
        rows = cursor.fetchall()
        logger.debug(f"Fetched {len(rows)} completed deals.")
        return {"status": "ok", "data": rows}

    except mysql.Error as e:
        logger.error(f"Get completed deals DB error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        logger.error(f"Get completed deals unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@router.post("/add_completed_deals")
def add_completed_deals(payload: CompletedDealsPayload):
    items = payload.items
    manager = payload.manager
    if not items:
        raise HTTPException(status_code=400, detail="items가 비어있습니다.")

    source_table_map = {
        "상가": "serve_shop_data",
        "원룸": "serve_oneroom_data",
        "확인": "naver_shop_check_confirm",
        "마이리스트(상가)": "mylist_shop", # 마이리스트(원룸)도 필요하다면 추가
        "네이버": "naver_shop"
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
            src = obj.source.strip()
            st_ = obj.status.strip() # "계약완료"/"부재중"/"광고X"
            memo_ = obj.memo or ""

            if src not in source_table_map:
                errors.append(f"ID={sid} => 알 수 없는 source='{src}'")
                continue
            
            table_name = source_table_map[src]

            try:
                # 1. 원본 데이터 조회
                sql_sel = f"SELECT * FROM `{table_name}` WHERE id=%s"
                cursor.execute(sql_sel, (sid,))
                row = cursor.fetchone()
                if not row:
                    errors.append(f"ID={sid}, source='{src}' 원본 없음")
                    continue

                # 2. completed_deals에 맞게 데이터 준비
                completed_data = dict(row) # 원본 복사
                completed_data.pop('id', None) # 원본 id 제거
                completed_data['manager'] = manager
                completed_data['memo'] = memo_
                completed_data['status_cd'] = st_
                completed_data['ad_end_date'] = date.today() # 완료일은 오늘
                
                # Null 값 및 기본값 처리 (필요시 추가/수정)
                numeric_cols = ["curr_floor","total_floor","deposit","monthly","lat","lng","area"]
                string_cols = [
                    "gu","dong","jibun","ho","manage_fee","premium","current_use",
                    "rooms","baths","building_usage","parking","naver_property_no",
                    "serve_property_no","photo_path","owner_name","owner_relation",
                    "owner_phone","lessee_phone","memo","manager","status_cd"
                ]
                date_cols = ["approval_date","ad_start_date"]
                
                for col in numeric_cols:
                    if completed_data.get(col) is None: completed_data[col] = 0
                for col in string_cols:
                    if completed_data.get(col) is None: completed_data[col] = ""
                for col in date_cols:
                     if completed_data.get(col) == '': completed_data[col] = None
                     # date/datetime 객체가 아닐 경우 변환 시도 (필요시)
                     # elif isinstance(completed_data.get(col), str):
                     #     try: completed_data[col] = datetime.strptime(completed_data[col].split(' ')[0], '%Y-%m-%d').date()
                     #     except: completed_data[col] = None
                
                # completed_deals 테이블에 존재하는 컬럼과 값만 필터링
                cols_to_insert = []
                vals_to_insert = []
                for col, val in completed_data.items():
                    # COMPLETED_DEALS_COLUMNS 세트에 있는 컬럼만 추가
                    if col in COMPLETED_DEALS_COLUMNS:
                        cols_to_insert.append(col)
                        vals_to_insert.append(val)

                if not cols_to_insert:
                     errors.append(f"ID={sid}, source='{src}' 처리 중 삽입할 유효 데이터 없음")
                     logger.warning(f"No valid columns to insert for ID={sid}, source='{src}'. Original data keys: {list(completed_data.keys())}")
                     continue # 다음 아이템으로

                # 필터링된 컬럼과 값으로 INSERT 문 생성
                cols_str = ",".join([f"`{c}`" for c in cols_to_insert])
                placeholders = ",".join(["%s"] * len(vals_to_insert))
                insert_sql = f"INSERT INTO completed_deals ({cols_str}) VALUES ({placeholders})"
                logger.debug(f"Executing INSERT for ID={sid}, source='{src}': {insert_sql} with {len(vals_to_insert)} values.") # 로그 추가

                cursor.execute(insert_sql, tuple(vals_to_insert)) # 필터링된 데이터로 실행

                new_id = cursor.lastrowid
                inserted_list.append((sid, src, new_id))
                logger.debug(f"Added completed deal from {src}(ID:{sid}) -> completed_deals(ID:{new_id}). Status: '{st_}', Manager: '{manager}'")

            except mysql.Error as db_err:
                errors.append(f"ID={sid}, source='{src}' 처리 중 DB 오류: {db_err}")
                logger.error(f"DB Error during processing ID={sid}, source='{src}': {db_err}", exc_info=True) # exc_info 추가
            except Exception as ex2:
                errors.append(f"ID={sid}, source='{src}' 처리 중 예외 발생: {ex2}")
                logger.error(f"Exception during processing ID={sid}, source='{src}': {ex2}", exc_info=True) # exc_info 추가

        # 모든 아이템 처리 후 에러가 있었는지 확인하고 최종 commit 또는 rollback 결정 가능
        if errors:
             logger.warning(f"Add completed deals finished with errors. Processed: {len(items)}, Inserted: {len(inserted_list)}, Errors: {len(errors)}. Errors: {errors}")
             # 필요하다면 여기서 conn.rollback() 호출하여 전체 트랜잭션 취소 가능
             conn.commit() # 일단 커밋하고 에러는 반환 (기존 로직 유지)
        else:
             conn.commit()
             logger.info(f"Add completed deals finished successfully. Processed: {len(items)}, Inserted: {len(inserted_list)}")

        return {
            "status": "ok",
            "inserted_list": inserted_list,
            "errors": errors # 에러 목록 반환
        }

    except mysql.Error as ex:
        logger.error(f"Add completed deals main DB error: {ex}", exc_info=True) # exc_info 추가
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {ex}")
    except Exception as ex:
        logger.error(f"Add completed deals unexpected error: {ex}", exc_info=True)
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Server error: {ex}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close() 