# 부동산 매물 관리 시스템 기술 문서

## 1. 프로젝트 개요

본 프로젝트는 기존의 PyQt5로 작성된 데스크톱 애플리케이션을 웹 환경으로 마이그레이션하는 작업입니다. 이 시스템은 부동산 매물을 체계적으로 관리하고, 다양한 정보를 조회할 수 있는 기능을 제공합니다.

### 1.1 주요 기능
- 매물체크(확인): 매물의 상세 정보 확인
- 써브상가: 상가 매물 정보 조회
- 써브원룸: 원룸 매물 정보 조회
- 추천매물: 추천 매물 관리 및 조회
- 마이리스트(상가): 나의 상가 매물 관리
- 계약완료: 계약이 완료된 매물 관리

## 2. 시스템 아키텍처

### 2.1 전체 아키텍처
- **프론트엔드**: JavaScript를 사용한 웹 애플리케이션
- **백엔드**: Python으로 구현된 API 서버
- **데이터베이스**: 매물 및 사용자 정보 저장

### 2.2 코드 구조
```
web_frontend/
├── js/
│   ├── feature/
│   │   ├── baseTab.js           # 모든 탭의 기본 클래스
│   │   ├── checkConfirmTab.js   # 매물체크(확인) 탭
│   │   ├── serveShopTab.js      # 써브상가 탭
│   │   ├── serveOneroomTab.js   # 써브원룸 탭
│   │   ├── recommendTab.js      # 추천매물 탭
│   │   ├── mylistShopTab.js     # 마이리스트(상가) 탭
│   │   └── completedDealsTab.js # 계약완료 탭
│   ├── main.js                  # 애플리케이션 진입점
│   ├── state.js                 # 전역 상태 관리
│   └── config.js                # 설정 (API 주소 등)
└── style.css                    # 스타일 시트
```

## 3. 모듈 구조

### 3.1 BaseTab 클래스
모든 탭의 공통 기능을 제공하는 기본 클래스입니다.

```javascript
// baseTab.js 주요 기능
export class BaseTab {
  constructor(tabId, tableId, headers) {
    // 탭 초기화 속성들
  }
  
  init() {
    // 탭 초기화
  }
  
  registerAddressEvents() {
    // 주소 선택 이벤트 등록
  }
  
  filterByAddress(address) {
    // 주소별 데이터 필터링
  }
  
  populateTable(data) {
    // 테이블에 데이터 채우기
  }
}
```

### 3.2 탭 간 통신
- **커스텀 이벤트**: 'address-selected', 'addresses-selected', 'data-updated' 등을 통한 탭 간 통신
- **이벤트 핸들러**: main.js의 registerGlobalEvents() 함수에 등록
- **데이터 캐싱**: 각 탭은 this.dataCache 객체에 주소별로 데이터 캐싱

## 4. 주요 기능 설명

### 4.1 매물체크(확인) 탭
- **기능**: 매물의 상세 정보 확인
- **주요 클래스**: CheckConfirmTab
- **데이터 로드**: 'address-selected' 이벤트 수신 시 해당 주소의 매물 확인 정보 로드
- **API 엔드포인트**: /shop/get_all_confirm_with_items

### 4.2 써브상가 탭
- **기능**: 상가 매물 정보 조회
- **주요 클래스**: ServeShopTab
- **데이터 로드**: 주소 선택 시 해당 주소의 상가 매물 정보 로드
- **API 엔드포인트**: /shop/get_serve_shop_data

### 4.3 써브원룸 탭
- **기능**: 원룸 매물 정보 조회
- **주요 클래스**: ServeOneroomTab
- **데이터 로드**: 주소 선택 시 해당 주소의 원룸 매물 정보 로드
- **API 엔드포인트**: /shop/get_serve_oneroom_data

### 4.4 추천매물 탭
- **기능**: 추천 매물 관리 및 조회
- **주요 클래스**: RecommendTab
- **데이터 로드**: 주소 선택 시 해당 주소의 추천 매물 정보 로드
- **API 엔드포인트**: /recommend/get_recommend_data

### 4.5 마이리스트(상가) 탭
- **기능**: 나의 상가 매물 관리
- **주요 클래스**: MyListShopTab
- **데이터 로드**: 담당자별 마이리스트 데이터 로드
- **주요 이벤트**: 행 클릭 시 'address-selected' 이벤트 발생
- **특별 기능**: 
  - 행 클릭 시 체크박스 선택
  - 선택된 주소 데이터가 다른 탭에도 표시
- **API 엔드포인트**: /mylist/get_mylist_shop_data

### 4.6 계약완료 탭
- **기능**: 계약이 완료된 매물 관리
- **주요 클래스**: CompletedDealsTab
- **데이터 로드**: 주소 선택 시 해당 주소의 계약 완료 정보 로드
- **API 엔드포인트**: /completed/get_completed_deals

