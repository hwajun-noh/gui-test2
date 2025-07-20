from fastapi import APIRouter, HTTPException, Request, Query
import json
import mysql.connector as mysql
from settings import get_db_connection, logger # settings.py에서 임포트
# models.py가 필요하면 임포트 (현재 이 파일의 엔드포인트는 사용하지 않음)

router = APIRouter()

@router.get("/get_customer_data")
def get_customer_data(
    manager: str,
    role: str = Query("manager", description="admin 또는 manager") # Query로 변경
):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        
        if role.lower() == "admin":
            sql = """
            SELECT
              id, manager,
              gu, dong, rectangles,
              deposit_min, deposit_max,
              monthly_min, monthly_max,
              area_min, area_max,
              floor_min, floor_max,
              is_top_floor,
              premium, biz_type, contact,
              real_deposit_monthly, last_contact_date,
              memo_json
            FROM `customer`
            ORDER BY id ASC
            """
            cur.execute(sql)
        else:
            sql = """
            SELECT
            id,
            manager,

            gu,
            dong,
            rectangles,  -- JSON

            deposit_min,
            deposit_max,
            monthly_min,
            monthly_max,
            area_min,
            area_max,
            floor_min,
            floor_max,
            is_top_floor,
            premium,
            biz_type,
            contact,
            real_deposit_monthly,
            last_contact_date,
            memo_json
            FROM `customer`
            WHERE manager=%s
            ORDER BY id ASC
            """
            cur.execute(sql, (manager,))
        rows = cur.fetchall()
        
        # 변환 로직 (기존과 동일)
        data = []
        for r in rows:
            gu_list = []
            if r["gu"]:
                gu_list = [x.strip() for x in r["gu"].split(",") if x.strip()]

            dong_list = []
            if r["dong"]:
                dong_list = [x.strip() for x in r["dong"].split(",") if x.strip()]

            rects_list = []
            if r["rectangles"]:
                try:
                    rects_list = json.loads(r["rectangles"])
                except:
                    rects_list = []

            region_obj = {
                "gu_list": gu_list,
                "dong_list": dong_list,
                "rectangles": rects_list
            }
            region_json_str = json.dumps(region_obj, ensure_ascii=False)

            if r["deposit_min"] < r["deposit_max"]:
                deposit_str = f"{r['deposit_min']}~{r['deposit_max']}"
            else:
                deposit_str = str(r["deposit_min"])

            if r["monthly_min"] < r["monthly_max"]:
                rent_str = f"{r['monthly_min']}~{r['monthly_max']}"
            else:
                rent_str = str(r["monthly_min"])

            if r["area_min"] < r["area_max"]:
                pyeong_str = f"{int(r['area_min'])}~{int(r['area_max'])}"
            else:
                pyeong_str = str(int(r["area_min"]))
            if r.get("is_top_floor", 0) == 1:
                floor_str = "탑층"
            else:
                if r["floor_min"] < 0 and r["floor_max"] < 0:
                    floor_str = "지하층"
                elif r["floor_min"] >= 2 and r["floor_max"] >= 999:
                    floor_str = "2층이상"
                elif r["floor_min"] != r["floor_max"]:
                    floor_str = f"{r['floor_min']}층~{r['floor_max']}층"
                else:
                    floor_str = f"{r['floor_min']}층"

            premium_str  = r["premium"] or ""
            biz_type_str = r["biz_type"] or ""
            contact_str  = r["contact"] or ""
            real_dep_mon = r["real_deposit_monthly"] or ""
            last_contact = r["last_contact_date"] or ""
            memo_str     = r["memo_json"] or ""

            row_dict = {
                "id": r["id"], 
                "지역": region_json_str,
                "보증금": deposit_str,
                "월세": rent_str,
                "평수": pyeong_str,
                "층": floor_str,
                "권리금": premium_str,
                "업종": biz_type_str,
                "연락처": contact_str,
                "실보증금/월세": real_dep_mon,
                "최근연락날짜": last_contact,
                "메모": memo_str,
                "담당자": r["manager"],
                "manager": r["manager"]
            }
            data.append(row_dict)
            
        return {"data": data}
        
    except mysql.Error as e:
        logger.error(f"Get customer data DB error (manager: {manager}, role: {role}): {e}")
        raise HTTPException(status_code=500, detail="데이터베이스 오류 발생")
    except Exception as e:
        logger.error(f"Get customer data unexpected error (manager: {manager}, role: {role}): {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류 발생")
    finally:
        if cur: cur.close()
        if conn: conn.close()

