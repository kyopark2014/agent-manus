# Anthropic 모델 명명 규칙 참조

## AWS Bedrock 모델 ID 패턴

Anthropic 모델의 AWS Bedrock 모델 ID는 다음 패턴을 따릅니다:

```
anthropic.claude-{series}-{version}-{date}-v{revision}:{context}
```

예시:
- `anthropic.claude-sonnet-4-5-20250929-v1:0`
- `anthropic.claude-opus-4-7`
- `anthropic.claude-opus-4-1-20250805-v1:0`
- `anthropic.claude-3-7-sonnet-20250219-v1:0`
- `anthropic.claude-3-haiku-20240307-v1:0`

## 사용자 입력 → 키워드 변환 규칙

| 사용자 입력 | 변환 키워드 | 매칭 예시 |
|------------|------------|---------|
| `sonnet 4.7` | `["sonnet", "4-7"]` | `claude-sonnet-4-7-...` |
| `opus 4.7` | `["opus", "4-7"]` | `claude-opus-4-7` |
| `haiku 4.5` | `["haiku", "4-5"]` | `claude-haiku-4-5-...` |
| `sonnet 4.5` | `["sonnet", "4-5"]` | `claude-sonnet-4-5-...` |
| `opus 4` | `["opus", "4"]` | `claude-opus-4-...` |
| `sonnet 4` | `["sonnet", "4"]` | `claude-sonnet-4-...` |
| `haiku 3.5` | `["haiku", "3-5"]` | `claude-3-5-haiku-...` |
| `sonnet 3.7` | `["sonnet", "3-7"]` | `claude-3-7-sonnet-...` |

**변환 규칙:**
1. 소문자로 변환
2. `.` → `-` 치환
3. 공백으로 분리하여 키워드 배열 생성
4. 모델 ID에 모든 키워드가 포함되면 매칭

## 주의사항

- `sonnet 4`를 검색하면 `sonnet-4-5`, `sonnet-4-6`, `sonnet-4-7` 등 4 시리즈 전체가 매칭될 수 있음
- 더 구체적인 버전(예: `sonnet 4.5`)을 입력하면 정확한 모델만 매칭됨
- 날짜 접미사(`-20250929`)나 버전 접미사(`-v1:0`)는 입력하지 않아도 됨

## AWS 주요 리전 목록

| 리전 코드 | 위치 |
|----------|------|
| `us-east-1` | 미국 동부 (버지니아) |
| `us-east-2` | 미국 동부 (오하이오) |
| `us-west-2` | 미국 서부 (오레곤) |
| `eu-west-1` | 유럽 (아일랜드) |
| `eu-west-2` | 유럽 (런던) |
| `eu-central-1` | 유럽 (프랑크푸르트) |
| `ap-northeast-1` | 아시아 태평양 (도쿄) |
| `ap-northeast-2` | 아시아 태평양 (서울) |
| `ap-southeast-1` | 아시아 태평양 (싱가포르) |
| `ap-southeast-2` | 아시아 태평양 (시드니) |