## 5. API 문서

### 5.1 API 엔드포인트 목록

#### 5.1.1 매물 관리
- **GET /shop/managers**
  - 기능: 담당자 목록 조회
  - 응답: `{"success": true, "managers": ["담당자1", "담당자2", ...]}`

- **GET /shop/get_images**
  - 기능: 특정 경로의 이미지 목록 조회
  - 파라미터: `path` (이미지 폴더 경로)
  - 응답: `{"status": "ok", "images": ["이미지URL1", "이미지URL2", ...]}`

#### 5.1.2 매물체크(확인) 관련
- **POST /shop/get_all_confirm_with_items**
  - 기능: 매물 확인 데이터 조회
  - 요청 본문: `{"manager": "담당자명", "role": "역할"}`
  - 응답: `{"status": "ok", "data": [매물확인데이터배열]}`

#### 5.1.3 써브상가 관련
- **GET /shop/get_serve_shop_data**
  - 기능: 상가 매물 데이터 조회
  - 파라미터: `address` (주소, 여러 개 가능)
  - 응답: `{"status": "ok", "data": [상가매물데이터배열]}`

#### 5.1.4 써브원룸 관련
- **GET /shop/get_serve_oneroom_data**
  - 기능: 원룸 매물 데이터 조회
  - 파라미터: `address` (주소, 여러 개 가능)
  - 응답: `{"status": "ok", "data": [원룸매물데이터배열]}`

#### 5.1.5 추천매물 관련
- **POST /recommend/get_recommend_data**
  - 기능: 추천 매물 데이터 조회
  - 요청 본문: `{}`
  - 응답: `{"status": "ok", "data": [추천매물데이터배열]}`

#### 5.1.6 마이리스트(상가) 관련
- **GET /mylist/get_mylist_shop_data**
  - 기능: 마이리스트 상가 데이터 조회
  - 파라미터: `manager` (담당자명), `role` (역할)
  - 응답: `{"status": "ok", "data": [마이리스트데이터배열]}`

#### 5.1.7 계약완료 관련
- **GET /completed/get_completed_deals**
  - 기능: 계약 완료 매물 데이터 조회
  - 응답: `{"status": "ok", "data": [계약완료데이터배열]}`

- **POST /completed/add_completed_deals**
  - 기능: 계약 완료 매물 추가
  - 요청 본문: `{"items": [매물정보배열], "manager": "담당자명"}`
  - 응답: `{"status": "ok"}`

## 6. 데이터 모델

### 6.1 공통 데이터 구조
- **주소(address)**: `dong` + `jibun` 형태 (예: "탄방동 935")
- **매물 ID(id)**: 각 매물의 고유 식별자
- **담당자(manager)**: 해당 매물 담당자
- **상태 코드(status_cd)**: 매물 상태 정보

### 6.2 주요 데이터 객체

#### 6.2.1 매물 확인 데이터(confirm)
```json
{
  "dong": "동이름",
  "jibun": "지번",
  "ho": "호수",
  "curr_floor": "현재층",
  "total_floor": "전체층",
  "deposit": "보증금",
  "monthly": "월세",
  "manage_fee": "관리비",
  "premium": "권리금",
  "current_use": "현업종",
  "area": "평수",
  "owner_phone": "연락처",
  "naver_property_no": "네이버매물번호",
  "serve_property_no": "써브매물번호",
  "memo": "제목",
  "matching_biz_type": "매칭업종",
  "manager": "담당자",
  "check_memo": "확인메모"
}
```

#### 6.2.2 상가 매물 데이터(shop)
```json
{
  "dong": "동이름",
  "jibun": "지번",
  "ho": "호수",
  "curr_floor": "현재층",
  "total_floor": "전체층",
  "deposit": "보증금",
  "monthly": "월세",
  "manage_fee": "관리비",
  "premium": "권리금",
  "current_use": "현업종",
  "area": "평수",
  "owner_phone": "연락처",
  "naver_property_no": "네이버매물번호",
  "serve_property_no": "써브매물번호",
  "manager": "담당자",
  "memo": "메모",
  "parking": "주차",
  "building_usage": "용도",
  "approval_date": "사용승인일",
  "rooms": "방수",
  "baths": "화장실수",
  "ad_end_date": "광고종료일",
  "photo_path": "사진경로",
  "owner_name": "소유자명",
  "owner_relation": "관계"
}
```

#### 6.2.3 원룸 매물 데이터(oneroom)
상가 매물 데이터와 유사하며 다음 필드 추가:
```json
{
  "in_date": "입주가능일",
  "password": "비밀번호",
  "options": "옵션"
}
```

