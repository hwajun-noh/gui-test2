import logging
import os
from dotenv import load_dotenv
# server_utils에서 함수 임포트
from server_utils import resource_path, is_pyinstaller_exe

# --- 로깅 설정 --- 
log_level = logging.DEBUG
log_format = "%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"
logging.basicConfig(level=log_level, format=log_format, force=True)
logger = logging.getLogger(__name__)
logger.info(f"Server logging configured to level: {logging.getLevelName(log_level)}")
# --- 로깅 설정 끝 ---

# --- .env 파일 로딩 --- 
# settings.py 파일이 있는 디렉토리
current_dir = os.path.dirname(os.path.abspath(__file__)) 

# 우선순위: 1) 메인 디렉토리의 .env, 2) static 폴더의 환경별 파일
main_env_path = os.path.join(current_dir, ".env")

if os.path.exists(main_env_path):
    load_dotenv(main_env_path, override=True)
    logger.info(f"Loaded environment variables from: {main_env_path}")
else:
    # 기존 방식 fallback
    if is_pyinstaller_exe():
        env_file_name = ".env.production"
    else:
        env_file_name = ".env.development"
    
    env_path = os.path.join(current_dir, "static", env_file_name)
    load_dotenv(env_path, override=True)
    logger.info(f"Loaded environment variables from: {env_path}")

# 로드된 환경변수 확인 로그 추가
shop_env = os.environ.get("USE_SUPABASE_SHOP", "not_found")
oneroom_env = os.environ.get("USE_SUPABASE_ONEROOM", "not_found")
naver_env = os.environ.get("USE_SUPABASE_NAVER", "not_found")
logger.info(f"Environment variables loaded - SHOP: {shop_env}, ONEROOM: {oneroom_env}, NAVER: {naver_env}")

# --- 서버 설정 --- 
SERVER_HOST_DEFAULT = os.environ.get("SERVER_HOST_DEFAULT", "localhost")
SERVER_PORT_DEFAULT = int(os.environ.get("SERVER_PORT_DEFAULT", "8001"))

# --- MySQL DB 설정 (기존 유지) --- 
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "a13030z0!!")
DB_NAME = os.environ.get("DB_NAME", "mydb")
DB_CHARSET = os.environ.get("DB_CHARSET", "utf8mb4")

# --- Supabase 설정 (새로 추가) ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
USE_SUPABASE_SHOP = os.environ.get("USE_SUPABASE_SHOP", "false").lower() == "true"

# Supabase 클라이언트 초기화
supabase_client = None
if SUPABASE_URL and SUPABASE_ANON_KEY:
    try:
        from supabase import create_client, Client
        import httpx
        
        # HTTP/2 오류 해결을 위해 HTTP/1.1 사용
        transport = httpx.HTTPTransport(http2=False)
        client = httpx.Client(transport=transport)
        
        # 커스텀 HTTP 클라이언트로 Supabase 클라이언트 생성
        supabase_client: Client = create_client(
            supabase_url=SUPABASE_URL, 
            supabase_key=SUPABASE_ANON_KEY,
            options={
                "httpx_client": client
            }
        )
        logger.info("Supabase client initialized successfully with HTTP/1.1")
    except ImportError:
        logger.warning("Supabase library not installed. Run: pip install supabase")
        supabase_client = None
    except (TypeError, Exception) as e:
        # 파라미터 이슈 처리 - 가장 간단한 방식
        try:
            supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            logger.info("Supabase client initialized with simple parameters")
        except Exception as e2:
            logger.warning(f"Supabase client initialization failed: {e2}")
            logger.warning("Continuing without Supabase client - USE_SUPABASE_SHOP will be ignored")
            supabase_client = None
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        supabase_client = None
else:
    logger.warning("Supabase credentials not found in environment variables")

def get_db_connection():
    """기존 MySQL 연결 함수 (하위 호환성 유지)"""
    import mysql.connector as mysql
    try:
        conn = mysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset=DB_CHARSET,
            use_unicode=True
        )
        return conn
    except mysql.Error as e:
        # logger.error(f"Database connection error: {e}")
        logger.exception(f"Database connection mysql.Error: {e}") # 스택 트레이스 포함 로깅
        raise  # 연결 실패 시 에러를 다시 발생시켜 호출 측에서 알 수 있도록 함 
    except Exception as e:
        logger.exception(f"Database connection general Exception: {e}") # 다른 예외도 상세 로깅
        raise # 연결 실패 시 에러를 다시 발생시켜 호출 측에서 알 수 있도록 함 

def get_supabase_client():
    """Supabase 클라이언트 반환"""
    if supabase_client is None:
        raise Exception("Supabase client is not initialized. Check your credentials.")
    return supabase_client 