###############################################
# my_selenium_tk.py
# - m_type 제거 (무조건 상가)
# - "다음" 버튼으로 다음 행 이동
# - 매칭업종, 확인메모는 기존 UI 테이블이 갖고 있는 data_list에서 가져옴
# - 수정 후 data_list 반환
###############################################
from 써브module import initialize_driver
import asyncio
import threading
from tkinter import simpledialog

import tkinter as tk
from tkinter import messagebox
import json
import time
import requests
import re
import urllib.parse
# Selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

######################################################
# (A) 지도/URL/좌표 관련
######################################################
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 파일 핸들러 (로그 파일에 기록)
fh = logging.FileHandler("tk_debug.log", mode="w", encoding="utf-8")
fh.setLevel(logging.DEBUG)

# 콘솔 핸들러 (터미널에 출력)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)

logger.addHandler(fh)
logger.addHandler(ch)
def create_naver_url(lat, lng, naver_no=None):
    """
    상가 전용 URL (m_type 제거)
    lat, lon: 문자열
    article_no: 매물번호 (문자열)
    """
    base_url = f"https://new.land.naver.com/offices?ms={lat},{lng},18&a=SG:SMS:GJCG:APTHGJ:GM:TJ&e=RETAIL"
    if naver_no:
        return base_url + f"&articleNo={naver_no}"
    return base_url

def click_cadastral_map(driver):
    """
    드라이버에서 '지적도로 보기' 버튼 클릭
    """
    btn = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, ".map_control--tool[aria-label='지적도로 보기']"))
    )
    try :
        driver.execute_script("arguments[0].click();", btn)
        print("[INFO] 지적도 버튼 클릭 완료")

    except Exception as e:
        print(f"[ERR] click_cadastral_map: {e}")

def remove_article_no(url: str) -> str:
    """
    예: "https://new.land.naver.com/offices?ms=...&articleNo=12345"
    -> "https://new.land.naver.com/offices?ms=..."
    """
    if "articleNo=" not in url:
        return url
    # &articleNo=1234 형태 제거
    new_url = re.sub(r'[&?]articleNo=\d+', '', url)
    # 필요 시 &만 남아서 "?&" 같은 현상이면 추가 정리
    new_url = re.sub(r'\?&', '?', new_url)
    # 끝에 ?가 걸려 있으면 제거
    new_url = re.sub(r'\?$', '', new_url)
    return new_url



######################################################
# (C) Tkinter App (다음 버튼 -> 다음 행)
######################################################
def kill_leftover_chromedriver():
    import psutil
    """
    OS 전역에서 'chromedriver' 프로세스 이름을 갖는 모든 프로세스를 kill
    (맥, 리눅스, 윈도우 모두 가능)
    """
    for proc in psutil.process_iter():
        try:
            p_name = proc.name().lower()  # 예: 'chromedriver', 'chrome', ...
            if "chromedriver" in p_name:
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

