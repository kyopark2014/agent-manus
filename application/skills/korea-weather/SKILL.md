---
name: korea-weather
description: 기상청 날씨누리 동네예보·현재날씨와 에어코리아 대기질로 한국 날씨를 조회합니다. 사용자가 "날씨", "오늘 날씨", "우산", "미세먼지", "기온", "비 오나요", "현재 위치 날씨" 등을 묻거나 특정 지역(동/구/시) 날씨를 요청할 때 사용합니다. API 키 불필요.
---

# Korea Weather

기상청 날씨누리(weather.go.kr) 행정동 단위 동네예보·현재날씨와 에어코리아 대기질을 조회합니다.

## When to Use

- 한국 날씨 / 기온 / 강수 / 습도 / 바람 문의
- 미세먼지·초미세먼지 등 대기질 문의
- 지역명을 주지 않은 "날씨 알려줘", "우산 필요해?" 류 요청
- 특정 동·구·시 날씨 (예: 반포3동, 서초구, 부산 해운대)

## Script Location

application working directory 기준 전체 경로를 사용하세요.

| 스크립트 | 용도 |
| --- | --- |
| `skills/korea-weather/scripts/recall_home_location.py` | 지역명 미지정 시 memory에서 집/거주 주소 조회 |
| `skills/korea-weather/scripts/get_weather.py` | 기상청 동네예보·현재날씨·대기질 조회 |

**IMPORTANT**: `scripts/...`로 줄이지 말고 위 전체 경로를 사용하세요.

## Critical Rules

1. 지역명이 없으면 **먼저** memory로 집/거주 주소를 조회하세요.
   ```bash
   python skills/korea-weather/scripts/recall_home_location.py
   ```
   - 주소가 나오면 그 값으로 `get_weather.py`를 실행하세요.
   - `LOCATION_NOT_FOUND`이면 `get_weather.py`를 location 없이 실행해 IP 대략 위치를 시도하세요.
   - 먼저 사용자에게 지역을 묻지 마세요.
2. 위치 해석 순서: memory(집 주소) → 공인 IP 대략 위치 → `LOCATION_NEEDED`
3. 결과가 `LOCATION_NEEDED`로 시작하면 그때만 지역명을 물어보세요. 도시를 임의로 지어내지 마세요.
4. 사용자 답변에서 기온·강수확률·습도 등에 `**` / `*` 마크다운 강조를 쓰지 마세요. 예: `최고 30℃`, `강수확률 60%`.
5. 그래프·이미지를 만들지 마세요. 텍스트 요약 + 표 + 링크만 전달하세요.

## Quick Start

### 지역명 없음 → memory 먼저

```bash
# 1) memory에서 집/거주 주소
loc=$(python skills/korea-weather/scripts/recall_home_location.py)

# 2) 주소가 있으면 그 지역으로 날씨 조회
if [ "$loc" != "LOCATION_NOT_FOUND" ]; then
  python skills/korea-weather/scripts/get_weather.py "$loc"
else
  # memory 실패 시 IP 폴백(스크립트 내부)
  python skills/korea-weather/scripts/get_weather.py
fi
```

JSON 상세 결과:

```bash
python skills/korea-weather/scripts/recall_home_location.py --json
```

### 현재 위치 별칭(스크립트 내부 memory→IP)

```bash
python skills/korea-weather/scripts/get_weather.py "현재위치"
```

### 지역명 지정

```bash
python skills/korea-weather/scripts/get_weather.py "서울 서초구 반포3동"
python skills/korea-weather/scripts/get_weather.py "부산 해운대"
python skills/korea-weather/scripts/get_weather.py "제주"
```

### 예보구역 stnId

```bash
python skills/korea-weather/scripts/get_weather.py --stnid 109
```

| stnId | 대표 지역 |
| --- | --- |
| 108 / 109 | 서울·인천·경기 |
| 105 | 강원 |
| 131 | 충북 |
| 133 | 대전·세종·충남 |
| 146 | 전북 |
| 156 | 광주·전남 |
| 143 | 대구·경북 |
| 159 | 부산·울산·경남 |
| 184 | 제주 |

## Usage (agent)

```python
import subprocess

RECALL = "skills/korea-weather/scripts/recall_home_location.py"
WEATHER = "skills/korea-weather/scripts/get_weather.py"

# 지역 미지정 → memory 조회 후 날씨
mem = subprocess.run(["python", RECALL], capture_output=True, text=True)
loc = mem.stdout.strip()
if mem.returncode == 0 and loc and loc != "LOCATION_NOT_FOUND":
    result = subprocess.run(["python", WEATHER, loc], capture_output=True, text=True)
else:
    # memory 실패 → IP 폴백
    result = subprocess.run(["python", WEATHER], capture_output=True, text=True)
print(result.stdout)

# 지역 지정
result = subprocess.run(["python", WEATHER, "강남구"], capture_output=True, text=True)
print(result.stdout)

# stnId
result = subprocess.run(["python", WEATHER, "--stnid", "159"], capture_output=True, text=True)
print(result.stdout)
```

## Response Contents

스크립트 stdout에 다음이 포함됩니다.

- 행정동명·위치 해석 메모(memory / IP)
- 현재 기온·체감·습도·바람
- 오늘/내일 날씨·최저·최고·강수확률
- 시간대별 요약 표
- 일별 예보 표
- 대기질(해당 권역)
- 광역 단기예보 참고(있을 때)
- 날씨누리·에어코리아 링크

## Dependencies

- `requests`, `beautifulsoup4` (application 환경에 이미 포함)
- API 키 불필요
- memory 조회: `application/mcp_memory.py` (AgentCore), `AGENTCORE_USER_ID` 환경변수(선택)
- 공인 IP 지오로케이션(`ip-api.com`) — memory 실패 시 폴백

## Troubleshooting

### 지역을 찾을 수 없음

동·구·시까지 구체적으로 다시 조회하세요. 예: `서울 서초구`, `반포3동`.

### LOCATION_NOT_FOUND (memory)

저장된 집 주소가 없습니다. `get_weather.py`로 IP 폴백을 시도하거나, 사용자에게 지역명을 요청하세요.

### LOCATION_NEEDED

memory·IP 모두 실패했습니다. 사용자에게 지역명을 요청하세요.

### 네트워크 오류

날씨누리/에어코리아 일시 장애일 수 있습니다. 잠시 후 재시도하세요.
