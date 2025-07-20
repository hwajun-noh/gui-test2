# my_selenium_tk_for_mylist.py

import tkinter as tk
from tkinter import messagebox, simpledialog, Entry, StringVar
import time
import re
import psutil
import requests
import json
import logging
import urllib.parse
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import Qt
# Selenium 관련
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

#########################################
# (A) 드라이버 초기화/유틸 함수
#########################################

def initialize_driver(
    headless=False,
    load_images=True,
    page_load_strategy="normal"
):
    """
    Selenium WebDriver 초기화 함수
    
    Args:
        headless: 헤드리스 모드 여부
        load_images: 이미지 로딩 여부
        page_load_strategy: 페이지 로드 전략 ('normal', 'eager', 'none')
    
    Returns:
        WebDriver 인스턴스
    """
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    
    # 연결 재시도 로직 추가
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            chrome_options = Options()
            
            # 헤드리스 모드
            if headless:
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--window-size=1280,1024")
            else:
                # 디버그 시 창 크게 보기
                chrome_options.add_argument("--start-maximized")
            
            # 이미지 로딩 비활성화 (성능 향상)
            if not load_images:
                prefs = {"profile.managed_default_content_settings.images": 2}
                chrome_options.add_experimental_option("prefs", prefs)
            
            # 페이지 로드 전략 설정
            chrome_options.page_load_strategy = page_load_strategy
            
            # 안정성 향상을 위한 추가 옵션
            chrome_options.add_argument("--disable-gpu")  # GPU 가속 비활성화
            chrome_options.add_argument("--no-sandbox")  # 샌드박스 비활성화
            chrome_options.add_argument("--disable-dev-shm-usage")  # 공유 메모리 사용 비활성화
            chrome_options.add_argument("--disable-extensions")  # 확장 프로그램 비활성화
            chrome_options.add_argument("--disable-browser-side-navigation")  # 브라우저 사이드 내비게이션 비활성화
            chrome_options.add_argument("--disable-site-isolation-trials")  # 사이트 격리 비활성화
            chrome_options.add_argument("--no-default-browser-check")  # 기본 브라우저 확인 비활성화
            chrome_options.add_argument("--ignore-certificate-errors")  # 인증서 오류 무시
            chrome_options.add_argument("--ignore-ssl-errors")  # SSL 오류 무시
            chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])  # 로깅 비활성화
            
            # WebDriver 초기화
            print(f"[INFO] ChromeDriver 초기화 시도 #{retry_count+1}...")
            driver = webdriver.Chrome(options=chrome_options)
            
            # 연결 확인 (빈 페이지 로드)
            driver.get("about:blank")
            print("[INFO] ChromeDriver 초기화 성공!")
            return driver
            
        except Exception as e:
            retry_count += 1
            print(f"[ERROR] ChromeDriver 초기화 실패 (시도 {retry_count}/{max_retries}): {e}")
            
            # 혹시 실패하더라도 남아있는 프로세스 정리
            try:
                kill_leftover_chromedriver()
            except:
                pass
            
            # 마지막 시도가 아니면 잠시 대기 후 재시도
            if retry_count < max_retries:
                wait_time = retry_count * 2  # 재시도마다 대기 시간 증가
                print(f"[INFO] {wait_time}초 후 재시도...")
                time.sleep(wait_time)
            
    # 모든 시도 실패
    print("[ERROR] 모든 ChromeDriver 초기화 시도 실패")
    raise RuntimeError("ChromeDriver 초기화 실패. 네트워크 연결과 Chrome 설치 상태를 확인하세요.")


def kill_leftover_chromedriver():
    """남아있는 chromedriver 프로세스 강제 종료"""
    for proc in psutil.process_iter():
        try:
            p_name = proc.name().lower()
            if "chromedriver" in p_name:
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


def create_naver_url(lat, lng):
    # naver_no 파라미터는 받지만, URL에는 붙이지 않음
    base_url = f"https://new.land.naver.com/offices?ms={lat},{lng},18&a=SG:SMS:GJCG:APTHGJ:GM:TJ&e=RETAIL"
    return base_url


def complete_address(address, district_data):
    """
    불완전한 주소를 완성합니다.
    district_data의 구/동 정보를 이용해 주소를 완성합니다.
    
    Args:
        address (str): 불완전한 주소 문자열
        district_data (dict): 구별 동 목록이 있는 딕셔너리
        
    Returns:
        str: 완성된 주소
    """
    if not address:
        return None
    
    print(f"[DEBUG] 주소 변환 시작: '{address}'")
        
    # 기본 지역 (대전) - 항상 "대전광역시"로 고정
    city = "대전광역시"
    
    # 이미 시/도가 포함된 경우에도 "대전광역시"로 시작하도록 설정
    # 대전 이외의 다른 지역이 포함된 경우에도 대전으로 강제 변환
    if any(address.startswith(city_prefix) for city_prefix in ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]):
        # 첫 공백 이후의 텍스트만 가져오기
        space_index = address.find(" ")
        if space_index > -1:
            address = address[space_index+1:]
    
    # 구 이름 직접 포함 확인 (예: "서구 둔산동", "중구 은행동" 등)
    district = None
    dong = None
    
    # 명시적 구 이름이 주소에 포함된 경우 (예: "서구 괴정동")
    for gu in district_data.keys():
        if gu in address:
            district = gu
            # 해당 구의 동 목록에서 동 찾기
            for d in district_data[gu]:
                if d in address:
                    dong = d
                    print(f"[DEBUG] 구({gu})와 동({d})을 모두 찾았습니다.")
                    break
            # 구는 찾았지만 동을 못 찾은 경우
            if not dong:
                print(f"[DEBUG] 구({gu})는 찾았으나 해당 구의 동을 찾지 못했습니다.")
            break
    
    # 구 이름이 없고 동 이름만 있는 경우 처리 (예: "괴정동 95-14")
    if not district:
        # 알려진 특수 동 이름 (여러 구에 동일한 이름이 있는 경우 매핑)
        special_dong_mapping = {
            "괴정동": "서구",    # 괴정동은 서구에 있음 (동구가 아님)
            "용계동": "동구",    # 용계동은 동구와 유성구 모두에 있지만, 기본적으로 동구로 처리
            "용계동 124": "유성구", # 특정 번지의 용계동은 유성구에 있음
            "신동": "유성구",    # 신동은 유성구에 있음
        }
        
        # 1. 특수 동 이름 먼저 확인
        for special_dong, mapped_gu in special_dong_mapping.items():
            if special_dong in address:
                district = mapped_gu
                dong = special_dong.split()[0]  # "용계동 124"에서 "용계동"만 추출
                print(f"[DEBUG] 특수 매핑: 동({dong})은 {district}에 있습니다.")
                break
                
        # 2. 특수 매핑이 없으면 모든 구의 동 목록을 순회
        if not district:
            # 발견된 모든 동 저장
            found_dongs = []
            
            for gu, dongs in district_data.items():
                for d in dongs:
                    if d in address:
                        found_dongs.append((gu, d))
            
            # 동을 찾은 경우
            if found_dongs:
                if len(found_dongs) > 1:
                    # 여러 동이 매칭된 경우 (예: "용계동"은 동구와 유성구 모두에 있음)
                    print(f"[DEBUG] 다중 매칭: {found_dongs}")
                    
                    # 더 긴 동 이름을 우선시 (예: "온천동"보다 "신온천동"이 우선)
                    found_dongs.sort(key=lambda x: len(x[1]), reverse=True)
                    
                    # 주소에서 동 이름의 위치를 찾아 더 정확히 매칭되는 것 선택
                    best_match = None
                    for gu, d in found_dongs:
                        # 동 이름이 주소에서 독립된 단어로 있는지 확인
                        # 예: "온천2동"이 "신온천동"보다 "온천동"에 더 가까움
                        if re.search(r'\b' + re.escape(d) + r'\b', address):
                            best_match = (gu, d)
                            break
                    
                    # 더 나은 매칭이 없으면 첫 번째 사용
                    if not best_match:
                        best_match = found_dongs[0]
                        
                    district, dong = best_match
                    print(f"[DEBUG] 최종 선택된 매칭: 동({dong})은 {district}에 있습니다.")
                else:
                    # 단일 매칭인 경우
                    district, dong = found_dongs[0]
                    print(f"[DEBUG] 단일 매칭: 동({dong})은 {district}에 있습니다.")
    
    # 3. 번지수 패턴 확인 (예: "123-45", "123번지" 등)
    has_address_number = bool(re.search(r'\d+(-\d+)?(\s?번지)?', address))
    
    # 주소 조합
    if district and dong:
        # 이미 동이 포함되어 있는지 확인
        if dong in address:
            # 이미 구가 포함되어 있는지 확인
            if district in address:
                full_address = f"{city} {address}"
            else:
                full_address = f"{city} {district} {address}"
        else:
            full_address = f"{city} {district} {dong} {address}"
    elif district:
        full_address = f"{city} {district} {address}"
    else:
        # 아무 정보도 없으면 대전시청 붙여서 반환
        full_address = f"{city} {address}"
    
    # 번지수가 있어서 주소로 인식할 수 있는지 확인
    address_quality = "높음" if has_address_number else "낮음"
    print(f"[DEBUG] 주소 변환 결과: '{full_address}' (번지수 포함: {has_address_number}, 품질: {address_quality})")
    
    return full_address


