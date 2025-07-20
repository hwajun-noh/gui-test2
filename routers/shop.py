from fastapi import APIRouter, HTTPException, Request, Query, Body
import json
import os
import mysql.connector as mysql
from datetime import datetime, date, timedelta
from typing import List # List 임포트 추가
from settings import get_db_connection, logger, get_supabase_client # settings.py에서 임포트
from models import SearchFilter # models.py에서 임포트 (필요시)
# server_utils 에서 필요한 함수가 있다면 임포트

router = APIRouter()

@router.get("/search_manager_data")
def search_manager_data(
    # 라우팅 경로에서 manager/role 제거됨. 쿼리 파라미터는 유지 (하지만 사용 안 함)
    manager: str = Query("", description="DEPRECATED: Not used for filtering"),
    role: str = Query("manager", description="DEPRECATED: Not used for filtering"),
    ad_date: str = Query("", description="광고 시작일 필터 (YYYY-MM-DD, 쉼표 구분 가능)"),
    last_id: int = Query(0, description="페이지네이션용 마지막 ID") # last_id 추가
    # offset/limit 제거
):
    # 환경변수로 MySQL vs Supabase 선택
    use_supabase = os.environ.get("USE_SUPABASE_NAVER", "false").lower() == "true"
    
    # 디버그 로그 추가
    logger.info(f"search_manager_data API 호출 - USE_SUPABASE_NAVER: {use_supabase}")
    
    if use_supabase:
        logger.info("Supabase 경로로 실행")
        return search_manager_data_supabase(manager, role, ad_date, last_id)
    else:
        logger.info("MySQL 경로로 실행")
        return search_manager_data_mysql(manager, role, ad_date, last_id)

