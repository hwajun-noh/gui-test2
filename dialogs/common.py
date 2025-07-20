# dialogs/common.py

import os
import sys
from dotenv import load_dotenv

# PyQt5 기본 모듈 (필요에 따라 추가)
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt

def resource_path(relative_path: str) -> str:
    """
    PyInstaller 빌드된 실행파일이면, 
    sys._MEIPASS 경로 아래에서 relative_path를 찾는다.
    개발 환경이면, 현재 .py 파일이 있는 위치(__file__ 기준)에서 relative_path를 찾는다.
    """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    else:
        # Not bundled, use the normal path relative to this common.py file
        # Assuming common.py is in the 'dialogs' directory
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Construct the full path
    # If relative_path starts with 'static', adjust base path accordingly if needed
    # Example: If static is outside the dialogs dir
    if relative_path.startswith('static') or relative_path.startswith('static/') or relative_path.startswith('static\\'):
         # Assume static is at the project root (one level above dialogs)
         project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
         return os.path.join(project_root, relative_path)
         
    return os.path.join(base_path, relative_path)

def is_pyinstaller_exe() -> bool:
    return hasattr(sys, '_MEIPASS')

# Load environment variables
if is_pyinstaller_exe():
    env_file_name = ".env.production"
else:
    env_file_name = ".env.development"

# Correctly locate static directory relative to this common.py file
# Assuming static is one level above the dialogs directory
static_dir_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
env_path = os.path.join(static_dir_path, env_file_name)

# Check if the .env file exists before loading
if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"Loaded environment variables from: {env_path}")
else:
    print(f"Warning: Environment file not found at {env_path}. Using defaults.")

# Get environment variables with defaults
SERVER_HOST_CONNECT = os.environ.get("SERVER_HOST_CONNECT", "localhost")
SERVER_PORT_DEFAULT = int(os.environ.get("SERVER_PORT_DEFAULT", "8000"))

print(f"[Common] SERVER_HOST_CONNECT: {SERVER_HOST_CONNECT}")
print(f"[Common] SERVER_PORT_DEFAULT: {SERVER_PORT_DEFAULT}")
