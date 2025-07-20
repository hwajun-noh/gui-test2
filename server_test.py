# server_test.py (Refactored)
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
from dotenv import load_dotenv # dotenv 임포트 추가
# --- 경로 로깅 코드 추가 ---
import sys
# --- 경로 로깅 코드 추가 ---

# --- resource_path 및 is_pyinstaller_exe 함수 정의 추가 ---
def resource_path(relative_path: str) -> str:
    """
    PyInstaller 빌드된 실행파일이면, 
    sys._MEIPASS 경로 아래에서 relative_path를 찾는다.
    개발 환경이면, 현재 .py 파일이 있는 위치(__file__ 기준)에서 relative_path를 찾는다.
    """
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def is_pyinstaller_exe() -> bool:
    import sys
    return hasattr(sys, '_MEIPASS')
# --- 함수 정의 추가 완료 ---

# --- .env 파일 로딩 로직 추가 ---
if is_pyinstaller_exe():
    env_file_name = ".env.production"
else:
    env_file_name = ".env.development"

# .env 파일이 static 폴더 안에 있다고 가정
env_path = resource_path(os.path.join("static", env_file_name))

if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"Loaded environment variables from: {env_path}") # 로깅 대신 print 사용 (로거 설정 전일 수 있음)
else:
    print(f"Warning: Environment file not found at {env_path}")
# --- .env 파일 로딩 완료 ---

# 설정 및 유틸리티 임포트
# settings.py에서 필요한 설정값과 로거를 가져옵니다.
from settings import SERVER_HOST_DEFAULT, SERVER_PORT_DEFAULT, logger
# server_utils.py에서 resource_path 함수를 가져옵니다.
# resource_path 사용 여부는 static_dir 설정 방식에 따라 결정됩니다.
# from server_utils import resource_path

# 라우터 임포트
# routers 패키지 내의 각 모듈에서 APIRouter 인스턴스를 가져옵니다.
from routers import (
    auth_router, customer_router, shop_router, recommend_router,
    mylist_router, completed_router, manager_router, websocket_router
)
# 배치 처리 라우터 추가
from routers.batch import router as batch_router

# --- mylist 모듈 로드 경로 확인 로그 추가 ---
import importlib
mylist_module = importlib.import_module("routers.mylist")
try:
    logger.info(f"Imported mylist router from: {mylist_module.__file__}")
except AttributeError:
    logger.warning("Could not determine path for imported 'mylist' module.")
# --- mylist 모듈 로드 경로 확인 로그 추가 ---

# --- FastAPI 앱 인스턴스 생성 ---
# --- 경로 로깅 코드 추가 ---
logger.info(f"--- Server Starting ---")
logger.info(f"Current Working Directory: {os.getcwd()}")
logger.info(f"Python Executable: {sys.executable}")
logger.info(f"Python Path: {sys.path}")
logger.info(f"__file__: {__file__}")
# --- 경로 로깅 코드 추가 ---
app = FastAPI()
logger.info("FastAPI application created.")

# --- CORS 미들웨어 추가 --- 
# 주의: 개발 중에는 origins="*" 로 모든 출처를 허용할 수 있지만,
# 실제 배포 시에는 보안을 위해 프론트엔드 출처만 명시하는 것이 좋습니다.
origins = [
    "http://localhost", # 필요하다면 localhost의 다른 포트도 추가
    "http://localhost:5500",
    "http://127.0.0.1", 
    "http://127.0.0.1:5500",
    "null" # file:// 에서 열 경우 origin이 null일 수 있음
    # 실제 프론트엔드 배포 주소 추가
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # 허용할 출처 목록
    allow_credentials=True, # 쿠키 포함 요청 허용 여부
    allow_methods=["*"], # 허용할 HTTP 메소드 (GET, POST, ...) 
    allow_headers=["*"], # 허용할 HTTP 헤더 
)
logger.info(f"Added CORS middleware with allowed origins: {origins}")
# --- CORS 미들웨어 추가 완료 ---

# --- 정적 파일 마운트 (resource_path 사용) ---
try:
    static_dir = resource_path("static") 
    if not os.path.isdir(static_dir):
         logger.warning(f"Static directory not found at: {static_dir}. Static files may not be served.")
         # 필요시 기본 경로 설정 또는 에러 발생
         # static_dir = "./static" # 예: 기본 경로
    else:
        app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")
        logger.info(f"Mounted static directory at /static from: {static_dir}")
except Exception as e:
     logger.error(f"Failed to mount static directory '{static_dir}': {e}")
# --- 정적 파일 마운트 완료 ---

# --- 라우터 포함 ---
# 각 기능별 라우터를 FastAPI 앱에 등록합니다.
# API 문서 구성을 위해 prefix와 tags를 추가하는 것이 좋습니다.
app.include_router(auth_router, tags=["Authentication"])
app.include_router(customer_router, prefix="/customer", tags=["Customer Management"])
app.include_router(shop_router, prefix="/shop", tags=["Shop/Property Search"])
app.include_router(recommend_router, prefix="/recommend", tags=["Recommendations"])
app.include_router(mylist_router, prefix="/mylist", tags=["My List"])
app.include_router(completed_router, prefix="/completed", tags=["Completed Deals"])
app.include_router(manager_router, prefix="/manager", tags=["Manager Info"])
app.include_router(websocket_router) # WebSocket은 일반적으로 prefix 없이 사용
app.include_router(batch_router, prefix="/batch", tags=["Batch Operations"])
logger.info("Included all routers.")
# --- 서버 준비 완료 로그 추가 ---
logger.info("--- Server Ready ---")
# --- 서버 준비 완료 로그 추가 ---

# --- 서버 실행 ---
if __name__ == "__main__":
    logger.info(f"Starting server on http://{SERVER_HOST_DEFAULT}:{SERVER_PORT_DEFAULT}")
    # settings.py에서 가져온 호스트 및 포트 정보 사용
    # uvicorn.run(app, host=SERVER_HOST_DEFAULT, port=SERVER_PORT_DEFAULT)
    # 개발 시 reloader 활성화: uvicorn server_test:app --reload
    # 아래 uvicorn.run은 프로덕션 또는 간단한 실행용입니다.
    # reload=True 옵션은 if __name__ == "__main__": 블록 내에서는 권장되지 않습니다.
    uvicorn.run("server_test:app", host=SERVER_HOST_DEFAULT, port=SERVER_PORT_DEFAULT, reload=False) # reload=False가 기본값 