"""
마이리스트 원룸 데이터 로더
"""
import logging
import requests
from PyQt5.QtCore import QObject, pyqtSignal

class OneRoomLoader(QObject):
    """원룸 데이터 로더 클래스"""
    
    dataLoaded = pyqtSignal(list)
    loadError = pyqtSignal(str)
    
    def __init__(self, server_host, server_port, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.server_host = server_host
        self.server_port = server_port
        
    def load_data(self, manager, role):
        """
        원룸 데이터 로드
        
        Args:
            manager (str): 담당자 이름
            role (str): 사용자 역할 (admin/manager)
            
        Returns:
            list: 원룸 데이터 목록
        """
        try:
            url = f"http://{self.server_host}:{self.server_port}/mylist/get_mylist_oneroom_data"
            params = {"manager": manager, "role": role}
            
            self.logger.info(f"원룸 데이터 로드 중: URL={url}, 매니저={manager}, 역할={role}")
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            
            result = resp.json()
            
            if result.get("status") == "ok":
                rows = result.get("data", [])
                self.logger.info(f"원룸 데이터 {len(rows)}개 로드 완료")
                self.dataLoaded.emit(rows)
                return rows
            else:
                error_msg = result.get("message", "알 수 없는 오류")
                self.logger.error(f"원룸 데이터 로드 실패: {error_msg}")
                self.loadError.emit(f"데이터 로드 실패: {error_msg}")
                return []
                
        except requests.RequestException as e:
            error_msg = f"서버 요청 오류: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.loadError.emit(error_msg)
            return []
            
        except Exception as e:
            error_msg = f"예상치 못한 오류: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.loadError.emit(error_msg)
            return [] 