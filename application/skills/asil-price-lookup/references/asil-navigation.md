# 아실(ASIL) 사이트 상세 네비게이션 가이드

## 사이트 구조

아실(https://asil.kr)은 네이버 지도 기반의 아파트 부동산 정보 사이트입니다.

### 페이지 레이아웃

```
[헤더: 메뉴바]
  - Home | 매물Home | 순위분석 | 가격분석 | 인구변화 | 입주물량 | 분양
[필터 영역]
  - 시도 > 시구군 > 읍면동 선택
  - 평형 / 세대수 / 입주년차 / 매매실거래가 / 평당가격 / 전세가 / 갭 / 전세가율 필터
[콘텐츠 영역]
  - #sub1: 좌측 목록 (지역/단지 리스트) - iframe
  - #sub2: 우측 상세 (단지 상세 정보) - iframe
  - 지도 영역
```

## 단계별 네비게이션

### 1. 지역 선택 (시도 → 시구군 → 읍면동)

상단 필터 영역의 지역 선택 버튼 클릭:

```bash
browser-use open "https://asil.kr/asil/index.jsp"
browser-use state
# 필터 영역에서 "시도" 버튼 찾기
browser-use click <시도_버튼_index>
browser-use state
# 시도 목록에서 원하는 지역 클릭 (예: 서울)
browser-use click <서울_index>
browser-use state
# 시구군 선택
browser-use click <구_index>
browser-use state
# 읍면동 선택
browser-use click <동_index>
browser-use state
# 아파트 목록에서 단지 선택
browser-use click <아파트_index>
```

### 2. 단지 상세 페이지 구조

단지 클릭 시 `#sub2` iframe에 단지 상세 정보 로드:

```
URL: /app/apt_info.jsp?os=pc&apt=<APT_SEQ>

탭 구성:
- 실거래가 (매매)
- 전세/월세
- 매물
- 단지정보
- 학군
- 주변정보
```

### 3. 실거래가 탭 데이터

```bash
# 단지 상세 페이지에서 실거래가 탭 클릭
browser-use eval "document.querySelector('#sub2').contentDocument.querySelector('a[href*=\"apt_price\"]').click()"

# 또는 직접 URL 접근
browser-use open "https://asil.kr/asil/apt_price_2020.jsp?os=pc&building=apt&apt=<APT_SEQ>"
browser-use state
browser-use get html --selector "table"
```

실거래가 테이블 구조:
```
| 계약일 | 층 | 평형(㎡) | 거래금액 | 거래유형 |
|--------|-----|---------|---------|---------|
| 2025.01 | 5층 | 84㎡(25평) | 9억 5,000 | 매매 |
```

### 4. 전세/월세 탭 데이터

```bash
# 전세/월세 탭 클릭
browser-use eval "document.querySelector('#sub2').contentDocument.querySelector('a[href*=\"jeonse\"], a[href*=\"wolse\"], .tab_jeonse').click()"

# 또는 매물 페이지 직접 접근
browser-use open "https://asil.kr/app/sale_of_apt.jsp?os=pc&user=0&apt=<APT_SEQ>"
browser-use state
```

전세/월세 데이터 구조:
```
전세:
| 평형 | 층 | 전세가 | 등록일 |
|------|-----|-------|-------|
| 25평 | 중층 | 5억 | 2025.01 |

월세:
| 평형 | 층 | 보증금 | 월세 | 등록일 |
|------|-----|-------|------|-------|
| 25평 | 중층 | 1억 | 80만 | 2025.01 |
```

## iframe 내부 데이터 추출 방법

아실은 iframe 구조를 사용하므로 직접 DOM 접근이 필요합니다:

```bash
# sub1 (좌측 목록) 내부 HTML 추출
browser-use eval "document.querySelector('#sub1').contentDocument.body.innerHTML.substring(0, 3000)"

# sub2 (우측 상세) 내부 HTML 추출
browser-use eval "document.querySelector('#sub2').contentDocument.body.innerHTML.substring(0, 3000)"

# 테이블 데이터만 추출
browser-use eval "Array.from(document.querySelector('#sub2').contentDocument.querySelectorAll('table tr')).map(r => Array.from(r.querySelectorAll('td,th')).map(c => c.innerText.trim()).join(' | ')).join('\n')"

# 실거래가 목록 추출
browser-use eval "Array.from(document.querySelector('#sub2').contentDocument.querySelectorAll('.deal_item, .price_item, tr')).map(el => el.innerText.trim()).filter(t => t.length > 0).join('\n')"
```

## 아파트 코드(APT_SEQ) 찾기

URL에서 apt 파라미터 확인:
```bash
browser-use get title
browser-use eval "window.location.href"
# 또는 sub2 iframe URL 확인
browser-use eval "document.querySelector('#sub2').src"
```

## 검색 기능 활용

아실 사이트 검색창 사용:
```bash
browser-use state
# 검색 입력창 찾기 (상단 지역 네비게이션 또는 검색 기능)
browser-use eval "document.querySelector('input[type=text], .search_input').focus()"
browser-use type "아파트명"
browser-use keys "Enter"
browser-use state
```

## 자주 발생하는 문제 해결

### 문제 1: iframe 내용이 비어있음
```bash
# 페이지 로딩 대기
browser-use wait selector "#sub2" --state visible --timeout 5000
browser-use eval "document.querySelector('#sub2').contentDocument.readyState"
```

### 문제 2: 지도 핀이 클릭되지 않음
```bash
# 지도 확대 후 재시도
browser-use eval "map.setZoom(16)"
browser-use state
```

### 문제 3: 데이터가 동적으로 로드됨
```bash
# 스크롤 후 데이터 로드 대기
browser-use scroll down
browser-use wait text "거래일" --timeout 3000
browser-use get html --selector "table"
```

## 주요 CSS 셀렉터

| 요소 | 셀렉터 |
|------|--------|
| 좌측 목록 iframe | `#sub1` |
| 우측 상세 iframe | `#sub2` |
| 지역 선택 버튼 | `.filter_area a` |
| 시도 목록 | `.area_area ul li a` |
| 시구군 목록 | `.area_sigu ul li a` |
| 읍면동 목록 | `.area_dong ul li a` |
| 아파트 목록 | `.area_apt ul li a` |
| 지도 핀 | `.pin_st2` |
| 실거래가 탭 | `a[href*="apt_price"]` |
| 가격 테이블 | `table.price_table, .deal_list table` |

## 데이터 수집 완전 예시

```bash
# 1. 사이트 열기
browser-use open "https://asil.kr/asil/index.jsp"

# 2. 서울 선택
browser-use state
browser-use click <시도_버튼>
browser-use click <서울>

# 3. 강남구 선택
browser-use click <강남구>

# 4. 대치동 선택
browser-use click <대치동>

# 5. 은마아파트 선택
browser-use click <은마아파트>

# 6. 단지 상세 로드 확인
browser-use eval "document.querySelector('#sub2').src"

# 7. 실거래가 데이터 추출
browser-use eval "Array.from(document.querySelector('#sub2').contentDocument.querySelectorAll('tr')).map(r => r.innerText.trim()).filter(t=>t).join('\n')"

# 8. 전세/월세 탭으로 이동
browser-use eval "document.querySelector('#sub2').contentDocument.querySelector('.tab_jeonse, a[onclick*=\"jeonse\"]').click()"
browser-use eval "Array.from(document.querySelector('#sub2').contentDocument.querySelectorAll('tr')).map(r => r.innerText.trim()).filter(t=>t).join('\n')"
```
