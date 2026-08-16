---
name: model-discover
description: >
  AWS Bedrock에서 Anthropic Claude 모델의 리전별 지원 여부를 확인하는 스킬.
  사용자가 "sonnet 4.7", "opus 4.7", "haiku 4.5" 등의 모델명을 입력하면
  AWS 주요 10개 리전(미국, 유럽, 아시아 태평양)에서 해당 모델이 지원되는지 조회하고
  지원 리전 목록과 실제 모델 ID를 알려준다.
  다음과 같은 요청에 사용한다:
  (1) "sonnet 4.7 어느 리전에서 쓸 수 있어?",
  (2) "opus 4.7 지원 리전 알려줘",
  (3) "AWS Bedrock에서 claude haiku 4.5 쓸 수 있는 리전은?",
  (4) 특정 Claude 모델의 가용 리전 확인 요청
---

# Model Discover

AWS Bedrock에서 Anthropic Claude 모델의 리전별 지원 여부를 확인한다.

## 워크플로우

1. 사용자 입력에서 모델명 파악 (예: "sonnet 4.7", "opus 4.7")
2. `scripts/check_model.py` 실행
3. 결과를 사용자에게 친절하게 설명

## 스크립트 실행

```bash
python skills/model-discover/scripts/check_model.py "sonnet 4.7"
python skills/model-discover/scripts/check_model.py "opus 4.7"
python skills/model-discover/scripts/check_model.py "haiku 4.5"

# JSON 출력
python skills/model-discover/scripts/check_model.py "opus 4.7" --json

# 특정 리전만 검색
python skills/model-discover/scripts/check_model.py "sonnet 4.5" --regions us-east-1 ap-northeast-2
```

## 모델명 입력 규칙

- 형식: `{시리즈} {버전}` (예: `sonnet 4.7`, `opus 4.7`, `haiku 4.5`)
- 버전의 `.`은 자동으로 `-`로 변환되어 모델 ID와 매칭됨
- 버전 생략 시 해당 시리즈 전체 매칭 (예: `sonnet 4` → 4.x 전체)
- 모델 명명 규칙 상세: `references/model-naming.md` 참조

## 검색 대상 리전 (기본 10개)

us-east-1, us-east-2, us-west-2, eu-west-1, eu-west-2, eu-central-1,
ap-northeast-1, ap-northeast-2, ap-southeast-1, ap-southeast-2

## 결과 해석 및 전달

스크립트 출력을 그대로 전달하되, 다음을 추가로 안내한다:
- 지원 리전이 없을 경우: 모델명 오타 가능성 또는 아직 미출시 안내
- 에러 리전이 있을 경우: AWS 자격증명 또는 권한 문제 가능성 안내
- 여러 모델 ID가 매칭될 경우: 각 모델 ID의 차이(날짜, 버전) 설명