def naver_geocode(address, client_id="tyflqyq5uv", client_secret="kD4Ru39nlD8dguN49DEnZsJeVZPMUPkbG9bBvkNh"):
    """
    네이버 클라우드 플랫폼의 Geocoding API를 사용하여 주소를 좌표로 변환합니다.
    
    Args:
        address (str): 주소 문자열
        client_id (str): 네이버 클라우드 플랫폼 클라이언트 ID (기본값 제공됨)
        client_secret (str): 네이버 클라우드 플랫폼 클라이언트 시크릿 (기본값 제공됨)
        
    Returns:
        tuple: (위도, 경도) 또는 실패 시 None
    """
    try:
        # 주소가 없으면 처리할 수 없음
        if not address:
            print("[ERROR] 역지오코딩 실패: 주소가 비어있음")
            return None, None
            
        # URL 인코딩
        encoded_address = urllib.parse.quote(address)
        
        # 네이버 클라우드 플랫폼 Geocoding API
        url = f"https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode?query={encoded_address}"
        print(f"[DEBUG] 네이버 API 요청: {url}")
        
        headers = {
            'X-NCP-APIGW-API-KEY-ID': client_id,      # 클라이언트 ID
            'X-NCP-APIGW-API-KEY': client_secret,     # 클라이언트 Secret
            'Accept': 'application/json'
        }
        
        print(f"[INFO] 네이버 지도 API 호출 시작 - 주소: '{address}'")
        response = requests.get(url, headers=headers)
        
        # HTTP 에러 코드 확인 및 로깅
        if response.status_code != 200:
            print(f"[ERROR] 네이버 API 응답 오류 - 상태 코드: {response.status_code}")
            print(f"[ERROR] 응답 내용: {response.text}")
            return None, None
            
        # JSON 파싱
        try:
            data = response.json()
            print(f"[DEBUG] 네이버 API 응답: {data}")
        except Exception as json_e:
            print(f"[ERROR] JSON 파싱 오류: {str(json_e)}")
            print(f"[ERROR] 원본 응답: {response.text[:200]}...")  # 첫 200자만 로깅
            return None, None
        
        # 결과 확인
        if data and 'status' in data and data['status'] == 'OK' and 'addresses' in data and data['addresses']:
            first_result = data['addresses'][0]
            lat = first_result.get('y')
            lng = first_result.get('x')
            
            # 추가 정보 로깅
            jibun_addr = first_result.get('jibunAddress', '')
            road_addr = first_result.get('roadAddress', '')
            print(f"[INFO] 좌표 변환 성공: 위도={lat}, 경도={lng}")
            print(f"[INFO] 주소정보: 지번주소='{jibun_addr}', 도로명주소='{road_addr}'")
            
            return lat, lng
        else:
            error_message = "알 수 없는 오류"
            if 'status' in data and data['status'] != 'OK':
                error_message = f"API 상태 코드: {data.get('status')}"
            elif 'errorMessage' in data:
                error_message = data.get('errorMessage')
            
            print(f"[ERROR] 역지오코딩 실패: {error_message} (주소: {address})")
            return None, None
    
    except Exception as e:
        print(f"[ERROR] 역지오코딩 중 예외 발생: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None, None


def click_cadastral_map(driver):
    """
    '지적도로 보기' 버튼 클릭
    """
    btn = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, ".map_control--tool[aria-label='지적도로 보기']"))
    )
    driver.execute_script("arguments[0].click();", btn)


#########################################
# (B) Tkinter App (mylist용)
#########################################