#### 6.2.4 마이리스트 데이터(mylist)
상가 매물 데이터와 유사하며 다음 필드 추가:
```json
{
  "re_ad_yn": "재광고여부" // "Y" 또는 "N"
}
```

## 7. 이벤트 시스템

### 7.1 주소 선택 이벤트
- **이벤트 이름**: 'address-selected'
- **발생 상황**: 마이리스트 탭에서 행 클릭 시
- **이벤트 데이터**: `{address: "주소", source: "출처"}`
- **처리 흐름**: 
  1. 마이리스트 탭에서 행 클릭
  2. 'address-selected' 이벤트 발생
  3. main.js의 이벤트 리스너가 이벤트 수신
  4. 모든 탭의 lastSelectedAddress 업데이트
  5. 각 탭에서 filterByAddress() 호출하여 데이터 필터링

```javascript
// 이벤트 발생 예시 (mylistShopTab.js)
const selectEvent = new CustomEvent('address-selected', {
  detail: {
    address: address,
    source: 'mylist-shop'
  }
});
document.dispatchEvent(selectEvent);
```

### 7.2 다중 주소 선택 이벤트
- **이벤트 이름**: 'addresses-selected'
- **발생 상황**: 고객 탭에서 다중 선택 시
- **이벤트 데이터**: `{addresses: ["주소1", "주소2", ...], fromCustomer: true}`
- **처리 흐름**:
  1. 고객 탭에서 다중 주소 선택
  2. 'addresses-selected' 이벤트 발생
  3. main.js의 이벤트 리스너가 이벤트 수신
  4. 모든 탭의 selectedAddresses 업데이트
  5. 각 탭에서 filterByAddresses() 호출하여 데이터 필터링

### 7.3 이미지 슬라이드쇼 요청 이벤트
- **이벤트 이름**: 'show-property-images'
- **발생 상황**: 주소 열 클릭 시
- **이벤트 데이터**: `{address: "주소", photoPath: "경로"}`
- **처리 흐름**:
  1. 주소 열 클릭
  2. 'show-property-images' 이벤트 발생
  3. main.js의 이벤트 리스너가 이벤트 수신
  4. 이미지 슬라이드쇼 모달 표시

## 8. 개발 가이드라인

### 8.1 새 기능 추가 방법
1. BaseTab 클래스를 상속받아 새 탭 클래스 생성
2. 필요한 메서드 오버라이드 (init, loadData, populateTable 등)
3. main.js에 탭 초기화 코드 추가
4. 필요한 이벤트 처리 로직 구현

### 8.2 행 클릭 처리 방법
```javascript
// 행 클릭 이벤트 핸들러 구현 예시
onRowClick(row, event) {
  // 부모 클래스의 기본 동작 수행
  super.onRowClick(row, event);
  
  // 주소 추출
  const address = row.cells[0].textContent;
  if (!address) return;

  // 행 선택 상태 설정
  this.tableElement.querySelectorAll('tbody tr.selected').forEach(tr => {
    tr.classList.remove('selected');
  });
  row.classList.add('selected');
  
  // 체크박스 선택 (있는 경우)
  const checkbox = row.querySelector('input[type="checkbox"]');
  if (checkbox) {
    checkbox.checked = true;
  }
  
  // 주소 선택 이벤트 발생
  const selectEvent = new CustomEvent('address-selected', {
    detail: {
      address: address,
      source: this.tabId
    }
  });
  document.dispatchEvent(selectEvent);
}
```

### 8.3 API 요청 방법
```javascript
// API 요청 예시
loadDataForAddress(address) {
  this.showLoadingMessage();
  
  // 캐시 확인
  if (this.dataCache[address]) {
    this.populateTable(this.dataCache[address]);
    return;
  }
  
  // 서버에서 데이터 로드
  fetch(`${API_BASE_URL}/shop/get_serve_shop_data?address=${encodeURIComponent(address)}`)
    .then(response => {
      if (!response.ok) {
        throw new Error('서버 응답 오류: ' + response.status);
      }
      return response.json();
    })
    .then(data => {
      if (data.status === 'ok') {
        // 데이터 처리
        const rows = data.data || [];
        
        // 캐시에 저장
        rows.forEach(item => {
          const addrStr = (item.dong && item.jibun) 
            ? (item.dong + ' ' + item.jibun).trim() 
            : '';
          
          if (addrStr) {
            if (!this.dataCache[addrStr]) {
              this.dataCache[addrStr] = [];
            }
            this.dataCache[addrStr].push(item);
          }
        });
        
        // 테이블에 표시
        this.populateTable(this.dataCache[address] || []);
      } else {
        this.showErrorMessage(data.message || '데이터 로드 실패');
      }
    })
    .catch(error => {
      console.error('데이터 로드 오류:', error);
      this.showErrorMessage(error.message);
    });
}