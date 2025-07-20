# base_container.py
import logging
import os
import pathlib
import threading
import time
import requests
from concurrent.futures import ThreadPoolExecutor

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QTimer, Q_ARG, QObject, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (QTabWidget, QMessageBox, QLabel, QVBoxLayout, 
                            QSplitter, QWidget, QTableView, QHeaderView)
from PyQt5.QtGui import QStandardItemModel, QStandardItem

# 다른 모듈 가져오기
from mylist.logger_manager import MyListLoggerManager
from mylist.row_manager import MyListRowManager
from mylist.status_handler import MyListStatusHandler
from mylist.naver_checker import MyListNaverChecker

# 기존 로직 클래스
# from mylist_sanga_logic import MyListSangaLogic  # 상가 모듈화 진행 중
# from mylist_oneroom_logic import MyListOneroomLogic # 원룸 모듈화 진행 중
# from mylist_completed_logic import MyListCompletedLogic # 계약완료 모듈화 진행 중

# 모듈화된 클래스 (단계적 전환)
from mylist.sanga.__compatibility import SangaBridge  # 상가 호환성 레이어
from mylist.oneroom.__compatibility import OneRoomBridge # 원룸 호환성 레이어
from mylist.completed.__compatibility import CompletedDealBridge # 계약완료 호환성 레이어

# 기존 리팩토링 클래스
from mylist_pending_manager import MyListPendingManager
from mylist_save_handler import MyListSaveHandler

from mylist_constants import RE_AD_BG_COLOR, NEW_AD_BG_COLOR