def search_manager_data_mysql(
    manager: str = "",
    role: str = "manager",
    ad_date: str = "",
    last_id: int = 0
):
    """MySQL 버전 - 기존 로직"""
    
    # (1) ad_date 쉼표 분할
    splitted_dates = []
    if ad_date.strip():
        splitted_dates = [d_.strip() for d_ in ad_date.split(",") if d_.strip()]
        
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # (2) 모든 customer 전부 SELECT (manager/role 필터링 없음)
        logger.info("Fetching ALL customer data for shop search (ignoring manager/role)")
        sql_all_customer = """
        SELECT
        id AS customer_id,
        manager,
        deposit_min, deposit_max,
        monthly_min, monthly_max,
        area_min, area_max,
        floor_min, floor_max,
        is_top_floor,
        dong,  -- e.g. "가양동, 대동"
        rectangles, -- JSON : [[swLng, swLat, neLng, neLat], ...]
        biz_type
        FROM customer
        """
        cursor.execute(sql_all_customer)
        customers = cursor.fetchall()
        logger.info(f"Found {len(customers)} customers to process for shop search.")

        by_naver_id = {}  # { shop_id: { naver_shop행..., biz_manager_list: [] } }

        for cust in customers:
            if not cust: continue
            cust_manager_name = cust.get("manager", "")
            deposit_min = cust.get("deposit_min", 0)
            deposit_max = cust.get("deposit_max", 99999999)
            monthly_min = cust.get("monthly_min", 0)
            monthly_max = cust.get("monthly_max", 99999999)
            area_min  = float(cust.get("area_min", 0.0))
            area_max  = float(cust.get("area_max", 99999999.0))
            floor_min = cust.get("floor_min", -999)
            floor_max = cust.get("floor_max", 9999)
            is_top_floor = cust.get("is_top_floor", 0)
            dong_str = cust.get("dong", "")
            rect_json = cust.get("rectangles", "[]")
            biz_type_cust = cust.get("biz_type","")
            
            biz_manager_list = []
            if biz_type_cust:
                # 구분자를 쉼표(,) 대신 파이프(|)로 변경
                splitted_biz = [b.strip() for b in biz_type_cust.split("|") if b.strip()]
                for individual_biz in splitted_biz:
                    biz_manager_list.append({"biz": individual_biz, "manager": cust_manager_name})

            area_min_m2 = area_min * 3.3058
            area_max_m2 = area_max * 3.3058
            dong_list = [x.strip() for x in dong_str.split(",") if x.strip()]
            try:
                rects = json.loads(rect_json)
            except: rects = []

            base_sql = """
            SELECT
              n.id AS shop_id,
              n.type, n.verification_method,
              n.gu, n.dong, n.jibun, n.ho,
              n.curr_floor, n.total_floor,
              n.deposit, n.monthly,
              n.manage_fee, n.premium, n.current_use, n.area,
              n.rooms, n.baths, n.building_usage,
              n.naver_property_no, n.serve_property_no,
              n.approval_date, n.memo, n.manager,
              n.photo_path, n.owner_name, n.owner_relation,
              n.owner_phone, n.lessee_phone,
              n.ad_start_date, n.ad_end_date,
              n.lat, n.lng, n.parking,     
              c.check_memo AS check_memo 
            FROM naver_shop n
            LEFT JOIN naver_shop_check_confirm c ON n.id = c.property_id
            WHERE 1=1
            """
            wheres = []
            params_ = []

            wheres.append("n.deposit BETWEEN %s AND %s")
            params_.extend([deposit_min, deposit_max])
            wheres.append("n.monthly BETWEEN %s AND %s")
            params_.extend([monthly_min, monthly_max])
            wheres.append("n.area BETWEEN %s AND %s")
            params_.extend([area_min_m2, area_max_m2])
            wheres.append("(n.curr_floor BETWEEN %s AND %s)")
            params_.extend([floor_min, floor_max])
            if is_top_floor == 1:
                wheres.append("n.curr_floor = n.total_floor")

            or_clauses = []
            or_params = []
            if dong_list:
                placeholders = ",".join(["%s"]*len(dong_list))
                or_clauses.append(f"n.dong IN ({placeholders})")
                or_params.extend(dong_list)
            rect_subs = []
            for rect in rects:
                if len(rect)==4:
                    swLng, swLat, neLng, neLat = rect
                    rect_subs.append("(n.lng BETWEEN %s AND %s AND n.lat BETWEEN %s AND %s)")
                    or_params.extend([swLng, neLng, swLat, neLat])
            if rect_subs:
                or_clauses.append(" OR ".join(rect_subs))
            if or_clauses:
                wheres.append("( " + " OR ".join(or_clauses) + " )")
            params_.extend(or_params)
            
            # last_id 조건 추가
            if last_id > 0:
                 wheres.append("n.id > %s")
                 params_.append(last_id)
                 
            if wheres:
                base_sql += " AND " + " AND ".join(wheres)
            
            # 페이징 없이 일단 조회 (나중에 필요하면 추가)
            # base_sql += " ORDER BY n.id ASC LIMIT 1000" # 예시
            
            cursor.execute(base_sql, tuple(params_))
            matched_rows = cursor.fetchall()

            for row_ in matched_rows:
                sid = row_["shop_id"]
                if sid not in by_naver_id:
                    by_naver_id[sid] = dict(row_)
                    by_naver_id[sid]["biz_manager_list"] = []
                for b_item in biz_manager_list: # 여기서 biz_manager_list 사용
                    by_naver_id[sid]["biz_manager_list"].append(b_item)

        # [C] 최종 결과 all_results (구조 변경 적용)
        all_results = list(by_naver_id.values()) # 바로 리스트로 변환

        # [D] 추가 필터(ad_date)
        filtered = []
        if splitted_dates:
            # 날짜 문자열 비교를 위해 정렬
            splitted_dates.sort()
            min_date_str = splitted_dates[0]
            max_date_str = splitted_dates[-1]
            try:
                min_date = datetime.strptime(min_date_str, "%Y-%m-%d").date()
                max_date = datetime.strptime(max_date_str, "%Y-%m-%d").date()
            except ValueError:
                logger.warning(f"Invalid ad_date format provided: {ad_date}. Skipping date filter.")
                filtered = all_results # 날짜 파싱 실패 시 필터링 안 함
            else:
                for rd in all_results:
                    ad_start = rd.get("ad_start_date")
                    if not ad_start: continue
                    
                    ad_start_date_obj = None
                    if isinstance(ad_start, date): # DB에서 date 타입으로 온 경우
                        ad_start_date_obj = ad_start
                    elif isinstance(ad_start, str): # 문자열인 경우
                        try:
                            ad_start_date_obj = datetime.strptime(ad_start.split(" ")[0], "%Y-%m-%d").date()
                        except ValueError:
                            continue # 파싱 실패 시 제외
                    
                    if ad_start_date_obj and (min_date <= ad_start_date_obj <= max_date):
                         filtered.append(rd)
        else:
            filtered = all_results # 날짜 필터 없으면 전체

        # [E] 정렬 (ad_start_date 내림차순)
        def ad_start_date_key(rowdict):
            val = rowdict.get("ad_start_date")
            if isinstance(val, date): return val
            if isinstance(val, str):
                try: return datetime.strptime(val.split(" ")[0], "%Y-%m-%d").date()
                except: pass
            return date(1900, 1, 1) # None이거나 파싱 실패 시 최소 날짜
        
        filtered.sort(key=ad_start_date_key, reverse=True)

        logger.info(f"Shop search completed. Returning {len(filtered)} results.")
        return {
            "status": "ok",
            "count": len(filtered),
            "total_count": len(filtered), # 현재 페이징 없으므로 count와 동일
            "data": filtered
        }

    except mysql.Error as e:
        logger.exception(f"Search manager data DB error: {e}")
        raise HTTPException(status_code=500, detail="데이터베이스 오류 발생")
    except Exception as e:
        logger.exception(f"Search manager data unexpected error: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류 발생")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def search_manager_data_supabase(
    manager: str = "",
    role: str = "manager", 
    ad_date: str = "",
    last_id: int = 0
):
    """Supabase 버전: search_manager_data"""
    try:
        supabase = get_supabase_client()
        
        # (1) ad_date 쉼표 분할
        splitted_dates = []
        if ad_date.strip():
            splitted_dates = [d_.strip() for d_ in ad_date.split(",") if d_.strip()]
        
        # (2) customer 테이블에서 모든 고객 데이터 조회 (MySQL 연결 필요)
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            sql_all_customer = """
            SELECT
            id AS customer_id,
            manager,
            deposit_min, deposit_max,
            monthly_min, monthly_max,
            area_min, area_max,
            floor_min, floor_max,
            is_top_floor,
            dong,
            rectangles,
            biz_type
            FROM customer
            """
            cursor.execute(sql_all_customer)
            customers = cursor.fetchall()
            logger.info(f"Found {len(customers)} customers to process for shop search.")
            
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

        by_naver_id = {}

        for cust in customers:
            if not cust: continue
            cust_manager_name = cust.get("manager", "")
            deposit_min = cust.get("deposit_min", 0)
            deposit_max = cust.get("deposit_max", 99999999)
            monthly_min = cust.get("monthly_min", 0)
            monthly_max = cust.get("monthly_max", 99999999)
            area_min  = float(cust.get("area_min", 0.0))
            area_max  = float(cust.get("area_max", 99999999.0))
            floor_min = cust.get("floor_min", -999)
            floor_max = cust.get("floor_max", 9999)
            is_top_floor = cust.get("is_top_floor", 0)
            dong_str = cust.get("dong", "")
            rect_json = cust.get("rectangles", "[]")
            biz_type_cust = cust.get("biz_type","")
            
            biz_manager_list = []
            if biz_type_cust:
                splitted_biz = [b.strip() for b in biz_type_cust.split("|") if b.strip()]
                for individual_biz in splitted_biz:
                    biz_manager_list.append({"biz": individual_biz, "manager": cust_manager_name})

            area_min_m2 = area_min * 3.3058
            area_max_m2 = area_max * 3.3058
            dong_list = [x.strip() for x in dong_str.split(",") if x.strip()]
            try:
                rects = json.loads(rect_json)
            except: rects = []

            # Supabase에서 naver_shop 조회 (조인 없이)
            query = supabase.table('naver_shop').select("""
                id,
                type, verification_method,
                gu, dong, jibun, ho,
                curr_floor, total_floor,
                deposit, monthly,
                manage_fee, premium, current_use, area,
                rooms, baths, building_usage,
                naver_property_no, serve_property_no,
                approval_date, memo, manager,
                photo_path, owner_name, owner_relation,
                owner_phone, lessee_phone,
                ad_start_date, ad_end_date,
                lat, lng, parking
            """)
            
            # 필터 조건들 적용
            query = query.gte('deposit', deposit_min).lte('deposit', deposit_max)
            query = query.gte('monthly', monthly_min).lte('monthly', monthly_max)
            query = query.gte('area', area_min_m2).lte('area', area_max_m2)
            query = query.gte('curr_floor', floor_min).lte('curr_floor', floor_max)
            
            if is_top_floor == 1:
                # Supabase에서는 컬럼 간 비교가 제한적이므로 클라이언트에서 필터링
                pass
            
            if dong_list:
                query = query.in_('dong', dong_list)
            
            if last_id > 0:
                query = query.gt('id', last_id)
            
            # 위도/경도 범위 필터링은 복잡하므로 일단 모든 데이터 가져온 후 클라이언트에서 필터링
            result = query.execute()
            
            for row_ in result.data:
                # 최상층 필터 적용
                if is_top_floor == 1 and row_.get('curr_floor') != row_.get('total_floor'):
                    continue
                
                # 위도/경도 범위 체크
                lat = row_.get('lat')
                lng = row_.get('lng')
                if lat and lng and rects:
                    in_rect = False
                    for rect in rects:
                        if len(rect) == 4:
                            swLng, swLat, neLng, neLat = rect
                            if swLng <= lng <= neLng and swLat <= lat <= neLat:
                                in_rect = True
                                break
                    if not in_rect:
                        continue
                
                sid = row_["id"]
                if sid not in by_naver_id:
                    # 데이터 구조 조정
                    shop_data = dict(row_)
                    shop_data["shop_id"] = sid
                    shop_data["check_memo"] = ""  # 기본값으로 빈 문자열 설정
                    
                    by_naver_id[sid] = shop_data
                    by_naver_id[sid]["biz_manager_list"] = []
                
                for b_item in biz_manager_list:
                    by_naver_id[sid]["biz_manager_list"].append(b_item)

        # check_memo 별도 조회 및 매핑
        if by_naver_id:
            property_ids = list(by_naver_id.keys())
            check_query = supabase.table('naver_shop_check_confirm').select('property_id, check_memo').in_('property_id', property_ids)
            check_result = check_query.execute()
            
            # check_memo 매핑
            for check_row in check_result.data:
                prop_id = check_row.get('property_id')
                if prop_id in by_naver_id:
                    by_naver_id[prop_id]["check_memo"] = check_row.get('check_memo', '')

        # 최종 결과
        all_results = list(by_naver_id.values())

        # ad_date 필터
        filtered = []
        if splitted_dates:
            splitted_dates.sort()
            min_date_str = splitted_dates[0]
            max_date_str = splitted_dates[-1]
            try:
                min_date = datetime.strptime(min_date_str, "%Y-%m-%d").date()
                max_date = datetime.strptime(max_date_str, "%Y-%m-%d").date()
            except ValueError:
                logger.warning(f"Invalid ad_date format provided: {ad_date}. Skipping date filter.")
                filtered = all_results
            else:
                for rd in all_results:
                    ad_start = rd.get("ad_start_date")
                    if not ad_start: continue
                    
                    ad_start_date_obj = None
                    if isinstance(ad_start, str):
                        try:
                            ad_start_date_obj = datetime.strptime(ad_start.split(" ")[0], "%Y-%m-%d").date()
                        except ValueError:
                            continue
                    
                    if ad_start_date_obj and (min_date <= ad_start_date_obj <= max_date):
                         filtered.append(rd)
        else:
            filtered = all_results

        # 정렬
        def ad_start_date_key(rowdict):
            val = rowdict.get("ad_start_date")
            if isinstance(val, str):
                try: return datetime.strptime(val.split(" ")[0], "%Y-%m-%d").date()
                except: pass
            return date(1900, 1, 1)
        
        filtered.sort(key=ad_start_date_key, reverse=True)

        logger.info(f"Supabase shop search completed. Returning {len(filtered)} results.")
        return {
            "status": "ok",
            "total_count": len(filtered),
            "count": len(filtered),
            "data": filtered
        }

    except Exception as e:
        logger.error(f"Supabase search_manager_data 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Supabase 오류: {str(e)}")