class SangaCheckAppMylist:
    def __init__(self, data_list, parent_app=None, start_index=0, row_callback=None):
        """
        마이리스트용 상가 검수 창 초기화
        
        Args:
            data_list: 검토할 데이터 목록 (리스트)
            parent_app: 부모 애플리케이션 참조
            start_index: 시작할 행 인덱스 (0부터 시작)
            row_callback: 행 변경 시 호출할 콜백 함수
        """
        # data_list 유효성 검사
        if isinstance(data_list, dict):
            print("[WARNING] 딕셔너리가 전달되어 리스트로 변환합니다.")
            self.data_list = [data_list]  # 단일 항목을 리스트로 변환
        elif not isinstance(data_list, list):
            print(f"[ERROR] 지원되지 않는 데이터 유형: {type(data_list)}")
            self.data_list = []  # 빈 리스트로 초기화
        else:
            self.data_list = data_list
            
        # 데이터 크기 로깅
        total_items = len(self.data_list)
        print(f"[INFO] SangaCheckAppMylist 초기화: 데이터 항목 수 = {total_items}개")
        
        # 한 행만 있다면 - 전체 데이터를 구성해야 함
        if total_items == 1:
            print("[WARNING] 단일 행만 전달되었습니다. 전체 행을 강제로 구성합니다.")
            
            # 1. 첫 번째 행에서 주소 추출
            if isinstance(self.data_list[0], dict) and 'addr' in self.data_list[0]:
                addr = self.data_list[0].get('addr', '')
                print(f"[INFO] 기준 주소: {addr}")
                
                # 2. 주소에서 동 추출
                import re
                dong_match = re.search(r'([가-힣]+동|[가-힣]+면)', addr)
                if dong_match:
                    dong = dong_match.group(1)
                    print(f"[INFO] 추출된 동: {dong}")
                    
                    # 3. 부모 앱이 존재하는 경우 해당 동의 모든 행을 가져오기 시도
                    if parent_app:
                        print(f"[INFO] 부모 앱에서 '{dong}' 관련 모든 행 검색 시도 중...")
                        
                        # 3.1. 부모 앱에서 get_rows_by_dong 메서드 호출 시도
                        if hasattr(parent_app, 'get_rows_by_dong'):
                            try:
                                all_rows = parent_app.get_rows_by_dong(dong)
                                if all_rows and len(all_rows) > 1:
                                    print(f"[INFO] '{dong}'에 대한 {len(all_rows)}개 행 발견!")
                                    self.data_list = all_rows
                                    total_items = len(all_rows)
                            except Exception as e:
                                print(f"[WARNING] get_rows_by_dong 호출 실패: {e}")
                        
                        # 3.2. 부모 앱에서 테이블 데이터를 직접 검색
                        if total_items <= 1 and hasattr(parent_app, 'tableWidget'):
                            try:
                                row_count = parent_app.tableWidget.rowCount()
                                matching_rows = []
                                
                                print(f"[INFO] 테이블에서 '{dong}' 포함된 행 검색 중 (총 {row_count}행)...")
                                
                                for i in range(row_count):
                                    try:
                                        # 각 행에서 주소 추출 (일반적으로 1열에 주소가 있음)
                                        addr_item = parent_app.tableWidget.item(i, 1)
                                        if addr_item and dong in addr_item.text():
                                            # 일치하는 행 데이터 가져오기
                                            if hasattr(parent_app, 'get_row_data'):
                                                row_data = parent_app.get_row_data(i)
                                                if row_data:
                                                    matching_rows.append(row_data)
                                            # 또는 간단한 딕셔너리로 구성
                                            else:
                                                row_dict = {}
                                                for col in range(parent_app.tableWidget.columnCount()):
                                                    item = parent_app.tableWidget.item(i, col)
                                                    header = parent_app.tableWidget.horizontalHeaderItem(col)
                                                    if item and header:
                                                        key = header.text().lower().replace(' ', '_')
                                                        row_dict[key] = item.text()
                                                # 필수 필드 추가
                                                row_dict['id'] = i
                                                row_dict['idx'] = i
                                                matching_rows.append(row_dict)
                                    except Exception as row_err:
                                        print(f"[WARNING] 행 {i} 처리 중 오류: {row_err}")
                                
                                if len(matching_rows) > 1:
                                    print(f"[INFO] 테이블에서 '{dong}' 관련 {len(matching_rows)}개 행 발견!")
                                    self.data_list = matching_rows
                                    total_items = len(matching_rows)
                                
                            except Exception as e:
                                print(f"[WARNING] 테이블 검색 실패: {e}")
                
                # 4. 그래도 안 되면 부모 앱의 다른 탭에서 데이터 가져오기 시도
                if total_items <= 1 and parent_app:
                    # 4.1 탭 속성 검색
                    for tab_attr in ['mylistTab', 'myListTab', 'tabMyList', 'shopTab', 'tabShop']:
                        if hasattr(parent_app, tab_attr):
                            tab = getattr(parent_app, tab_attr)
                            print(f"[INFO] 부모 앱의 {tab_attr}에서 데이터 가져오기 시도...")
                            
                            # 탭에서 전체 데이터 가져오기 시도
                            if hasattr(tab, 'get_all_data'):
                                try:
                                    tab_data = tab.get_all_data()
                                    if tab_data and len(tab_data) > 1:
                                        print(f"[INFO] {tab_attr}에서 {len(tab_data)}개 행 발견!")
                                        self.data_list = tab_data
                                        break
                                except Exception as e:
                                    print(f"[WARNING] {tab_attr}.get_all_data() 호출 실패: {e}")
        
        # 첫 항목 샘플 출력 (디버깅용)
        if total_items > 0:
            first_item = self.data_list[0]
            if isinstance(first_item, dict):
                sample_keys = list(first_item.keys())[:5]
                print(f"[DEBUG] 데이터 샘플 키: {sample_keys}")
                # 주소 샘플 출력
                if 'addr' in first_item:
                    print(f"[DEBUG] 첫 번째 행 주소: {first_item['addr']}")
                # 마지막 행 주소도 출력
                if total_items > 1 and isinstance(self.data_list[-1], dict) and 'addr' in self.data_list[-1]:
                    print(f"[DEBUG] 마지막 행 주소: {self.data_list[-1]['addr']}")
        
        self.parent_app = parent_app
        
        # 시작 인덱스 유효성 검사
        if start_index < 0 or (total_items > 0 and start_index >= total_items):
            print(f"[WARNING] 시작 인덱스({start_index})가 범위를 벗어났습니다. 0으로 설정합니다.")
            self.idx = 0
        else:
            self.idx = start_index
            
        self.row_callback = row_callback
        
        # 네이버 API 키 - 하드코딩
        self.client_id = "tyflqyq5uv"
        self.client_secret = "kD4Ru39nlD8dguN49DEnZsJeVZPMUPkbG9bBvkNh"
        
        # district_data를 parent_app에서 가져오거나 기본값 사용
        self.district_data = getattr(parent_app, 'district_data', {
            "동구": ["가양동","가오동","구도동","낭월동","내탑동","대동","대별동","대성동","마산동","비룡동",
                "사성동","삼괴동","삼성동","삼정동","상소동","성남동","세천동","소제동","소호동","신상동",
                "신안동","신촌동","신하동","신흥동","용계동","용운동","용전동","원동","이사동",
                "인동","자양동","장척동","정동","주산동","주촌동","중동","직동","천동","추동","판암동",
                "하소동","홍도동","효동","효평동"],
            "서구": ["가수원동","가장동","갈마동","관저동","괴곡동","괴정동","내동","도마동","도안동","둔산동",
                "만년동","매노동","변동","복수동","봉곡동","산직동","오동","용문동","용촌동","우명동",
                "원정동","월평동","장안동","정림동","탄방동","흑석동"],
            "유성구": ["가정동","갑동","계산동","관평동","교촌동","구룡동","구성동","구암동","궁동","금고동",
                "금탄동","노은동","대정동","덕명동","덕진동","도룡동","둔곡동","문지동","반석동",
                "방동","방현동","복용동","봉명동","봉산동","상대동","성북동","세동","송강동","송정동",
                "수남동","신동","신봉동","신성동","안산동","어은동","외삼동","용계동","용산동","원내동",
                "원신흥동","원촌동","자운동","장대동","전민동","죽동","지족동","추목동",
                "탑립동",
                "하기동","학하동","화암동"],
            "중구": ["구완동","금동","대사동","대흥동","목달동","목동","무수동","문창동","문화동","부사동",
                "사정동","산성동","석교동","선화동","안영동","어남동","오류동","옥계동","용두동","유천동",
                "은행동","정생동","중촌동","침산동","태평동","호동"],
            "대덕구": ["갈전동","대화동","덕암동","목상동","문평동","미호동","법동","부수동","비래동","삼정동",
                "상서동","석봉동","송촌동","신대동","신일동","신탄진동","연축동","오정동","와동","용호동",
                "읍내동","이현동","중리동","평촌동","황호동"]
        })

        # 1. 먼저 Tkinter UI 초기화
        self.root = tk.Tk()
        self.root.title("상가 검수(mylist전용)")
        window_width = 420
        window_height = 500  # 주소 검색 필드 추가로 높이 증가

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        # 오른쪽에서 2cm(약 75픽셀) 떨어지게 설정
        x_pos = screen_w - window_width - 75
        y_pos = 0
        self.root.geometry(f"{window_width}x{window_height}+{x_pos}+{y_pos}")
        self.root.attributes("-topmost", True)
        
        # 종료 플래그 초기화
        self.closing = False
        
        # 윈도우 종료 프로토콜 설정
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        ### 주소 검색 프레임 추가 ###
        self.search_frame = tk.Frame(self.root)
        self.search_frame.pack(pady=5, padx=5, fill=tk.X)
        
        # 주소 입력 필드
        self.address_var = tk.StringVar()
        tk.Label(self.search_frame, text="주소:").grid(row=0, column=0, padx=5, sticky=tk.W)
        self.address_entry = tk.Entry(self.search_frame, textvariable=self.address_var, width=30)
        self.address_entry.grid(row=0, column=1, padx=5, sticky=tk.W+tk.E)
        # 엔터키 바인딩 추가
        self.address_entry.bind("<Return>", lambda event: self.search_address())
        
        # 검색 버튼
        self.search_btn = tk.Button(self.search_frame, text="검색", command=self.search_address, width=8)
        self.search_btn.grid(row=0, column=2, padx=5)

        ### (A) "필드별 라벨"을 담는 Frame ###
        self.info_frame = tk.Frame(self.root)
        self.info_frame.pack(pady=10, padx=5, anchor="nw")
        self.lbl_index = tk.Label(self.info_frame, font=("맑은 고딕", 14), anchor="w")
        self.lbl_index.pack(anchor="w")
        # 필드별 라벨을 여러 개 만듭니다.
        self.lbl_naver_no = tk.Label(self.info_frame, font=("맑은 고딕", 14), anchor="w")
        self.lbl_naver_no.pack(anchor="w")

        self.lbl_addr = tk.Label(self.info_frame, font=("맑은 고딕", 14), anchor="w")
        self.lbl_addr.pack(anchor="w")

        self.lbl_ho = tk.Label(self.info_frame, font=("맑은 고딕", 14), anchor="w")
        self.lbl_ho.pack(anchor="w")

        self.lbl_floor = tk.Label(self.info_frame, font=("맑은 고딕", 14), anchor="w")
        self.lbl_floor.pack(anchor="w")

        self.lbl_deposit_rent = tk.Label(self.info_frame, font=("맑은 고딕", 14), anchor="w")
        self.lbl_deposit_rent.pack(anchor="w")

        self.lbl_premium = tk.Label(self.info_frame, font=("맑은 고딕", 14), anchor="w")
        self.lbl_premium.pack(anchor="w")

        self.lbl_current_use = tk.Label(self.info_frame, font=("맑은 고딕", 14), anchor="w")
        self.lbl_current_use.pack(anchor="w")

        self.lbl_area = tk.Label(self.info_frame, font=("맑은 고딕", 14), anchor="w")
        self.lbl_area.pack(anchor="w")

        self.lbl_phone = tk.Label(self.info_frame, font=("맑은 고딕", 14), anchor="w")
        self.lbl_phone.pack(anchor="w")

        self.lbl_approve = tk.Label(self.info_frame, font=("맑은 고딕", 14), anchor="w")
        self.lbl_approve.pack(anchor="w")

        self.lbl_memo = tk.Label(self.info_frame, font=("맑은 고딕", 14), anchor="w")
        self.lbl_memo.pack(anchor="w")

        self.lbl_ad_end = tk.Label(self.info_frame, font=("맑은 고딕", 14), anchor="w")
        self.lbl_ad_end.pack(anchor="w")

        frm_bottom = tk.Frame(self.root)
        frm_bottom.pack(side=tk.BOTTOM, pady=5)

        self.btn_next = tk.Button(frm_bottom, text="다음", command=self.on_next, width=10)
        self.btn_next.grid(row=0, column=0, padx=5)

        self.btn_input = tk.Button(frm_bottom, text="행번호입력", command=self.on_row_input, width=10)
        self.btn_input.grid(row=0, column=1, padx=5)

        self.btn_close = tk.Button(frm_bottom, text="닫기", command=self.on_close, width=10)
        self.btn_close.grid(row=0, column=2, padx=5)
        
        # 초기 UI 표시 (Selenium 초기화 전에 현재 데이터로 UI 업데이트)
        self.display_current_info()
        
        # 2. 그 다음 Selenium 초기화 (백그라운드 작업 구조화)
        try:
            print("[INFO] ChromeDriver 프로세스 정리 중...")
            kill_leftover_chromedriver()
            print("[INFO] ChromeDriver 초기화 시작...")
            self.driver = initialize_driver(headless=False, load_images=True, page_load_strategy="eager")
            self.driver.delete_all_cookies()
            self.driver.get("about:blank")
            print("[INFO] ChromeDriver 초기화 완료")
            
            # 시작 인덱스가 유효한 경우 지도 로드
            if 0 <= self.idx < len(self.data_list):
                print(f"[INFO] 행번호 {self.idx+1}번으로 지도 로딩 중...")
                loaded_ok = self.auto_map_load()
                if loaded_ok:
                    print(f"[INFO] 지도 로딩 성공 - 지적도 표시 중...")
                    click_cadastral_map(self.driver)
                else:
                    print(f"[WARN] 지도 로딩 실패 - UI만 표시합니다.")
            else:
                print(f"[WARN] 시작 인덱스({start_index})가 유효하지 않아 지도를 로드하지 않습니다.")
        except Exception as e:
            print(f"[ERROR] ChromeDriver 초기화 실패: {e}")
            import traceback
            print(traceback.format_exc())

    def run(self):
        """
        Tkinter 메인루프 실행 및 리소스 정리
        """
        try:
            self.root.mainloop()
        except Exception as e:
            print(f"[ERROR] mylist Tkinter mainloop 실행 중 오류: {e}")
            import traceback
            print(traceback.format_exc())
        finally:
            # 리소스 정리 재시도 (혹시 on_close가 제대로 호출되지 않은 경우)
            try:
                # 이미 종료 중인지 확인
                if not getattr(self, 'closing', False):
                    print("[WARNING] 메인루프 종료 후 리소스 정리 시도")
                    self.cleanup_resources()
            except:
                pass
                
        return self.data_list  # mylist에선 수정 없음
        
    def cleanup_resources(self):
        """
        모든 리소스를 안전하게 정리하는 메서드
        """
        # 종료 중임을 표시
        self.closing = True
        
        # 1. 셀레니움 드라이버 종료
        try:
            print("[INFO] 셀레니움 드라이버 종료 중...")
            if hasattr(self, 'driver') and self.driver:
                self.driver.quit()
                self.driver = None
                print("[INFO] 셀레니움 드라이버 정상 종료 완료")
        except Exception as e:
            print(f"[WARN] 셀레니움 드라이버 종료 중 오류: {e}")
            try:
                # 강제 종료 시도
                kill_leftover_chromedriver()
                print("[INFO] chromedriver 프로세스 강제 종료 시도 완료")
            except Exception as kill_err:
                print(f"[ERROR] chromedriver 강제 종료 중 오류: {kill_err}")
        
        # 2. 부모 앱에 종료 알림
        try:
            if hasattr(self, 'parent_app') and self.parent_app:
                if hasattr(self.parent_app, 'set_terminating'):
                    self.parent_app.set_terminating(True)
                    print("[INFO] 애플리케이션 종료 플래그 설정 완료")
                
                # 부모 앱에 창 종료 알림 (메서드가 있는 경우)
                if hasattr(self.parent_app, 'on_mylist_tk_closed'):
                    try:
                        self.parent_app.on_mylist_tk_closed()
                        print("[INFO] 부모 앱에 창 종료 이벤트 알림 완료")
                    except Exception as e:
                        print(f"[WARNING] 부모 앱 종료 알림 실패: {e}")
        except Exception as e:
            print(f"[WARN] 종료 플래그 설정 중 오류: {e}")
            
        print("[INFO] 리소스 정리 완료")

    def on_close(self):
        """
        창이 닫힐 때 모든 리소스를 안전하게 정리합니다.
        ThreadPoolExecutor는 직접 종료하지 않고 부모 앱에 상태만 알립니다.
        """
        print("[INFO] 상가 검수 창 종료 시작...")
        
        # 중복 종료 방지
        if getattr(self, 'closing', False):
            print("[INFO] 이미 종료 중입니다.")
            return
        
        # 리소스 정리
        self.cleanup_resources()
        
        # 마지막으로 Tk 창 닫기
        try:
            self.root.destroy()
            print("[INFO] mylist Tk 창 정상 종료 완료")
        except Exception as e:
            print(f"[ERROR] mylist Tk 창 종료 중 오류: {e}")
        
        print("[INFO] 상가 검수 창 종료 완료")

    def on_next(self):
        """
        '다음' 버튼 클릭 시 다음 행으로 이동하는 기능입니다.
        """
        if self.idx < 0 or self.idx >= len(self.data_list):
            print("[경고] 현재 인덱스가 범위를 벗어났습니다.")
            return
            
        # 다음 행 계산
        new_idx = self.idx + 1
        total_rows = len(self.data_list)
        
        # 마지막 행인 경우 종료
        if new_idx >= total_rows:
            messagebox.showinfo("완료", "마지막 매물까지 확인 완료!")
            print(f"[INFO] 마지막 행({total_rows})까지 모두 확인 완료!")
            self.on_close()
            return
            
        # 행 이동 로깅
        print(f"[INFO] 다음 행으로 이동: {self.idx+1} → {new_idx+1} / {total_rows}")
        self.idx = new_idx

        # 지도 로딩
        loaded_ok = self.auto_map_load()
        if loaded_ok:
            click_cadastral_map(self.driver)
            
        # UI 업데이트
        self.display_current_info()

        # 콜백 호출 (행 변경 알림)
        rowd = self.data_list[self.idx]
        pk_id = rowd.get("id")
        if pk_id and self.row_callback:
            print(f"[INFO] 행 변경 콜백 호출: pk_id={pk_id}, row_idx={self.idx}")
            self.row_callback(pk_id, self.idx)

    def on_row_input(self):
        """
        사용자가 직접 이동할 행번호를 입력하는 다이얼로그를 표시합니다.
        입력된 번호는 1부터 시작하는 행번호입니다.
        """
        total_rows = len(self.data_list)
        row = simpledialog.askinteger(
            "행번호 입력", 
            f"이동할 행번호(1~{total_rows})를 입력하세요:", 
            parent=self.root
        )
        
        if row is None:  # 취소 버튼을 누른 경우
            return
            
        new_idx = row - 1  # 내부 인덱스는 0부터 시작
        if new_idx < 0 or new_idx >= total_rows:
            messagebox.showerror("오류", f"유효한 행번호가 아닙니다. 1~{total_rows} 사이의 값을 입력하세요.")
            return

        print(f"[INFO] 행번호 {row}번으로 이동합니다. (인덱스: {new_idx})")
        self.idx = new_idx
        
        # 지도 로딩
        loaded_ok = self.auto_map_load()
        if loaded_ok:
            click_cadastral_map(self.driver)
        
        # UI 업데이트
        self.display_current_info()

        # 콜백 호출 (선택된 행이 변경됨을 부모에게 알림)
        rowd = self.data_list[self.idx]
        pk_id = rowd.get("id")
        if pk_id and self.row_callback:
            self.row_callback(pk_id, self.idx)

    def display_current_info(self):
        # 1. 먼저 data_list 유효성과 크기 확인 (디버깅)
        try:
            data_len = len(self.data_list)
            print(f"[DEBUG] display_current_info: 전체 행 수={data_len}, 현재 인덱스={self.idx}")
            
            # 데이터 형식 로깅 (첫 번째 항목만)
            if data_len > 0:
                first_item = self.data_list[0]
                if isinstance(first_item, dict):
                    sample_keys = list(first_item.keys())[:5]  # 처음 5개 키만 표시
                    print(f"[DEBUG] 데이터 샘플 키: {sample_keys}")
                else:
                    print(f"[WARNING] 첫 번째 항목이 딕셔너리가 아님: {type(first_item)}")
        except Exception as e:
            print(f"[ERROR] data_list 디버깅 중 오류: {e}")
            
        # 2. 범위 확인 
        if self.idx < 0 or self.idx >= len(self.data_list):
            # 범위초과 -> 각 라벨 초기화
            total_rows = len(self.data_list)
            self.lbl_index.config(text=f"[범위초과 {self.idx+1}] (총 {total_rows}행)", fg="red")
            self.lbl_naver_no.config(text="[범위초과]", fg="red")
            self.lbl_addr.config(text="", fg="black")
            self.lbl_ho.config(text="", fg="black")
            self.lbl_floor.config(text="", fg="black")
            self.lbl_deposit_rent.config(text="", fg="black")
            self.lbl_premium.config(text="", fg="black")
            self.lbl_current_use.config(text="", fg="black")
            self.lbl_area.config(text="", fg="black")
            self.lbl_phone.config(text="", fg="black")
            self.lbl_approve.config(text="", fg="black")
            self.lbl_memo.config(text="", fg="black")
            self.lbl_ad_end.config(text="", fg="black")
            return
        
        try:
            # 행 번호 표시 (1부터 시작하도록)
            total_count = len(self.data_list)
            current_row = self.idx + 1
            self.lbl_index.config(text=f"행번호: ({current_row}/{total_count})", fg="blue", font=("맑은 고딕", 14, "bold"))
            self.root.title(f"상가 검수(mylist전용) - {current_row}/{total_count}")

            # 안전하게 데이터 가져오기
            try:
                rowd = self.data_list[self.idx]
                if not isinstance(rowd, dict):
                    print(f"[오류] 데이터가 딕셔너리가 아님: {type(rowd)}")
                    rowd = {}  # 빈 딕셔너리로 초기화
            except Exception as e:
                print(f"[오류] 데이터 접근 중 오류: {e}")
                rowd = {}  # 오류 발생시 빈 딕셔너리로 초기화
            
            # 모든 필드에 대해 안전하게 가져오기
            # 네이버 매물번호 처리 (여러 키 이름 시도)
            naver_no = rowd.get("naver_no", "") or rowd.get("매물번호", "") or rowd.get("naver_property_no", "")
            serve_no = rowd.get("serve_no", "") or rowd.get("serve_property_no", "")
            
            # 매물번호 문자열 생성
            if naver_no and serve_no:
                full_no_str = f"{naver_no}/{serve_no}"
            elif naver_no:
                full_no_str = naver_no
            elif serve_no:
                full_no_str = serve_no
            else:
                # 자체 매물번호 있는지 확인
                full_no_str = rowd.get("매물번호", "")
            
            # 각 필드에 대해 여러 가능한 키 이름 확인 (다양한 키 이름 시도)
            address_str = rowd.get("addr", "") or rowd.get("주소", "")
            ho_val = rowd.get("ho", "") or rowd.get("호", "")
            floor_val = rowd.get("floor", "") or rowd.get("층", "")
            
            # 보증금/월세 처리 (복합 필드)
            deposit_rent = rowd.get("deposit_rent", "") or rowd.get("보증금/월세", "")
            if not deposit_rent:
                # 개별 필드 시도
                deposit = rowd.get("deposit", "") or rowd.get("보증금", "")
                rent = rowd.get("rent", "") or rowd.get("월세", "")
                if deposit or rent:
                    deposit_rent = f"{deposit}/{rent}" if deposit and rent else deposit or rent
            
            premium_val = rowd.get("premium", "") or rowd.get("권리금", "")
            use_val = rowd.get("current_use", "") or rowd.get("현업종", "")
            area_val = rowd.get("area", "") or rowd.get("평수", "")
            phone_val = rowd.get("owner_phone", "") or rowd.get("연락처", "")
            appr_val = rowd.get("approval_date", "") or rowd.get("사용승인일", "")
            memo_val = rowd.get("memo", "") or rowd.get("메모", "")
            ad_end_val = rowd.get("ad_end_date", "") or rowd.get("광고종료일", "")

            # (㎡ -> 평) 계산
            pyeong_str = ""
            try:
                if area_val and isinstance(area_val, str):
                    # 여러 형식 처리
                    clean_area = area_val.replace('㎡', '').replace('m²', '').strip()
                    if clean_area:
                        sqm = float(clean_area)
                        pyeong = sqm / 3.3058
                        pyeong_str = f"({pyeong:.2f}평)"
            except (ValueError, TypeError) as e:
                print(f"[경고] 평수 변환 실패: {area_val} - {e}")
                pass

            #### (B) 필드별 함수 ####
            def set_label(label_widget, prefix, value):
                """
                - 값이 비어있으면 빨간색, 아니면 검정색.
                - prefix: "매물번호", "주소" 등
                """
                try:
                    if value is None:  # None 값 처리
                        label_widget.config(text=f"{prefix}: (None)", fg="red")
                    elif not str(value).strip():  # 빈 문자열이나 공백만 있는 경우
                        label_widget.config(text=f"{prefix}: (비어있음)", fg="red")
                    else:
                        label_widget.config(text=f"{prefix}: {value}", fg="black")
                except Exception as e:
                    print(f"[오류] 라벨 설정 중 오류 ({prefix}): {e}")
                    try:
                        label_widget.config(text=f"{prefix}: (오류)", fg="red")
                    except:
                        pass

            # (C) 이제 각 라벨에 값을 설정
            full_area_str = f"{area_val}㎡ {pyeong_str}".strip()

            # (B) 각 라벨 업데이트
            try:
                set_label(self.lbl_naver_no,      "매물번호",    full_no_str)
                set_label(self.lbl_addr,          "주소",        address_str)
                set_label(self.lbl_ho,            "호",          ho_val)
                set_label(self.lbl_floor,         "층",          floor_val)
                set_label(self.lbl_deposit_rent,  "보증금/월세", deposit_rent)
                set_label(self.lbl_premium,       "권리금",      premium_val)
                set_label(self.lbl_current_use,   "현업종",      use_val)
                set_label(self.lbl_area,          "평수",        full_area_str)
                set_label(self.lbl_phone,         "연락처",      phone_val)
                set_label(self.lbl_approve,       "사용승인일",  appr_val)
                set_label(self.lbl_memo,          "메모",        memo_val)
                set_label(self.lbl_ad_end,        "광고종료일",  ad_end_val)
            except Exception as e:
                print(f"[오류] 라벨 업데이트 중 오류: {e}")
                
        except Exception as e:
            print(f"[오류] display_current_info 실행 중 오류: {e}")
            import traceback
            print(traceback.format_exc())

    def search_address(self):
        """
        사용자가 입력한 주소로 지도를 로딩합니다.
        """
        try:
            address = self.address_var.get().strip()
            if not address:
                messagebox.showwarning("주소 없음", "검색할 주소를 입력하세요.")
                return
            
            print(f"[INFO] 주소 검색: '{address}'")
            
            # 주소 완성하기 (도시 항상 대전광역시)
            full_addr = complete_address(address, self.district_data)
            
            # 네이버 지도 API로 좌표 변환
            lat, lng = naver_geocode(full_addr, self.client_id, self.client_secret)
            
            if lat and lng:
                print(f"[INFO] 좌표 변환 성공: {lat}, {lng}")
                url = create_naver_url(lat, lng)
                print(f"[INFO] 지도 URL: {url}")
                self.driver.get(url)
                
                # 지적도 보기 추가
                click_cadastral_map(self.driver)
                
            else:
                print(f"[경고] 좌표 변환 실패. 대전시청 기본값 사용")
                # 대전시청 좌표 (기본값)
                lat = "36.3504119"
                lng = "127.3845475"
                url = create_naver_url(lat, lng)
                self.driver.get(url)
                click_cadastral_map(self.driver)
                
        except Exception as e:
            print(f"[ERROR] 주소 검색 중 오류: {e}")
            import traceback
            print(traceback.format_exc())
            messagebox.showerror("오류", f"주소 검색 중 오류가 발생했습니다: {str(e)}")

    def auto_map_load(self):
        """
        셀레니움으로 지도 페이지 로딩:
         - lat,lng,naver_no 이용
         - 광고 종료시(에러) articleNo 제거 후 지도만 표시
         - 좌표 없을 시 district_data를 이용해 주소 완성 후 좌표 얻기
        """
        try:
            # 안전하게 데이터 가져오기
            try:
                if self.idx < 0 or self.idx >= len(self.data_list):
                    print("[경고] 인덱스 범위 초과")
                    return False
                
                rowd = self.data_list[self.idx]
                if not isinstance(rowd, dict):
                    print(f"[오류] 데이터가 딕셔너리가 아님: {type(rowd)}")
                    rowd = {}  # 빈 딕셔너리로 초기화
            except Exception as e:
                print(f"[오류] 데이터 접근 중 오류: {e}")
                rowd = {}  # 오류 발생시 빈 딕셔너리로 초기화
            
            lat_ = rowd.get("lat", "")
            lng_ = rowd.get("lng", "")
            
            # 위도/경도가 없거나 서울시청 기본값인 경우 주소로 찾기 시도
            is_default_coords = (lat_ == "37.5665" and lng_ == "126.9780")
            
            if not lat_ or not lng_ or is_default_coords:
                addr = rowd.get("addr", "")
                print(f"[INFO] 좌표 정보 없거나 기본값임. 주소로 좌표 탐색: '{addr}'")
                
                if not addr:
                    print("[ERROR] 주소가 비어있어 좌표 변환 불가능. 기본값 사용")
                    # 대전시청 좌표 (기본값)
                    lat_ = "36.3504119"
                    lng_ = "127.3845475"
                else:
                    # 주소 완성하기 (도시 항상 대전광역시)
                    full_addr = complete_address(addr, self.district_data)
                    
                    # 네이버 지도 API로 좌표 변환 (3번까지 시도)
                    retry_count = 3
                    lat_, lng_ = None, None
                    
                    while retry_count > 0 and (not lat_ or not lng_):
                        lat_, lng_ = naver_geocode(full_addr, self.client_id, self.client_secret)
                        if lat_ and lng_:
                            break
                        retry_count -= 1
                        if retry_count > 0:
                            print(f"[INFO] 좌표 변환 재시도 (남은 시도: {retry_count})")
                            time.sleep(1)  # 재시도 전 1초 대기
                    
                    # 좌표를 얻었으면 데이터에 저장
                    if lat_ and lng_:
                        print(f"[INFO] 좌표 변환 성공: {lat_}, {lng_}")
                        rowd["lat"] = lat_
                        rowd["lng"] = lng_
                    else:
                        print(f"[경고] 좌표 변환 실패. 대전시청 기본값 사용")
                        # 대전시청 좌표 (기본값)
                        lat_ = "36.3504119"
                        lng_ = "127.3845475"
            
            url = create_naver_url(lat_, lng_)
            print(f"[INFO] 지도 URL: {url}")
            self.driver.get(url)
            
            # 지도 로딩 대기
            print(f"[INFO] 지도 로딩 완료: {lat_}, {lng_}")
            return True
            
        except Exception as e:
            print(f"[ERROR] 지도 로딩 중 오류: {e}")
            import traceback
            print(traceback.format_exc())
            return False


