# loaders.py - 상가 데이터 로딩 관련 모듈
import time
import requests
import logging
from PyQt5.QtCore import Qt, QObject, pyqtSignal

# 로거 인스턴스
logger = logging.getLogger(__name__)

class SangaDataLoader(QObject):
    """
    상가 데이터 로더 클래스
    
    서버에서 상가 데이터를 비동기적으로 로드하는 기능을 제공합니다.
    """
    # 데이터 로딩 완료 시그널
    loading_completed = pyqtSignal(dict)
    
    def __init__(self, logic_instance):
        """
        초기화
        
        Args:
            logic_instance: 상가 로직 인스턴스
        """
        super().__init__(parent=None)  # 부모를 None으로 설정
        self.logic = logic_instance
        self.parent_app = logic_instance.parent_app
        self.server_host = self.parent_app.server_host
        self.server_port = self.parent_app.server_port
    
    def load_data(self, manager=None, filters=None):
        """
        데이터 로딩 실행
        
        Args:
            manager: 담당자 필터 (없으면 전체)
            filters: 추가 필터 조건
        """
        # 매니저 정보 설정
        current_manager = manager or self.logic.parent_app.current_manager
        current_role = self.logic.parent_app.current_role
        
        logger.info(f"bg_load_mylist_shop_data: Fetching for manager='{current_manager}', role='{current_role}'")
        
        # 백그라운드 작업 실행
        future = self.parent_app.executor.submit(
            self._bg_load_mylist_shop_data,
            current_manager,
            current_role,
            filters
        )
        
        # 콜백 설정
        future.add_done_callback(self._handle_load_completion)
    
    def _bg_load_mylist_shop_data(self, manager, role, filters=None):
        """
        (백그라운드 스레드) GET 요청을 통해 마이리스트 상가 데이터를 가져옵니다.
        """
        url = f"http://{self.server_host}:{self.server_port}/mylist/get_all_mylist_shop_data"
        params = {"manager": manager, "role": role}
        
        # 추가 필터 적용
        if filters:
            params.update(filters)
        
        try:
            logger.debug(f"bg_load_mylist_shop_data: Sending GET request to {url} with params: {params}")
            resp = requests.get(url, params=params, timeout=10)
            logger.debug(f"bg_load_mylist_shop_data: Received response status {resp.status_code}")
            resp.raise_for_status()
            j = resp.json()
            
            status = j.get('status')
            logger.info(f"bg_load_mylist_shop_data: API response status='{status}'.")
            
            if status != "ok":
                logger.error(f"bg_load_mylist_shop_data: API error - Status: {status}, Message: {j.get('message')}")
                return {"status": "error", "data": [], "message": j.get('message')}
            
            data_len = len(j.get('data', []))
            logger.info(f"bg_load_mylist_shop_data: Successfully fetched {data_len} rows.")
            return {"status": "ok", "data": j.get("data", [])}
            
        except requests.Timeout:
            logger.error("bg_load_mylist_shop_data: Request timed out.", exc_info=True)
            return {"status": "exception", "message": "Request timed out", "data": []}
            
        except requests.RequestException as ex:
            logger.error(f"bg_load_mylist_shop_data: RequestException - {ex}", exc_info=True)
            return {"status": "exception", "message": str(ex), "data": []}
            
        except Exception as ex_other:
            logger.error(f"bg_load_mylist_shop_data: Unexpected error - {ex_other}", exc_info=True)
            return {"status": "exception", "message": f"Unexpected error: {ex_other}", "data": []}
    
    def _handle_load_completion(self, future):
        """
        (콜백 함수) 로딩 완료 처리
        
        future.result()의 결과를 메인 스레드로 전달하기 위해
        시그널을 발생시킵니다.
        """
        try:
            result = future.result()
            
            # 데이터 로딩 완료 시그널 발생
            # 이 시그널은 _process_fetched_data_slot에 연결되어 있어야 함
            self.loading_completed.emit(result)
            
        except Exception as e:
            logger.error(f"데이터 로딩 콜백 오류: {e}", exc_info=True)
            
            # 오류 발생 시에도 시그널은 발생시켜 처리할 수 있게 함
            self.loading_completed.emit({
                "status": "exception", 
                "message": f"콜백 처리 오류: {e}", 
                "data": []
            })

def get_api_endpoint(server_host, server_port):
    """상가 데이터 가져오기 API 엔드포인트를 반환합니다."""
    return f"http://{server_host}:{server_port}/mylist/get_all_mylist_shop_data"