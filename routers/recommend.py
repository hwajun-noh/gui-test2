from fastapi import APIRouter, HTTPException, Request, Body, Query
import mysql.connector as mysql
from datetime import datetime, date
from settings import get_db_connection, logger
# models.py 등 다른 모듈 import 필요시 추가

router = APIRouter()

@router.post("/get_recommend_data")
async def get_recommend_data(request: Request):
    body = await request.json()
    address_list = body.get("addresses", [])
    if not address_list:
        return {"status": "ok", "data": []}
        
    logger.info(f"Fetching recommend_data for {len(address_list)} addresses")
    conn = None 
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        placeholders = ",".join(["%s"] * len(address_list))
        sql = f"SELECT * FROM recommend_data WHERE CONCAT(dong, ' ', jibun) IN ({placeholders}) ORDER BY recommend_date DESC, id DESC"
        logger.debug(f"Executing SQL: {sql}")
        cursor.execute(sql, tuple(address_list))
        rows = cursor.fetchall()
        logger.info(f"Fetched {len(rows)} rows from recommend_data.") 

        # 날짜/시간 객체를 ISO 형식 문자열로 변환
        for row in rows:
            for key, value in row.items():
                if isinstance(value, (datetime, date)) and not isinstance(value, str):
                    try:
                        row[key] = value.isoformat()
                    except Exception as fmt_err:
                        logger.warning(f"Could not format date/time field '{key}' with value '{value}': {fmt_err}. Using str().")
                        row[key] = str(value) 

        logger.debug(f"Returning {len(rows)} recommend_data rows.") 
        return {"status": "ok", "data": rows}

    except mysql.Error as e:
        logger.error(f"Get recommend_data DB Error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        logger.error(f"Get recommend_data General Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@router.post("/register_recommend_data")
def register_recommend_property(data: dict = Body(...)):
    source_id = data.get("source_id")
    source_table = data.get("source_table") # "naver_shop_check_confirm" 또는 "serve_shop_data"
    dialog_matching_biz = data.get("matching_biz", "")
    dialog_manager = data.get("manager", "")
    dialog_check_memo = data.get("check_memo", "")

    if not source_id or not source_table:
        raise HTTPException(status_code=400, detail="source_id와 source_table은 필수입니다.")
    if source_table not in ["naver_shop_check_confirm", "serve_shop_data", "mylist_shop", "naver_shop", "recommend_data"]:
         raise HTTPException(status_code=400, detail="유효하지 않은 source_table입니다.")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. 원본 테이블에서 데이터 조회
        sql_select = f"SELECT * FROM `{source_table}` WHERE id = %s"
        cursor.execute(sql_select, (source_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="원본 테이블에서 해당 ID의 데이터를 찾을 수 없습니다.")

        # 2. recommend_data에 맞게 필드 매핑 및 준비
        recommend_data = {}
        recommend_data['property_id'] = row.get("id") # 원본 ID
        recommend_data['gu'] = row.get("gu", "")
        recommend_data['dong'] = row.get("dong", "")
        recommend_data['jibun'] = row.get("jibun", "")
        recommend_data['ho'] = row.get("ho", "")
        recommend_data['curr_floor'] = row.get("curr_floor", 0)
        recommend_data['total_floor'] = row.get("total_floor", 0)
        recommend_data['deposit'] = row.get("deposit", 0)
        recommend_data['monthly'] = row.get("monthly", 0)
        recommend_data['manage_fee'] = row.get("manage_fee", 0.0)
        recommend_data['premium'] = str(row.get("premium", ""))[:100]
        recommend_data['current_use'] = str(row.get("current_use", ""))[:100]
        recommend_data['area'] = row.get("area", 0.0)
        recommend_data['rooms'] = row.get("rooms", "")
        recommend_data['baths'] = row.get("baths", "")
        recommend_data['building_usage'] = str(row.get("building_usage", ""))[:50]
        recommend_data['naver_property_no'] = str(row.get("naver_property_no", ""))[:10]
        recommend_data['serve_property_no'] = str(row.get("serve_property_no", ""))[:10]
        recommend_data['approval_date'] = row.get("approval_date") # 날짜 타입 유지 또는 None
        recommend_data['memo'] = row.get("memo", "") # 원본 메모
        recommend_data['photo_path'] = str(row.get("photo_path", ""))[:255]
        recommend_data['owner_name'] = str(row.get("owner_name", ""))[:50]
        recommend_data['owner_relation'] = str(row.get("owner_relation", ""))[:50]
        recommend_data['owner_phone'] = str(row.get("owner_phone", ""))[:50]
        recommend_data['lessee_phone'] = str(row.get("lessee_phone", ""))[:50]
        recommend_data['ad_start_date'] = row.get("ad_start_date") # 날짜 타입 유지 또는 None
        recommend_data['ad_end_date'] = row.get("ad_end_date") # 날짜 타입 유지 또는 None
        recommend_data['lat'] = row.get("lat", 0.0)
        recommend_data['lng'] = row.get("lng", 0.0)
        recommend_data['parking'] = row.get("parking", "")
        recommend_data['status_cd'] = row.get("status_cd","") # status_cd 추가
        
        # 대화상자에서 받은 값으로 덮어쓰기
        recommend_data['manager'] = dialog_manager
        recommend_data['matching_biz'] = dialog_matching_biz
        recommend_data['check_memo'] = dialog_check_memo # check_memo 필드 사용
        recommend_data['recommend_date'] = datetime.now().date() # 추천일은 오늘 날짜
        
        # 출처(source) 필드 설정
        if source_table == "naver_shop_check_confirm":
            recommend_data['source'] = "확인"
        elif source_table == "serve_shop_data":
            recommend_data['source'] = "상가"
        elif source_table == "mylist_shop":
            recommend_data['source'] = "마이리스트(상가)"
        elif source_table == "naver_shop":
             recommend_data['source'] = "네이버"
        elif source_table == "recommend_data":
             recommend_data['source'] = "추천"
            
        # Null 허용 컬럼 처리 (DB 스키마에 따라 필요시 추가/수정)
        for key in ['approval_date', 'ad_start_date', 'ad_end_date']:
             if recommend_data[key] == '':
                 recommend_data[key] = None

        # 3. recommend_data 테이블에 INSERT
        cols = recommend_data.keys()
        vals = recommend_data.values()
        sql_insert = f"""
        INSERT INTO recommend_data ({ ",".join([f'`{c}`' for c in cols]) }) 
        VALUES ({ ",".join(['%s']*len(vals)) })
        """
        
        cursor.execute(sql_insert, tuple(vals))
        conn.commit()
        insert_id = cursor.lastrowid
        logger.info(f"Registered recommend property. Source: {source_table}(ID:{source_id}) -> recommend_data (ID:{insert_id})")
        return {"status": "ok", "message": "추천매물 등록 완료", "insert_id": insert_id}

    except mysql.Error as e:
        logger.error(f"Register recommend property DB error: {e}")
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except HTTPException as http_ex:
         raise http_ex
    except Exception as e:
        logger.error(f"Register recommend property unexpected error: {e}", exc_info=True)
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Server error: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@router.get("/get_addresses_by_biz_manager")
def get_addresses_by_biz_manager(
    biz: str,
    manager: str,
    role: str = Query("manager", description="admin 또는 manager")
):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql = """
            SELECT DISTINCT CONCAT(dong, ' ', jibun) AS addr
            FROM recommend_data 
        """
        params = [biz]
        where_clauses = ["matching_biz = %s"]
        
        if role.lower() != "admin":
            where_clauses.append("manager = %s")
            params.append(manager)
            
        sql += " WHERE " + " AND ".join(where_clauses)
        
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
        addresses = [r[0].strip() for r in rows if r and r[0]] # Non-empty check
        logger.debug(f"Fetched {len(addresses)} addresses for biz '{biz}', manager '{manager}' (role: {role})")
        return {
            "status": "ok",
            "addresses": addresses,
            "count": len(addresses),
            "role_used": role
        }
    except mysql.Error as e:
        logger.error(f"Get addresses by biz/manager DB error (biz: {biz}, manager: {manager}, role: {role}): {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        logger.error(f"Get addresses by biz/manager unexpected error (biz: {biz}, manager: {manager}, role: {role}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close() 