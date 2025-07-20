import os
import sys
from datetime import datetime, timedelta

def resource_path(relative_path: str) -> str:
    """
    PyInstaller 빌드된 실행파일이면,
    sys._MEIPASS 경로 아래에서 relative_path를 찾는다.
    개발 환경이면, 현재 .py 파일이 있는 위치(__file__ 기준)에서 relative_path를 찾는다.
    """
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        # 주의: 이 함수가 server_utils.py로 이동하면 __file__ 기준 경로가 달라질 수 있습니다.
        #       프로젝트 루트 기준 상대 경로를 사용하도록 조정이 필요할 수 있습니다.
        #       일단은 원래 로직 유지. settings.py에서 env 파일 경로 설정 시 주의.
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def is_pyinstaller_exe() -> bool:
    import sys
    return hasattr(sys, '_MEIPASS')

def get_today_string():
    return datetime.now().strftime("%Y-%m-%d")

def get_week_later_string():
    return (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d") 