def launch_selenium_tk_for_mylist(
    data_list,
    parent_app=None,
    row_callback=None,
    start_index=0
):
    """
    마이리스트 '상가(새광고)' 탭에서 쓸 전용 함수.
    
    [중요] 호출하는 쪽에서 반드시 아래와 같이 전체 데이터를 전달해야 합니다:
    
    # 올바른 사용법:
    full_data = self.get_all_data()  # 전체 데이터
    current_idx = self.get_selected_row_index()  # 현재 선택된 행 번호
    updated = launch_selenium_tk_for_mylist(
        data_list=full_data,  # 전체 데이터
        parent_app=self,
        row_callback=self.on_row_selected,
        start_index=current_idx  # 선택된 행 번호
    )
    
    Args:
        data_list (list): 전체 데이터 리스트
        parent_app: 부모 앱 참조
        row_callback: 행 변경 시 호출할 콜백
        start_index: 시작 인덱스 (0부터 시작)
        
    Returns:
        list: 업데이트된 데이터 리스트
    """
    # data_list 유효성 확인
    if not data_list:
        print("[ERROR] data_list가 비어있습니다.")
        return data_list
    
    # 단일 행만 전달된 경우 모든 데이터 가져오기 (특히 중요)
    if isinstance(data_list, dict) or (isinstance(data_list, list) and len(data_list) == 1):
        print("[WARNING] 단일 행만 전달됨. 전체 데이터를 가져오려고 시도합니다.")
        full_data = None
        
        # 0. 주소에 기반한 모든 행 가져오기 시도
        try:
            single_item = data_list[0] if isinstance(data_list, list) else data_list
            if isinstance(single_item, dict) and 'addr' in single_item:
                addr = single_item['addr']
                if addr:
                    print(f"[INFO] 주소 '{addr}'에 기반한 전체 데이터 검색 시도...")
                    
                    # 주소에서 동 추출
                    import re
                    dong_match = re.search(r'([가-힣]+동|[가-힣]+면)', addr)
                    if dong_match:
                        dong = dong_match.group(1)
                        print(f"[INFO] 추출된 동: {dong}")
                        
                        # 부모 앱에서 동 기반으로 데이터 가져오기
                        if parent_app:
                            # 1. get_rows_by_dong 메서드 시도
                            if hasattr(parent_app, 'get_rows_by_dong'):
                                try:
                                    dong_rows = parent_app.get_rows_by_dong(dong)
                                    if dong_rows and isinstance(dong_rows, list) and len(dong_rows) > 1:
                                        print(f"[INFO] '{dong}'에 대한 {len(dong_rows)}개 행 발견!")
                                        data_list = dong_rows
                                        full_data = dong_rows
                                except Exception as e:
                                    print(f"[WARNING] get_rows_by_dong 호출 실패: {e}")
                            
                            # 2. get_rows_by_address 메서드 시도
                            if not full_data and hasattr(parent_app, 'get_rows_by_address'):
                                try:
                                    addr_rows = parent_app.get_rows_by_address(addr)
                                    if addr_rows and isinstance(addr_rows, list) and len(addr_rows) > 1:
                                        print(f"[INFO] 주소 '{addr}'에 대한 {len(addr_rows)}개 행 발견!")
                                        data_list = addr_rows
                                        full_data = addr_rows
                                except Exception as e:
                                    print(f"[WARNING] get_rows_by_address 호출 실패: {e}")
                            
                            # 3. get_rows_for_address 메서드 시도 (다른 이름 관례)
                            if not full_data and hasattr(parent_app, 'get_rows_for_address'):
                                try:
                                    addr_rows = parent_app.get_rows_for_address(addr)
                                    if addr_rows and isinstance(addr_rows, list) and len(addr_rows) > 1:
                                        print(f"[INFO] 주소 '{addr}'에 대한 {len(addr_rows)}개 행 발견!")
                                        data_list = addr_rows
                                        full_data = addr_rows
                                except Exception as e:
                                    print(f"[WARNING] get_rows_for_address 호출 실패: {e}")
                            
                            # 4. 테이블 위젯에서 직접 검색
                            if not full_data and hasattr(parent_app, 'tableWidget'):
                                try:
                                    table = parent_app.tableWidget
                                    if hasattr(table, 'rowCount'):
                                        row_count = table.rowCount()
                                        if row_count > 1:
                                            print(f"[INFO] 테이블에서 '{dong}' 포함 행 검색 (총 {row_count}행)...")
                                            matching_rows = []
                                            
                                            for i in range(row_count):
                                                try:
                                                    # 주소 열을 찾음 (보통 1 또는 2)
                                                    for addr_col in [1, 2, 0]:
                                                        if addr_col < table.columnCount():
                                                            addr_item = table.item(i, addr_col)
                                                            if addr_item and (dong in addr_item.text() or addr == addr_item.text()):
                                                                if hasattr(parent_app, 'get_row_data'):
                                                                    row_data = parent_app.get_row_data(i)
                                                                    if row_data:
                                                                        matching_rows.append(row_data)
                                                                break
                                                except Exception as row_err:
                                                    print(f"[WARNING] 행 {i} 검색 중 오류: {row_err}")
                                            
                                            if len(matching_rows) > 1:
                                                print(f"[INFO] 테이블에서 '{dong}' 관련 {len(matching_rows)}개 행 발견!")
                                                data_list = matching_rows
                                                full_data = matching_rows
                                except Exception as e:
                                    print(f"[WARNING] 테이블 검색 실패: {e}")
                            
                            # 5. 다른 탭에서 데이터 가져오기 시도
                            if not full_data:
                                for tab_name in ['mylistTab', 'myListTab', 'tabMyList', 'shopTab', 'tabShop', 'allTab']:
                                    if hasattr(parent_app, tab_name):
                                        tab = getattr(parent_app, tab_name)
                                        if hasattr(tab, 'get_rows_by_address') or hasattr(tab, 'get_rows_for_address'):
                                            try:
                                                method_name = 'get_rows_by_address' if hasattr(tab, 'get_rows_by_address') else 'get_rows_for_address'
                                                method = getattr(tab, method_name)
                                                tab_rows = method(addr)
                                                if tab_rows and len(tab_rows) > 1:
                                                    print(f"[INFO] {tab_name}에서 '{addr}'에 대한 {len(tab_rows)}개 행 발견!")
                                                    data_list = tab_rows
                                                    full_data = tab_rows
                                                    break
                                            except Exception as e:
                                                print(f"[WARNING] {tab_name} 검색 실패: {e}")
        except Exception as e:
            print(f"[WARNING] 주소 기반 검색 실패: {e}")
        
        # 1. 다양한 방법으로 전체 데이터 가져오기 시도
        if not full_data and parent_app:
            # 가장 기본적인 방법: get_all_data() 메서드 호출
            if hasattr(parent_app, 'get_all_data'):
                try:
                    full_data = parent_app.get_all_data()
                    if full_data and isinstance(full_data, list) and len(full_data) > len(data_list):
                        print(f"[INFO] get_all_data()로 전체 {len(full_data)}개 행 가져옴")
                        data_list = full_data
                except Exception as e:
                    print(f"[WARNING] get_all_data() 호출 실패: {e}")
            
            # 2. 테이블에서 직접 데이터 가져오기
            if not full_data and hasattr(parent_app, 'tableWidget'):
                try:
                    if hasattr(parent_app.tableWidget, 'rowCount'):
                        row_count = parent_app.tableWidget.rowCount()
                        if row_count > 1 and hasattr(parent_app, 'get_row_data'):
                            print(f"[INFO] 테이블에서 {row_count}개 행 가져오는 중...")
                            rows = []
                            for i in range(row_count):
                                row_data = parent_app.get_row_data(i)
                                if row_data:
                                    rows.append(row_data)
                            if len(rows) > len(data_list):
                                print(f"[INFO] 테이블에서 {len(rows)}개 행 가져옴")
                                data_list = rows
                                full_data = rows
                except Exception as e:
                    print(f"[WARNING] 테이블에서 데이터 가져오기 실패: {e}")
            
            # 3. 다른 테이블 필드 참조 시도
            if not full_data:
                for table_attr in ['tableView', 'tabledata', 'table', 'dataTable', 'grid', 'listView']:
                    if hasattr(parent_app, table_attr):
                        try:
                            print(f"[INFO] {table_attr}에서 데이터 가져오기 시도...")
                            table_obj = getattr(parent_app, table_attr)
                            if hasattr(table_obj, 'model') and hasattr(table_obj.model(), 'rowCount'):
                                row_count = table_obj.model().rowCount()
                                print(f"[INFO] {table_attr}에서 {row_count}개 행 발견")
                                # 이 경우 get_all_data 호출을 시도
                                if hasattr(parent_app, 'get_all_data'):
                                    full_data = parent_app.get_all_data()
                                    if full_data and len(full_data) > len(data_list):
                                        data_list = full_data
                                        break
                        except Exception as e:
                            print(f"[WARNING] {table_attr} 접근 실패: {e}")
            
            # 4. 데이터 관리자를 통한 접근
            if not full_data:
                for mgr_name in ['data_manager', 'dataManager', 'db_manager', 'dbManager', 'model']:
                    if hasattr(parent_app, mgr_name):
                        try:
                            mgr = getattr(parent_app, mgr_name)
                            print(f"[INFO] {mgr_name}를 통해 데이터 가져오기 시도...")
                            if hasattr(mgr, 'get_all_rows'):
                                all_rows = mgr.get_all_rows()
                                if all_rows and len(all_rows) > len(data_list):
                                    print(f"[INFO] {mgr_name}.get_all_rows()로 {len(all_rows)}개 행 가져옴")
                                    data_list = all_rows
                                    break
                        except Exception as e:
                            print(f"[WARNING] {mgr_name} 접근 실패: {e}")
            
            # 5. 마지막 시도: 자식 위젯 찾기
            if not full_data:
                try:
                    if hasattr(parent_app, 'findChildren'):
                        from PyQt5.QtWidgets import QTableWidget, QTableView
                        tables = parent_app.findChildren(QTableWidget) + parent_app.findChildren(QTableView)
                        if tables:
                            print(f"[INFO] {len(tables)}개 테이블 위젯 발견, 첫 번째 테이블에서 데이터 가져오는 중...")
                            table = tables[0]
                            if hasattr(table, 'rowCount'):
                                row_count = table.rowCount()
                                if row_count > 1 and hasattr(parent_app, 'get_row_data'):
                                    rows = []
                                    for i in range(row_count):
                                        try:
                                            row_data = parent_app.get_row_data(i)
                                            if row_data:
                                                rows.append(row_data)
                                        except:
                                            pass
                                    if len(rows) > len(data_list):
                                        print(f"[INFO] 테이블 위젯에서 {len(rows)}개 행 가져옴")
                                        data_list = rows
                except Exception as e:
                    print(f"[WARNING] 테이블 위젯 검색 실패: {e}")
    
    # 단일 행이 딕셔너리로 전달된 경우 리스트로 변환
    if isinstance(data_list, dict):
        print("[WARNING] data_list가 딕셔너리로 전달됨. 리스트로 변환합니다.")
        data_list = [data_list]  # 리스트로 변환
    
    # 결과 로깅
    item_count = len(data_list)
    print(f"[INFO] my_selenium_tk_for_mylist 시작: 총 {item_count}개 행, 시작 인덱스={start_index+1}")
    
    # 항목이 적으면 경고
    if item_count <= 1:
        print("[WARNING] 단일 행만 로딩됨. 모든 행이 표시되지 않을 수 있습니다.")
        print("[WARNING] 호출하는 쪽에서 get_all_data()를 통해 전체 데이터를 전달해야 합니다.")
    
    # 시작 인덱스 유효성 검사
    if start_index < 0 or (item_count > 0 and start_index >= item_count):
        print(f"[WARNING] 시작 인덱스({start_index})가 범위를 벗어남. 0으로 조정합니다.")
        start_index = 0
    
    app = SangaCheckAppMylist(
        data_list=data_list,
        parent_app=parent_app,
        start_index=start_index,
        row_callback=row_callback
    )
    updated_list = app.run()
    return updated_list