@router.post("/get_serve_shop_data")
async def get_serve_shop_data(request: Request):
    # 환경변수로 Supabase 사용 여부 결정
    from settings import USE_SUPABASE_SHOP
    
    if USE_SUPABASE_SHOP:
        return await get_serve_shop_data_supabase(request)
    else:
        return await get_serve_shop_data_mysql(request)

async def get_serve_shop_data_supabase(request: Request):
    """Supabase 버전: serve_shop_data 조회"""
    body = await request.json()
    address_list = body.get("addresses", [])
    if not address_list:
        return {"status": "ok", "data": []}
    
    try:
        supabase = get_supabase_client()
        
        # 주소 리스트로 필터링 조건 생성
        or_conditions = []
        for addr in address_list:
            if ' ' in addr:
                dong, jibun = addr.split(' ', 1)
                or_conditions.append(f"and(dong.eq.{dong},jibun.eq.{jibun})")
        
        # 쿼리 실행
        query = supabase.table('serve_shop_data').select('*')
        if or_conditions:
            query = query.or_(','.join(or_conditions))
        
        response = query.order('id', desc=False).execute()
        
        logger.info(f"Supabase serve_shop_data query result: {len(response.data)} rows")
        return {"status": "ok", "data": response.data}
        
    except Exception as e:
        logger.error(f"Get serve shop data Supabase error: {e}")
        raise HTTPException(status_code=500, detail=f"Supabase 오류 발생: {str(e)}")

async def get_serve_shop_data_mysql(request: Request):
    """기존 MySQL 버전: serve_shop_data 조회"""
    body = await request.json()
    address_list = body.get("addresses", [])
    if not address_list:
        return {"status": "ok","data":[]}
        
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        placeholders = ",".join(["%s"] * len(address_list))
        sql = f"""
        SELECT
          id, gu, dong, jibun, ho, curr_floor, total_floor,
          deposit, monthly, manage_fee, premium, current_use, area,
          owner_phone, naver_property_no, serve_property_no, manager,
          memo, status_cd, parking, building_usage, approval_date,
          rooms, baths, ad_end_date, photo_path, owner_name, owner_relation
        FROM serve_shop_data
        WHERE CONCAT(dong, ' ', jibun) IN ({placeholders})
        ORDER BY id ASC
        """
        cursor.execute(sql, tuple(address_list))
        rows = cursor.fetchall()
        logger.info(f"MySQL serve_shop_data query result: {len(rows)} rows")
        return {"status": "ok", "data": rows}

    except mysql.Error as e:
        logger.error(f"Get serve shop data DB error: {e}")
        raise HTTPException(status_code=500, detail="데이터베이스 오류 발생")
    except Exception as e:
        logger.error(f"Get serve shop data unexpected error: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류 발생")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@router.post("/get_serve_oneroom_data")
async def get_serve_oneroom_data(request: Request):
    # 환경변수로 MySQL vs Supabase 선택
    use_supabase = os.environ.get("USE_SUPABASE_ONEROOM", "false").lower() == "true"
    
    if use_supabase:
        return await get_serve_oneroom_data_supabase(request)
    else:
        return await get_serve_oneroom_data_mysql(request)

async def get_serve_oneroom_data_mysql(request: Request):
    """MySQL 버전 - 기존 로직"""
    body = await request.json()
    address_list = body.get("addresses", [])
    if not address_list:
        return {"status":"ok","data":[]}
        
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        placeholders = ",".join(["%s"]*len(address_list))
        sql = f"""
        SELECT
          id, gu, dong, jibun, ho, curr_floor, total_floor, deposit, monthly,
          manage_fee, in_date, status_cd, `password`, rooms, baths,
          owner_phone, naver_property_no, serve_property_no, manager, memo,
          `options`, parking, building_usage, approval_date, area, ad_end_date,
          photo_path, owner_name, owner_relation, lat, lng
        FROM serve_oneroom_data
        WHERE CONCAT(dong, ' ', jibun) IN ({placeholders})
        ORDER BY id ASC
        """
        cursor.execute(sql, tuple(address_list))
        rows = cursor.fetchall()
        logger.info(f"MySQL serve_oneroom_data query result: {len(rows)} rows")
        return {"status":"ok","data":rows}

    except mysql.Error as e:
        logger.error(f"Get serve oneroom data DB error: {e}")
        raise HTTPException(status_code=500, detail="데이터베이스 오류 발생")
    except Exception as e:
        logger.error(f"Get serve oneroom data unexpected error: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류 발생")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

async def get_serve_oneroom_data_supabase(request: Request):
    """Supabase 버전 - 새로운 로직"""
    try:
        body = await request.json()
        address_list = body.get("addresses", [])
        if not address_list:
            return {"status":"ok","data":[]}
        
        supabase = get_supabase_client()
        if not supabase:
            logger.error("Supabase client not available, falling back to MySQL")
            return await get_serve_oneroom_data_mysql(request)
        
        # Supabase 쿼리 - PostgreSQL CONCAT 함수 사용
        conditions = []
        for addr in address_list:
            conditions.append(f"(dong || ' ' || jibun) = '{addr}'")
        
        where_clause = " OR ".join(conditions)
        
        response = supabase.table('serve_oneroom_data').select(
            'id, gu, dong, jibun, ho, curr_floor, total_floor, deposit, monthly, '
            'manage_fee, in_date, status_cd, password, rooms, baths, '
            'owner_phone, naver_property_no, serve_property_no, manager, memo, '
            'options, parking, building_usage, approval_date, area, ad_end_date, '
            'photo_path, owner_name, owner_relation, lat, lng'
        ).or_(where_clause).order('id', desc=False).execute()
        
        rows = response.data if response.data else []
        logger.info(f"Supabase serve_oneroom_data query result: {len(rows)} rows")
        return {"status":"ok","data":rows}
        
    except Exception as e:
        logger.error(f"Supabase serve_oneroom_data error: {e}")
        logger.info("Falling back to MySQL")
        return await get_serve_oneroom_data_mysql(request)

