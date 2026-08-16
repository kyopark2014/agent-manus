# img2textocr

이미지 파일(PNG, JPG 등)에서 Tesseract OCR을 사용해 본문 텍스트를 추출하는 Agent Skill입니다.
상단 header(페이지 제목)와 하단 footer(페이지 번호 등)를 자동으로 제거하고 본문만 추출합니다.

---

## 배경

2017 NEC(National Electrical Code) PDF를 페이지 단위 PNG 이미지로 변환한 후,
각 페이지 이미지에서 본문 텍스트만 추출하는 작업이 필요했습니다.

문서 이미지의 특성상:
- **상단 header**: 현재 Article/Section 제목이 표시됨 (예: `90.1 ARTICLE 90 — INTRODUCTION`)
- **하단 footer**: 페이지 번호와 출처가 표시됨 (예: `70-30 NATIONAL ELECTRICAL CODE 2017 Edition`)

이 두 영역은 본문 텍스트 추출 시 불필요하므로 자동으로 제거합니다.

---

## 파일 구조

```
img2textocr/
├── SKILL.md                  ← Agent 트리거 설명 및 사용 가이드
├── README.md                 ← 이 문서
└── scripts/
    └── img2textocr.py        ← OCR 실행 스크립트 (메인)
```

---

## 동작 방식

```
[원본 이미지]
     │
     ▼
┌─────────────────────┐
│  상단 crop (기본 9%)  │  ← header 제거
├─────────────────────┤
│                     │
│      본문 영역        │  ← OCR 대상
│                     │
├─────────────────────┤
│  하단 crop (기본 4%)  │  ← footer 제거
└─────────────────────┘
     │
     ▼
[그레이스케일 변환 + Contrast/Sharpness 향상]
     │
     ▼
[Tesseract OCR (psm=6, dpi=300)]
     │
     ▼
[페이지번호 라인 정규식 제거]
     │
     ▼
[.txt 파일 저장]
```

---

## 스크립트 사용법

### 기본 사용

```bash
python skills/img2textocr/scripts/img2textocr.py <image_path> [output_txt_path]
```

### 옵션

| 옵션 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `image_path` | str | (필수) | 소스 이미지 경로 |
| `output_path` | str | 자동 | 출력 .txt 경로 (미지정 시 이미지와 동일 경로에 동일 파일명.txt) |
| `--top-crop` | float | 0.09 | 상단에서 crop할 비율 (header 제거) |
| `--bottom-crop` | float | 0.04 | 하단에서 crop할 비율 (footer 제거) |
| `--lang` | str | eng | Tesseract 언어 코드 |
| `--psm` | int | 6 | Tesseract 페이지 세그멘테이션 모드 |

### 예시

```bash
# 기본 실행
python skills/img2textocr/scripts/img2textocr.py \
    artifacts/2017-NEC-Code/page_033.png \
    artifacts/2017-NEC-Code/page_033.txt

# header가 더 큰 경우 (12% crop)
python skills/img2textocr/scripts/img2textocr.py \
    artifacts/2017-NEC-Code/page_033.png \
    --top-crop 0.12

# 한국어+영어 혼합 문서
python skills/img2textocr/scripts/img2textocr.py \
    page.png \
    --lang kor+eng
```

---

## 의존성

| 패키지 | 설치 방법 | 비고 |
|--------|-----------|------|
| `pytesseract` | 스크립트 자동 설치 | Python Tesseract 래퍼 |
| `Pillow` | 스크립트 자동 설치 | 이미지 처리 |
| `tesseract` | `brew install tesseract` | 시스템 설치 필요 |

> ⚠️ `tesseract` 바이너리는 시스템에 직접 설치되어 있어야 합니다.
> macOS: `brew install tesseract`
> Ubuntu: `sudo apt install tesseract-ocr`

---

## Agent 트리거 예시

다음과 같은 사용자 요청에서 이 skill이 활성화됩니다:

- `"page_033.png을 img2text로 변환해줘"`
- `"이 이미지에서 본문만 추출해줘"`
- `"header/footer 제외하고 텍스트 추출해줘"`
- `"artifacts/2017-NEC-Code/page_035.png를 텍스트로 변환해줘"`

---

## 실제 작업 결과 예시

**입력**: `artifacts/2017-NEC-Code/page_033.png` (1275×1650 px)

**출력**: `artifacts/2017-NEC-Code/page_033.txt`

```
ARTICLE 90
Introduction

90.1 Purpose.
(A) Practical Safeguarding. The purpose of this Code is the
practical safeguarding of persons and property from hazards
arising from the use of electricity. ...

90.2 Scope.
(A) Covered. This Code covers the installation and removal of
electrical conductors, equipment, and raceways; ...
```

- 추출 문자 수: 약 5,500자
- header(`90.1 ARTICLE 90 — INTRODUCTION`) 제거 ✅
- footer(`70-30 NATIONAL ELECTRICAL CODE 2017 Edition`) 제거 ✅