#######################################################################
# 부모 앱에서 이 모듈을 호출하는 방법 예시
#######################################################################

# 호출 예시: SangaMylistTab 클래스 내부에서

def show_mylist_tk(self):
    """
    현재 선택된 행을 기반으로 상가 확인 창을 표시합니다.
    중요: 반드시 전체 데이터를 전달해야 합니다.
    """
    # 1. 현재 선택된 행 인덱스 가져오기
    selected_row = self.tableWidget.currentRow()
    if selected_row < 0:
        QMessageBox.warning(self, "경고", "선택된 행이 없습니다.")
        return
    
    # 2. 전체 데이터 가져오기
    all_data = self.get_all_data()  # 테이블의 전체 데이터
    if not all_data:
        QMessageBox.warning(self, "경고", "표시할 데이터가 없습니다.")
        return
    
    # 3. 로깅 - 데이터 크기 확인
    print(f"상가 확인창 표시: 전체 {len(all_data)}개 행, 선택 행 번호: {selected_row+1}")
    
    # 4. 상가 확인창 실행 - 전체 데이터와 시작 인덱스 전달
    updated_data = launch_selenium_tk_for_mylist(
        data_list=all_data,  # 중요: 전체 데이터를 전달
        parent_app=self,
        row_callback=self.on_tk_row_changed,
        start_index=selected_row
    )
    
    # 5. 업데이트된 데이터 처리 (필요시)
    if updated_data and len(updated_data) > 0:
        self.update_table_with_data(updated_data)

