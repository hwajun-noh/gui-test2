# logger_manager.py
import logging
import os
import pathlib
from logging.handlers import RotatingFileHandler

class MyListLoggerManager:
    """
    마이리스트 로깅을 관리하는 클래스
    - 기본 로그 설정
    - 파일 및 콘솔 로깅 설정
    - 로그 파일 관리
    """
    
    def __init__(self):
        """로거 매니저 초기화"""
        self.is_initialized = False
        self.initialize_logging()
    
    def initialize_logging(self):
        """로깅 설정 초기화"""
        if self.is_initialized:
            return
            
        # 루트 로거가 이미 설정되어 있는지 확인
        root_logger = logging.getLogger()
        if not root_logger.hasHandlers():
            try:
                # 항상 현재 실행 위치에 로그 파일 저장
                log_file_name = 'mylist_debug.log'
                log_file_path = os.path.join(os.getcwd(), log_file_name)

                logging.basicConfig(
                    filename=log_file_path,
                    level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
                    filemode='w'  # 실행 시마다 로그 파일 덮어쓰기 ('a'로 바꾸면 이어쓰기)
                )
                
                # 콘솔 핸들러 추가
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.INFO)
                formatter = logging.Formatter('%(levelname)s - %(message)s')
                console_handler.setFormatter(formatter)
                root_logger.addHandler(console_handler)
                
                logging.info(f"로깅이 {log_file_path}에 구성되었습니다.")
            except Exception as log_ex:
                # 파일 설정 실패 시 콘솔 로깅으로 폴백
                logging.basicConfig(
                    level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s'
                )
                logging.exception(f"[CRITICAL] 파일 로깅 구성 실패: {log_ex}. 콘솔 로깅 사용.")
        else:
            # 이미 구성된 경우 이 정보 로깅
            existing_handlers = root_logger.handlers
            logging.warning(f"로깅이 이미 구성되어 있습니다. 핸들러: {existing_handlers}")
        
        # 세부 로그 폴더 생성 및 핸들러 추가
        self._setup_detailed_logging()
        
        self.is_initialized = True
    
    def _setup_detailed_logging(self):
        """세부 로깅 설정 (flow_debug.log 등)"""
        try:
            # 로그 폴더 생성
            log_dir = pathlib.Path("logs")
            log_dir.mkdir(exist_ok=True)
            
            # flow_debug.log 파일 경로
            flow_log_path = log_dir / "flow_debug.log"
            
            # 파일 핸들러 설정
            file_handler = RotatingFileHandler(
                flow_log_path, 
                maxBytes=5*1024*1024,  # 5MB
                backupCount=3,
                encoding="utf-8"
            )
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s:%(lineno)d | %(message)s")
            file_handler.setFormatter(formatter)
            
            # root 로거에 핸들러 추가
            root_logger = logging.getLogger()
            root_logger.addHandler(file_handler)
            logging.info(f"세부 로그 핸들러가 {flow_log_path}에 추가되었습니다.")
            
        except Exception as e:
            logging.error(f"세부 로그 설정 실패: {e}", exc_info=True)
    
    def get_logger(self, name):
        """지정된 이름으로 로거 인스턴스를 반환합니다."""
        if not self.is_initialized:
            self.initialize_logging()
        
        logger = logging.getLogger(name)
        return logger