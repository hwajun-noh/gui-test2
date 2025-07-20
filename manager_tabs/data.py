import json
import logging
import requests
from datetime import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt

logger = logging.getLogger(__name__)

class ManagerDataMixin:
    """ManagerCheckTab의 데이터 관련 메서드를 관리하는 Mixin 클래스"""
    
    def refresh_tab_data(self, force_reload=False):
        """
        매니저 체크 탭 데이터를 새로고침합니다.
        
        Args:
            force_reload: True면 서버에서 전체 데이터를 다시 가져옴, False면 마지막 로드 ID를 사용한 증분 로드
        """
        # 이미 데이터를 로딩 중이면 중복 요청 방지
        if hasattr(self, 'loading_data_flag') and self.loading_data_flag:
            self.logger.info("이미 데이터 로딩 중이므로 중복 요청을 무시합니다.")
            return
            
        # UI에 로딩 중 상태 표시 즉시 설정 (확인용 메시지 표시)
        self.parent_app.statusBar().showMessage("매니저 체크 탭 데이터 로딩 준비 중...", 0)
        QtWidgets.QApplication.processEvents()  # UI 업데이트를 즉시 처리
            
        # 로컬 캐시가 있고 force_reload=False이면 로컬 필터만 적용
        if not force_reload and hasattr(self, 'cached_manager_data_1month') and self.cached_manager_data_1month:
            self.logger.info("로컬 캐시가 있고 force_reload=False이므로 로컬 필터만 적용합니다.")
            self.apply_local_filter_manager_data()
            return
            
        # 로딩 시작 시그널 발생
        self.loadingStarted.emit()
        QtWidgets.QApplication.processEvents()  # UI 업데이트를 즉시 처리
        
        # 기존 정렬 상태 저장 (데이터 로딩 후 복원하기 위해)
        if hasattr(self, 'check_manager_view') and self.check_manager_view:
            header_view = self.check_manager_view.horizontalHeader()
            sort_column = header_view.sortIndicatorSection()
            sort_order = header_view.sortIndicatorOrder()
            self.saved_sort_state = (sort_column, sort_order)
        
        # 강제 새로고침(force_reload)이 요청되면 last_loaded_id를 0으로 재설정
        if force_reload:
            self.last_loaded_id = 0
            self.logger.info("강제 새로고침이 요청되어 마지막 로드 ID를 0으로 재설정합니다.")
        
        # 현재 상태 로깅
        self.logger.info(f"refresh_tab_data 시작: current_manager={self.current_manager}, role={self.current_role}, force_reload={force_reload}")
        
        try:
            # 백그라운드 스레드를 통해 서버에서 데이터 로드
            future = self.parent_app.executor.submit(
                self._bg_load_manager_data,
                self.current_manager,
                self.current_role,
                self.filter_ad_date_value,
                self.last_loaded_id
            )
            future.add_done_callback(self._on_refresh_manager_check_tab_done)
            self.logger.info(f"매니저 체크 데이터 로드 요청을 백그라운드로 전송 (last_id: {self.last_loaded_id})")
            
            # 사용자에게 로딩 중임을 알림
            self.parent_app.statusBar().showMessage("매니저 체크 데이터 로딩 중... 이 작업은 백그라운드에서 처리됩니다.", 0)
            QtWidgets.QApplication.processEvents()  # UI 업데이트를 즉시 처리
        except Exception as e:
            self.logger.error(f"데이터 로드 요청 실패: {e}", exc_info=True)
            self.loadingError.emit(f"데이터 로드 요청 실패: {e}")
            QtWidgets.QApplication.processEvents()  # UI 업데이트를 즉시 처리

    def _on_refresh_manager_check_tab_done(self, future):
        """
        백그라운드 데이터 로딩이 완료됐을 때 호출되는 메소드입니다.
        """
        try:
            result = future.result()
            
            self.logger.info(f"_on_refresh_manager_check_tab_done: 백그라운드 작업 완료, 결과 타입: {type(result)}")
            
            # 중간 상태 업데이트 (사용자에게 백그라운드 작업 상태 알림)
            self.parent_app.statusBar().showMessage("매니저 체크 데이터 가져오기 완료, 처리 중...", 0)
            QtWidgets.QApplication.processEvents()  # UI 업데이트를 즉시 처리
            
            if not result:
                self.logger.error("백그라운드 함수에서 결과를 반환하지 않았습니다.")
                self.loadingError.emit("백그라운드 함수에서 결과를 반환하지 않았습니다.")
                QtWidgets.QApplication.processEvents()  # UI 업데이트를 즉시 처리
                return

            status_ = result.get("status", "error")
            if status_ != "ok":
                msg_ = result.get("message", "알 수 없는 오류")
                self.logger.error(f"데이터 로드 실패: {status_} - {msg_}")
                self.loadingError.emit(f"데이터 로드 실패: {status_} - {msg_}")
                QtWidgets.QApplication.processEvents()  # UI 업데이트를 즉시 처리
                return

            new_rows = result.get("data", [])
            self.logger.info(f"서버에서 받은 데이터 수: {len(new_rows)}개")
            
            # 데이터 개수 표시 업데이트
            self.parent_app.statusBar().showMessage(f"매니저 체크 데이터 {len(new_rows)}건 처리 중...", 0)
            QtWidgets.QApplication.processEvents()  # UI 업데이트를 즉시 처리
            
            if not new_rows:
                self.loadingFinished.emit("새로운 데이터가 없습니다")
                QtWidgets.QApplication.processEvents()  # UI 업데이트를 즉시 처리
                
                # 로딩 메시지 행 제거
                if self.manager_source_model.rowCount() == 1:
                    # 첫번째 행을 확인하여 로딩 메시지인지 확인
                    first_item = self.manager_source_model.item(0, 0)
                    if first_item and first_item.text() == "데이터 로딩 중...":
                        self.manager_source_model.removeRow(0)
                
                return
                
            # 로그에 첫 번째 행 내용 출력 (디버깅용)
            if new_rows:
                first_row = new_rows[0]
                self.logger.info(f"첫 번째 행 샘플 데이터: {first_row.get('dong', '')} {first_row.get('jibun', '')}, 매칭업종: {[b.get('biz', '') for b in first_row.get('biz_manager_list', [])]}")
                
            # 서버에서 가져온 새 데이터의 최대 ID 값을 저장 (다음 요청을 위해)
            if new_rows:
                max_id = max((row.get("shop_id", 0) for row in new_rows), default=0)
                if max_id > self.last_loaded_id:
                    self.last_loaded_id = max_id
                    self.logger.debug(f"마지막 로드 ID를 {max_id}로 업데이트했습니다.")
                
            # 로컬 캐시 업데이트
            self.cached_manager_data_1month = new_rows
            
            # 메타데이터 처리 상태 업데이트
            self.parent_app.statusBar().showMessage(f"메타데이터 처리 중... ({len(new_rows)}건)", 0)
            QtWidgets.QApplication.processEvents()  # UI 업데이트를 즉시 처리
            
            # 백그라운드에서 biz_set, dong_map 및 주소 캐싱 구성
            future_build = self.parent_app.executor.submit(
                self._bg_build_metadata,
                new_rows
            )
            future_build.add_done_callback(self._on_build_metadata_done)
            
            # 테이블 업데이트는 메타데이터 처리 후 진행됨
            self.parent_app.statusBar().showMessage(f"데이터 처리 중... ({len(new_rows)}건)", 0)
                
        except Exception as e:
            self.logger.error(f"데이터 로딩 중 오류 발생: {e}", exc_info=True)
            self.loadingError.emit(f"데이터 로딩 중 오류 발생: {e}")
            QtWidgets.QApplication.processEvents()  # UI 업데이트를 즉시 처리

    def _on_build_metadata_done(self, future):
        """메타데이터 구성이 완료된 후 호출"""
        try:
            metadata = future.result()
            # 메인 스레드로 결과 전달을 위해 시그널 발생
            self.metadataReady.emit(metadata)
        except Exception as e:
            self.loadingError.emit(f"메타데이터 처리 중 오류: {e}")

    def _handle_loading_started(self):
        """로딩 시작 시 호출되는 슬롯"""
        self.loading_data_flag = True
        self.parent_app.statusBar().showMessage("데이터 로딩 중...", 0)  # 0은 무기한을 의미
        QtWidgets.QApplication.processEvents()  # UI 업데이트를 즉시 처리
        
        # 테이블에 로딩 중 메시지 추가
        if self.manager_source_model.rowCount() == 0:
            # 테이블이 비어있을 때만 로딩 행 추가
            self.manager_source_model.setRowCount(1)
            loading_item = QtGui.QStandardItem("데이터 로딩 중...")
            loading_item.setForeground(Qt.gray)
            self.manager_source_model.setItem(0, 0, loading_item)
            QtWidgets.QApplication.processEvents()  # UI 업데이트를 즉시 처리
    
    def _handle_loading_finished(self, message):
        """로딩 완료 시 호출되는 슬롯"""
        self.loading_data_flag = False
        self.parent_app.statusBar().showMessage(message, 3000)
        QtWidgets.QApplication.processEvents()  # UI 업데이트를 즉시 처리
    
    def _handle_loading_error(self, error_message):
        """로딩 오류 발생 시 호출되는 슬롯"""
        self.loading_data_flag = False
        self.parent_app.statusBar().showMessage(error_message, 3000)
        self.logger.error(f"데이터 로딩 오류: {error_message}")
        QtWidgets.QApplication.processEvents()  # UI 업데이트를 즉시 처리
    
    def _handle_metadata_ready(self, metadata):
        """메타데이터 준비 완료 시 호출되는 슬롯"""
        if "error" in metadata:
            self.loadingError.emit(f"메타데이터 구성 실패: {metadata['error']}")
            return
            
        # 메타데이터 업데이트
        self.real_biz_set = metadata["biz_set"]
        self.real_dong_map = metadata["dong_map"]
        
        # 주소 캐싱 (parent.new_addresses에 추가)
        if hasattr(self.parent_app, 'new_addresses'):
            self.parent_app.new_addresses.update(metadata["addresses"])
        
        # 다음 단계: 테이블 데이터 준비
        future_ui = self.parent_app.executor.submit(
            self._bg_prepare_table_data,
            self.cached_manager_data_1month
        )
        future_ui.add_done_callback(self._on_prepare_table_data_done)
    
    def _handle_table_data_ready(self, filtered_rows):
        """테이블 데이터 준비 완료 시 호출되는 슬롯"""
        # 테이블 업데이트 - populate_check_manager_table 내에서 정렬 상태 복원
        self.populate_check_manager_table(filtered_rows, append=False)
        
        # populate_check_manager_table에서 정렬 상태 복원을 하지만, 혹시 다른 루트로 여기를 거치는 케이스가 있을 수 있어 이중 체크
        if hasattr(self, 'check_manager_view') and hasattr(self, 'saved_sort_state'):
            sort_column, sort_order = self.saved_sort_state
            # 확인부터 - 현재 정렬 상태와 저장된 상태가 다른 경우에만 적용
            current_header_view = self.check_manager_view.horizontalHeader()
            current_sort_column = current_header_view.sortIndicatorSection()
            current_sort_order = current_header_view.sortIndicatorOrder()
            
            if current_sort_column != sort_column or current_sort_order != sort_order:
                self.logger.info(f"_handle_table_data_ready에서 누락된 정렬 상태 복원: 열={sort_column}, 순서={sort_order}")
                self.check_manager_view.sortByColumn(sort_column, sort_order)
            
        self.logger.info(f"테이블 모델 업데이트 완료: {len(filtered_rows)}건")
        self.loadingFinished.emit(f"데이터 로딩 완료: {len(filtered_rows)}건")

    def _on_prepare_table_data_done(self, future):
        """필터링된 테이블 데이터로 UI 업데이트"""
        try:
            result = future.result()
            if isinstance(result, dict) and "error" in result:
                self.loadingError.emit(f"테이블 데이터 준비 실패: {result['error']}")
            else:
                # 메인 스레드로 결과 전달을 위해 시그널 발생
                self.tableDataReady.emit(result)
        except Exception as e:
            self.loadingError.emit(f"UI 업데이트 준비 중 오류: {e}")

    def _bg_load_manager_data(self, manager, role, ad_date, last_id):
        """
        (백그라운드 스레드) 서버에서 매니저 데이터를 가져옴. 
        - 캐시 확인, 매니저 선택, 날짜 필터 적용도 모두 수행.
        """
        url = f"http://{self.server_host}:{self.server_port}/shop/search_manager_data"
        
        # 1) API 요청 파라미터 구성
        params = {"manager": manager}
        if role:
            params["role"] = role
        if ad_date:
            params["ad_date"] = ad_date
        if last_id:
            params["last_id"] = last_id
        
        self.logger.info(f"_bg_load_manager_data: URL={url}, params={params}")

        # 2) API 호출
        try:
            # 중요: 여기에서 타임아웃 늘렸음. 10초->20초
            self.logger.info("서버에 API 요청 시작...")
            resp = requests.get(url, params=params, timeout=20)
            self.logger.info(f"서버 응답 받음: 상태 코드={resp.status_code}, 크기={len(resp.content)}")
            
            try:
                j = resp.json()
                data_count = len(j.get("data", [])) if "data" in j else 0
                self.logger.info(f"JSON 파싱 성공: 상태={j.get('status')}, 데이터 수={data_count}")
                return j
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON 파싱 실패: {e}, 응답 내용={resp.text[:500]}")
                return {"status":"error", "message": f"JSON 파싱 오류: {e}"}
            
        except requests.exceptions.Timeout:
            self.logger.error("서버 요청 타임아웃 (요청 시간 초과)")
            return {
                "status": "error",
                "message": "서버 요청 타임아웃 (요청 시간 초과)"
            }
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"서버 연결 실패: {e}")
            return {
                "status": "error",
                "message": "서버 연결 실패 (서버가 실행 중인지 확인하세요)"
            }
        except Exception as ex:
            self.logger.error(f"기타 예외 발생: {ex}", exc_info=True)
            return {
                "status": "exception",
                "message": str(ex)
            }

    def _bg_build_metadata(self, rows):
        """백그라운드에서 메타데이터(biz_set, dong_map 등)를 구성"""
        try:
            # 캐시가 있으면 기존 데이터 재사용
            if hasattr(self, 'real_biz_set') and hasattr(self, 'real_dong_map'):
                # 기존 데이터와 새 데이터를 합치는 로직
                self.logger.info("기존 메타데이터 캐시를 활용합니다.")
                
                # 1. 비즈니스 세트 업데이트
                new_biz_set = self.build_real_biz_set(rows)
                real_biz_set = self.real_biz_set.union(new_biz_set)
                
                # 2. 동 맵 업데이트 (기존 맵을 복사 후 수정)
                real_dong_map = self.real_dong_map.copy()
                new_dong_map = self.build_real_dong_map(rows)
                
                # 기존 맵에 새 동 정보 추가
                for gu, dongs in new_dong_map.items():
                    if gu in real_dong_map:
                        # 기존 리스트와 새 리스트 병합 후 중복 제거
                        real_dong_map[gu] = sorted(list(set(real_dong_map[gu] + dongs)))
                    else:
                        real_dong_map[gu] = dongs
            else:
                # 캐시가 없으면 새로 구성
                self.logger.info("메타데이터 캐시가 없어 새로 구성합니다.")
                real_biz_set = self.build_real_biz_set(rows)
                real_dong_map = self.build_real_dong_map(rows)
                
            # 주소 집합 구성 (항상 새로 구성)
            unique_addresses = set()
            for row in rows:
                addr_str = (row.get("dong", "") + " " + row.get("jibun", "")).strip()
                if addr_str:
                    unique_addresses.add(addr_str)
                    
            return {
                "biz_set": real_biz_set,
                "dong_map": real_dong_map,
                "addresses": unique_addresses
            }
        except Exception as e:
            self.logger.error(f"메타데이터 구성 중 오류: {e}", exc_info=True)
            return {"error": str(e)}

    def _bg_prepare_table_data(self, rows):
        """백그라운드에서 테이블 데이터 필터링 및 준비"""
        try:
            # 필요한 필터 변수 미리 준비
            start_time = datetime.now()
            
            # A. 동(전체) 목록 구성
            all_selected_dongs = []
            has_dong_filter = False
            if hasattr(self, 'selected_dongs_by_gu') and self.selected_dongs_by_gu:
                for gu, dset in self.selected_dongs_by_gu.items():
                    if dset:
                        all_selected_dongs.extend(list(dset))
                        has_dong_filter = True
            
            # 성능 최적화: 동 필터 빠른 탐색을 위해 집합으로 변환
            dong_filter_set = set(all_selected_dongs) if has_dong_filter else None
            
            # B. 업종 필터 - 여기서는 self.selected_biz_types 사용
            has_biz_filter = bool(self.selected_biz_types)
            biz_filter_set = set(self.selected_biz_types) if has_biz_filter else None
     
            # C. 날짜 필터
            min_date, max_date = None, None
            has_date_filter = False
            if self.filter_ad_date_value:
                date_splitted = [d_.strip() for d_ in self.filter_ad_date_value.split(",") if d_.strip()]
                if len(date_splitted) >= 1:
                    try:
                        min_date = datetime.strptime(date_splitted[0], "%Y-%m-%d").date()
                        max_date = datetime.strptime(date_splitted[-1], "%Y-%m-%d").date()
                        has_date_filter = True
                    except ValueError:
                        self.logger.warning(f"날짜 형식 오류: {self.filter_ad_date_value}")
            
            # 전체 필터 상태 로깅
            self.logger.info(f"필터 상태: 동 필터={has_dong_filter}({len(all_selected_dongs) if all_selected_dongs else 0}개), " +
                     f"업종 필터={has_biz_filter}({len(self.selected_biz_types) if self.selected_biz_types else 0}개), " +
                     f"날짜 필터={has_date_filter}({min_date}~{max_date if has_date_filter else ''})")
            
            # D. 필터링 수행 - 최적화된 방식
            filtered_rows = []
            
            # 필터 조건이 없으면 전체 데이터 반환
            if not has_dong_filter and not has_biz_filter and not has_date_filter:
                self.logger.info("필터 조건이 없어 전체 데이터를 반환합니다.")
                return rows
                
            # 필터링 수행
            for row in rows:
                # 기본적으로 행을 포함
                include_row = True
                
                # (1) 동 필터 - 집합 이용하여 O(1) 탐색 - 필터가 있는 경우에만 적용
                if has_dong_filter and dong_filter_set:
                    row_dong = row.get("dong", "").strip()
                    if row_dong not in dong_filter_set:
                        include_row = False
                        continue
                    
                # (2) 업종 필터 - biz_manager_list 미리 캐싱 - 필터가 있는 경우에만 적용
                if has_biz_filter and biz_filter_set:
                    bm_list = row.get("biz_manager_list", [])
                    # 빠른 탐색을 위해 any() 최적화
                    found_any = False
                    for bm in bm_list:
                        if bm.get("biz", "") in biz_filter_set:
                            found_any = True
                            break
                    if not found_any:
                        include_row = False
                        continue
                        
                # (3) 날짜 필터 - 최적화 및 오류 처리 개선
                if has_date_filter and min_date and max_date:
                    ad_str = row.get("ad_start_date", "").strip()
                    if not ad_str:
                        include_row = False
                        continue
                        
                    # 날짜 파싱 최적화
                    try: 
                        # 날짜 형식 확인 및 일관성 유지
                        if " " in ad_str:  # 날짜에 시간이 포함된 경우 (예: "2025-05-04 12:34:56")
                            ad_date_str = ad_str.split(" ")[0]  # 날짜 부분만 추출
                        else:
                            ad_date_str = ad_str
                            
                        ad_date_obj = datetime.strptime(ad_date_str, "%Y-%m-%d").date()
                        
                        # 날짜 범위 검사
                        if ad_date_obj < min_date or ad_date_obj > max_date:
                            include_row = False
                            continue
                    except (ValueError, AttributeError, IndexError) as e: 
                        # 날짜 형식 오류 발생 시 로그 기록
                        if isinstance(e, ValueError):
                            self.logger.debug(f"날짜 파싱 오류 (무시): '{ad_str}' - {e}")
                        include_row = False
                        continue
                        
                # 모든 필터 통과하면 결과에 추가
                if include_row:
                    filtered_rows.append(row)
            
            # 처리 시간 측정 및 로깅
            end_time = datetime.now()
            elapsed_ms = (end_time - start_time).total_seconds() * 1000
            self.logger.info(f"데이터 필터링 완료: {len(rows)}개 → {len(filtered_rows)}개 ({elapsed_ms:.1f}ms)")
            
            # 필터링 결과 샘플 로깅
            if filtered_rows:
                sample = filtered_rows[0]
                self.logger.info(f"필터링 샘플 데이터: 주소='{sample.get('dong', '')} {sample.get('jibun', '')}', 매칭업종: {[b.get('biz', '') for b in sample.get('biz_manager_list', [])]}")
            
            # 필터링 결과가 0개인 경우 안전 조치 적용
            if not filtered_rows:
                self.logger.warning("필터링 결과가 0개입니다. 필터 조건이 너무 제한적인지 확인하세요.")
                
                # 날짜 필터만 적용된 경우 자동으로 필터 우회
                if has_date_filter and not has_dong_filter and not has_biz_filter:
                    self.logger.warning("날짜 필터만 적용되어 0개 결과가 나왔으므로, 날짜 필터를 우회하고 모든 데이터를 반환합니다.")
                    return rows[:1000]  # 데이터가 너무 많은 경우를 대비해 최대 1000개 항목으로 제한
            
            return filtered_rows
                
        except Exception as e:
            self.logger.error(f"테이블 데이터 준비 중 오류: {e}", exc_info=True)
            # 오류 발생 시 안전하게 일부 데이터 반환
            self.logger.warning("필터링 오류가 발생하여 필터 없이 일부 데이터를 반환합니다.")
            if len(rows) > 1000:
                return rows[:1000]  # 데이터가 너무 많은 경우를 대비해 최대 1000개 항목으로 제한

    def build_real_dong_map(self, big_rows):
        """Builds a map of available dongs from data, filtered by parent's district data."""
        # Logic from main_app_part7/build_real_dong_map
        # Needs access to parent's district_data
        if not hasattr(self.parent_app, 'district_data'): return {}
        
        # Initialize with all GUs from parent data
        real_map = { gu: set() for gu in self.parent_app.district_data.keys() }
        for row in big_rows:
            gu_ = row.get("gu","").strip()
            d_  = row.get("dong","").strip()
            # Check if gu_ exists in parent data first
            if gu_ in self.parent_app.district_data and d_:
                # Check if dong is valid within that gu
                if d_ in self.parent_app.district_data[gu_]: 
                    real_map[gu_].add(d_)
        # Convert sets to sorted lists for consistency
        for gu_name in real_map:
            real_map[gu_name] = sorted(list(real_map[gu_name]))
        return real_map
        
    def build_real_biz_set(self, big_rows):
        """Builds a set of unique business types from data."""
        # Logic from main_app_part7/build_real_biz_set
        biz_set = set()
        for r in big_rows:
             biz_manager_list = r.get("biz_manager_list", [])
             for item in biz_manager_list:
                 b_ = item.get("biz","").strip()
                 if b_:
                     biz_set.add(b_)
        return biz_set

    def apply_local_filter_manager_data(self):
        """Applies filters locally to the cached data."""
        # Logic from main_app_part7/apply_local_filter_manager_data
        # Use local cache: self.cached_manager_data_1month
        if not hasattr(self, 'cached_manager_data_1month') or not self.cached_manager_data_1month:
             self.logger.warning("ManagerCheckTab 로컬 캐시가 초기화되지 않았거나 비어 있습니다.")
             self.populate_check_manager_table([], append=False)
             return

        # 현재 정렬 상태 저장
        if hasattr(self, 'check_manager_view') and self.check_manager_view:
            header_view = self.check_manager_view.horizontalHeader()
            sort_column = header_view.sortIndicatorSection()
            sort_order = header_view.sortIndicatorOrder()
            self.saved_sort_state = (sort_column, sort_order)
            self.logger.info(f"로컬 필터 적용 전 정렬 상태 저장: 열={sort_column}, 순서={sort_order}")
             
        # A. 동(전체) 목록 구성 from local state
        all_selected_dongs = []
        if hasattr(self, 'selected_dongs_by_gu'):
             for gu, dset in self.selected_dongs_by_gu.items():
                 if dset: all_selected_dongs.extend(list(dset))
        
        # B. 업종 필터 from local state (리스트 사용)
        # splitted_biz = [x.strip() for x in self.filter_biz_value.split(",") if x.strip()] if self.filter_biz_value else [] # 삭제
 
        # C. 날짜 필터 from local state
        min_date, max_date = None, None
        if self.filter_ad_date_value:
            date_splitted = [d_.strip() for d_ in self.filter_ad_date_value.split(",") if d_.strip()]
            if len(date_splitted) >= 1:
                 try:
                     min_date = datetime.strptime(date_splitted[0], "%Y-%m-%d").date()
                     # Use last date if multiple selected, else use first date as max too
                     max_date = datetime.strptime(date_splitted[-1], "%Y-%m-%d").date()
                 except ValueError:
                     self.logger.warning(f"필터에서 잘못된 날짜 형식: {self.filter_ad_date_value}")
                     min_date, max_date = None, None # Invalidate date filter on parse error

        # D. 로컬 캐시에서 조건 검사
        filtered = []
        for row in self.cached_manager_data_1month:
            # (1) 동 필터
            if all_selected_dongs:
                row_dong = row.get("dong","").strip()
                if row_dong not in all_selected_dongs: continue
            # (2) 업종 필터 (리스트 직접 사용)
            # if splitted_biz: # 삭제
            if self.selected_biz_types:
                bm_list = row.get("biz_manager_list", [])
                # found_any = any((bm.get("biz","") in splitted_biz) for bm in bm_list) # 삭제
                found_any = any((bm.get("biz","") in self.selected_biz_types) for bm in bm_list)
                if not found_any: continue
            # (3) 날짜 필터 (ad_start_date)
            if min_date and max_date:
                ad_str = row.get("ad_start_date","").strip()
                if not ad_str: continue
                try: 
                     ad_date_obj = datetime.strptime(ad_str.split(" ")[0], "%Y-%m-%d").date()
                except ValueError: 
                     # print(f" [FILTER] Excluding parse error ad_start_date='{ad_str}'") # Too verbose
                     continue
                if ad_date_obj < min_date or ad_date_obj > max_date: continue
            filtered.append(row)

        # E. 테이블(모델) 갱신 - Sorting handled in populate method
        self.populate_check_manager_table(filtered, append=False) # Populate with filtered data

    def reload_manager_data_with_filter(self):
        """날짜 범위에 따라 서버에서 데이터를 다시 로드하거나 로컬 필터를 적용합니다."""
        # 로컬 캐시가 없거나 비어있으면 무조건 서버에서 로드
        if not hasattr(self, 'cached_manager_data_1month') or not self.cached_manager_data_1month:
            self.logger.info("로컬 캐시가 없어 서버에서 데이터를 전체 로드합니다.")
            self.last_loaded_id = 0  # 전체 데이터 새로고침
            self.refresh_tab_data(force_reload=True)
            return
            
        # 날짜 필터 확인
        earliest_day_str = ""
        if self.filter_ad_date_value:
            splitted = [x.strip() for x in self.filter_ad_date_value.split(",") if x.strip()]
            if splitted: 
                earliest_day_str = splitted[0]

        needs_server_reload = False
        if earliest_day_str:
            try:
                earliest_date = datetime.strptime(earliest_day_str, "%Y-%m-%d").date()
                now_date = datetime.now().date()
                diff_days = (now_date - earliest_date).days
                
                # 31일 이상 이전 데이터는 서버에서 다시 로드 필요
                if diff_days > 31:
                    self.logger.info(f"날짜 범위({diff_days}일)가 31일을 초과하여 서버에서 전체 데이터를 다시 로드합니다.")
                    needs_server_reload = True
            except ValueError: 
                self.logger.warning(f"날짜 파싱 실패: '{earliest_day_str}'. 서버에서 데이터를 다시 로드합니다.")
                needs_server_reload = True
        
        # 현재 선택된 동이나 업종이 로컬 캐시의 데이터 범위를 벗어나는지 확인
        if not needs_server_reload:
            # 선택된 동이 real_dong_map에 없는 경우 확인
            all_selected_dongs = []
            if hasattr(self, 'selected_dongs_by_gu'):
                for gu, dset in self.selected_dongs_by_gu.items():
                    all_selected_dongs.extend(list(dset))
                    
            if all_selected_dongs and hasattr(self, 'real_dong_map'):
                all_available_dongs = []
                for gu, dongs in self.real_dong_map.items():
                    all_available_dongs.extend(dongs)
                    
                # 선택된 동 중 하나라도 로컬 캐시에 없으면 서버 리로드 필요
                for dong in all_selected_dongs:
                    if dong not in all_available_dongs:
                        self.logger.info(f"선택된 동 '{dong}'이 로컬 캐시에 없어 서버에서 데이터를 다시 로드합니다.")
                        needs_server_reload = True
                        break
            
            # 선택된 업종이 real_biz_set에 없는 경우 확인
            if not needs_server_reload and hasattr(self, 'selected_biz_types') and self.selected_biz_types:
                if hasattr(self, 'real_biz_set'):
                    for biz in self.selected_biz_types:
                        if biz not in self.real_biz_set:
                            self.logger.info(f"선택된 업종 '{biz}'이 로컬 캐시에 없어 서버에서 데이터를 다시 로드합니다.")
                            needs_server_reload = True
                            break
        
        if needs_server_reload:
            self.last_loaded_id = 0  # 전체 데이터 새로고침
            self.refresh_tab_data(force_reload=True)
        else:
            self.logger.info("로컬 필터를 적용합니다.")
            self.apply_local_filter_manager_data()  # 로컬 캐시에 필터 적용

    def check_new_manager_data(self):
         """Periodically checks for new data (timer callback)."""
         # Logic from main_app_part7/check_new_manager_data (if exists)
         self.logger.info("ManagerCheckTab: 타이머에 의해 새 데이터 확인 시작")
         
         # 기존 정렬 상태 저장 (직접 저장)
         if hasattr(self, 'check_manager_view') and self.check_manager_view:
             header_view = self.check_manager_view.horizontalHeader()
             sort_column = header_view.sortIndicatorSection()
             sort_order = header_view.sortIndicatorOrder()
             self.saved_sort_state = (sort_column, sort_order)
             self.logger.info(f"기존 정렬 상태 저장: 열={sort_column}, 순서={sort_order}")
             
         # 데이터 새로고침 (force_reload=False로 증분 로드)
         self.refresh_tab_data()

    def update_real_biz_set(self):
        """
        업종 목록을 최신 상태로 갱신합니다.
        고객 추가/삭제 후 호출하여 업종 다이얼로그에 표시되는 업종 목록을 최신화합니다.
        """
        if not hasattr(self, 'cached_manager_data_1month') or not self.cached_manager_data_1month:
            # 캐시 데이터가 없는 경우 전체 데이터를 다시 로드
            self.logger.info("업종 목록 갱신을 위해 데이터를 다시 로드합니다.")
            self.refresh_tab_data(force_reload=True)
            return
            
        # 캐시된 데이터로부터 업종 목록 갱신
        self.logger.info("캐시된 데이터로부터 업종 목록을 갱신합니다.")
        self.real_biz_set = self.build_real_biz_set(self.cached_manager_data_1month)
        self.logger.info(f"업종 목록 갱신 완료: {len(self.real_biz_set)}개의 업종")
        
        # 선택된 업종 중 더 이상 존재하지 않는 업종이 있는지 확인하고 제거
        if hasattr(self, 'selected_biz_types') and self.selected_biz_types:
            valid_selected_biz = [biz for biz in self.selected_biz_types if biz in self.real_biz_set]
            if len(valid_selected_biz) != len(self.selected_biz_types):
                self.logger.info(f"선택된 업종 중 {len(self.selected_biz_types) - len(valid_selected_biz)}개가 제거되었습니다.")
                self.selected_biz_types = valid_selected_biz
                
                # 필터 표시 레이블 업데이트
                display_text = "; ".join(valid_selected_biz)
                if hasattr(self, 'lbl_selected_biz') and self.lbl_selected_biz:
                    self.lbl_selected_biz.setText(display_text if display_text else "(없음)")
                    self.lbl_selected_biz.setToolTip(display_text)
        
        # 필터 재적용
        self.apply_local_filter_manager_data() 