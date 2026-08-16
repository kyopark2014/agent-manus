---
name: img2text
description: >
  폴더 내 모든 이미지를 AWS Bedrock(LLM) 멀티모달로 순차 변환해 하나의 통합 Markdown 파일(.md)로 만든다.
  `mcp_server_text_extraction.py`와 동일한 전처리(크기·픽셀 제한)·추출 파이프라인을 사용한다.
  출력은 명시적으로 Markdown이며, 도표·그림 등이 있으면 의미를 상세 서술하도록 프롬프트한다.
  상단 header·하단 footer 제외 및 문장 단위 구분을 적용한다.
  트리거: img2text, 이미지 폴더에서 Markdown 추출, 멀티 페이지 이미지 LLM 변환,
  `artifacts/...` 같은 스캔 폴더 전체 LLM 추출, WB_Troubleshooting 같은 매뉴얼 폴더 일괄 변환.
---

# img2text (LLM 이미지→Markdown, 폴더 배치)

## 개요

입력으로 **이미지 파일들이 들어 있는 디렉터리 경로**를 받는다 (예: `artifacts/WB_Troubleshooting Manual_KOR_4.4`).

1. 해당 폴더의 **파일 목록**을 가져온다.
2. **이미지 확장자만** 필터링한다 (`.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.bmp`, `.tiff`, `.tif`).
3. 파일명 **자연 정렬**(숫자 기준: `page_2` → `page_10` 순)으로 한 장씩 처리한다.
4. 각 이미지에 대해 **`application/mcp_server_text_extraction.py`**와 동일한 방식으로 내용을 생성한다.
   - `_prepare_image_base64` → `_extract_text_with_llm` → `_parse_result` 흐름.
   - 실행 편의: 배치 스크립트 `skills/img2text/scripts/batch_img2text.py`가 위 로직을 호출한다.
5. 폴더 **바로 안쪽**에 **`{폴더이름}.md`** 파일을 만들고, 페이지별 구획과 함께 **Markdown 본문**을 기록한다 (통합 한 파일).

## LLM 프롬프트 (배치·MCP 공통)

`extract_text_from_image`의 `prompt` 인수 또는 배치 스크립트가 전달하는 프롬프트에 아래 블록을 **통째로** 사용한다.

```
페이지 내용을 Markdown 형식으로 변환합니다. 평문이 아니라 제목(#·##)·목록·강조·코드 블록 등 Markdown 문법을 적절히 써서 구조화해 주세요. 문장 단위로 읽기 쉽게 구분합니다. 상단의 header와 하단의 footer는 출력에서 제외합니다. 상단 header는 주로 현재 페이지 제목이고, footer에는 페이지 번호 등이 있는데, 변환 결과에는 포함하지 않습니다.

페이지에 그림·도표·사진·스크린샷·다이어그램·캡처 등 시각적 요소가 있으면, 그 이미지가 무엇을 보여주는지·본문과 어떤 관계인지·어떤 정보를 전달하는지를 빠짐없이 상세히 풀어서 서술합니다.
```

`<result>` 태그가 없으면 `_parse_result`는 응답 전체를 반환하므로, 태그 강제는 선택 사항이다.

## 에이전트 워크플로우

### A. 배치 스크립트 권장 (동일 코드 경로)

저장소 **`application`** 디렉터리에서 실행한다.

```bash
cd application
python skills/img2text/scripts/batch_img2text.py "artifacts/WB_Troubleshooting Manual_KOR_4.4"
```

- 출력 기본값: `artifacts/WB_Troubleshooting Manual_KOR_4.4/WB_Troubleshooting Manual_KOR_4.4.md`
- 다른 출력 경로: `--output /path/to/out.md`

### B. MCP 도구로 수동 반복

MCP `extract_text_from_image`를 사용할 때 각 이미지에 대해 `image_path`와 위 **LLM 프롬프트 전문**을 `prompt`로 넘긴다. 폴더 전체는 파일 목록 순서대로 반복 호출한 뒤, 결과를 `{폴더이름}.md`에 같은 형식으로 합친다.

## 출력 파일 형식 (통합 `.md`)

배치 스크립트는 각 이미지 구역을 Markdown 제목으로 구분한다.

```markdown
## 파일: page_001.png

(해당 이미지에서 생성한 Markdown 본문 — 그림이 있으면 의미 상세 서술 포함)

## 파일: page_002.png

...
```

## 참조 구현

| 구분 | 경로 |
|------|------|
| Bedrock 멀티모달 추출 | `application/mcp_server_text_extraction.py` (`_prepare_image_base64`, `_extract_text_with_llm`, `_parse_result`, `extract_text_from_image`) |
| 배치 실행 | `application/skills/img2text/scripts/batch_img2text.py` |

## 의존성

`mcp_server_text_extraction.py`와 동일: `boto3`, `langchain-aws`, `langchain-core`, `Pillow`, 설정(`utils.load_config`, `info.get_model_info`), AWS 자격·Bedrock 권한.

## 예시

사용자: `artifacts/WB_Troubleshooting Manual_KOR_4.4 폴더 이미지 전부 img2text로 합쳐줘`

에이전트: `application`에서 `batch_img2text.py`를 해당 폴더 인수로 실행하고, 생성된 `{폴더이름}.md` 경로와 앞부분 미리보기를 보고한다.
