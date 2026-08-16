---
name: ppt-translator
description: >-
  Amazon Bedrock 기반 PowerPoint(.pptx) 번역. 서식·레이아웃·차트 메타(제목/축 등)를 보존하며
  텍스트를 한국어(ko) 등 대상 언어로 변환. CLI(`python -m ppt_translator.cli`)·SQLite 캐시·용어집·
  원문 언어 자동 감지. PPT/슬라이드 번역, pptx 한국어, Bedrock 프레젠테이션 번역, batch translate,
  dry-run 비용 추정.
---

# PPT Translator (한국어 변환)

## Directory Convention (경로 혼동 방지)

| 심볼 | 의미 |
|------|------|
| **`{workspace}`** | **프로젝트(저장소) 루트** — `application/` 디렉터리를 포함하는 최상위 경로 |
| **`{WORKING_DIR}`** | **`application/`** 디렉터리 — 이 저장소에서 시스템이 노출하는 작업 루트 |

이 스킬의 **유일한 소스·실행 루트**:

```
{WORKING_DIR}/skills/ppt-translator
```

- 모든 `cd`, `read_file`, `pip install -r requirements.txt` 경로는 위 경로를 기준으로 쓴다.
- `python -m ppt_translator.cli` 를 쓰려면 **CWD를 위 경로로 설정**해야 `ppt_translator` 패키지가 `sys.path`에 잡힌다.

## 번들 구성

| 항목 | 경로 |
|------|------|
| 에이전트 지침 | `{WORKING_DIR}/skills/ppt-translator/SKILL.md` (이 파일) |
| 패키지 | `{WORKING_DIR}/skills/ppt-translator/ppt_translator/` |
| CLI | `python -m ppt_translator.cli` (Click) |
| 의존성 | `{WORKING_DIR}/skills/ppt-translator/requirements.txt` |
| 용어집 예시 | `{WORKING_DIR}/skills/ppt-translator/glossary.yaml` — CWD에 `./glossary.yaml` 이 있으면 자동 탐색 |