# 콜백 예시
def on_tk_row_changed(self, pk_id, row_index):
    """상가 확인창에서 행이 변경되었을 때 호출되는 콜백"""
    # 테이블에서 해당 행 선택
    self.tableWidget.selectRow(row_index)
    # 필요시 추가 작업 수행

# 전체 데이터 제공 메서드 (필수)
def get_all_data(self):
    """테이블의 모든 행 데이터를 반환"""
    data = []
    for row in range(self.tableWidget.rowCount()):
        row_data = self.get_row_data(row)
        if row_data:
            data.append(row_data)
    return data

def get_row_data(self, row):
    """특정 행의 데이터를 딕셔너리로 반환"""
    if row < 0 or row >= self.tableWidget.rowCount():
        return None
    
    data = {}
    # 열 이름과 인덱스는 실제 구현에 맞게 수정
    column_mapping = {
        0: "id", 1: "addr", 2: "ho", 3: "floor", 
        4: "price", 5: "premium", 6: "current_use", 
        7: "area", 8: "owner_phone", 9: "naver_no"
    }
    
    for col, key in column_mapping.items():
        item = self.tableWidget.item(row, col)
        if item:
            data[key] = item.text()
    
    # 기타 필요한 데이터 추가
    data["lat"] = self.tableWidget.item(row, 0).data(Qt.UserRole)
    data["lng"] = self.tableWidget.item(row, 0).data(Qt.UserRole + 1)
    
    return data

