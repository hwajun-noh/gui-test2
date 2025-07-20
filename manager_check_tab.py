import logging

# 모듈화된 ManagerCheckTab 클래스 임포트
from manager_tabs import ManagerCheckTab

# 로깅 설정
logger = logging.getLogger(__name__)

# 재내보내기 설정 - 기존 코드와의 호환성을 위해
__all__ = ['ManagerCheckTab']

