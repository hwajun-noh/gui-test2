"""
마이리스트 계약완료 데이터 로더

계약완료된 매물 정보 데이터 로딩 기능 제공
"""
import logging
import json
import requests
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal, QThread

class CompletedDealLoader(QObject):
    """계약완료 데이터 로더 클래스"""
    
    # 시그널 정의
    dataLoaded = pyqtSignal(list)  # 데이터 로드 완료 시 (리스트)
    loadError = pyqtSignal(str)  # 로드 오류 시 (오류 메시지)
    loadProgress = pyqtSignal(int, int)  # 진행 상황 (현재, 전체)
    
    def __init__(self, server_host="localhost", server_port=8000, parent=None):
        """
        초기화
        
        Args:
            server_host (str): 서버 호스트
            server_port (int): 서버 포트
            parent: 부모 객체
        """
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        
        # 서버 정보
        self.server_host = server_host
        self.server_port = server_port
        self.api_url = f"http://{server_host}:{server_port}/api"
        
        # 로딩 스레드
        self.load_thread = None
        
    def load_data(self, manager=None, role=None, days=30):
        """
        데이터 로드
        
        Args:
            manager (str): 담당자 이름
            role (str): 사용자 역할
            days (int): 최근 몇 일의 데이터를 로드할지
        """
        # 이전 스레드가 실행 중이면 종료
        if self.load_thread and self.load_thread.isRunning():
            self.logger.warning("이전 로드 작업이 진행 중입니다. 중단 후 재시작합니다.")
            self.load_thread.terminate()
            
        # 새 로드 스레드 시작
        self.load_thread = LoadThread(self.api_url, manager, role, days)
        self.load_thread.dataLoaded.connect(self._on_data_loaded)
        self.load_thread.loadError.connect(self._on_load_error)
        self.load_thread.loadProgress.connect(self._on_load_progress)
        self.load_thread.start()
        
    def _on_data_loaded(self, data):
        """
        데이터 로드 완료 처리
        
        Args:
            data (list): 로드된 데이터
        """
        self.logger.info(f"계약완료 데이터 {len(data)}개 로드 완료")
        self.dataLoaded.emit(data)
        
    def _on_load_error(self, error_msg):
        """
        로드 오류 처리
        
        Args:
            error_msg (str): 오류 메시지
        """
        self.logger.error(f"계약완료 데이터 로드 오류: {error_msg}")
        self.loadError.emit(error_msg)
        
    def _on_load_progress(self, current, total):
        """
        로드 진행 상황 처리
        
        Args:
            current (int): 현재 처리 수
            total (int): 전체 처리 수
        """
        self.logger.debug(f"계약완료 데이터 로드 진행: {current}/{total}")
        self.loadProgress.emit(current, total)
        
class LoadThread(QThread):
    """데이터 로드 스레드"""
    
    # 시그널 정의
    dataLoaded = pyqtSignal(list)
    loadError = pyqtSignal(str)
    loadProgress = pyqtSignal(int, int)
    
    def __init__(self, api_url, manager=None, role=None, days=30):
        """
        초기화
        
        Args:
            api_url (str): API URL
            manager (str): 담당자 이름
            role (str): 사용자 역할
            days (int): 최근 몇 일의 데이터를 로드할지
        """
        super().__init__()
        self.logger = logging.getLogger(f"{__name__}.LoadThread")
        
        self.api_url = api_url
        self.manager = manager
        self.role = role
        self.days = days
        
    def run(self):
        """스레드 실행"""
        try:
            # API 요청 준비
            url = f"{self.api_url}/completed_deals"
            params = {}
            
            # 파라미터 설정
            if self.manager and self.manager.lower() != "admin":
                params["manager"] = self.manager
                
            if self.days > 0:
                params["days"] = self.days
                
            self.logger.info(f"계약완료 데이터 로드 시작: {url} (params: {params})")
            
            # 요청 보내기
            response = requests.get(url, params=params, timeout=30)
            
            # 응답 처리
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and "results" in data:
                    results = data["results"]
                    total = data.get("total", len(results))
                    
                    self.logger.info(f"계약완료 데이터 {len(results)}개 수신 (total: {total})")
                    
                    # 데이터 처리 및 진행 상황 보고
                    processed_data = []
                    for i, item in enumerate(results):
                        # 날짜 형식 변환
                        if "contract_date" in item and item["contract_date"]:
                            try:
                                date_obj = datetime.fromisoformat(item["contract_date"].replace("Z", "+00:00"))
                                item["contract_date"] = date_obj.strftime("%Y-%m-%d")
                            except ValueError:
                                pass
                                
                        processed_data.append(item)
                        
                        # 진행 상황 보고 (10% 단위)
                        if i % max(1, len(results) // 10) == 0:
                            self.loadProgress.emit(i, len(results))
                            
                    # 처리 완료
                    self.loadProgress.emit(len(results), len(results))
                    self.dataLoaded.emit(processed_data)
                else:
                    self.dataLoaded.emit([])
            else:
                self.loadError.emit(f"서버 오류: {response.status_code} {response.reason}")
                
        except requests.RequestException as e:
            self.loadError.emit(f"요청 오류: {e}")
        except Exception as e:
            self.loadError.emit(f"데이터 로드 중 오류 발생: {e}")
            self.logger.error(f"데이터 로드 중 예외 발생: {e}", exc_info=True) 