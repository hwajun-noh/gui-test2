# mylist_container.py
"""
마이리스트 컨테이너 모듈 (리팩토링 버전)
모듈화된 코드를 사용하여 클래스 및 함수를 재구성합니다.
"""

# 외부 모듈 가져오기
from PyQt5.QtCore import QObject

# 내부 리팩토링된 모듈 가져오기
from mylist.base_container import MyListContainer as BaseMyListContainer

# 필요하면 추가 모듈 가져오기
# from mylist.oneroom import OneRoomModel, OneRoomCommands
# from mylist.completed import CompletedModel, CompletedCommands

class MyListContainer(BaseMyListContainer):
    """
    마이리스트 컨테이너 클래스 
    - 상가, 원룸, 계약완료 탭을 관리
    - 데이터 로딩 및 표시
    - 상태 변경 처리
    """
    
    def __init__(self, parent_app=None, manager=None, role=None, server_host=None, server_port=None):
        """
        마이리스트 컨테이너 초기화
        
        Args:
            parent_app: 부모 애플리케이션 참조
            manager: 담당자 정보
            role: 사용자 역할
            server_host: 서버 호스트
            server_port: 서버 포트
        """
        # 기본 클래스 초기화
        super().__init__(parent_app, manager, role, server_host, server_port)
        self.logger.info("MyListContainer initialized with modularized structure")
        
    # 각 메서드는 base_container.py 또는 해당 모듈에 있는 메서드를 그대로 사용
    # 여기서는 추가적인 사용자 정의 동작만 구현
        
    def load_initial_data(self):
        """모든 탭의 초기 데이터를 로드합니다."""
        self.logger.info("MyListContainer: Loading initial data for all tabs.")
        # 이미 init_tabs 메서드에서 초기 데이터 로딩을 수행함
        
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    container = MyListContainer(parent_app=None, manager="test", role="admin", server_host="localhost", server_port=8000)
    container.get_widget().show()
    sys.exit(app.exec_())