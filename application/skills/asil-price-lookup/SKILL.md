---
name: asil-price-lookup
description: 아실(asil.kr) 사이트에서 아파트 실거래가(매매), 전세, 월세 정보를 조회합니다. browser-use CLI와 Python BeautifulSoup을 사용하여 특정 아파트 단지의 매매 실거래가, 전세가, 월세 정보를 검색하고 결과를 정리합니다. 사용자가 "아파트 실거래가 조회", "전세 시세 확인", "월세 정보", "아파트 매매가", "갱신 제외 전세" 등을 요청할 때 사용합니다.
---

# 아실(ASIL) 아파트 가격 조회

아실(https://asil.kr)에서 아파트의 매매 실거래가, 전세, 월세 정보를 browser-use CLI로 조회합니다.

## 사전 조건

```bash
browser-use doctor   # 설치 확인
```

## 평형 표기 규칙

아실에서 제공하는 `span.type` 값은 **전용면적(㎡)** 이며, 아파트 관행상 부르는 **평형명**은 공급면적 기준입니다.
단순히 ㎡ ÷ 3.3으로 계산하면 틀린 평형이 나오므로, 아래 매핑 테이블을 사용하세요.

| 전용면적(㎡) | 평형 호칭 |
|------------|---------|
| 49㎡ | 20평형 |
| 59㎡ | 24평형 |
| 74㎡ | 30평형 |
| 84㎡ | 32평형 |
| 101㎡ | 40평형 |
| 114㎡ | 45평형 |
| 134㎡ | 52평형 |

매핑 테이블에 없는 면적은 `round(㎡ / 3.3)` 으로 근사값을 표시하되, "약 N평" 형식으로 표기합니다.

```python
PYEONG_MAP = {
    49: 20, 59: 24, 74: 30, 84: 32,
    101: 40, 114: 45, 134: 52,
}

def to_pyeong(sqm_str):
    sqm = int(sqm_str)
    if sqm in PYEONG_MAP:
        return f"{PYEONG_MAP[sqm]}평형"
    return f"약 {round(sqm / 3.3)}평형"
```

## 핵심 워크플로우

### 1단계: 아파트 검색 (APT_SEQ 획득)

```python
import subprocess

# 메인 페이지 열기
subprocess.run(['browser-use', 'open', 'https://asil.kr/asil/index.jsp'], ...)

# ⚠️ 검색창은 Shadow DOM 내부에 있으므로 반드시 eval로 접근
subprocess.run(['browser-use', 'eval', """
    var iframe = document.querySelector('#sub1');
    var iframeDoc = iframe.contentDocument;
    var searchDiv = iframeDoc.querySelector('div');
    var shadowRoot = searchDiv ? searchDiv.shadowRoot : null;
    var input = shadowRoot ? shadowRoot.querySelector('#keyword') : iframeDoc.querySelector('#keyword');
    if(input) {
        input.focus();
        input.value = '검색어';
        input.dispatchEvent(new Event('input', {bubbles:true}));
        input.dispatchEvent(new KeyboardEvent('keyup', {bubbles:true}));
        'ok';
    } else { 'not found'; }
"""], ...)

import time; time.sleep(2)

# 검색 결과에서 APT_SEQ 추출
result = subprocess.run(['browser-use', 'eval',
    "document.querySelector('#sub1').contentDocument.body.innerHTML"], ...)
# HTML에서 openApt('APT_SEQ','단지명') 패턴으로 APT_SEQ 확인
```

검색 결과 HTML 예시:
```html
<li><a onclick="openApt('2771','동아')">동아<br>
  <i>서울 서초구 잠원동 / 02년07월 / 991세대 / 아파트</i></a></li>
```

### 2단계: 실거래가 페이지 접근

아실의 `apt_price_2020.jsp`는 **매매/전세/월세를 모두 포함하는 통합 페이지**입니다.
별도 탭 전환 없이 한 번에 모든 거래 유형 데이터를 가져올 수 있습니다.

```python
subprocess.run(['browser-use', 'open',
    f'https://asil.kr/asil/apt_price_2020.jsp?os=pc&building=apt&apt={APT_SEQ}'], ...)

import time; time.sleep(2)

# iframe #ifrm 내부 HTML 추출
result = subprocess.run(['browser-use', 'eval',
    "document.querySelector('#ifrm').contentDocument.body.innerHTML"], ...)

html_content = result.stdout
if html_content.startswith("result: "):
    html_content = html_content[8:]
```

### 3단계: HTML 파싱 (BeautifulSoup)

```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(html_content, 'html.parser')
rows = soup.select('table#tableList1 tbody tr')

transactions = []
current_month = None

for row in rows:
    mm_span = row.select_one('span.mm')
    dd_span = row.select_one('span.dd')
    info_span = row.select_one('span.info')   # 갱신 여부
    price_td = row.select_one('td.price')
    type_span = row.select_one('span.type')   # 전용면적(㎡)
    dong_span = row.select_one('span.aptdong')
    floor_span = row.select_one('span.aptfloor')

    if not price_td:
        continue

    if mm_span and mm_span.text.strip():
        current_month = mm_span.text.strip()  # "26.03" 형식

    deal_type_span = price_td.select_one('span.b')   # 전세/매매/월세
    price_span = price_td.select_one('span.eb')       # 가격

    if not deal_type_span or not price_span:
        continue

    sqm = type_span.text.strip() if type_span else ''
    transactions.append({
        'month': current_month,
        'day': dd_span.text.strip() if dd_span else '',
        'deal_type': deal_type_span.text.strip(),
        'price': price_span.text.strip(),
        'is_renewal': bool(info_span and '갱신' in info_span.text),
        'sqm': sqm,                    # 전용면적 ("84")
        'pyeong': to_pyeong(sqm) if sqm else '',  # 평형 호칭 ("32평형")
        'dong': dong_span.text.strip() if dong_span else '',
        'floor': floor_span.text.strip() if floor_span else '',
    })
```

### 4단계: 필터링 및 결과 정리

```python
# 전세만, 갱신 제외
jeonse = [t for t in transactions
          if t['deal_type'] == '전세' and not t['is_renewal']]

# 매매만
maemae = [t for t in transactions if t['deal_type'] == '매매']

# 최근 N개월 필터 (month 형식: "26.03" = 2026년 3월)
recent_months = ['26.02', '26.03']
recent = [t for t in jeonse if t['month'] in recent_months]
```

## 아실 URL 패턴

| 기능 | URL 패턴 |
|------|---------|
| 메인 | `https://asil.kr/asil/index.jsp` |
| 실거래가(통합) | `https://asil.kr/asil/apt_price_2020.jsp?os=pc&building=apt&apt=<APT_SEQ>` |
| 단지 상세 | `https://asil.kr/app/apt_info.jsp?os=pc&apt=<APT_SEQ>` |
| 매물 목록 | `https://asil.kr/app/sale_of_apt.jsp?os=pc&user=0&apt=<APT_SEQ>` |

## 주요 iframe 구조

| iframe ID | 역할 |
|-----------|------|
| `#sub1` | 좌측 목록 (검색/지역/단지 리스트) |
| `#ifrm` | 실거래가 페이지 내 데이터 테이블 |

## 데이터 구조

### 거래 테이블 (`table#tableList1 tbody tr`)

| 셀렉터 | 내용 |
|--------|------|
| `span.mm` | 계약 연월 ("26.03") — 같은 월은 첫 행에만 표시 |
| `span.dd` | 계약 일 |
| `span.info` | "갱신" 텍스트 (갱신 계약인 경우) |
| `td.price span.b` | 거래 유형 (전세/매매/월세) |
| `td.price span.eb` | 가격 ("12억 5,000") |
| `span.type` | **전용면적** ㎡ ("84") — 평형 호칭과 다름, 위 매핑 테이블 사용 |
| `span.aptdong` | 동 ("103동") |
| `span.aptfloor` | 층 ("5층") |

## 결과 정리 형식

```
📍 아파트명: [단지명]
📍 위치: [시/구/동]
🏠 세대수: [N세대] | 입주: [YYYY년]

🏡 전세 실거래 내역 (갱신 제외, 최신순)
계약일         평형              가격           위치
2026.03.25    84㎡ (32평형)    12억 5,000만원  103동 5층
2026.02.28    59㎡ (24평형)    8억             106동 5층
...

📊 평형별 요약
📐 59㎡ (24평형) - N건
   최고가: X억 / 최저가: X억 / 평균가: X억

🔗 출처: https://asil.kr/asil/apt_price_2020.jsp?os=pc&building=apt&apt=<APT_SEQ>
```

## 주의사항

- **평형 표기**: `span.type`은 전용면적(㎡)이며 평형 호칭과 다름 — 반드시 `PYEONG_MAP` 사용
- **검색창 Shadow DOM**: `#sub1` iframe 내 검색창은 Shadow DOM 안에 있어 `browser-use type` 불가 → `eval`로 접근
- **통합 페이지**: `apt_price_2020.jsp`는 매매/전세/월세 모두 포함 — 탭 전환 불필요
- **월 표시 누락**: 같은 월의 거래는 첫 행에만 `span.mm`이 있으므로 `current_month` 변수로 추적 필수
- **데이터 로딩**: `browser-use open` 후 `time.sleep(2)` 대기 필요

## 참고

- 상세 네비게이션: [asil-navigation.md](references/asil-navigation.md)