class SangaCheckApp:
    def __init__(
        self,
        data_list,
        parent_app,                #  ← 추가
        start_index=0,
        on_row_changed=None,
        on_memo_changed=None,
        on_close_callback=None     # ← 종료 콜백 추가
    ):
        self.data_list = data_list
        self.idx = start_index
        self.on_row_changed = on_row_changed  # ★ 콜백(함수) 저장
        self.on_memo_changed = on_memo_changed
        self.on_close_callback = on_close_callback  # ★ 종료 콜백 저장
        self.parent_app = parent_app
        self.driver = None  # 초기값 None으로 설정
        self.is_shutting_down = False  # 종료 상태 플래그 추가
        
        self.root = tk.Tk()
        self.root.title("상가 현장확인")
        window_width = 400
        window_height = 650  # 주소 검색창 추가로 높이 증가

        # 종료 이벤트 가로채기
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 화면 크기
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # 오른쪽에서 2cm(약 75픽셀) 떨어지게 설정
        x_pos = screen_width - window_width - 75
        y_pos = 0

        # geometry 설정
        self.root.geometry(f"{window_width}x{window_height}+{x_pos}+{y_pos}")
        self.root.attributes("-topmost", True)
        self.first_click_done = False  # 추가: 아직 '다음' 버튼 안 눌림
        
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
                "원신흥동","원촌동","자운동","장대동","전민동","죽동","지족동","추목동","탑립동",
                "하기동","학하동","화암동"],
            "중구": ["구완동","금동","대사동","대흥동","목달동","목동","무수동","문창동","문화동","부사동",
                "사정동","산성동","석교동","선화동","안영동","어남동","오류동","옥계동","용두동","유천동",
                "은행동","정생동","중촌동","침산동","태평동","호동"],
            "대덕구": ["갈전동","대화동","덕암동","목상동","문평동","미호동","법동","부수동","비래동","삼정동",
                "상서동","석봉동","송촌동","신대동","신일동","신탄진동","연축동","오정동","와동","용호동",
                "읍내동","이현동","중리동","평촌동","황호동"]
        })
        
        # GUI 구성
        # 주소 검색 프레임 추가
        self.search_frame = tk.Frame(self.root)
        self.search_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # 주소 입력 필드
        self.address_var = tk.StringVar()
        tk.Label(self.search_frame, text="주소:").grid(row=0, column=0, padx=5, sticky=tk.W)
        self.address_entry = tk.Entry(self.search_frame, textvariable=self.address_var, width=25)
        self.address_entry.grid(row=0, column=1, padx=5, sticky=tk.W+tk.E)
        # 엔터키 바인딩 추가
        self.address_entry.bind("<Return>", lambda event: self.search_address())
        
        # 검색 버튼
        self.search_btn = tk.Button(self.search_frame, text="검색", command=self.search_address, width=8)
        self.search_btn.grid(row=0, column=2, padx=5)

        frm_top = tk.Frame(self.root)
        frm_top.pack(fill=tk.X, pady=5)

        # 행정보 표시 레이블
        self.info_label = tk.Label(self.root, text="", fg="blue")
        self.info_label.pack(pady=5)

        # 업종별 메모 영역
        self.frame_memo = tk.Frame(self.root)
        self.frame_memo.pack(pady=5)

        # 버튼영역
        frm_bottom = tk.Frame(self.root)
        frm_bottom.pack(side=tk.BOTTOM, pady=10)

        self.btn_next = tk.Button(frm_bottom, text="다음", width=10, command=self.on_next)
        self.btn_next.grid(row=0, column=0, padx=5)

        self.btn_close = tk.Button(frm_bottom, text="닫기", width=10, command=self.on_close)
        self.btn_close.grid(row=0, column=1, padx=5)
        
        self.btn_input_row = tk.Button(frm_bottom, text="행번호입력", width=10, command=self.on_row_input)
        self.btn_input_row.grid(row=0, column=2, padx=5)
        
        # 추천매물등록 버튼 추가
        self.btn_recommend = tk.Button(frm_bottom, text="추천매물등록", width=12, command=self.on_recommend)
        self.btn_recommend.grid(row=0, column=3, padx=5)
        
        # 메모 Entry dict
        self.entry_dict = {}  # { "카페": tk.Entry, "음식점": ... }
        
        # Selenium driver 안전하게 초기화
        try:
            kill_leftover_chromedriver()
            logger.info("셀레니움 드라이버 초기화 시작")
            self.driver = initialize_driver(headless=False, load_images=True, page_load_strategy='eager')
            self.driver.delete_all_cookies()
            self.driver.get('about:blank')  # 이전 URL 제거
            logger.info("셀레니움 드라이버 초기화 완료")
            
            self.set_current_row_ui()
            if 0 <= self.idx < len(self.data_list):
                try:
                    self.auto_map_load()
                    click_cadastral_map(self.driver)
                    self.set_current_row_ui()
                except Exception as e:
                    logger.error(f"지도 로딩 중 오류: {e}")
                    messagebox.showwarning("경고", "지도 로딩 중 오류가 발생했습니다.\n계속 진행하시겠습니까?")
        except Exception as e:
            logger.error(f"셀레니움 드라이버 초기화 오류: {e}")
            messagebox.showerror("오류", "브라우저를 시작할 수 없습니다.\n프로그램이 제한된 기능으로 실행됩니다.")

    # 주소 검색 함수 추가
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
            
            # 주소 완성하기 (도시 항상 대전광역시로 가정)
            full_addr = self.complete_address(address)
            
            # 네이버 지도 API로 좌표 변환
            lat, lng = self.naver_geocode(full_addr)
            
            if lat and lng:
                print(f"[INFO] 좌표 변환 성공: {lat}, {lng}")
                url = create_naver_url(lat, lng)
                print(f"[INFO] 지도 URL: {url}")
                self.driver.get(url)
                
                # 지적도 보기 추가
                click_cadastral_map(self.driver)
            else:
                print(f"[경고] 좌표 변환 실패. 대전시청 기본값 사용")
                # 대전시청 좌표
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
            
    def complete_address(self, address):
        """
        불완전한 주소를 완성합니다.
        district_data의 구/동 정보를 이용해 주소를 완성합니다.
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
        for gu in self.district_data.keys():
            if gu in address:
                district = gu
                # 해당 구의 동 목록에서 동 찾기
                for d in self.district_data[gu]:
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
                
                for gu, dongs in self.district_data.items():
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
            # 아무 정보도 없으면 대전시 붙여서 반환
            full_address = f"{city} {address}"
        
        # 번지수가 있어서 주소로 인식할 수 있는지 확인
        address_quality = "높음" if has_address_number else "낮음"
        print(f"[DEBUG] 주소 변환 결과: '{full_address}' (번지수 포함: {has_address_number}, 품질: {address_quality})")
        
        return full_address
        
    def naver_geocode(self, address):
        """
        네이버 클라우드 플랫폼의 Geocoding API를 사용하여 주소를 좌표로 변환합니다.
        
        Args:
            address (str): 주소 문자열
            
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
                'X-NCP-APIGW-API-KEY-ID': self.client_id,      # 클라이언트 ID
                'X-NCP-APIGW-API-KEY': self.client_secret,     # 클라이언트 Secret
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

    def on_row_input(self):
        row = simpledialog.askinteger("행번호 입력", "이동할 행번호를 입력하세요(1 ~ ...):", parent=self.root)
        if row is not None:
            new_idx = row - 1
            if 0 <= new_idx < len(self.data_list):
                self.idx = new_idx

                # (A) 지도 로딩
                loaded_ok = self.auto_map_load()
                if not loaded_ok:
                    # 지도 로딩 실패해도 UI는 업데이트
                    print("[INFO] 행번호입력 → 광고 종료 -> UI만 업데이트합니다.")
                    self.set_current_row_ui()
                else:
                    # 정상 로딩 시 지적도 표시
                    click_cadastral_map(self.driver)
                    self.set_current_row_ui()

                # (B) 행 변경 알림 콜백
                rowd = self.data_list[self.idx]
                pk_id = rowd.get("id", None)
                if pk_id and self.on_row_changed:
                    self.on_row_changed(pk_id, self.idx)
            else:
                messagebox.showerror("오류", "유효한 행 범위를 벗어났습니다.")

    def parse_memo_json(self, memo_str):
        """
        예: '[{"biz":"카페","memo":"기존메모"},{"biz":"술집","memo":"..."}]'
        => { "카페":"기존메모", "술집":"..." }
        """
        out = {}
        if memo_str:
            try:
                arr = json.loads(memo_str)
                for obj in arr:
                    b_ = obj.get("biz","")
                    m_ = obj.get("memo","")
                    if b_:
                        out[b_] = m_
            except:
                pass
        return out

    def build_memo_json(self):
        """
        row_data["매칭업종"] => "카페,음식점" => ["카페","음식점"]
        -> self.entry_dict[biz].get()
        => [{"biz":..,"memo":..},...]
        """
        rowd = self.data_list[self.idx]
        upjong_str = rowd.get("매칭업종","")
        upjongs = [x.strip() for x in upjong_str.split(",") if x.strip()]

        arr = []
        for biz in upjongs:
            ent = self.entry_dict.get(biz)
            if ent:
                val = ent.get().strip()
                if val:
                    arr.append({"biz": biz, "memo": val})
        return json.dumps(arr, ensure_ascii=False)



    def set_current_row_ui(self):
        """
        간소화된 UI - 호, 현재업종, 권리금, 관리비, 사용승인일, 주차대수, 용도 등 제거
        1) 주소(폭 크게=50)
        2) 업종별 확인메모(check_memo)
        """
        # 기존: frame_memo children 제거
        for w in self.frame_memo.winfo_children():
            w.destroy()
        self.entry_dict.clear()

        if self.idx < 0 or self.idx >= len(self.data_list):
            self.info_label.config(text="범위초과")
            return

        rowd = self.data_list[self.idx]
        info_txt = f"[{self.idx+1}/{len(self.data_list)}]"
        self.info_label.config(text=info_txt)

        row_index = 0

        # ========== (1) 주소(폭 50) ==========
        lbl_addr = tk.Label(self.frame_memo, text="주소")
        lbl_addr.grid(row=row_index, column=0, sticky="w", padx=5, pady=3)

        ent_addr = tk.Entry(self.frame_memo, width=30)
        ent_addr.grid(row=row_index, column=1, padx=5, pady=3, sticky="w")
        ent_addr.insert(0, rowd.get("addr",""))
        self.entry_dict["addr"] = ent_addr
        ent_addr.config(state="readonly")
        row_index += 1

        # ========== (2) 업종별 확인메모(check_memo) ==========
        upjong_str = rowd.get("매칭업종","")
        upjong_list = [x.strip() for x in upjong_str.split(",") if x.strip()]

        memo_str = rowd.get("check_memo","")
        memo_map = self.parse_memo_json(memo_str)

        row_index += 1
        lbl_title = tk.Label(self.frame_memo, text="업종별 확인메모", fg="blue")
        lbl_title.grid(row=row_index, column=0, padx=5, pady=3, sticky="w")
        row_index += 1

        self.upjong_texts = []
        for biz in upjong_list:
            lbl_biz = tk.Label(self.frame_memo, text=biz)
            lbl_biz.grid(row=row_index, column=0, sticky="nw", padx=5, pady=3)

            txt_box = tk.Text(self.frame_memo, width=30, height=2)
            txt_box.grid(row=row_index, column=1, padx=5, pady=3, sticky="w")

            old_val = memo_map.get(biz,"")
            txt_box.insert("1.0", old_val)

            self.upjong_texts.append((biz, txt_box))
            row_index += 1


    def auto_map_load(self):
        """
        로드에 안전한 예외 처리 추가
        """
        try:
            if not self.driver:
                logger.error("[ERROR] auto_map_load -> driver is None")
                return False
                
            rowd = self.data_list[self.idx]
            lat_ = rowd.get("lat","")
            lng_ = rowd.get("lng","")
            if not lat_ or not lng_:
                logger.warning(f"[WARN] 좌표 정보 없음: lat={lat_}, lng={lng_}")
                return False
                
            url = create_naver_url(lat_, lng_, rowd.get("naver_no",""))
            logger.debug(f"[DEBUG] 지도 URL: {url}")

            # 메인 탭 로딩
            try:
                self.driver.get(url)
                # 짧은 대기 시간으로 로딩 대기 
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"[ERROR] 지도 로딩 실패: {e}")
                return False
            
            try:
                current_url = self.driver.current_url
                if "new.land.naver.com/error" in current_url:
                    logger.info("[INFO] 광고 종료 or 오류 페이지 감지 => articleNo 제거 후 재로드")
                    url_no_article = remove_article_no(url)

                    # 다시 접속 (지도를 보거나 일단 로딩)
                    self.driver.get(url_no_article)
                    return False
            except Exception as e:
                logger.error(f"[ERROR] URL 확인 실패: {e}")
                return False

            return True
        except Exception as e:
            logger.error(f"[ERROR] auto_map_load 실행 중 오류: {e}")
            return False

    def extract_ui_to_rowd(self, row_index: int):
        """
        간소화된 버전 - 현재 Tkinter Entry/Text 값들 → rowd에 저장
        - 업종별확인메모(check_memo)만 저장
        - 성공 시 rowd return, 실패 시 None
        """
        if row_index < 0 or row_index >= len(self.data_list):
            return None

        rowd = self.data_list[row_index]

        # 업종별 확인메모
        arr = []
        for (biz, txt) in self.upjong_texts:
            memo_s = txt.get("1.0","end").strip()
            arr.append({"biz": biz, "memo": memo_s})
        check_memo_json = json.dumps(arr, ensure_ascii=False)

        # rowd에 반영
        rowd["check_memo"] = check_memo_json
        return rowd
        
    def on_recommend(self):
        """
        추천매물등록 기능
        - 현재 업종별 확인메모를 가져와서 추천매물로 등록
        - parent_app의 메서드를 호출하여 실제 등록 처리
        """
        try:
            # 종료 중이면 작업 취소
            if self.is_shutting_down:
                logger.debug("종료 중이므로 추천매물 등록 작업이 취소되었습니다.")
                return
                
            if self.idx < 0 or self.idx >= len(self.data_list):
                messagebox.showerror("오류", "유효한 행이 선택되지 않았습니다.")
                return

            # 현재 행 데이터 가져오기
            rowd = self.extract_ui_to_rowd(self.idx)
            if rowd is None:
                return
            
            # 업종별 메모가 있는지 확인
            if not self.has_any_memo(rowd):
                answer = messagebox.askyesno("경고", "업종별 확인메모가 없습니다. 그래도 추천매물로 등록하시겠습니까?")
                if not answer:
                    return
            
            # 추천매물로 등록하기 위한 데이터 준비
            recommend_data = {
                "id": rowd.get("id"),
                "addr": rowd.get("addr", ""),
                "lat": rowd.get("lat", ""),
                "lng": rowd.get("lng", ""),
                "check_memo": rowd.get("check_memo", ""),
                "매칭업종": rowd.get("매칭업종", "")
            }
            
            # 추천매물 등록 작업 수행
            success = self.add_recommend_property(recommend_data)
                
        except Exception as e:
            logger.error(f"추천매물 등록 중 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
            messagebox.showerror("오류", f"추천매물 등록 중 오류가 발생했습니다: {str(e)}")

    def has_any_memo(self, rowd: dict) -> bool:
        """
        rowd["check_memo"] 가 JSON 형태:
        '[{"biz":"카페","memo":""}, {"biz":"PC방","memo":"..."}, ...]'
        → 하나라도 memo != ""가 있으면 True
        전부 ""이면 False
        """
        import json

        cm_str = rowd.get("check_memo","").strip()
        if not cm_str:
            return False

        try:
            arr = json.loads(cm_str)
        except:
            # 파싱 실패 => 그래도 뭔가 있으면 저장하도록 True 처리?
            # or 그냥 False로 취급?
            print("[WARN] has_any_memo => JSONDecodeError => treat as memo empty")
            return False

        # 배열 돌며 memo 있는지
        for obj in arr:
            if obj.get("memo","").strip() != "":
                # 한 개라도 내용이 있으면 True
                return True
        return False

    def add_recommend_property(self, recommend_data):
        """
        추천매물 등록 처리 함수 - API 요청을 통해 추천매물 등록
        
        Args:
            recommend_data (dict): 추천매물 데이터
                - id: 원본 매물 ID
                - addr: 주소
                - lat, lng: 좌표
                - check_memo: 업종별 확인메모 JSON
                - 매칭업종: 업종 목록
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 종료 중이면 작업 취소
            if self.is_shutting_down:
                logger.debug("종료 중이므로 추천매물 등록 작업이 취소되었습니다.")
                return False
                
            logger.info(f"추천매물 등록 시작: {recommend_data['addr']}")
            
            # 매칭업종이 없으면 리턴
            if not recommend_data.get('매칭업종'):
                logger.warning("매칭업종 정보가 없어 추천매물 등록을 진행할 수 없습니다.")
                messagebox.showerror("오류", "매칭업종 정보가 없습니다.")
                return False
            
            # 체크메모 JSON 파싱
            check_memo_str = recommend_data.get('check_memo', '')
            upjong_memo_list = []
            
            if check_memo_str:
                try:
                    arr = json.loads(check_memo_str)
                    for obj in arr:
                        biz = obj.get('biz', '')
                        memo = obj.get('memo', '')
                        if biz and memo:
                            upjong_memo_list.append({"biz": biz, "memo": memo})
                except json.JSONDecodeError:
                    logger.error(f"체크메모 JSON 파싱 실패: {check_memo_str}")
            
            # 매칭업종 목록 추출
            upjong_str = recommend_data.get('매칭업종', '')
            upjong_list = [x.strip() for x in upjong_str.split(';') if x.strip()]
            
            # 업종별 메모가 없으면 매칭업종 목록만 사용
            if not upjong_memo_list:
                upjong_memo_list = [{"biz": biz, "memo": "추천예정"} for biz in upjong_list]
                
            # 필요한 데이터 구성
            row_data = {
                "주소": recommend_data.get('addr', ''),
                "id": recommend_data.get('id', ''),
                "출처": "확인",  # 기본값 설정
                "source_table": recommend_data["source_table"],
                "lat": recommend_data.get('lat', ''),
                "lng": recommend_data.get('lng', '')
            }
            
            # parent_app이 종료 중인지 확인 - API 호출은 계속 시도
            if hasattr(self.parent_app, 'terminating') and self.parent_app.terminating:
                logger.warning("부모 앱이 종료 중이지만 API 호출을 계속 진행합니다.")
                
            # 전역 종료 플래그 확인 - API 호출은 계속 시도
            if 'APP_SHUTTING_DOWN' in globals() and globals().get('APP_SHUTTING_DOWN'):
                logger.warning("APP_SHUTTING_DOWN 플래그가 설정되어 있지만 API 호출을 계속 진행합니다.")
            
            # 서버 호스트 확인 (기본값은 localhost:8000)
            server_host = "localhost"
            server_port = "8000"
            
            # parent_app에서 서버 호스트/포트 정보 추출 시도
            if hasattr(self.parent_app, 'server_host') and self.parent_app.server_host:
                server_host = self.parent_app.server_host
            if hasattr(self.parent_app, 'server_port') and self.parent_app.server_port:
                server_port = str(self.parent_app.server_port)
            
            # 정확한 API 엔드포인트 - 실제 존재하는 경로로 수정
            url = f"http://{server_host}:{server_port}/recommend/register_recommend_data"
            
            # ID 확인
            source_id = recommend_data.get("id")
            if not source_id:
                logger.warning("유효한 source_id가 없습니다.")
                messagebox.showerror("오류", "ID 정보가 없습니다.")
                return False
            
            try:
                logger.info(f"추천매물 등록 API 호출: {url}")
                
                # 모든 업종을 한 번에 처리하는 방식으로 변경
                try:
                    # selected_items 배열 구성
                    selected_items = []
                    for item in upjong_memo_list:
                        selected_items.append({
                            "biz": item.get("biz", ""),
                            "manager": self.parent_app.current_manager if hasattr(self.parent_app, 'current_manager') else "관리자",
                            "memo": item.get("memo", "")
                        })
                    
                    # API 요청 데이터 구성 - manager_check_tab.py와 동일한 형식 사용
                    api_data = {
                        "source_id": source_id,
                        "source_table": recommend_data["source_table"],
                        "selected_items": selected_items  # 모든 업종을 한 번에 전송
                    }
                    
                    # API 호출 (타임아웃 5초)
                    resp = requests.post(url, json=api_data, timeout=5)
                    
                    # 응답 확인
                    if resp.status_code == 200:
                        try:
                            result = resp.json()
                            if result.get("status") == "ok":
                                logger.info(f"추천매물 등록 성공: {result.get('message', '성공')}")
                                messagebox.showinfo("성공", f"추천매물로 등록되었습니다. ({len(selected_items)}개 업종)")
                                
                                # 추천 탭 새로고침 시도 (가능한 경우)
                                if hasattr(self.parent_app, 'refresh_recommend_tab'):
                                    try:
                                        if (hasattr(self.parent_app, 'executor') and 
                                            not getattr(self.parent_app.executor, '_shutdown', False)):
                                            self.parent_app.refresh_recommend_tab()
                                    except Exception as refresh_err:
                                        logger.warning(f"추천 탭 새로고침 중 오류: {refresh_err}")
                                        
                                return True
                            else:
                                error_msg = result.get("message", "알 수 없는 오류가 발생했습니다.")
                                logger.error(f"추천매물 등록 실패 (API 오류): {error_msg}")
                                
                                # 오류 메시지 표시
                                messagebox.showerror("등록 실패", f"추천매물 등록에 실패했습니다: {error_msg}")
                                return False
                        except Exception as e:
                            logger.warning(f"JSON 응답 파싱 실패: {e}")
                            messagebox.showerror("응답 처리 오류", "서버 응답을 처리하는 중 오류가 발생했습니다.")
                            return False
                    else:
                        logger.error(f"HTTP 오류: {resp.status_code} - {resp.text}")
                        messagebox.showerror("API 오류", f"HTTP 오류: 상태 코드 {resp.status_code}\n{resp.text}")
                        return False
                except requests.RequestException as e:
                    logger.warning(f"API 요청 실패: {e}")
                    messagebox.showerror("연결 오류", f"서버 연결 중 오류가 발생했습니다: {e}")
                    return False
                except Exception as e:
                    logger.warning(f"처리 중 예상치 못한 오류: {e}")
                    messagebox.showerror("처리 오류", f"요청 처리 중 오류가 발생했습니다: {e}")
                    return False
            except Exception as api_err:
                logger.error(f"API 호출 처리 중 오류: {api_err}")
                import traceback
                logger.error(traceback.format_exc())
                
                # API 호출 실패 시 오류 메시지 표시
                messagebox.showerror("오류", f"API 호출 중 오류가 발생했습니다: {str(api_err)}")
                return False
                
        except Exception as e:
            logger.error(f"추천매물 등록 중 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # 예외 발생 시 오류 메시지 표시
            messagebox.showerror("오류", f"추천매물 등록 중 오류가 발생했습니다: {str(e)}")
            return False

    def on_next(self):
        """
        '다음' 버튼 클릭 시 호출
        - 현재 행 데이터 저장
        - 다음 행으로 이동
        - UI 업데이트
        """
        logger.debug(f"[DEBUG] on_next -> idx={self.idx}")
        
        try:
            if self.idx < 0 or self.idx >= len(self.data_list):
                return

            # (A) extract rowd
            rowd = self.extract_ui_to_rowd(self.idx)
            logger.debug(f"[DEBUG] on_next -> rowd={rowd}")
            if rowd is None:
                logger.warning(f"[WARN] on_next -> rowd is None")
                return  # 유효성검사 실패 시, 취소
            
            # (B) 메모가 있는 경우에만 DB 저장
            try:
                if self.has_any_memo(rowd):
                    # DB 저장 (현재 행만) => self.commit_row_changes
                    self.commit_row_changes(self.idx)
                    logger.info("[INFO] 현재 행의 메모가 있어 DB에 저장했습니다.")
                else:
                    logger.info("[INFO] 현재 행의 메모가 없어 DB 저장을 건너뜁니다.")
            except Exception as e:
                logger.error(f"[ERROR] 행 데이터 저장 중 오류: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # 오류가 발생해도 계속 진행 (다음 행으로 이동)

            # 현재 테이블 정렬 상태 저장 (parent_app의 UI 정렬 상태)
            current_sort_column = None
            current_sort_order = None
            if hasattr(self, 'parent_app') and self.parent_app:
                if hasattr(self.parent_app, 'check_manager_view') and self.parent_app.check_manager_view:
                    header = self.parent_app.check_manager_view.horizontalHeader()
                    if header:
                        current_sort_column = header.sortIndicatorSection()
                        current_sort_order = header.sortIndicatorOrder()
                        logger.debug(f"[DEBUG] 현재 테이블 정렬 상태 저장: 컬럼={current_sort_column}, 순서={current_sort_order}")

            # (C) idx++
            self.idx += 1
            if self.idx >= len(self.data_list):
                messagebox.showinfo("완료", "모든 행 확인 완료!")
                self.on_close()
                return

            # 지도 로딩
            try:
                if self.driver:
                    loaded_ok = self.auto_map_load()
                    if not loaded_ok:
                        logger.info("[INFO] 광고 종료 -> 지도 로딩 건너뜁니다.")
                    else:
                        click_cadastral_map(self.driver)
                else:
                    logger.warning("[WARN] 드라이버가 None 상태여서 지도를 로드할 수 없습니다.")
            except Exception as e:
                logger.error(f"[ERROR] 지도 로딩 중 오류: {e}")
                messagebox.showwarning("경고", "지도 로딩 중 오류가 발생했습니다.")
            
            # 그래도 UI는 업데이트
            self.set_current_row_ui()

            # (E) row_callback
            try:
                rowd2 = self.data_list[self.idx]
                pk_id = rowd2.get("id")
                if pk_id and self.on_row_changed:
                    # 콜백 함수 실행 전 안전하게 체크
                    if callable(self.on_row_changed):
                        try:
                            self.on_row_changed(pk_id, self.idx)
                            
                            # 콜백 후 부모 앱의 테이블 정렬 상태 복원
                            if current_sort_column is not None and current_sort_order is not None:
                                if hasattr(self.parent_app, 'check_manager_view') and self.parent_app.check_manager_view:
                                    self.parent_app.check_manager_view.sortByColumn(current_sort_column, current_sort_order)
                                    logger.debug(f"[DEBUG] 테이블 정렬 상태 복원: 컬럼={current_sort_column}, 순서={current_sort_order}")
                                    
                        except Exception as callback_err:
                            logger.error(f"[ERROR] 행 변경 콜백 실행 중 오류: {callback_err}")
                    else:
                        logger.warning("[WARN] on_row_changed가 호출 가능한 함수가 아닙니다.")
            except Exception as e:
                logger.error(f"[ERROR] 행 변경 콜백 실행 중 오류: {e}")
        except Exception as e:
            logger.error(f"[ERROR] on_next 실행 중 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
            messagebox.showerror("오류", f"다음 행으로 이동 중 오류가 발생했습니다: {str(e)}")

    def on_close(self):
        """
        자원을 안전하게 정리하고 창을 닫습니다.
        """
        try:
            # 이미 종료 중이면 중복 호출 방지
            if self.is_shutting_down:
                logger.debug("이미 종료 중입니다.")
                return
                
            # 종료 플래그 설정
            self.is_shutting_down = True
            logger.info("[INFO] 상가 검수 창 종료 시작...")
            
            # 셀레니움 드라이버 종료
            logger.info("[INFO] 셀레니움 드라이버 종료 중...")
            if hasattr(self, 'driver') and self.driver:
                try:
                    self.driver.quit()
                    logger.info("[INFO] 셀레니움 드라이버 종료 완료")
                except Exception as e:
                    logger.warning(f"[WARN] 드라이버 종료 중 오류: {e}")
                    
                # 드라이버 참조 제거
                self.driver = None
        except Exception as e:
            logger.warning(f"[WARN] 셀레니움 드라이버 종료 중 오류: {e}")
            try:
                # 강제 종료 시도
                kill_leftover_chromedriver()
                logger.info("[INFO] chromedriver 프로세스 강제 종료 완료")
            except Exception as kill_err:
                logger.error(f"[ERROR] chromedriver 강제 종료 중 오류: {kill_err}")
            
        # 모든 진행 중인 작업 취소
        try:
            # 진행 중인 모든 작업 취소 로직 (파이썬 스레드는 강제 종료가 어려움)
            # 대신 종료 플래그를 설정하여 콜백에서 확인하도록 함
            logger.info("[INFO] 모든 진행 중인 작업 취소 중...")
        except Exception as e:
            logger.warning(f"[WARN] 작업 취소 중 오류: {e}")
            
        # 백그라운드 작업 중지 요청 및 대기
        if hasattr(self, 'parent_app') and self.parent_app:
            logger.info("[INFO] 셀레니움 Tk 창 종료 중: 백그라운드 작업 중지 요청...")
            if hasattr(self.parent_app, 'set_terminating'):
                try:
                    self.parent_app.set_terminating(True)
                    logger.info("[INFO] 애플리케이션 종료 플래그 설정됨")
                except Exception as e:
                    logger.warning(f"[WARN] 종료 플래그 설정 중 오류: {e}")
                
            # 백그라운드 스레드 종료 대기 (필요시)
            try:
                # 이전 코드: 메인 앱의 executor를 종료시키는 부분 제거
                # if (hasattr(self.parent_app, 'executor') and 
                #     hasattr(self.parent_app.executor, '_shutdown') and 
                #     not self.parent_app.executor._shutdown):
                #     logger.info("[INFO] ThreadPoolExecutor 종료 대기 중...")
                #     self.parent_app.executor.shutdown(wait=False)
                #     logger.info("[INFO] ThreadPoolExecutor 종료 요청 완료")
                
                # 대신 TK만 안전하게 종료하도록 변경
                logger.info("[INFO] TK 창 안전 종료 - 메인 앱 executor는 종료하지 않음")
            except Exception as e:
                logger.warning(f"[WARN] 안전 종료 처리 중 오류: {e}")
        
        # 종료 콜백 함수 호출 (추가)
        try:
            if self.on_close_callback and callable(self.on_close_callback):
                logger.info("[INFO] 종료 콜백 함수 호출 중...")
                self.on_close_callback()
                logger.info("[INFO] 종료 콜백 함수 호출 완료")
        except Exception as e:
            logger.error(f"[ERROR] 종료 콜백 함수 호출 중 오류: {e}")
        
        # 최종적으로 Tk 창 닫기
        try:
            logger.info("[INFO] Tk 창 종료 중...")
            self.root.destroy()
            logger.info("[INFO] Tk 창 정상 종료 완료")
        except Exception as e:
            logger.error(f"[ERROR] Tk 창 종료 중 오류: {e}")

    def run(self):
        try:
            # 종료 상태가 아닌 경우에만 mainloop 실행
            if not self.is_shutting_down:
                self.root.mainloop()
        except Exception as e:
            logger.error(f"[ERROR] Tkinter mainloop 실행 중 오류: {e}")
        finally:
            # 창이 닫히더라도 백그라운드 리소스 정리
            try:
                if not self.is_shutting_down:
                    # on_close가 호출되지 않았다면 여기서 종료 플래그 설정
                    self.is_shutting_down = True
                    
                    # on_close가 호출되지 않았으면 여기서 종료 콜백 호출 (추가)
                    if self.on_close_callback and callable(self.on_close_callback):
                        logger.info("[INFO] run() 종료 시 콜백 함수 호출 중...")
                        try:
                            self.on_close_callback()
                        except Exception as cb_e:
                            logger.error(f"[ERROR] run() 종료 시 콜백 함수 호출 중 오류: {cb_e}")
                    
                if self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self.driver = None
            except Exception as e:
                logger.warning(f"[WARN] 드라이버 종료 중 오류: {e}")
                
            # chromedriver 프로세스 강제 종료
            try:
                kill_leftover_chromedriver()
                logger.info("[INFO] chromedriver 프로세스 강제 종료 완료")
            except Exception as e:
                logger.warning(f"[WARN] chromedriver 강제 종료 중 오류: {e}")

        return self.data_list

    def commit_row_changes(self, row_index):
        """
        1) row_index 범위 검사
        2) self.data_list[row_index] => rowd
        3) rowd["check_memo"] JSON 파싱 => 업종별 [{ "biz":"...", "manager":"...", "memo":"..." }, ...]
        4) 메모가 있는 항목만 DB 저장 (업종별)
        5) PyQt 테이블에도 update_single_row_by_id 로 갱신
        """
        if row_index < 0 or row_index >= len(self.data_list):
            return  # 범위 오류

        rowd = self.data_list[row_index]
        pk_id = rowd.get("id")
        if not pk_id:
            logger.warning("[WARN] commit_row_changes => pk_id가 없음 => DB 업데이트 불가")
            return

        logger.info(f"[INFO] commit_row_changes => row {row_index+1}, pk_id={pk_id}, rowd={rowd}")

        # (A) check_memo JSON 파싱
        import json
        cm_str = rowd.get("check_memo","").strip()
        if not cm_str:
            logger.info("[INFO] check_memo가 없음 => 저장할 항목이 없습니다.")
            return

        try:
            arr = json.loads(cm_str)  # 예: [{"biz":"공방","manager":"유OO","memo":"..."}, {"biz":"카페","manager":"노OO","memo":""}, ...]
        except json.JSONDecodeError:
            logger.warning("[WARN] check_memo JSON 파싱 실패 => skip")
            return

        # (B) 업종별 DB 저장 (memo 비어있지 않은 항목만)
        for obj in arr:
            memo_val = obj.get("memo","").strip()
            if not memo_val:
                # 메모가 비었으면 저장 안 함
                continue
            biz_with_bracket = obj.get("biz","")  # 예: "공방[유]"
            # (1) 정규식으로 대괄호 파싱:  ^(.*)\[(.*)\]$
            m = re.match(r'^(.*)\[(.*)\]$', biz_with_bracket)
            if m:
                pure_biz = m.group(1)      # "공방"
                manager_extracted = m.group(2)  # "유"
                # (2) 실제 필드로 교체
                obj["biz"] = pure_biz.strip()
                obj["manager"] = manager_extracted.strip()   # <-- 새로 만든 키
            else:
                # 대괄호가 없으면 'manager'는 빈 문자열 or rowd["manager"] 등
                obj["manager"] = ""
            # 실제 DB 저장 로직 (예시)
            # self.parent_app.save_upjong_to_db(pk_id, biz_name, used_manager, memo_val)

        # (C) 필요하다면 rowd["manager"]에 통합 값 넣기? => (원하면)
        # 예) 업종이 여러개라도, 여기서는 안 합치고 넘어감
        # rowd["manager"] = ""  # 또는 필요 시 뭔가 넣을 수도 있음

        # (D) PyQt 테이블 갱신 로직 개선
        # 여러 경로로 행 갱신 시도 (안전한 속성 체크)
        updated = False
        
        # 1. 직접 manager_check_tab을 통해 시도
        if hasattr(self.parent_app, 'manager_check_tab'):
            try:
                if hasattr(self.parent_app.manager_check_tab, 'find_row_by_id') and \
                   hasattr(self.parent_app.manager_check_tab, 'update_single_row_by_id'):
                    logger.info("[INFO] manager_check_tab을 통해 행 갱신을 시도합니다.")
                    table_row = self.parent_app.manager_check_tab.find_row_by_id(pk_id)
                    if table_row is not None:
                        self.parent_app.manager_check_tab.update_single_row_by_id(pk_id, rowd)
                        logger.info(f"[INFO] row {row_index+1} => DB 반영 & PyQt 갱신 완료.")
                        updated = True
            except Exception as e:
                logger.error(f"[ERROR] manager_check_tab을 통한 행 갱신 중 오류: {e}")
                # 실패해도 다른 방법 시도
        
        # 2. parent_app에 직접 메서드가 있는지 확인
        if not updated and hasattr(self.parent_app, 'find_row_by_id') and \
           hasattr(self.parent_app, 'update_single_row_by_id'):
            try:
                logger.info("[INFO] parent_app을 통해 행 갱신을 시도합니다.")
                table_row = self.parent_app.find_row_by_id(pk_id)
                if table_row is not None:
                    self.parent_app.update_single_row_by_id(pk_id, rowd)
                    logger.info(f"[INFO] parent_app을 통해 행 {row_index+1} 갱신 완료.")
                    updated = True
            except Exception as e:
                logger.warning(f"[WARN] parent_app을 통한 행 갱신 중 오류: {e}")
        
        # 3. parent_app.all_tab을 통한 시도
        if not updated and hasattr(self.parent_app, 'all_tab'):
            try:
                if hasattr(self.parent_app.all_tab, 'find_row_by_id') and \
                   hasattr(self.parent_app.all_tab, 'update_single_row_by_id'):
                    logger.info("[INFO] all_tab을 통해 행 갱신을 시도합니다.")
                    table_row = self.parent_app.all_tab.find_row_by_id(pk_id)
                    if table_row is not None:
                        self.parent_app.all_tab.update_single_row_by_id(pk_id, rowd)
                        logger.info(f"[INFO] all_tab을 통해 행 {row_index+1} 갱신 완료.")
                        updated = True
            except Exception as e:
                logger.warning(f"[WARN] all_tab을 통한 행 갱신 중 오류: {e}")
        
        # 어떤 방법으로도 업데이트하지 못했을 경우
        if not updated:
            logger.warning(f"[WARN] 테이블 갱신을 위한 적절한 메서드를 찾을 수 없어 메모리에만 업데이트합니다.")
            # 메모리에 있는 data_list만 업데이트
            self.data_list[row_index] = rowd

######################################################
# (D) 최종 호출 함수
######################################################
def launch_selenium_tk(data_list, 
                       parent_app,
                       row_callback=None, 
                       memo_callback=None,
                       start_index=0,
                       on_close_callback=None):  # ← 종료 콜백 매개변수 추가
    """
    data_list  : 필수
    parent_app : 필수 (부모 앱 참조)
    row_callback: 행 변경 시 알림
    memo_callback: 확인메모가 입력되었을 때 알림
    start_index: 시작 인덱스
    on_close_callback: TK 창이 종료될 때 호출될 콜백 함수
    
    안전한 예외 처리 추가
    """
    try:
        logger.info("[INFO] 셀레니움 TK 시작 중...")
        app = SangaCheckApp(data_list, 
                          parent_app,
                          start_index=start_index, 
                          on_row_changed=row_callback, 
                          on_memo_changed=memo_callback,
                          on_close_callback=on_close_callback)  # ← 종료 콜백 전달
        updated_list = app.run()
        logger.info("[INFO] 셀레니움 TK 종료됨")
        return updated_list
    except Exception as e:
        logger.error(f"[ERROR] 셀레니움 TK 실행 중 오류: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # 크롬 드라이버 잔여 프로세스 정리
        try:
            kill_leftover_chromedriver()
            logger.info("[INFO] 오류 발생 후 chromedriver 프로세스 강제 종료")
        except:
            pass
            
        # 종료 콜백 함수 호출 시도 (예외 발생 시에도)
        try:
            if on_close_callback and callable(on_close_callback):
                logger.info("[INFO] 예외 발생 후 종료 콜백 함수 호출 중...")
                on_close_callback()
        except Exception as cb_e:
            logger.error(f"[ERROR] 종료 콜백 함수 호출 중 오류: {cb_e}")
            
        # 에러 발생 시에도 원본 데이터 반환
        return data_list