@router.post("/add_customer")
def add_customer(payload: dict):
    manager = payload.get("manager", "")
    gu_list   = payload.get("gu_list", [])
    dong_list = payload.get("dong_list", [])
    rects     = payload.get("rectangles", [])
    deposit_min  = int(payload.get("deposit_min", 0))
    deposit_max  = int(payload.get("deposit_max", 0))
    monthly_min  = int(payload.get("monthly_min", 0))
    monthly_max  = int(payload.get("monthly_max", 0))
    area_min     = float(payload.get("area_min", 0.0))
    area_max     = float(payload.get("area_max", 0.0))
    floor_min    = int(payload.get("floor_min", 0))
    floor_max    = int(payload.get("floor_max", 0))
    is_top_floor = int(payload.get("is_top_floor", 0))
    premium_str  = payload.get("premium", "")
    biz_type_str = payload.get("biz_type", "")
    contact_str  = payload.get("contact", "")
    real_dep_mon = payload.get("real_deposit_monthly", "")
    last_contact = payload.get("last_contact_date", "")
    memo_json_str  = payload.get("memo_json", "")
    
    gu_str = ",".join(gu_list)     
    dong_str = ",".join(dong_list)
    rectangles_json = json.dumps(rects, ensure_ascii=False)

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        sql = """
        INSERT INTO `customer` (
          gu, dong, rectangles, deposit_min, deposit_max,
          monthly_min, monthly_max, area_min, area_max,
          floor_min, floor_max, is_top_floor,
          premium, biz_type, contact,
          real_deposit_monthly, last_contact_date, memo_json, manager
        ) VALUES (
          %s, %s, %s, %s, %s,
          %s, %s, %s, %s,
          %s, %s, %s,
          %s, %s, %s,
          %s, %s, %s, %s
        )
        """
        
        cur.execute(sql, (
            gu_str, dong_str, rectangles_json, deposit_min, deposit_max,
            monthly_min, monthly_max, area_min, area_max,
            floor_min, floor_max, is_top_floor,
            premium_str, biz_type_str, contact_str,
            real_dep_mon, last_contact, memo_json_str, manager
        ))
        conn.commit()
        id_val = cur.lastrowid
        logger.info(f"Added new customer (ID: {id_val}) by manager: {manager}")
        return {"status": "success", "id_val": id_val}
        
    except mysql.Error as e:
        logger.error(f"Add customer DB error (manager: {manager}): {e}")
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="데이터베이스 오류 발생")
    except Exception as e:
        logger.error(f"Add customer unexpected error (manager: {manager}): {e}")
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="서버 내부 오류 발생")
    finally:
        if cur: cur.close()
        if conn: conn.close()