@router.post("/get_all_confirm_with_items")
async def get_all_confirm_with_items(request: Request):
    body = await request.json()
    address_list = body.get("addresses", [])
    if not address_list:
        return {"status": "ok", "data": []}
        
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        placeholders = ",".join(["%s"] * len(address_list))
        sql = f"""
        SELECT
          c.id AS confirm_id, c.property_id AS property_id,
          c.gu, c.dong, c.jibun, c.ho, c.curr_floor, c.total_floor,
          c.deposit, c.monthly, c.manage_fee, c.premium, c.current_use,
          c.area, c.rooms, c.baths, c.building_usage, c.lat, c.lng,
          c.naver_property_no, c.serve_property_no, c.approval_date, c.memo, c.manager,
          c.photo_path, c.owner_name, c.owner_relation, c.owner_phone, c.lessee_phone,
          c.ad_start_date, c.ad_end_date, c.parking, c.status_cd, # status_cd 추가
          i.id AS item_id, i.matching_biz_type, i.check_memo
        FROM naver_shop_check_confirm c
        LEFT JOIN naver_shop_check_items i ON i.check_confirm_id = c.id
        WHERE CONCAT(c.dong, ' ', c.jibun) IN ({placeholders})
        ORDER BY c.ad_end_date DESC, c.id ASC, i.id ASC
        """
        cursor.execute(sql, tuple(address_list))
        rows = cursor.fetchall()
        return {"status": "ok", "data": rows}

    except mysql.Error as e:
        logger.error(f"Get confirm with items DB error: {e}")
        raise HTTPException(status_code=500, detail="데이터베이스 오류 발생")
    except Exception as e:
        logger.error(f"Get confirm with items unexpected error: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류 발생")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@router.post("/batch_update_naver_shop_extra")
def batch_update_naver_shop_extra(payload: dict):
    updates = payload.get("updates", [])
    if not updates:
        raise HTTPException(status_code=400, detail="updates 목록이 비어있습니다.")

    conn = None
    processed_managers = set()
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        for upd in updates:
            str_id = upd.get("id", "")
            try: property_id = int(str_id)
            except ValueError: continue
            changed_vals = upd.get("values", {})
            logger.debug(f"Processing shop extra update for property_id={property_id}, changed_vals={changed_vals}")

            # naver_shop에서 기본 정보 조회
            cursor.execute("""
                SELECT gu, dong, jibun, curr_floor, total_floor, deposit, monthly, area, 
                       memo, naver_property_no, ad_start_date, lat, lng
                FROM naver_shop WHERE id=%s
            """, (property_id,))
            row_shop = cursor.fetchone()
            if not row_shop:
                logger.warning(f"No naver_shop row found for property_id={property_id}, skipping.")
                continue

            def strval(x): return str(x) if x is not None else ""

            base_fields = {
                "property_id": property_id, # 정수형 유지
                "gu": strval(row_shop.get("gu")),
                "dong": strval(row_shop.get("dong")),
                "jibun": strval(row_shop.get("jibun")),
                "curr_floor": strval(row_shop.get("curr_floor")),
                "total_floor": strval(row_shop.get("total_floor")),
                "deposit": strval(row_shop.get("deposit")),
                "monthly": strval(row_shop.get("monthly")),
                "area": strval(row_shop.get("area")),
                "memo": strval(row_shop.get("memo")),
                "naver_property_no": strval(row_shop.get("naver_property_no")),
                "ad_start_date": row_shop.get("ad_start_date"), # 날짜 객체 유지
                "lat": row_shop.get("lat"), # 숫자 유지
                "lng": row_shop.get("lng") # 숫자 유지
            }

            # 나머지 컬럼 기본값
            extra_cols = [
                "manager","building_usage","approval_date","ho",
                "owner_phone","premium","current_use","manage_fee","parking",
                "ad_end_date","photo_path","owner_name","owner_relation","lessee_phone",
                "rooms","baths","check_memo","serve_property_no","status_cd"
            ]
            for c_ in extra_cols:
                if c_ not in base_fields:
                    base_fields[c_] = "" if c_ != "approval_date" and c_ != "ad_end_date" else None

            # 변경 값 적용
            for key, new_val in changed_vals.items():
                new_val_str = str(new_val).strip()
                if not new_val_str: continue
                if key == "price" and "/" in new_val_str:
                    dep_s, mon_s = new_val_str.split("/", 1)
                    base_fields["deposit"] = dep_s.strip()
                    base_fields["monthly"] = mon_s.strip()
                elif key == "floor" and "/" in new_val_str:
                    cf_s, tf_s = new_val_str.split("/", 1)
                    base_fields["curr_floor"] = cf_s.strip()
                    base_fields["total_floor"] = tf_s.strip()
                elif key in base_fields:
                     base_fields[key] = new_val_str

            # check_memo 파싱 및 필터링
            raw_memo = base_fields.get("check_memo","").strip()
            memo_items = []
            if raw_memo:
                try: memo_items = json.loads(raw_memo)
                except: pass
            filtered_memo_items = [it for it in memo_items if it.get("biz") and it.get("memo") and it.get("manager")]
            if not filtered_memo_items:
                logger.info(f"No valid check_memo items for property_id={property_id}, skipping confirm/items update.")
                continue

            # manager별 그룹화
            groups = {}
            for item in filtered_memo_items:
                mgr_name = item["manager"]
                groups.setdefault(mgr_name, []).append(item)
                processed_managers.add(mgr_name)

            # manager별 Upsert
            for mgr_name, item_list in groups.items():
                bf_copy = dict(base_fields)
                bf_copy["manager"] = mgr_name
                cm_list = [{"biz": sub["biz"], "memo": sub["memo"] } for sub in item_list]
                bf_copy["check_memo"] = json.dumps(cm_list, ensure_ascii=False)

                # Upsert 로직
                insert_cols = []
                insert_vals = []
                update_pairs = []
                
                # 컬럼과 값 준비 (None 아닌 것만)
                for c_, v_ in bf_copy.items():
                    # property_id는 항상 포함
                    if c_ == "property_id" or v_ is not None:
                        insert_cols.append(f"`{c_}`")
                        insert_vals.append(v_)
                        if c_ != "property_id": # id는 update 대상에서 제외
                            update_pairs.append(f"`{c_}`=VALUES(`{c_}`)")
                            
                if not insert_cols:
                     logger.warning(f"No columns to insert/update for property_id={property_id}, manager={mgr_name}")
                     continue

                sql_upsert = f"""
                INSERT INTO naver_shop_check_confirm ({ ",".join(insert_cols) })
                VALUES ({ ",".join(['%s']*len(insert_vals)) })
                ON DUPLICATE KEY UPDATE { ",".join(update_pairs) }
                """
                
                try:
                    cursor.execute(sql_upsert, tuple(insert_vals))
                    # confirm_id 찾기
                    cursor.execute("SELECT id FROM naver_shop_check_confirm WHERE property_id=%s AND manager=%s", (property_id, mgr_name))
                    row_cc = cursor.fetchone()
                    if not row_cc:
                        logger.error(f"Failed to find confirm_id after upsert for property_id={property_id}, manager={mgr_name}")
                        continue
                    confirm_id = row_cc["id"]
                    
                    # check_items 삭제 후 재삽입
                    cursor.execute("DELETE FROM naver_shop_check_items WHERE check_confirm_id=%s", (confirm_id,))
                    sql_item_ins = "INSERT INTO naver_shop_check_items (check_confirm_id, matching_biz_type, check_memo, manager) VALUES (%s, %s, %s, %s)"
                    items_to_insert = []
                    for sub2 in item_list:
                         items_to_insert.append((confirm_id, sub2["biz"], sub2["memo"], sub2["manager"]))
                    if items_to_insert:
                         cursor.executemany(sql_item_ins, items_to_insert)
                    logger.info(f"Upserted confirm/items for manager={mgr_name}, confirm_id={confirm_id}, items={len(item_list)}")
                    
                except mysql.Error as upsert_err:
                     logger.error(f"Error during confirm/items upsert for property_id={property_id}, manager={mgr_name}: {upsert_err}")
                     conn.rollback() # 개별 매니저 처리 중 오류 시 롤백 후 다음 매니저 시도 (선택적)
                     continue # 다음 매니저 처리
            
            logger.info(f"Finished processing property_id={property_id}. Handled {len(groups)} manager group(s).")
            conn.commit() # 각 property_id 처리 후 커밋

        logger.info(f"Batch shop extra update completed. Processed managers: {processed_managers}")
        return {"status":"ok","message":"batch multi-manager done"}

    except mysql.Error as e:
        logger.error(f"Batch update naver_shop_extra DB error: {e}")
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="데이터베이스 오류 발생")
    except Exception as e:
        logger.error(f"Batch update naver_shop_extra unexpected error: {e}")
        import traceback
        traceback.print_exc()
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="서버 내부 오류 발생")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@router.get("/get_naver_shop")
def get_naver_shop():
    # 환경변수로 MySQL vs Supabase 선택
    use_supabase = os.environ.get("USE_SUPABASE_NAVER", "false").lower() == "true"
    
    # 디버그 로그 추가
    logger.info(f"naver_shop API 호출 - USE_SUPABASE_NAVER: {use_supabase}")
    
    if use_supabase:
        logger.info("Supabase 경로로 실행")
        return get_naver_shop_supabase()
    else:
        logger.info("MySQL 경로로 실행")
        return get_naver_shop_mysql()

