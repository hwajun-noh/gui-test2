from fastapi import APIRouter, Request
from settings import get_db_connection
import logging
import asyncio
import concurrent.futures
import time

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/get_all_data_for_addresses")
async def get_all_data_for_addresses(request: Request):
    """
    한 번의 API 호출로 모든 탭의 데이터를 가져오는 배치 엔드포인트
    
    Request body:
    {
        "addresses": ["서구 가장동 42-3", "월평동 294", ...]
    }
    
    Response:
    {
        "status": "ok",
        "data": {
            "serve_shop": [...],
            "mylist_shop": [...],
            "serve_oneroom": [...],
            "recommend": [...],
            "completed_deals": [...],
            "check_confirm": [...]
        }
    }
    """
    conn = None
    try:
        body = await request.json()
        addresses = body.get("addresses", [])
        
        print(f"[DEBUG] BatchAPI: 요청 받음")
        print(f"[DEBUG] BatchAPI: 요청 body: {body}")
        print(f"[DEBUG] BatchAPI: addresses 타입: {type(addresses)}")
        print(f"[DEBUG] BatchAPI: addresses 내용: {addresses}")
        print(f"[DEBUG] BatchAPI: addresses 길이: {len(addresses)}")
        
        # 문자열인 경우 리스트로 변환 (안전장치)
        if isinstance(addresses, str):
            print(f"[WARNING] BatchAPI: addresses가 문자열입니다. 리스트로 변환합니다.")
            addresses = [addresses]
        
        print(f"[DEBUG] BatchAPI: 최종 주소 목록 ({len(addresses)}개):")
        for i, addr in enumerate(addresses):
            print(f"[DEBUG] BatchAPI:   [{i+1}] '{addr}' (타입: {type(addr)}, 길이: {len(addr)})")
        
        if not addresses:
            print(f"[DEBUG] BatchAPI: 주소 목록이 비어있음, 빈 응답 반환")
            return {"status": "ok", "data": {
                "serve_shop": [],
                "mylist_shop": [],
                "serve_oneroom": [],
                "recommend": [],
                "completed_deals": [],
                "check_confirm": []
            }}
        
        # ⏱️ 전체 API 실행 시간 측정 시작
        api_start_time = time.time()
        print(f"[⏱️ API] API 실행 시작: {api_start_time}")
        
        # ⏱️ 주소 파싱 시간 측정
        parse_start_time = time.time()
        
        # 🔒 더 정확한 주소 매칭을 위한 조건 생성 
        # 방법 1: TRIM + 정확한 문자열 매치
        # 방법 2: dong과 jibun을 개별적으로 파싱해서 매치 (더 안전함)
        
        # 주소를 dong과 jibun으로 분리하는 함수
        def parse_address(address):
            parts = address.strip().split()
            if len(parts) >= 2:
                dong = parts[0]
                jibun = ' '.join(parts[1:])  # 지번이 여러 부분으로 나뉠 수 있음
                return dong, jibun
            return address.strip(), ""
        
        # 파싱된 주소 조건 생성
        parsed_addresses = [parse_address(addr) for addr in addresses]
        print(f"[DEBUG] BatchAPI: 주소 파싱 결과:")
        for i, (dong, jibun) in enumerate(parsed_addresses):
            print(f"[DEBUG] BatchAPI:   [{i+1}] '{addresses[i]}' → dong='{dong}', jibun='{jibun}'")
        
        # 개별 필드 매칭으로 더 정확한 조건 생성
        address_conditions = []
        address_params = []
        
        for dong, jibun in parsed_addresses:
            if jibun:  # jibun이 있는 경우
                address_conditions.append("(dong = %s AND jibun = %s)")
                address_params.extend([dong, jibun])
            else:  # jibun이 없는 경우 (dong만 있는 경우)
                address_conditions.append("(dong = %s)")
                address_params.append(dong)
        
        address_condition = " OR ".join(address_conditions)
        
        # 파싱 후 유효성 검증
        if not address_conditions or not address_params:
            print(f"[WARNING] BatchAPI: 파싱된 주소 조건이 없음, 빈 응답 반환")
            return {"status": "ok", "data": {
                "serve_shop": [],
                "mylist_shop": [],
                "serve_oneroom": [],
                "recommend": [],
                "completed_deals": [],
                "check_confirm": []
            }}
        
        print(f"[DEBUG] BatchAPI: 생성된 주소 조건: {address_condition}")
        print(f"[DEBUG] BatchAPI: 바인딩 파라미터: {tuple(address_params)}")
        print(f"[DEBUG] BatchAPI: 파라미터 개수: {len(address_params)}개")
        
        # ⏱️ 주소 파싱 완료 시간 측정
        parse_time = time.time() - parse_start_time
        print(f"[⏱️ API] 주소 파싱 완료: {parse_time:.3f}초")
        
        # ⏱️ 병렬 쿼리 시작 시간 측정
        parallel_start_time = time.time()
        print(f"[⏱️ API] 병렬 쿼리 시작...")
        
        # 🚀 병렬 처리로 6개 테이블 동시 쿼리
        print("[DEBUG] BatchAPI: 6개 테이블 병렬 쿼리 시작...")
        
        # 테이블별 쿼리 함수 정의 (상세 시간 측정)
        def query_table(table_name, table_alias, condition, params):
            local_conn = None
            try:
                # ⏱️ 1. 커넥션 생성 시간 측정
                conn_start = time.time()
                local_conn = get_db_connection()
                conn_time = time.time() - conn_start
                
                cursor = local_conn.cursor(dictionary=True)
                
                # ⏱️ 2. 쿼리 준비 및 실행 시간 측정
                query_start = time.time()
                
                # 🚀 단순화: 모든 테이블에서 전체 컬럼 조회 (SELECT *)
                sql = f"SELECT * FROM {table_name} WHERE {condition}"
                print(f"[⏱️ QUERY] {table_alias}: {sql}")
                cursor.execute(sql, tuple(params))
                query_exec_time = time.time() - query_start
                
                # ⏱️ 3. 데이터 페치 시간 측정
                fetch_start = time.time()
                results = cursor.fetchall()
                fetch_time = time.time() - fetch_start
                
                # ⏱️ 전체 시간 계산
                total_time = conn_time + query_exec_time + fetch_time
                
                print(f"[⏱️ TIME] {table_alias}: conn={conn_time:.3f}s, query={query_exec_time:.3f}s, fetch={fetch_time:.3f}s, total={total_time:.3f}s")
                print(f"[DEBUG] BatchAPI: {table_alias} 쿼리 완료: {len(results)}개")
                
                # 🔍 매치된 결과 간단 로깅 (성능 최적화)
                if results and len(results) > 0:
                    print(f"[DEBUG] BatchAPI: {table_alias} → {len(results)}개 매치")
                
                return table_alias, results
                
            except Exception as e:
                print(f"[DEBUG] BatchAPI: {table_alias} 쿼리 오류: {e}")
                logger.error(f"배치 API - {table_alias} 오류: {e}")
                return table_alias, []
            finally:
                if local_conn:
                    local_conn.close()
        
        # 병렬 실행을 위한 테이블 정의
        tables = [
            ("serve_shop_data", "serve_shop"),
            ("mylist_shop", "mylist_shop"),
            ("serve_oneroom_data", "serve_oneroom"),
            ("recommend_data", "recommend"),
            ("completed_deals", "completed_deals"),
            ("naver_shop_check_confirm", "check_confirm")
        ]
        
        # ThreadPoolExecutor로 병렬 처리 (워커 수 최적화)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            # 모든 테이블을 병렬로 쿼리
            futures = {
                executor.submit(query_table, table_name, table_alias, address_condition, address_params): table_alias
                for table_name, table_alias in tables
            }
            
            # 결과 수집
            result_data = {}
            for future in concurrent.futures.as_completed(futures):
                table_alias, data = future.result()
                result_data[table_alias] = data
        
        # ⏱️ 병렬 쿼리 완료 시간 측정
        parallel_time = time.time() - parallel_start_time
        print(f"[⏱️ API] 병렬 쿼리 완료: {parallel_time:.3f}초")
        
        # ⏱️ 응답 데이터 생성 시간 측정 시작
        response_start_time = time.time()
        
        # 특별히 serve_shop 첫 번째 항목 로깅 (기존 로직 유지)
        if result_data.get("serve_shop") and len(result_data["serve_shop"]) > 0:
            sample = result_data["serve_shop"][0]
            addr_str = f"{sample.get('dong')} {sample.get('jibun')}"
            print(f"[DEBUG] BatchAPI: serve_shop 첫 번째 항목 주소: '{addr_str}'")
            
        print(f"[DEBUG] BatchAPI: 최종 결과 요약:")
        total_items = 0
        for key, data in result_data.items():
            print(f"[DEBUG] BatchAPI:   {key}: {len(data)}개")
            total_items += len(data)
        print(f"[DEBUG] BatchAPI: 전체 {total_items}개 항목 반환")
        
        logger.info(f"배치 API 완료 - 총 {len(addresses)}개 주소에 대한 모든 데이터 로드")
        
        response_data = {
            "status": "ok", 
            "data": result_data,
            "addresses": addresses
        }
        
        print(f"[DEBUG] BatchAPI: 응답 데이터 구조: {list(response_data.keys())}")
        
        # ⏱️ 응답 데이터 생성 완료 시간 측정
        response_time = time.time() - response_start_time
        print(f"[⏱️ API] 응답 데이터 생성: {response_time:.3f}초")
        
        # ⏱️ 전체 API 완료 시간 측정
        total_api_time = time.time() - api_start_time
        print(f"[⏱️ API] 전체 API 완료: {total_api_time:.3f}초")
        print(f"[⏱️ API] 시간 분석 - 파싱:{parse_time:.3f}s + 쿼리:{parallel_time:.3f}s + 응답:{response_time:.3f}s = 총:{total_api_time:.3f}s")
        
        return response_data
        
    except Exception as e:
        logger.error(f"배치 API 전체 오류: {e}")
        return {
            "status": "error", 
            "message": str(e),
            "data": {
                "serve_shop": [],
                "mylist_shop": [],
                "serve_oneroom": [],
                "recommend": [],
                "completed_deals": [],
                "check_confirm": []
            }
        }
        
    finally:
        # 병렬 처리에서는 각 스레드가 자체 커넥션을 관리하므로 여기서 추가 정리 불필요
        pass 