@router.post("/update_customer_sheet")
async def update_customer_sheet(request: Request):
    data = await request.json()
    cust_id       = data.get("id")
    manager       = data.get("manager")
    gu_list       = data.get("gu_list", [])
    dong_list     = data.get("dong_list", [])
    rects_list    = data.get("rects_list", [])
    deposit_min   = data.get("deposit_min", 0)
    deposit_max   = data.get("deposit_max", 0)
    monthly_min   = data.get("monthly_min", 0)
    monthly_max   = data.get("monthly_max", 0)
    area_min      = data.get("area_min", 0)
    area_max      = data.get("area_max", 0)
    floor_min     = data.get("floor_min", 0)
    floor_max     = data.get("floor_max", 0)
    is_top_floor  = data.get("is_top_floor", 0)
    premium       = data.get("premium", "")
    biz_type      = data.get("biz_type", "")
    contact       = data.get("contact", "")
    real_dep_mon  = data.get("real_deposit_monthly", "")
    last_contact  = data.get("last_contact_date", "")
    memo_json     = data.get("memo_json", "")
    
    if not cust_id or not manager:
        raise HTTPException(status_code=400, detail="id와 manager는 필수입니다.")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        gu_val = ",".join(gu_list)
        dong_val = ",".join(dong_list)
        rectangles_json = json.dumps(rects_list, ensure_ascii=False)
        sql = """
        UPDATE `customer`
           SET gu=%s, dong=%s, rectangles=%s, deposit_min=%s, deposit_max=%s,
               monthly_min=%s, monthly_max=%s, area_min=%s, area_max=%s,
               floor_min=%s, floor_max=%s, is_top_floor=%s, premium=%s,
               biz_type=%s, contact=%s, real_deposit_monthly=%s,
               last_contact_date=%s, memo_json=%s
         WHERE id=%s AND manager=%s
        """
        params = (
            gu_val, dong_val, rectangles_json, deposit_min, deposit_max,
            monthly_min, monthly_max, area_min, area_max,
            floor_min, floor_max, is_top_floor, premium,
            biz_type, contact, real_dep_mon, last_contact, memo_json,
            cust_id, manager
        )
        cursor.execute(sql, params)
        affected_rows = cursor.rowcount
        conn.commit()
        logger.info(f"Updated customer sheet (ID: {cust_id}) by manager: {manager}. Affected rows: {affected_rows}")
        return {"status": "ok", "affected_rows": affected_rows}

    except mysql.Error as e:
        logger.error(f"Update customer sheet DB error (ID: {cust_id}, manager: {manager}): {e}")
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="데이터베이스 오류 발생")
    except Exception as e:
        logger.error(f"Update customer sheet unexpected error (ID: {cust_id}, manager: {manager}): {e}")
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="서버 내부 오류 발생")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@router.post("/create_blank_customer")
async def create_blank_customer(request: Request):
    data = await request.json()
    manager = data.get("manager", "")
    if not manager:
        raise HTTPException(status_code=400, detail="manager는 필수입니다.")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        sql = """
        INSERT INTO customer (
            gu, dong, rectangles, deposit_min, deposit_max,
            monthly_min, monthly_max, area_min, area_max,
            floor_min, floor_max, is_top_floor,
            premium, biz_type, contact,
            real_deposit_monthly, last_contact_date, memo_json, manager
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s
        )
        """
        params = (
            "", "", "[]", 0, 0,
            0, 0, 0.0, 0.0,
            0, 0, 0,
            "", "", "",
            "", "", "", manager
        )
        cursor.execute(sql, params)
        conn.commit()
        new_id = cursor.lastrowid
        logger.info(f"Created blank customer (ID: {new_id}) for manager: {manager}")
        return {"status": "ok", "new_id": new_id}

    except mysql.Error as e:
        logger.error(f"Create blank customer DB error (manager: {manager}): {e}")
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="데이터베이스 오류 발생")
    except Exception as e:
        logger.error(f"Create blank customer unexpected error (manager: {manager}): {e}")
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="서버 내부 오류 발생")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@router.post("/delete_customer_row")
async def delete_customer_row(request: Request):
    data = await request.json()
    cust_id = data.get("id")
    if not cust_id:
        raise HTTPException(status_code=400, detail="id가 제공되지 않았습니다.")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 참고: 이 API는 manager 권한 확인 없이 id만으로 삭제합니다.
        # 필요 시 manager 정보도 받아서 WHERE 조건에 추가해야 합니다.
        sql = "DELETE FROM `customer` WHERE id=%s"
        cursor.execute(sql, (cust_id,))
        affected_rows = cursor.rowcount
        conn.commit()
        if affected_rows > 0:
             logger.info(f"Deleted customer row (ID: {cust_id}). Affected rows: {affected_rows}")
             return {"status": "ok", "deleted_count": affected_rows}
        else:
             logger.warning(f"Attempted to delete customer row (ID: {cust_id}), but no row was found.")
             raise HTTPException(status_code=404, detail="삭제할 고객 정보가 없습니다.")

    except mysql.Error as e:
        logger.error(f"Delete customer row DB error (ID: {cust_id}): {e}")
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="데이터베이스 오류 발생")
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Delete customer row unexpected error (ID: {cust_id}): {e}")
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="서버 내부 오류 발생")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@router.post("/delete_customer_data_bulk")
async def delete_customer_data_bulk(data: dict):
    manager = data.get("manager")
    role    = data.get("role", "manager")
    ids = data.get("ids", [])
    if not ids:
        single_id = data.get("id")
        if single_id is not None:
            ids = [single_id]
        else:
            raise HTTPException(status_code=400, detail="삭제할 id 목록이 없습니다.")
    
    # id 목록 유효성 검사 (정수형 ID만 필터링)
    valid_ids = [item_id for item_id in ids if isinstance(item_id, int) and item_id > 0]
    if not valid_ids:
         raise HTTPException(status_code=400, detail="유효한 삭제 ID 목록이 없습니다.")

    conn = None
    deleted_count = 0
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ",".join(["%s"] * len(valid_ids))

        if role == "admin":
            sql = f"DELETE FROM `customer` WHERE `id` IN ({placeholders})"
            params = tuple(valid_ids)
            manager_log_info = "(Admin)"
        else:
            if not manager:
                raise HTTPException(status_code=400, detail="일반 사용자는 manager 정보가 필수입니다.")
            sql = f"DELETE FROM `customer` WHERE `manager`=%s AND `id` IN ({placeholders})"
            params = tuple([manager] + valid_ids)
            manager_log_info = manager
        
        cursor.execute(sql, params)
        deleted_count = cursor.rowcount
        conn.commit()
        logger.info(f"Bulk deleted {deleted_count} customer(s) (IDs: {valid_ids}) by manager: {manager_log_info}")
        return {"status": "success", "deleted_count": deleted_count}

    except mysql.Error as e:
        logger.error(f"Bulk delete customer DB error (IDs: {valid_ids}, manager: {manager_log_info}): {e}")
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="데이터베이스 오류 발생")
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Bulk delete customer unexpected error (IDs: {valid_ids}, manager: {manager_log_info}): {e}")
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="서버 내부 오류 발생")
    finally:
        if cursor: cursor.close()
        if conn: conn.close() 