def get_naver_shop_mysql():
    """MySQL 버전 - 기존 로직"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        # 컬럼 목록 명시적 지정 권장
        sql = """
        SELECT
          id, type, verification_method,
          gu, dong, jibun, ho, curr_floor, total_floor, deposit, monthly,
          manage_fee, premium, current_use, area, rooms, baths, building_usage, 
          lat, lng, naver_property_no, serve_property_no, approval_date, memo, 
          manager, photo_path, owner_name, owner_relation, owner_phone, 
          lessee_phone, ad_start_date, ad_end_date, parking, status_cd # type, verification_method 추가
        FROM naver_shop
        ORDER BY id ASC
        """
        cur.execute(sql)
        rows = cur.fetchall()
        return {"data": rows}

    except mysql.Error as e:
        logger.error(f"Get naver_shop DB error: {e}")
        raise HTTPException(status_code=500, detail="데이터베이스 오류 발생")
    except Exception as e:
        logger.error(f"Get naver_shop unexpected error: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류 발생")
    finally:
        if cur: cur.close()
        if conn: conn.close()

def get_naver_shop_supabase():
    """Supabase 버전: naver_shop 전체 조회"""
    try:
        supabase = get_supabase_client()
        
        # 간단한 전체 데이터 조회
        result = supabase.table('naver_shop').select('*').execute()
        
        logger.info(f"Supabase naver_shop 조회 성공: {len(result.data)}개")
        return {"data": result.data}
        
    except Exception as e:
        logger.error(f"Supabase naver_shop 조회 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Supabase 오류: {str(e)}")

@router.get("/search_naver_shop")
def search_naver_shop(
    deposit_min: int = 0,
    deposit_max: int = 99999999,
    monthly_min: int = 0,
    monthly_max: int = 99999999,
    area_min: float = 0.0, # 단위: m2 가정
    area_max: float = 99999999.0,
    floor_min: int = -999, # 기본값 변경 (-999)
    floor_max: int = 9999,
    is_top_floor: bool = False,
    dong_list: str = Query("", description="동 목록 (쉼표 구분)"),
    rectangles: str = Query("", description="지도 범위 JSON 문자열 e.g., \"[[lng1,lat1,lng2,lat2],...]\""),
    offset: int = 0,
    limit: int = 100,
):
    # 환경변수로 MySQL vs Supabase 선택
    use_supabase = os.environ.get("USE_SUPABASE_NAVER", "false").lower() == "true"
    
    # 디버그 로그 추가
    logger.info(f"search_naver_shop API 호출 - USE_SUPABASE_NAVER: {use_supabase}")
    
    if use_supabase:
        logger.info("Supabase 경로로 실행")
        return search_naver_shop_supabase(deposit_min, deposit_max, monthly_min, monthly_max, 
                                         area_min, area_max, floor_min, floor_max, 
                                         is_top_floor, dong_list, rectangles, offset, limit)
    else:
        logger.info("MySQL 경로로 실행")
        return search_naver_shop_mysql(deposit_min, deposit_max, monthly_min, monthly_max, 
                                      area_min, area_max, floor_min, floor_max, 
                                      is_top_floor, dong_list, rectangles, offset, limit)

def search_naver_shop_mysql(
    deposit_min: int = 0,
    deposit_max: int = 99999999,
    monthly_min: int = 0,
    monthly_max: int = 99999999,
    area_min: float = 0.0,
    area_max: float = 99999999.0,
    floor_min: int = -999,
    floor_max: int = 9999,
    is_top_floor: bool = False,
    dong_list: str = "",
    rectangles: str = "",
    offset: int = 0,
    limit: int = 100,
):
    """MySQL 버전 - 기존 로직"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        base_sql = """
        SELECT
          n.id, n.type, n.verification_method,
          n.gu, n.dong, n.jibun, n.ho, n.curr_floor, n.total_floor,
          n.deposit, n.monthly, n.manage_fee, n.premium, n.current_use, n.area,
          n.rooms, n.baths, n.building_usage, n.naver_property_no, n.serve_property_no,
          n.approval_date, n.memo, n.photo_path, n.owner_name, n.owner_relation,
          n.owner_phone, n.lessee_phone, n.ad_start_date, n.ad_end_date, 
          n.lat, n.lng, n.parking, n.manager, # type, verification_method 추가
          c.check_memo
        FROM naver_shop n
        LEFT JOIN naver_shop_check_confirm c ON n.id = c.property_id
        WHERE 1=1
        """
        where_clauses = []
        params = []

        where_clauses.append("n.deposit BETWEEN %s AND %s")
        params.extend([deposit_min, deposit_max])
        where_clauses.append("n.monthly BETWEEN %s AND %s")
        params.extend([monthly_min, monthly_max])
        where_clauses.append("n.area BETWEEN %s AND %s")
        params.extend([area_min, area_max]) # area는 m2 단위로 가정
        where_clauses.append("(n.curr_floor BETWEEN %s AND %s)")
        params.extend([floor_min, floor_max])
        if is_top_floor:
            where_clauses.append("n.curr_floor = n.total_floor")

        if dong_list.strip():
            splitted = [x.strip() for x in dong_list.split(",") if x.strip()]
            if splitted:
                placeholders = ",".join(["%s"] * len(splitted))
                where_clauses.append(f"n.dong IN ({placeholders})")
                params.extend(splitted)

        if rectangles.strip():
            try:
                rect_arr = json.loads(rectangles)
                rect_subs = []
                rect_params = []
                for r_ in rect_arr:
                    if isinstance(r_, list) and len(r_)==4:
                        swLng, swLat, neLng, neLat = r_
                        # 경도/위도 유효성 검사 추가 가능
                        sub = "(n.lng BETWEEN %s AND %s AND n.lat BETWEEN %s AND %s)"
                        rect_subs.append(sub)
                        rect_params.extend([swLng, neLng, swLat, neLat])
                if rect_subs:
                    where_clauses.append("( " + " OR ".join(rect_subs) + " )")
                    params.extend(rect_params)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON format for rectangles: {rectangles}")
            except Exception as e:
                 logger.error(f"Error processing rectangles: {e}")

        final_sql = base_sql
        if where_clauses:
            final_sql += " AND " + " AND ".join(where_clauses)

        # Total count 쿼리
        count_sql = f"SELECT COUNT(*) AS cnt FROM ({final_sql.replace('LEFT JOIN naver_shop_check_confirm c ON n.id = c.property_id', '').replace('c.check_memo','NULL as check_memo')}) AS sub"
        # COUNT 쿼리에서는 JOIN 제거 및 c.check_memo 제거 (성능 개선)
        # 파라미터는 동일하게 사용
        cursor.execute(count_sql, tuple(params))
        row_cnt = cursor.fetchone()
        total_count = row_cnt["cnt"] if row_cnt else 0

        # Paging 쿼리
        final_sql += " ORDER BY n.ad_start_date DESC, n.id DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        cursor.execute(final_sql, tuple(params))
        rows = cursor.fetchall()

        # Post-processing (check_memo가 None이면 "")
        for r in rows:
            if r.get("check_memo") is None:
                r["check_memo"] = ""

        return {
            "status": "ok",
            "total_count": total_count,
            "count": len(rows),
            "data": rows
        }

    except mysql.Error as e:
        logger.error(f"Search naver_shop DB error: {e}")
        raise HTTPException(status_code=500, detail="데이터베이스 오류 발생")
    except Exception as e:
        logger.error(f"Search naver_shop unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="서버 내부 오류 발생")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def search_naver_shop_supabase(
    deposit_min: int = 0,
    deposit_max: int = 99999999,
    monthly_min: int = 0,
    monthly_max: int = 99999999,
    area_min: float = 0.0,
    area_max: float = 99999999.0,
    floor_min: int = -999,
    floor_max: int = 9999,
    is_top_floor: bool = False,
    dong_list: str = "",
    rectangles: str = "",
    offset: int = 0,
    limit: int = 100,
):
    """Supabase 버전: search_naver_shop"""
    try:
        supabase = get_supabase_client()
        
        # 기본 쿼리 - naver_shop (조인 없이)
        query = supabase.table('naver_shop').select("""
            id, type, verification_method,
            gu, dong, jibun, ho, curr_floor, total_floor,
            deposit, monthly, manage_fee, premium, current_use, area,
            rooms, baths, building_usage, naver_property_no, serve_property_no,
            approval_date, memo, photo_path, owner_name, owner_relation,
            owner_phone, lessee_phone, ad_start_date, ad_end_date,
            lat, lng, parking, manager
        """)
        
        # 필터 조건들 적용
        query = query.gte('deposit', deposit_min).lte('deposit', deposit_max)
        query = query.gte('monthly', monthly_min).lte('monthly', monthly_max)
        query = query.gte('area', area_min).lte('area', area_max)
        query = query.gte('curr_floor', floor_min).lte('curr_floor', floor_max)
        
        # 동 목록 필터
        if dong_list.strip():
            dong_list_parsed = [x.strip() for x in dong_list.split(",") if x.strip()]
            if dong_list_parsed:
                query = query.in_('dong', dong_list_parsed)
        
        # 정렬 및 페이징
        query = query.order('ad_start_date', desc=True).order('id', desc=True)
        query = query.range(offset, offset + limit - 1)
        
        result = query.execute()
        
        # 결과 후처리
        processed_rows = []
        property_ids = []
        
        for row in result.data:
            # 최상층 필터 적용
            if is_top_floor and row.get('curr_floor') != row.get('total_floor'):
                continue
            
            # 위도/경도 범위 체크
            if rectangles.strip():
                try:
                    rect_arr = json.loads(rectangles)
                    lat = row.get('lat')
                    lng = row.get('lng')
                    
                    if lat and lng and rect_arr:
                        in_rect = False
                        for rect in rect_arr:
                            if isinstance(rect, list) and len(rect) == 4:
                                swLng, swLat, neLng, neLat = rect
                                if swLng <= lng <= neLng and swLat <= lat <= neLat:
                                    in_rect = True
                                    break
                        if not in_rect:
                            continue
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"Rectangle filter error: {e}")
            
            # 데이터 구조 정리
            processed_row = dict(row)
            processed_row["check_memo"] = ""  # 기본값 설정
            processed_rows.append(processed_row)
            property_ids.append(row['id'])
        
        # check_memo 별도 조회 및 매핑
        if property_ids:
            check_query = supabase.table('naver_shop_check_confirm').select('property_id, check_memo').in_('property_id', property_ids)
            check_result = check_query.execute()
            
            # check_memo 매핑
            check_memo_dict = {}
            for check_row in check_result.data:
                check_memo_dict[check_row.get('property_id')] = check_row.get('check_memo', '')
            
            # processed_rows에 check_memo 추가
            for row in processed_rows:
                row_id = row['id']
                if row_id in check_memo_dict:
                    row["check_memo"] = check_memo_dict[row_id]
        
        logger.info(f"Supabase search_naver_shop 조회 성공: {len(processed_rows)}개 (전체: {len(processed_rows)})")
        return {
            "status": "ok",
            "total_count": len(processed_rows),
            "count": len(processed_rows),
            "data": processed_rows
        }
        
    except Exception as e:
        logger.error(f"Supabase search_naver_shop 조회 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Supabase 오류: {str(e)}")

# search_in_all_data 내부에 있던 함수들을 라우터 레벨로 이동 (필요시 server_utils.py로 이동)
def _decide_status(row_dict: dict) -> str:
    from datetime import datetime, date, timedelta
    s_cd = str(row_dict.get("status_cd","")).strip()
    if s_cd == "4": return "계약완료"
    if s_cd == "3": return "등록종료"
    ad_end_val = row_dict.get("ad_end_date")
    if not ad_end_val: return "확인필요"
    ad_end_dt = None
    if isinstance(ad_end_val, (datetime, date)):
        # date 객체일 경우 datetime 객체로 변환 (비교를 위해)
        if isinstance(ad_end_val, date) and not isinstance(ad_end_val, datetime):
            ad_end_dt = datetime.combine(ad_end_val, datetime.min.time()).date() # 시간 정보 추가 후 date()로 변환
        else:
             ad_end_dt = ad_end_val.date()
    else:
        try: ad_end_dt = datetime.strptime(str(ad_end_val).strip().split(" ")[0], "%Y-%m-%d").date()
        except: return "확인필요"
    today = date.today()
    if ad_end_dt < today: return "등록종료"
    if today <= ad_end_dt <= (today + timedelta(days=6)): return "재광고예정"
    return "서비스중"

def _unify_oneroom(row):
    addr_ = (row.get("dong","") + " " + row.get("jibun","")).strip()
    naver_no = (row.get("naver_property_no","") or "").strip()
    serve_no = (row.get("serve_property_no","") or "").strip()
    curr_floor = row.get("curr_floor", 0)
    total_floor = row.get("total_floor", 0)
    deposit = row.get("deposit", 0)
    monthly = row.get("monthly", 0)
    rooms = row.get("rooms", "")
    baths = row.get("baths", "")
    return {
        "주소": addr_, "호": row.get("ho",""), "층": f"{curr_floor}/{total_floor}",
        "보증금/월세": f"{deposit}/{monthly}", "관리비": str(row.get("manage_fee","")),
        "권리금": row.get("password",""), "현업종": row.get("in_date",""), "평수": str(row.get("area","")),
        "연락처": row.get("owner_phone",""),
        "매물번호": f"{naver_no}/{serve_no}",
        "제목": row.get("memo",""), "매칭업종": row.get("manager",""), "확인메모": _decide_status(row),
        "광고종료일": row.get("ad_end_date",""), "주차대수": str(row.get("parking","")),
        "용도": row.get("building_usage",""), "사용승인일": str(row.get("approval_date","")),
        "방/화장실": f"{rooms}/{baths}", "광고등록일": "",
        "사진경로": row.get("photo_path",""), "소유자명": row.get("owner_name",""), "관계": row.get("owner_relation",""),
        "출처": "원룸", "id": row.get("id")
    }

def _unify_shop(row):
    addr_ = (row.get("dong","") + " " + row.get("jibun","")).strip()
    naver_no = (row.get("naver_property_no","") or "").strip()
    serve_no = (row.get("serve_property_no","") or "").strip()
    curr_floor = row.get("curr_floor", 0)
    total_floor = row.get("total_floor", 0)
    deposit = row.get("deposit", 0)
    monthly = row.get("monthly", 0)
    rooms = row.get("rooms", "")
    baths = row.get("baths", "")
    return {
        "주소": addr_, "호": row.get("ho",""), "층": f"{curr_floor}/{total_floor}",
        "보증금/월세": f"{deposit}/{monthly}", "관리비": str(row.get("manage_fee","")),
        "권리금": row.get("premium",""), "현업종": row.get("current_use",""), "평수": str(row.get("area","")),
        "연락처": row.get("owner_phone",""), 
        "매물번호": f"{naver_no}/{serve_no}",
        "제목": row.get("memo",""), "매칭업종": row.get("manager",""), "확인메모": _decide_status(row),
        "광고종료일": row.get("ad_end_date",""), "주차대수": str(row.get("parking","")),
        "용도": row.get("building_usage",""), "사용승인일": str(row.get("approval_date","")),
        "방/화장실": f"{rooms}/{baths}", "광고등록일": str(row.get("ad_start_date","")),
        "사진경로": row.get("photo_path",""), "소유자명": row.get("owner_name",""), "관계": row.get("owner_relation",""),
        "출처": "상가", "id": row.get("id")
    }

def _unify_confirm(row):
    addr_ = (row.get("dong","") + " " + row.get("jibun","")).strip()
    naver_no = (row.get("naver_property_no","") or "").strip()
    serve_no = (row.get("serve_property_no","") or "").strip()
    curr_floor = row.get("curr_floor", 0)
    total_floor = row.get("total_floor", 0)
    deposit = row.get("deposit", 0)
    monthly = row.get("monthly", 0)
    rooms = row.get("rooms", "")
    baths = row.get("baths", "")
    return {
        "주소": addr_, "호": row.get("ho",""), "층": f"{curr_floor}/{total_floor}",
        "보증금/월세": f"{deposit}/{monthly}", "관리비": str(row.get("manage_fee","")),
        "권리금": row.get("premium",""), "현업종": row.get("current_use",""), "평수": str(row.get("area","")),
        "연락처": row.get("owner_phone",""), 
        "매물번호": f"{naver_no}/{serve_no}",
        "제목": row.get("memo",""), "매칭업종": row.get("manager",""), "확인메모": _decide_status(row),
        "광고종료일": row.get("ad_end_date",""), "주차대수": str(row.get("parking","")),
        "용도": row.get("building_usage",""), "사용승인일": str(row.get("approval_date","")),
        "방/화장실": f"{rooms}/{baths}", "광고등록일": str(row.get("ad_start_date","")),
        "사진경로": row.get("photo_path",""), "소유자명": row.get("owner_name",""), "관계": row.get("owner_relation",""),
        "출처": "확인", "id": row.get("id")
    }

def _unify_recommend(row):
    addr_ = (row.get("dong","") + " " + row.get("jibun","")).strip()
    biz_ = row.get("matching_biz","")
    mgr_ = row.get("manager","")
    naver_no = (row.get("naver_property_no","") or "").strip()
    serve_no = (row.get("serve_property_no","") or "").strip()
    curr_floor = row.get("curr_floor", 0)
    total_floor = row.get("total_floor", 0)
    deposit = row.get("deposit", 0)
    monthly = row.get("monthly", 0)
    rooms = row.get("rooms", "")
    baths = row.get("baths", "")
    return {
        "주소": addr_, "호": row.get("ho",""), "층": f"{curr_floor}/{total_floor}",
        "보증금/월세": f"{deposit}/{monthly}", "관리비": str(row.get("manage_fee","")),
        "권리금": row.get("premium",""), "현업종": row.get("current_use",""), "평수": str(row.get("area","")),
        "연락처": row.get("owner_phone",""), 
        "매물번호": f"{naver_no}/{serve_no}",
        "제목": row.get("memo",""), "매칭업종": f"{biz_}({mgr_})", "확인메모": _decide_status(row),
        "광고종료일": row.get("ad_end_date",""), "주차대수": str(row.get("parking","")),
        "용도": row.get("building_usage",""), "사용승인일": str(row.get("approval_date","")),
        "방/화장실": f"{rooms}/{baths}", "광고등록일": str(row.get("ad_start_date","")),
        "사진경로": row.get("photo_path",""), "소유자명": row.get("owner_name",""), "관계": row.get("owner_relation",""),
        "출처": "추천", "id": row.get("id")
    }

def _unify_mylist_shop(row):
    addr_ = (row.get("dong","") + " " + row.get("jibun","")).strip()
    naver_no = (row.get("naver_property_no","") or "").strip()
    serve_no = (row.get("serve_property_no","") or "").strip()
    curr_floor = row.get("curr_floor", 0)
    total_floor = row.get("total_floor", 0)
    deposit = row.get("deposit", 0)
    monthly = row.get("monthly", 0)
    rooms = row.get("rooms", "")
    baths = row.get("baths", "")
    return {
        "주소": addr_, "호": row.get("ho",""), "층": f"{curr_floor}/{total_floor}",
        "보증금/월세": f"{deposit}/{monthly}", "관리비": str(row.get("manage_fee","")),
        "권리금": row.get("premium",""), "현업종": row.get("current_use",""), "평수": str(row.get("area","")),
        "연락처": row.get("owner_phone",""), 
        "매물번호": f"{naver_no}/{serve_no}",
        "제목": row.get("memo",""), "매칭업종": row.get("manager",""), "확인메모": row.get("memo",""),
        "광고종료일": row.get("ad_end_date",""), "주차대수": str(row.get("parking","")),
        "용도": row.get("building_usage",""), "사용승인일": str(row.get("approval_date","")),
        "방/화장실": f"{rooms}/{baths}", "광고등록일": str(row.get("ad_start_date","")),
        "사진경로": row.get("photo_path",""), "소유자명": row.get("owner_name",""), "관계": row.get("owner_relation",""),
        "출처": "마이리스트(상가)", # 출처를 마이리스트(상가)로 설정
        "id": row.get("id") 
    }

def _unify_completed_deal(row):
    addr_ = (row.get("dong","") + " " + row.get("jibun","")).strip()
    naver_no = (row.get("naver_property_no","") or "").strip()
    serve_no = (row.get("serve_property_no","") or "").strip()
    curr_floor = row.get("curr_floor", 0)
    total_floor = row.get("total_floor", 0)
    deposit = row.get("deposit", 0)
    monthly = row.get("monthly", 0)
    rooms = row.get("rooms", "")
    baths = row.get("baths", "")
    return {
        "주소": addr_, "호": row.get("ho",""), "층": f"{curr_floor}/{total_floor}",
        "보증금/월세": f"{deposit}/{monthly}", "관리비": str(row.get("manage_fee","")),
        "권리금": row.get("premium",""), "현업종": row.get("current_use",""), "평수": str(row.get("area","")),
        "연락처": row.get("owner_phone",""), 
        "매물번호": f"{naver_no}/{serve_no}",
        "제목": row.get("memo",""), "매칭업종": row.get("manager",""), "확인메모": row.get("memo",""), # memo 값 사용
        "광고종료일": row.get("ad_end_date",""), "주차대수": str(row.get("parking","")),
        "용도": row.get("building_usage",""), "사용승인일": str(row.get("approval_date","")),
        "방/화장실": f"{rooms}/{baths}", "광고등록일": str(row.get("ad_start_date","")),
        "사진경로": row.get("photo_path",""), "소유자명": row.get("owner_name",""), "관계": row.get("owner_relation",""),
        "출처": "계약완료", # 출처를 계약완료로 설정
        "id": row.get("id")
    }

@router.post("/search_in_all_data")
def search_in_all_data(payload: dict = Body(...)):
    search_type = payload.get("search_type","").strip()
    keyword = payload.get("keyword","").strip()
    if not search_type or not keyword:
        return {"status":"ok","data":[]}

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        all_results = []
        like_keyword = f"%{keyword}%"
        
        search_config = {
            "serve_oneroom_data": _unify_oneroom,
            "serve_shop_data": _unify_shop,
            "naver_shop_check_confirm": _unify_confirm,
            "recommend_data": _unify_recommend,
            "mylist_shop": _unify_mylist_shop,  # _unify_shop 에서 _unify_mylist_shop 으로 변경
            "completed_deal": _unify_completed_deal  # _unify_completed_deal 추가
        }
        
        for table, unify_func in search_config.items():
            sql = f"SELECT * FROM `{table}` WHERE "
            params = []
            if search_type == "주소":
                sql += "CONCAT(REPLACE(dong,' ',''), REPLACE(jibun,' ','')) LIKE %s"
                params.append(like_keyword)
            elif search_type == "연락처":
                sql += "(owner_phone LIKE %s OR lessee_phone LIKE %s)"
                params.extend([like_keyword, like_keyword])
            elif search_type == "매물번호":
                sql += "(naver_property_no = %s OR serve_property_no = %s)"
                params.extend([keyword, keyword])
            elif search_type == "성함":
                sql += "owner_name LIKE %s"
                params.append(like_keyword)
            else:
                continue
                
            try:
                cursor.execute(sql, tuple(params))
                rows = cursor.fetchall()
                for row in rows:
                    all_results.append(unify_func(row))
            except mysql.Error as e:
                 logger.error(f"Error querying table `{table}` for search type '{search_type}': {e}")
            
        logger.info(f"Search in all data completed for type '{search_type}' keyword '{keyword}'. Found {len(all_results)} items.")
        return {"status":"ok","data": all_results}

    except mysql.Error as e:
        logger.error(f"Search in all data DB connection or cursor error: {e}")
        raise HTTPException(status_code=500, detail="데이터베이스 연결 또는 커서 오류 발생")
    except Exception as ex:
        logger.error(f"Search in all data unexpected error: {ex}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="서버 내부 오류 발생")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@router.get("/search_naver_shop_simple")
def search_naver_shop_simple(
    search_type: str = Query("전체", description='검색 타입: "전체", "주소", "매물번호"'),
    keyword: str = Query("", description="검색어"),
    within_1month: str = Query("0", description='최근 1달 이내 등록 매물만 보기 ("1" 또는 "0")')
):
    # 환경변수로 MySQL vs Supabase 선택
    use_supabase = os.environ.get("USE_SUPABASE_NAVER", "false").lower() == "true"
    
    # 디버그 로그 추가
    logger.info(f"search_naver_shop_simple API 호출 - USE_SUPABASE_NAVER: {use_supabase}")
    
    if use_supabase:
        logger.info("Supabase 경로로 실행")
        return search_naver_shop_simple_supabase(search_type, keyword, within_1month)
    else:
        logger.info("MySQL 경로로 실행")
        return search_naver_shop_simple_mysql(search_type, keyword, within_1month)

def search_naver_shop_simple_mysql(
    search_type: str = "전체",
    keyword: str = "",
    within_1month: str = "0"
):
    """MySQL 버전 - 기존 로직"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        base_sql = """
        SELECT id, gu, dong, jibun, ho, curr_floor, total_floor, deposit, monthly,
               area, naver_property_no, ad_start_date
        FROM `naver_shop` WHERE 1=1 
        """
        wheres = []
        params = []

        if keyword.strip():
            kw = keyword.strip()
            if search_type == "주소":
                wheres.append("CONCAT(dong, jibun) LIKE %s")
                params.append(f"%{kw}%")
            elif search_type == "매물번호":
                wheres.append("`naver_property_no` = %s")
                params.append(kw)
            else: # "전체"
                wheres.append("(CONCAT(dong,jibun) LIKE %s OR `naver_property_no`=%s)")
                params.append(f"%{kw}%")
                params.append(kw)

        if within_1month == "1":
            month_ago = (datetime.today() - timedelta(days=30)).date()
            wheres.append("`ad_start_date` >= %s")
            params.append(month_ago)

        if wheres:
            base_sql += " AND " + " AND ".join(wheres)

        base_sql += " ORDER BY `ad_start_date` DESC, `id` DESC LIMIT 300"
        
        cursor.execute(base_sql, tuple(params))
        rows = cursor.fetchall()
        
        return {"status": "ok", "count": len(rows), "data": rows}

    except mysql.Error as e:
        logger.error(f"Search naver_shop_simple DB error: {e}")
        raise HTTPException(status_code=500, detail="데이터베이스 오류 발생")
    except Exception as e:
        logger.error(f"Search naver_shop_simple unexpected error: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류 발생")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def search_naver_shop_simple_supabase(
    search_type: str = "전체",
    keyword: str = "",
    within_1month: str = "0"
):
    """Supabase 버전: search_naver_shop_simple"""
    try:
        supabase = get_supabase_client()
        
        # 기본 쿼리
        query = supabase.table('naver_shop').select("""
            id, gu, dong, jibun, ho, curr_floor, total_floor, 
            deposit, monthly, area, naver_property_no, ad_start_date
        """)
        
        # 키워드 검색 조건
        if keyword.strip():
            kw = keyword.strip()
            if search_type == "주소":
                # 주소 검색: dong + jibun 연결하여 검색
                # Supabase에서는 CONCAT이 제한적이므로 클라이언트에서 필터링
                pass  # 일단 모든 데이터를 가져온 후 클라이언트에서 필터링
            elif search_type == "매물번호":
                query = query.eq('naver_property_no', kw)
            else:  # "전체"
                # 전체 검색도 클라이언트에서 필터링
                pass
        
        # 1달 이내 필터
        if within_1month == "1":
            month_ago = (datetime.today() - timedelta(days=30)).date()
            query = query.gte('ad_start_date', month_ago.isoformat())
        
        # 정렬 및 제한
        query = query.order('ad_start_date', desc=True).order('id', desc=True).limit(300)
        
        result = query.execute()
        
        # 클라이언트 사이드 필터링 (주소 검색용)
        filtered_rows = []
        for row in result.data:
            # 키워드 필터링
            if keyword.strip() and search_type in ["주소", "전체"]:
                kw = keyword.strip()
                dong = row.get('dong', '') or ''
                jibun = row.get('jibun', '') or ''
                address = (dong + jibun).strip()
                naver_no = row.get('naver_property_no', '') or ''
                
                if search_type == "주소":
                    if kw not in address:
                        continue
                elif search_type == "전체":
                    if kw not in address and kw != naver_no:
                        continue
            
            filtered_rows.append(row)
        
        logger.info(f"Supabase search_naver_shop_simple 조회 성공: {len(filtered_rows)}개")
        return {"status": "ok", "count": len(filtered_rows), "data": filtered_rows}
        
    except Exception as e:
        logger.error(f"Supabase search_naver_shop_simple 조회 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Supabase 오류: {str(e)}")