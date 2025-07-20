# 🏢 GUI Management System

PyQt5 기반 부동산 관리 시스템 - 마이리스트, 상가관리, 고객관리 통합 플랫폼

## 🚀 최근 업데이트 (2025-07-20)
- ✅ **헤더 기반 컬럼 매핑 시스템** 추가 - 안전한 테이블 조작
- ✅ **마이리스트 로딩 성능 최적화** - 순차 로딩으로 500 에러 해결
- ✅ **GitHub 백업 시스템** 구축

## 프로젝트 구성

### 프론트엔드
- 웹 프론트엔드는 순수 JavaScript를 이용하여 구현
- 백엔드 API와 통신하여 데이터 로드 및 표시

### 백엔드
- Python으로 구현된 API 서버
- 데이터베이스에서 부동산 매물 정보 조회 및 관리

## 주요 기능

### 매물체크
- 부동산 매물의 상세 정보 확인
- API 경로: `/shop/get_all_confirm_with_items`

### 써브상가
- 상가 매물 정보 조회
- API 경로: `/shop/get_serve_shop_data`

### 써브원룸
- 원룸 매물 정보 조회
- API 경로: `/shop/get_serve_oneroom_data`

### 추천매물
- 추천 매물 관리 및 조회
- API 경로: `/recommend/get_recommend_data`

### 마이리스트(상가)
- 나의 상가 매물 관리
- 행 클릭 시 체크박스 선택 및 다른 탭과 데이터 연동
- API 경로: `/mylist/get_mylist_shop_data`

### 계약완료
- 계약이 완료된 매물 관리
- API 경로: `/completed/get_completed_deals`

## 이벤트 시스템

시스템은 다음과 같은 이벤트를 통해 탭 간 통신을 합니다:

- **address-selected**: 마이리스트 탭에서 행 클릭 시 발생, 모든 탭에 주소 선택 정보 전파
- **addresses-selected**: 다중 주소 선택 시 발생
- **show-property-images**: 이미지 슬라이드쇼 요청 시 발생

## 개발 시작하기

1. 저장소 클론
2. 웹 서버 실행
3. API 서버 실행

## 상세 문서

자세한 프로젝트 문서는 [PRD.md](./PRD.md) 파일을 참조하세요.