전체 옵션: `python -m ppt_translator.cli --help` 및 각 서브커맨드 `--help`.
구조·클래스: `ppt_translator/ppt_handler.py` (`FormattingExtractor`, `TextFrameUpdater`, `PowerPointTranslator`).
upstream 문서: [ppt-translator](https://github.com/daekeun-ml/ppt-translator)

## 데이터 흐름 (수정 시 이 순서 유지)

1. **진입**: `cli.py` (Click).
2. **오케스트레이션**: `ppt_handler.PowerPointTranslator` — 슬라이드·도형·노트·차트 대상, 서식 보존 번역.
3. **LLM**: `translation_engine.py` + `bedrock_client.py`, `config.Config` 의 모델·토큰 한도.
4. **원문**: `language_detection.py` — 자동 감지(옵션); 원문==대상이면 API 생략.
5. **차트**: `chart_handler.py` — 메타 텍스트만 번역, 수치 유지.
6. **후처리**: `post_processing.py` — `PowerPointPostProcessor` 등.
7. **캐시·비용**: `cache.py`, `pricing.py`.
8. **용어·프롬프트**: `glossary.py`, `prompts.py`.

별도 스크립트로 "간단 번역" 파이프라인을 만들지 말고 위 모듈을 확장한다.

## 한국어(ko) 기본값

`ppt_translator/config.py` 의 `Config.DEFAULT_TARGET_LANGUAGE` 는 기본 **`ko`**. 언어 미지정 시 대상은 한국어로 둔다. 한국어 폰트는 `FONT_KOREAN` / `FONT_MAP['ko']`.

## 사전 조건

- Python 3.11+
- AWS 자격 증명 + Bedrock 모델 액세스 (`AWS_REGION`, `BEDROCK_MODEL_ID` 등 — `ppt_translator/config.py`)
- 선택: `{WORKING_DIR}/skills/ppt-translator/.env` (`config` 가 패키지 상위 루트의 `.env` 를 로드)

## 실행 방법 (execute_code 사용)

`subprocess.run()` 으로 실행할 때는 **`capture_output=False`** 를 사용해 번역 진행 상황을 실시간으로 출력한다.

```python
import subprocess, sys, os

SKILL_DIR = "{WORKING_DIR}/skills/ppt-translator"
input_file  = "/path/to/input.pptx"          # 사용자가 지정한 절대 경로
output_file = "{WORKING_DIR}/artifacts/output_ko.pptx"  # artifacts/ 에 저장 권장

# 1) 의존성 설치
subprocess.run(["pip", "install", "-r", "requirements.txt", "-q"],
               cwd=SKILL_DIR, check=True)

# 2) 번역 실행 (capture_output=False → 진행 상황 실시간 출력)
result = subprocess.run(
    [sys.executable, "-m", "ppt_translator.cli",
     "translate", input_file,
     "-t", "ko",
     "-o", output_file],
    cwd=SKILL_DIR,
    capture_output=False,
    text=True,
)
print("Return code:", result.returncode)
```

## CLI 서브커맨드 & 옵션 레퍼런스

> **공통 주의**: 출력 경로는 `--output`이 아니라 반드시 `-o` / `--output-file` 을 사용한다.

### `translate` — 전체 슬라이드 번역

```bash
python -m ppt_translator.cli translate INPUT_FILE [OPTIONS]
```

| 옵션 | 단축 | 설명 |
|------|------|------|
| `--target-language` | `-t` | 대상 언어 (기본 `ko`) |
| `--output-file` | `-o` | 출력 파일 경로 |
| `--model-id` | `-m` | Bedrock 모델 ID |
| `--source-language` | | 원문 언어 코드 (예: `en`). 생략 시 자동 감지 |
| `--no-detect-source` | | 원문 언어 자동 감지 비활성화 (모델이 컨텍스트로 판단) |
| `--no-polishing` | | 자연어 다듬기(polishing) 비활성화 |
| `--glossary` | `-g` | 용어집 YAML 파일 (기본: CWD의 `./glossary.yaml`) |
| `--cache-backend` | | `sqlite`(기본) / `memory` / `none` |
| `--cache-path` | | SQLite 캐시 경로 |
| `--no-cache` | | 캐시 비활성화 |
| `--dry-run` | | 비용 추정만 (번역·저장 없음) |
| `--no-charts` | | 차트 메타 번역 건너뜀 |

### `translate-slides` — 특정 슬라이드만 번역

```bash
python -m ppt_translator.cli translate-slides INPUT_FILE -s "1,3,5" -t ko -o output.pptx
python -m ppt_translator.cli translate-slides INPUT_FILE -s "2-4"   -t ko -o output.pptx
```

| 옵션 | 단축 | 설명 |
|------|------|------|
| `--slides` | `-s` | 슬라이드 번호. 쉼표 `"1,3,5"` 또는 범위 `"2-4"` **(필수)** |
| (이하 `translate`와 동일) | | |

### `batch-translate` — 폴더 내 전체 .pptx 일괄 번역

```bash
python -m ppt_translator.cli batch-translate INPUT_FOLDER -t ko -o OUTPUT_FOLDER
```

| 옵션 | 단축 | 설명 |
|------|------|------|
| `--target-language` | `-t` | 대상 언어 |
| `--output-folder` | `-o` | 출력 폴더 경로 |
| `--workers` | `-w` | 병렬 처리 워커 수 (기본 4) |
| `--recursive` / `--no-recursive` | `-r` / `-R` | 하위 폴더 재귀 처리 (기본: 활성화) |
| (캐시·용어집·dry-run 등 `translate`와 동일) | | |

### `info` — 슬라이드 정보 미리보기

```bash
python -m ppt_translator.cli info INPUT_FILE
```