class MyListContainer(QObject):
    """
    마이리스트 컨테이너 - 상가, 원룸, 계약완료 탭을 관리하는 컨테이너 클래스
    """
    # 시그널 정의: API 결과(dict), 제거할 UI 행 인덱스(list), 탭 종류(str)
    statusChangeCompleteSignal = pyqtSignal(dict, list, str)

    def __init__(self, parent_app=None, manager=None, role=None, server_host=None, server_port=None):
        super().__init__()
        self.parent_app = parent_app
        self.current_manager = manager
        self.current_role = role
        self.server_host = server_host
        self.server_port = server_port

        # Logger 매니저 초기화
        self.logger_manager = MyListLoggerManager()
        self.logger = self.logger_manager.get_logger(__name__)
        self.logger.debug(f"MyListContainer.__init__: Received manager='{manager}' (Type: {type(manager)})")

        # 서버 설정은 이미 초기화 파라미터로 설정됨
        print(f"[DEBUG] MyListContainer: 서버 설정 - {self.server_host}:{self.server_port}")

        # 🚀 HTTP 세션 및 스레드풀 초기화 (배치 API용)
        # parent_app의 HTTP 세션을 재사용하여 연결 풀 공유
        if hasattr(parent_app, 'http_session') and parent_app.http_session:
            self.http_session = parent_app.http_session
            print(f"[DEBUG] MyListContainer: parent_app의 HTTP 세션 재사용")
        else:
            # fallback: 독립적인 HTTP 세션 생성
            self.http_session = requests.Session()
            self.http_session.mount('http://', requests.adapters.HTTPAdapter(
                pool_connections=10,
                pool_maxsize=10,
                max_retries=3
            ))
            print(f"[DEBUG] MyListContainer: 독립적인 HTTP 세션 생성")
            
        # parent_app의 ThreadPoolExecutor를 재사용하여 리소스 공유
        if hasattr(parent_app, 'executor') and parent_app.executor:
            self.executor = parent_app.executor
            print(f"[DEBUG] MyListContainer: parent_app의 ThreadPoolExecutor 재사용")
        else:
            # fallback: 독립적인 ThreadPoolExecutor 생성
            self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="MyList-Batch")
            print(f"[DEBUG] MyListContainer: 독립적인 ThreadPoolExecutor 생성")

        # 컴포넌트 및 매니저 초기화
        self._initialize_managers()
        
        # 🔧 수정: 단일 테이블 구조로 복원 (매물체크탭과 동일)
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout(self.main_widget)
        
        # 마이리스트 탭들만 표시 (하단 테이블은 main_app에서 처리)
        self.mylist_tabs = QTabWidget()
        self.main_layout.addWidget(self.mylist_tabs)
        
        # 하단 테이블 제거 (main_app에서 처리됨)
        self.bottom_table_widget = None
        self.splitter = None
        
        # 탭 초기화
        self.init_tabs()
        
        # 시그널 연결
        self._connect_signals()
        
        # 테이블 선택 시그널 연결 (탭 초기화 후)
        QTimer.singleShot(1000, self._connect_table_selection_signals)  # 1초 후 연결
        
        # 타이머 시작
        self.start_timers()
    
    def _initialize_managers(self):
        """내부 매니저 초기화 함수"""
        # 기본 매니저 초기화
        self.pending_manager = MyListPendingManager(parent=self)
        
        server_info = {'host': self.server_host, 'port': self.server_port}
        user_info = {'manager': self.current_manager, 'role': self.current_role}
        
        # 로직 클래스 초기화 (모두 호환성 레이어 사용)
        self.sanga_logic = SangaBridge(self.parent_app, self)
        
        # 원룸 로직 초기화 (호환성 레이어 사용)
        # self.oneroom_logic = MyListOneroomLogic(self.parent_app, self)  # 기존 방식
        self.oneroom_logic = OneRoomBridge(self.parent_app, self)  # 호환성 레이어 방식
        
        # 계약완료 로직 초기화 (호환성 레이어 사용)
        # self.completed_logic = MyListCompletedLogic(self.parent_app, self)  # 기존 방식
        self.completed_logic = CompletedDealBridge(self.parent_app, self)  # 호환성 레이어 방식
        
        # 저장 핸들러 초기화
        self.save_handler = MyListSaveHandler(self.parent_app, self, self.pending_manager, 
                                          self.sanga_logic, self.oneroom_logic, 
                                          server_info, user_info, parent=self)
        
        # 추가 관리자 초기화
        self.row_manager = MyListRowManager(self)
        self.status_handler = MyListStatusHandler(self)
        self.naver_checker = MyListNaverChecker(self)
    
    def _connect_signals(self):
        """시그널 연결 함수"""
        # 저장 핸들러 UI 정리 시그널 연결
        self.save_handler.cleanup_needed.connect(self._perform_ui_cleanup)
        
        # 상태 변경 완료 시그널 연결
        self.statusChangeCompleteSignal.connect(self._process_status_change_slot)
        
        # 상단 테이블 선택 시그널은 탭 초기화 후 지연 연결됨
    
    def get_widget(self):
        """Returns the main widget with splitter for embedding."""
        return self.main_widget
    
    # 하단 테이블 제거됨 - main_app에서 처리

    def init_tabs(self):
        """Initializes the individual tabs using their logic classes."""
        # 상가(새광고) 탭
        sanga_widget = self.sanga_logic.init_ui()
        self.mylist_tabs.addTab(sanga_widget, "상가(새광고)")

        # 원룸(새광고) 탭
        oneroom_widget = self.oneroom_logic.init_ui()
        self.mylist_tabs.addTab(oneroom_widget, "원룸(새광고)")

        # 계약완료 탭
        completed_widget = self.completed_logic.init_ui()
        self.mylist_tabs.addTab(completed_widget, "계약완료")

        # [제거됨] Load initial data for each tab
        # 성능 최적화: 프로그램 시작 시 즉시 사용 가능하도록 초기 자동 로딩 제거
        # 백그라운드 지연 로딩으로 대체됨 (main_app_test.py에서 3초 후 실행)
        # self.sanga_logic.load_data()     # 비활성화 - 백그라운드에서 로드됨
        # self.oneroom_logic.load_data()   # 비활성화 - 필요시 수동 로드

    # ============ 🚀 배치 API 로딩 메서드들 (매물체크탭 구조 재사용) ============
    
    def load_all_data_batch(self):
        """
        배치 API로 모든 마이리스트 데이터 한 번에 로딩
        매물체크탭의 구조를 재사용하여 성능 최적화
        """
        print(f"[DEBUG] MyListContainer: 배치 데이터 로딩 시작 - 담당자: {self.current_manager}")
        
        try:
            # 순차적 데이터 로딩 (동시 요청으로 인한 서버 500 에러 방지)
            print(f"[DEBUG] MyListContainer: 순차적 데이터 로딩 시작")
            
            # 상가 데이터 로딩
            if hasattr(self.sanga_logic, 'load_data'):
                print(f"[DEBUG] MyListContainer: 상가 데이터 로딩 시작")
                self.sanga_logic.load_data()
                print(f"[DEBUG] MyListContainer: 상가 데이터 로딩 완료")
                # 각 로딩 사이에 잠시 대기 (서버 부하 방지)
                import time
                time.sleep(0.5)
            
            # 원룸 데이터 로딩
            if hasattr(self.oneroom_logic, 'load_data'):
                print(f"[DEBUG] MyListContainer: 원룸 데이터 로딩 시작")
                self.oneroom_logic.load_data()
                print(f"[DEBUG] MyListContainer: 원룸 데이터 로딩 완료")
                time.sleep(0.5)
            
            # 계약완료 데이터 로딩
            print(f"[DEBUG] MyListContainer: 계약완료 데이터 로딩 시작")
            if self.completed_logic and hasattr(self.completed_logic, 'load_data'):
                self.completed_logic.load_data()
                print(f"[DEBUG] MyListContainer: 계약완료 데이터 로딩 완료")
            else:
                print(f"[DEBUG] MyListContainer: completed_logic 또는 load_data 메서드 없음: {type(self.completed_logic)}")
            
            print(f"[DEBUG] MyListContainer: 모든 탭 순차 로딩 완료")
            
        except Exception as e:
            print(f"[ERROR] MyListContainer: 데이터 로딩 실패: {e}")
    
    # ============ 배치 API 로딩 메서드들 끝 ============
    
    def start_timers(self):
        """Starts timers for auto-reload and auto-save."""
        # [자동 타이머 비활성화] 성능 최적화를 위해 자동 타이머들을 비활성화함
        # 사용자가 필요시 수동으로 새로고침하거나 저장하도록 변경
        self.logger.info("[Timer] Auto-timers disabled for performance optimization")
        
        # # Completed Deals Timer (managed by its logic class now)
        # self.completed_logic.start_timer()

        # # Auto-Save Timer (Managed here for both shop/oneroom pending)
        # self.save_handler.start_auto_save_timer()

    def stop_timers(self):
        """Stops all timers managed by the container and its logic classes."""
        self.logger.info("[Timer] Stopping all timers")
        self.completed_logic.stop_timer()
        self.save_handler.stop_auto_save_timer()
    
    # --- UI Cleanup Methods ---
    @pyqtSlot()
    def _perform_ui_cleanup(self):
        """Slot called by signal, defers the actual cleanup using QTimer.singleShot."""
        self.logger.info("[_perform_ui_cleanup] Slot called, scheduling cleanup using QTimer.singleShot.")
        if not self.save_handler:
             self.logger.error("[_perform_ui_cleanup] Save handler is not initialized.")
             return
        # Schedule the cleanup function to run shortly in the main event loop
        QTimer.singleShot(0, self._execute_actual_cleanup)

    def _execute_actual_cleanup(self):
        """Performs the actual UI cleanup. Called by QTimer.singleShot."""
        self.logger.info("[_execute_actual_cleanup] Executing actual UI cleanup.")
        try:
            # Call the original cleanup function
            removed_count = self.save_handler._cleanup_ui_marked_rows()
            self.logger.info(f"[_execute_actual_cleanup] UI cleanup finished. Removed {removed_count} rows.")
            # 저장 후 행 색상 업데이트
            self._update_rows_color_after_save()
        except Exception as e:
            self.logger.error(f"[_execute_actual_cleanup] Error during UI cleanup: {e}", exc_info=True)
            QMessageBox.critical(self.parent_app, "UI 정리 오류", f"UI 정리 중 오류 발생: {e}")
    
    def _update_rows_color_after_save(self):
        """저장 후 행 색상을 업데이트합니다. 재광고/새광고 여부에 따라 적절한 색상으로 변경합니다."""
        self.logger.info("Updating row colors after save operation")
        try:
            # 상가 모델 색상 업데이트
            if self.sanga_logic and self.sanga_logic.mylist_shop_model:
                model = self.sanga_logic.mylist_shop_model
                headers = [model.horizontalHeaderItem(j).text() for j in range(model.columnCount())]
                try:
                    re_ad_col_idx = headers.index("재광고")
                    for row in range(model.rowCount()):
                        re_ad_item = model.item(row, re_ad_col_idx)
                        if re_ad_item:
                            is_re_ad = (re_ad_item.text() == "재광고")
                            row_bg = RE_AD_BG_COLOR if is_re_ad else NEW_AD_BG_COLOR
                            for col in range(model.columnCount()):
                                item = model.item(row, col)
                                if item:
                                    item.setBackground(row_bg)
                    self.logger.info(f"Updated colors for {model.rowCount()} rows in shop model")
                except (ValueError, IndexError) as e:
                    self.logger.error(f"Error finding '재광고' column in shop model: {e}")
            
            # 원룸 모델 색상 업데이트 (필요시 구현)
            # 여기에 원룸 모델 색상 업데이트 로직 구현
            
        except Exception as e:
            self.logger.error(f"Error updating row colors after save: {e}", exc_info=True)
    
    # --- 테이블 필터링 ---
    def filter_tables_by_address(self, address_str):
        """Applies address filtering to all relevant MyList tabs."""
        self.sanga_logic.filter_table_by_address(address_str)
        self.oneroom_logic.filter_table_by_address(address_str)
        self.completed_logic.filter_table_by_address(address_str)
    
    # --- 추가 기능 핸들러 호출 ---
    
    # 상태 변경 처리
    @pyqtSlot(dict, list, str)
    def _process_status_change_slot(self, result, row_indices_to_remove, tab_type):
        """상태 변경 처리를 StatusHandler에 위임"""
        self.status_handler.process_status_change(result, row_indices_to_remove, tab_type)
        self._recalculate_manager_summary()
    
    def submit_status_change_task(self, payload, rows_to_remove_from_ui, tab_type):
        """상태 변경 작업 제출 - StatusHandler에 위임"""
        self.status_handler.submit_status_change_task(payload, rows_to_remove_from_ui, tab_type)
    
    # 요약 정보 계산
    def _recalculate_manager_summary(self):
        """상가 데이터 요약 정보 계산"""
        self.row_manager.recalculate_manager_summary()
    
    # 네이버 검수 기능
    def launch_naver_check_for_mylist(self):
        """네이버 검수 기능 실행"""
        self.naver_checker.launch_naver_check_for_mylist()
    
    def on_naver_check_row_changed(self, pk_id, row_idx):
        """네이버 검수 행 변경 콜백"""
        self.naver_checker.on_naver_check_row_changed(pk_id, row_idx)
    
    # 행 추가 함수들
    def add_new_shop_row(self, initial_data=None, parse_naver_format=False):
        """상가 행 추가 함수 - RowManager에 위임"""
        self.row_manager.add_new_shop_row(initial_data, parse_naver_format)
        self._recalculate_manager_summary()
    
    def add_new_oneroom_row(self, initial_data=None):
        """원룸 행 추가 함수 - RowManager에 위임"""
        self.row_manager.add_new_oneroom_row(initial_data)
    
    # 개발자 도구 (모듈 테스트용)
    def toggle_sanga_mode(self):
        """
        상가 모듈 모드 전환 (레거시 <-> 모듈식)
        - 개발 중에만 사용되는 도구
        
        Returns:
            str: 현재 모드 설명
        """
        if hasattr(self.sanga_logic, 'toggle_mode'):
            is_legacy = self.sanga_logic.toggle_mode()
            return f"상가 모듈 모드 전환: {'레거시' if is_legacy else '모듈식'}"
        return "상가 모듈 모드 전환 불가: 호환성 레이어 없음"
        
    def toggle_oneroom_mode(self):
        """
        원룸 모듈 모드 전환 (레거시 <-> 모듈식)
        - 개발 중에만 사용되는 도구
        
        Returns:
            str: 현재 모드 설명
        """
        if hasattr(self.oneroom_logic, 'toggle_mode'):
            is_legacy = self.oneroom_logic.toggle_mode()
            return f"원룸 모듈 모드 전환: {'레거시' if is_legacy else '모듈식'}"
        return "원룸 모듈 모드 전환 불가: 호환성 레이어 없음"
        
    def toggle_completed_mode(self):
        """
        계약완료 모듈 모드 전환 (레거시 <-> 모듈식)
        - 개발 중에만 사용되는 도구
        
        Returns:
            str: 현재 모드 설명
        """
        if hasattr(self.completed_logic, 'toggle_mode'):
            is_legacy = self.completed_logic.toggle_mode()
            return f"계약완료 모듈 모드 전환: {'레거시' if is_legacy else '모듈식'}"
        return "계약완료 모듈 모드 전환 불가: 호환성 레이어 없음"

    # ============ 🚀 상하 분할 및 매물체크 배치 API 재사용 메서드들 ============
    
    def _connect_table_selection_signals(self):
        """상단 테이블들의 선택 시그널 연결"""
        try:
            # 상가 탭 테이블 선택 시그널 (mylist_shop_view 사용)
            print(f"🔥🔥🔥 [BASE CONTAINER] 상가 시그널 연결 시도 시작")
            print(f"🔥 [BASE CONTAINER] sanga_logic 타입: {type(self.sanga_logic)}")
            
            sanga_view = getattr(self.sanga_logic, 'mylist_shop_view', None)
            print(f"🔥 [BASE CONTAINER] mylist_shop_view = {sanga_view}")
            
            if not sanga_view:
                sanga_view = getattr(self.sanga_logic, 'table_view', None)
                print(f"🔥 [BASE CONTAINER] fallback table_view = {sanga_view}")
                
            if sanga_view:
                # 🔥 상가 테이블의 selection 설정 확인 및 수정
                print(f"🔥 [SELECTION CONFIG] 상가 테이블 selection behavior: {sanga_view.selectionBehavior()}")
                print(f"🔥 [SELECTION CONFIG] 상가 테이블 selection mode: {sanga_view.selectionMode()}")
                
                # Selection 설정 강화
                from PyQt5.QtWidgets import QAbstractItemView
                sanga_view.setSelectionBehavior(QAbstractItemView.SelectRows)
                sanga_view.setSelectionMode(QAbstractItemView.SingleSelection)
                print(f"🔥 [SELECTION CONFIG] 상가 테이블 selection 설정 완료 - SelectRows, SingleSelection")
                
                selection_model = sanga_view.selectionModel()
                print(f"🔥 [BASE CONTAINER] 상가 selection_model = {selection_model}")
                if selection_model:
                    # 기존 연결 해제 (중복 방지)
                    try:
                        selection_model.selectionChanged.disconnect()
                        print(f"🔥 [BASE CONTAINER] 상가 기존 selectionChanged 시그널 연결 해제")
                    except:
                        pass  # 연결된 것이 없으면 무시
                    
                    # selectionChanged 시그널 사용 (원룸과 동일하게)
                    print(f"🔥 [BASE CONTAINER] 상가 selectionChanged 시그널 연결 시도")
                    selection_model.selectionChanged.connect(
                        lambda: self.update_selection_from_mylist("sanga")
                    )
                    print(f"🔥🔥🔥 [BASE CONTAINER] 상가 테이블 selectionChanged 시그널 연결 완료!!!")
                    
                    # 테스트용: 현재 selection_model에 대한 상세 정보 출력
                    print(f"🔥 [BASE CONTAINER] 시그널 연결 테스트 - hasSelection: {selection_model.hasSelection()}")
                    
                    # 🔥 추가: 클릭 이벤트에서 강제로 selection 변경 및 API 호출
                    def on_sanga_clicked(index):
                        print(f"🔥🔥🔥 [CLICK TEST] 상가 테이블 클릭됨! Row: {index.row()}, Column: {index.column()}")
                        
                        # 🔥 강제로 selection 변경
                        if index.isValid():
                            selection_model.setCurrentIndex(index, selection_model.SelectCurrent)
                            print(f"🔥 [FORCE SELECTION] 강제로 selection 변경: Row {index.row()}")
                            
                            # 🔥 직접 API 호출 트리거
                            print(f"🔥 [DIRECT CALL] 클릭 이벤트에서 직접 update_selection_from_mylist 호출")
                            self.update_selection_from_mylist("sanga")
                    
                    sanga_view.clicked.connect(on_sanga_clicked)
                    print(f"🔥 [BASE CONTAINER] 상가 테이블 clicked 시그널도 연결 완료 (클릭 테스트용)")
                    
                    # 🔥 추가: currentChanged도 base_container에서 직접 연결해보기
                    def on_sanga_current_changed(current, previous):
                        print(f"🔥🔥🔥 [CURRENT CHANGED TEST] 상가 currentChanged in base_container! Row: {current.row() if current.isValid() else 'INVALID'}")
                    
                    selection_model.currentChanged.connect(on_sanga_current_changed)
                    print(f"🔥 [BASE CONTAINER] 상가 currentChanged 시그널도 base_container에서 직접 연결 완료")
                    
                else:
                    print(f"🔥 [ERROR] MyListContainer: 상가 selection_model이 None")
            else:
                print(f"🔥 [ERROR] MyListContainer: 상가 테이블 뷰를 찾을 수 없음")
            
            # 원룸 탭 테이블 선택 시그널
            print(f"[DEBUG] MyListContainer: 원룸 시그널 연결 시도")
            oneroom_view = getattr(self.oneroom_logic, 'mylist_oneroom_view', None)
            if not oneroom_view:
                oneroom_view = getattr(self.oneroom_logic, 'table_view', None)
            
            if oneroom_view:
                selection_model = oneroom_view.selectionModel()
                if selection_model:
                    # 기존 연결 해제 (중복 방지)
                    try:
                        selection_model.selectionChanged.disconnect()
                        print(f"[DEBUG] MyListContainer: 원룸 기존 selectionChanged 시그널 연결 해제")
                    except:
                        pass  # 연결된 것이 없으면 무시
                    
                    selection_model.selectionChanged.connect(
                        lambda: self.update_selection_from_mylist("oneroom")
                    )
                    print(f"[DEBUG] MyListContainer: 원룸 테이블 selectionChanged 시그널 연결 완료")
                else:
                    print(f"[DEBUG] MyListContainer: 원룸 selection_model이 None")
            else:
                print(f"[DEBUG] MyListContainer: 원룸 테이블 뷰를 찾을 수 없음")
            
            # 계약완료 탭 테이블 선택 시그널
            print(f"[DEBUG] MyListContainer: 계약완료 시그널 연결 시도")
            completed_view = getattr(self.completed_logic, 'mylist_completed_view', None)
            if not completed_view:
                completed_view = getattr(self.completed_logic, 'table_view', None)
                
            if completed_view:
                selection_model = completed_view.selectionModel()
                if selection_model:
                    # 기존 연결 해제 (중복 방지)
                    try:
                        selection_model.selectionChanged.disconnect()
                        print(f"[DEBUG] MyListContainer: 계약완료 기존 selectionChanged 시그널 연결 해제")
                    except:
                        pass  # 연결된 것이 없으면 무시
                    
                    selection_model.selectionChanged.connect(
                        lambda: self.update_selection_from_mylist("completed")
                    )
                    print(f"[DEBUG] MyListContainer: 계약완료 테이블 selectionChanged 시그널 연결 완료")
                else:
                    print(f"[DEBUG] MyListContainer: 계약완료 selection_model이 None")
            else:
                print(f"[DEBUG] MyListContainer: 계약완료 테이블 뷰를 찾을 수 없음")
            
            print(f"[DEBUG] MyListContainer: 테이블 선택 시그널 연결 완료")
            
        except Exception as e:
            print(f"[ERROR] MyListContainer: 테이블 선택 시그널 연결 실패: {e}")

    def update_selection_from_mylist(self, tab_type):
        """매물체크탭처럼 parent_app을 통해 하단 테이블 업데이트"""
        print(f"🔥🔥🔥 [BASE CONTAINER SIGNAL] update_selection_from_mylist 호출됨! tab_type={tab_type}")
        
        try:
            # 주소 추출
            selected_address = self._extract_selected_address(tab_type)
            if not selected_address:
                print(f"🔥 [SIGNAL DEBUG] MyListContainer: 선택된 주소가 없음")
                return
            
            print(f"🔥🔥🔥 [SIGNAL FIRED] MyListContainer: {tab_type} 탭에서 '{selected_address}' 선택!")
            
            # parent_app의 update_selection_from_manager_check 메서드 호출 (매물체크탭과 동일)
            if self.parent_app and hasattr(self.parent_app, 'update_selection_from_manager_check'):
                print(f"🔥 [SIGNAL DEBUG] MyListContainer: parent_app.update_selection_from_manager_check('{selected_address}') 호출")
                self.parent_app.update_selection_from_manager_check(selected_address)
            else:
                print(f"🔥 [ERROR] MyListContainer: parent_app에 update_selection_from_manager_check 메서드가 없음")
            
        except Exception as e:
            print(f"🔥 [ERROR] MyListContainer: 선택 처리 실패: {e}")

    def _extract_selected_address(self, tab_type):
        """선택된 행에서 주소 추출"""
        try:
            table_view = None
            if tab_type == "sanga":
                # 상가는 mylist_shop_view 사용
                table_view = getattr(self.sanga_logic, 'mylist_shop_view', None)
                if not table_view:
                    table_view = getattr(self.sanga_logic, 'table_view', None)
            elif tab_type == "oneroom":
                # 원룸은 mylist_oneroom_view 사용  
                table_view = getattr(self.oneroom_logic, 'mylist_oneroom_view', None)
                if not table_view:
                    table_view = getattr(self.oneroom_logic, 'table_view', None)
            elif tab_type == "completed":
                # 계약완료는 mylist_completed_view 사용
                table_view = getattr(self.completed_logic, 'mylist_completed_view', None)
                if not table_view:
                    table_view = getattr(self.completed_logic, 'table_view', None)
            
            if not table_view:
                print(f"[DEBUG] MyListContainer: {tab_type} 탭의 테이블 뷰를 찾을 수 없음")
                return None
            
            # 선택된 행 가져오기
            selected_indexes = table_view.selectionModel().selectedRows()
            if not selected_indexes:
                print(f"[DEBUG] MyListContainer: {tab_type} 탭에서 선택된 행이 없음")
                return None
            
            # 첫 번째 선택된 행에서 주소 컬럼 찾기 (일반적으로 "주소" 또는 "address" 컬럼)
            row = selected_indexes[0].row()
            model = table_view.model()
            
            # 주소 컬럼 찾기 (헤더에서 "주소" 포함된 컬럼)
            for col in range(model.columnCount()):
                header = model.headerData(col, Qt.Horizontal, Qt.DisplayRole)
                if header and "주소" in str(header):
                    address_item = model.item(row, col)
                    if address_item:
                        address_text = address_item.text().strip()
                        print(f"[DEBUG] MyListContainer: {tab_type} 탭에서 추출된 주소: '{address_text}'")
                        return address_text
            
            print(f"[DEBUG] MyListContainer: {tab_type} 탭에서 주소 컬럼을 찾을 수 없음")
            return None
            
        except Exception as e:
            print(f"[ERROR] MyListContainer: 주소 추출 실패: {e}")
            return None

    # 배치 API 메서드들 제거됨 - parent_app을 통해 처리됨