###########################################################
# 사용 예시: 부모 앱에서 아래와 같이 구현하면 전체 행이 표시됩니다
###########################################################

"""
# 부모 앱 클래스에 아래 코드를 추가하세요:

def show_sangacheck_tk(self):
    # 1. 현재 선택된 행 가져오기
    curr_row = self.tableWidget.currentRow()
    if curr_row < 0:
        QMessageBox.warning(self, "알림", "선택된 행이 없습니다")
        return
    
    # 2. 전체 데이터 가져오기
    all_rows = []
    for row in range(self.tableWidget.rowCount()):
        row_data = {}
        # 모든 열 데이터 추출
        for col in range(self.tableWidget.columnCount()):
            item = self.tableWidget.item(row, col)
            if item:
                header = self.tableWidget.horizontalHeaderItem(col)
                key = header.text() if header else f"col{col}"
                row_data[key.lower().replace(' ', '_')] = item.text()
        
        # 필수 데이터 추가
        if 'id' not in row_data:
            row_data['id'] = row
        if 'addr' not in row_data and self.tableWidget.item(row, 1):
            row_data['addr'] = self.tableWidget.item(row, 1).text()
            
        # 좌표 데이터 추가
        if self.tableWidget.item(row, 0):
            row_data['lat'] = self.tableWidget.item(row, 0).data(Qt.UserRole) or ""
            row_data['lng'] = self.tableWidget.item(row, 0).data(Qt.UserRole + 1) or ""
            
        all_rows.append(row_data)
    
    # 3. TK 창 실행 - 전체 데이터 전달
    from my_selenium_tk_for_mylist import launch_selenium_tk_for_mylist
    launch_selenium_tk_for_mylist(
        data_list=all_rows,       # 전체 데이터 목록 전달
        parent_app=self,
        row_callback=self.on_row_selected,
        start_index=curr_row
    )
    
def on_row_selected(self, pk_id, row_idx):
    # 선택된 행 업데이트
    self.tableWidget.selectRow(row_idx)
"""
