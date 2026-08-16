---
name: account-status
description: Generate a account status report by taking an account name, analyze spend trends and AWS account mappings, create an HTML report, render chart image for email compatibility, ask recipient email after report completion, and send immediately without reconfirmation. All analysis and email narrative must be in Korean.
---

# Account Status (Single Account)

이 스킬은 계정명 하나를 입력받아 해당 계정의 지출/매출 상태를 분석하고, HTML 리포트를 생성한 뒤 차트를 이미지(JPEG 권장)로 변환하여 이메일 본문에 포함해 발송합니다.

## Language (필수)

- 사용자에게 보이는 분석 문장, 요약, 권장 조치, 이메일 본문은 **한국어**로 작성합니다.
- API 필드명/코드 식별자는 원문 그대로 사용해도 되지만, 해설은 한국어로 유지합니다.

## Purpose

- SFDC의 정보를 기반으로 계정 분석을 수행합니다.
- 입력값은 **account name**이며, 이름으로 계정을 찾은 후 1개 계정을 대상으로 리포트를 만듭니다.
- 이메일 클라이언트 JS 미실행 제약 때문에 Chart.js 결과를 이미지로 변환해 포함합니다.

## When to Use This Skill

- 특정 한 개 계정의 최신 상태를 빠르게 보고하고 싶을 때
- 계정별 매출/지출 변화, AWS 계정 매핑 상위 기여도를 이메일로 공유해야 할 때
- 기존 2개 계정 동시 리포트가 너무 커서 메일 방송이 어려운 경우

## Workflow

### Step 1) Resolve target account from account name

사용자에게 계정명을 받습니다. 이름으로 계정을 조회해 **정확히 1개 대상 계정**을 확정합니다.

- 아래 두 계정은 **알려진 SFDC Account ID**로 우선 매핑할 수 있습니다:
  - `LG Chemical` → `0015000000fSYKUAA4`
  - `LG Energy Solution` (LG Ensol) → `0014z00001bw6vaAAA`
- 입력 계정명이 위 별칭과 일치/유사하면 조회 전에 해당 ID를 우선 사용해도 됩니다.
- 동명이인이 여러 개면 사용자에게 후보를 보여주고 선택을 받습니다.
- 계정이 없으면 실패 사유를 알리고 종료합니다.

조회 결과에서 최소한 아래 값을 확보합니다:

- `accountId` (SFDC account id)
- `accountName`

확정 후 조회 예시:

```text
get_account_spend_summary(sfdcAccountId: "<resolved_account_id>")
get_account_spend_history(accountId: "<resolved_account_id>", includeMonthlyBreakdown: true)
```

### Step 2) Fetch financial and mapping data

확정된 단일 계정에 대해 아래 데이터를 조회합니다.

1. spend summary
2. spend history (월별 포함)
3. AWS account mappings (`chargeR12` 기준 정렬, 충분한 limit)
4. 서비스별 지출 데이터(서비스명 + R12 금액이 포함된 breakdown; 가능 시 `chargeR12` 기준 정렬)

가능하면 병렬 호출합니다.

AWS account 매핑 분석은 **MoM(전월 대비)** 중심으로 제공합니다.
- `aws_sentral`에서 제공되는 `momPercentCharge`를 기준으로 증감 추이를 해석합니다.
- AWS account 단위 YoY는 계산/신뢰 가능한 방식으로 제공하지 않으므로 분석 항목에서 제외합니다.

### Step 3) Compute metrics

아래 지표를 계산합니다.

- Rolling 12개월 성장률
- 전년 동월(YoY) 성장률
- 최근 3개월 추이(MoM)
- AWS 상위 10 계정의 `chargeR12` 합계 및 비중
- AWS 계정별 전체 비중(필수):  
  `(awsAccount.chargeR12 / aggregateTotals.mons12.chargeAmount) * 100`
- 서비스별 R12 상위 10 합계 및 비중
- 서비스별 전체 비중(필수):  
  `(service.chargeR12 / aggregateTotals.mons12.chargeAmount) * 100`

AWS 계정 분석에서는 각 행에 최소한 다음을 포함합니다:

- `accountRevenue.id`
- `accountRevenue.name`
- `accountRevenue.chargeR12`
- `accountRevenue.momPercentCharge`
- 계정 용도(필수; `accountRevenue.name`/`email`/`role` 패턴 기반 추정 가능)
- `accountRevenue.supportLevel`
- `accountRevenue.role`

표/요약/권장 조치에서 AWS 계정을 언급할 때는 **MoM을 항상** 제시합니다.
서비스를 언급할 때는 **R12 금액 + 전체 비중(%)**을 항상 함께 제시합니다.

### Step 4) Build single-account HTML report

리포트 파일 예시:  
`application/artifacts/<sanitized_account_name>_revenue.html`

필수 섹션:

1. 요약 카드 (12개월 총액, 월평균, 최고 월, MTD)
   - 카드 바로 아래에 "계정 요약 한 줄"을 추가하고, 핵심 사항을 한국어 문장으로 설명
2. 성장 분석 박스 (Rolling 12M / YoY / MoM)
3. 최근 3개월 표
4. 월별 매출 추이 차트 섹션
   - `<section id="account-monthly-trend-12m">` 유지
   - `<script>` 내 `const months12`, `const chargeData`, `const revenueData` 유지
5. 서비스/크레딧 변화 해설
6. 서비스별 R12 현황 (상위 10개)
   - 컬럼: 순위 | 서비스명 | R12 Charge | 전체 비중(%)
   - 서비스명 누락 시 `Unknown`으로 표기
7. AWS 계정 매핑 상위 10 분석
   - 컬럼: 순위 | 계정명 | AWS ID | 용도 | R12 Charge | 전체 비중(%) | MoM | Support | Role
   - 용도는 가능한 경우 명시하고, 불명확하면 `기타/미분류`로 표기
   - 주목 계정 플래그(급증/급감, Basic + 고비용, genai 패턴 등)
8. 권장 조치

### Step 5) Convert chart HTML data to image (email-safe)

이메일에서 JS가 동작하지 않으므로, 아래 스크립트로 차트 이미지를 생성합니다:

- 스크립트: `application/skills/account-status/scripts/html_to_chart_image.mjs`
- 출력 권장: `.jpg` (용량 작음)

예시:

```bash
node application/skills/account-status/scripts/html_to_chart_image.mjs \
  application/artifacts/<sanitized_account_name>_revenue.html \
  application/artifacts/<sanitized_account_name>_chart.jpg
```

의존성(`chart.js`, `skia-canvas`, `sharp`)은 루트 또는 해당 스킬 폴더에서 `npm install`로 준비합니다.
MCP tool 파라미터 크기 제한을 피하기 위해 차트 이미지는 기본적으로 저용량 설정(가로폭 축소 + JPEG 품질 하향)으로 생성합니다.
필요하면 아래 환경변수로 추가 축소를 적용합니다:

```bash
CHART_IMAGE_MAX_WIDTH=760 CHART_IMAGE_JPEG_QUALITY=65 \
node application/skills/account-status/scripts/html_to_chart_image.mjs \
  application/artifacts/<sanitized_account_name>_revenue.html \
  application/artifacts/<sanitized_account_name>_chart.jpg
```

### Step 6) Prepare email body (Korean)

이메일 본문(HTML) 구조:

1. 계정 요약
   - 계정 상태의 핵심을 한국어 1문장으로 먼저 제시
2. 핵심 성장 지표
3. 차트 이미지(`<img ...>`)
4. 서비스별 R12 현황(상위 10)
5. AWS 계정 매핑 요약(상위 10)
6. 리스크/기회 및 권장 액션

차트 삽입 방식:

- 1순위: data URL (`data:image/jpeg;base64,...`)
- 대안: 공개 `https://` 이미지 URL
- 첨부가 필요한 경우는 사용자 환경에 맞춰 수동 첨부 안내
- 본문 크기가 커도 차트 이미지는 **절대 제외하지 않음**(간결 버전으로 임의 축약 금지)
- 용량이 큰 경우에는 먼저 이미지 최적화(예: JPEG 품질/가로폭 조정) 후, 차트 이미지를 포함한 상태로 발송
- 본문 전송 전 차트 이미지 파일 크기를 확인하고, 크면 `CHART_IMAGE_MAX_WIDTH`/`CHART_IMAGE_JPEG_QUALITY`를 낮춰 재생성한 뒤 포함합니다.

### Step 7) Ask recipient email and send immediately

보고서(HTML + 차트 이미지)가 완성되면 수신 이메일 주소를 사용자에게 묻습니다.
이 단계에서는 주소만 확인하며, 추가 발송 확인은 받지 않습니다.

### Step 8) Send email

Step 7에서 이메일 주소를 받으면 즉시 발송합니다(재확인 없음).
- 발송 시 차트 이미지가 포함되지 않았다면 발송을 중단하고, 이미지 포함 형태로 본문을 재구성한 뒤 발송합니다.

#### 발송 수단 선택 (중요)

**큰 HTML 본문(예: data URL base64 이미지 포함, 20KB+)은 `email_send`의 `body` 파라미터로 직접 보내지 말 것.**
- MCP 툴 파라미터 경로로 큰 문자열을 전달하면 본문이 플레이스홀더/잘린 문자열로 전송되어 빈 메일이 나가는 현상이 있음.
- 차트 이미지를 포함한 본문은 반드시 **파일로 먼저 저장한 뒤 `email_draft` → `bodyFilePath`** 로 읽어 발송한다.

권장 절차:

1. 본문 HTML을 로컬 파일로 저장 (예: `$TMPDIR/<account>_email_body.html`).
   - base64는 `base64 -i <chart.jpg> | tr -d '\n' > $TMPDIR/<acct>_chart_b64.txt` 로 생성 후 heredoc에 주입.
   - **주의:** 작업 디렉토리가 샌드박스일 때 `/tmp/...` 직접 쓰기는 실패하므로 `$TMPDIR` 사용.
2. `email_draft` (operation=`create`) 호출 시 `bodyFilePath`에 위 파일 경로를 지정해 드래프트 생성.
3. 반환된 `draftId`/`draftChangeKey`로 `email_draft` (operation=`update`, `send: true`) 호출하여 즉시 발송.

```text
email_draft(operation: "create", to: ["<recipient>"], subject: "...",
            bodyFilePath: "$TMPDIR/<acct>_email_body.html")
email_draft(operation: "update", draftId: "<id>", draftChangeKey: "<key>", send: true)
```

짧은 본문(차트 이미지 없이 요약만)일 때만 `email_send`의 `body` 파라미터를 직접 사용해도 무방하다.

#### 차트 이미지 크기 가이드 (경험치)

- 경험상 `CHART_IMAGE_MAX_WIDTH=600, CHART_IMAGE_JPEG_QUALITY=55`면 JPEG 약 18KB, base64 인코딩 후 약 24KB로 Outlook 본문에 무리 없이 삽입됨.
- `760 / 65` 조합은 약 22KB / 30KB로 기본값으로 적당.
- 본문 조립 전 `wc -c` 등으로 base64 길이를 확인해 너무 크면 재생성.

#### 발송 실패/빈 본문 확인 시 복구

- 메일이 플레이스홀더 문자열(예: `__BODY_FROM_FILE__`)로 나갔다면 **삭제 시도하지 말고** 재발송한다(원본 메일은 사용자가 수신자 측에서 처리).
- 재발송 시 반드시 위의 `email_draft + bodyFilePath` 절차를 사용한다.

#### 스크립트 주의사항 (chart 생성)

- `scripts/html_to_chart_image.mjs` 의 템플릿 리터럴은 **백슬래시 이스케이프 금지** (`\`...\``가 아니라 백틱 그대로). 이스케이프된 상태면 Node가 `SyntaxError: Invalid or unexpected token`으로 실패함.

예시 제목:

- `<account name> 상태 분석 리포트 - YYYY-MM-DD`

## Output Contract

작업 완료 시 사용자에게 아래를 제공:

1. 분석 요약(한국어)
2. 생성된 HTML 경로
3. 생성된 차트 이미지 경로(JPEG 권장)
4. 메일 발송 여부(이메일 주소 확인 후 즉시 발송 / 발송 완료)

## Guardrails

- 계정이 확정되지 않으면 분석/발송을 진행하지 않습니다.
- AWS 계정 매핑 표/해설에서 **비중(%) 생략 금지**.
- AWS 계정 매핑 상위 10 표에서 **용도 컬럼 생략 금지**.
- 서비스별 R12 상위 10 표에서 **R12 금액/비중(%) 생략 금지**.
- 계정 요약에는 핵심 사항을 설명하는 **한국어 1문장 요약**을 반드시 포함합니다.
- 이메일 본문에서 차트 이미지를 임의로 제거한 간결 버전 발송 금지(예: "본문이 커서 차트 제외" 메시지 금지).
- 메일 크기 이슈가 있어도 **차트 이미지 포함 발송은 필수**이며, 필요 시 이미지 최적화 후 발송합니다.
- 과도한 추정 금지: 데이터가 없으면 `N/A`와 함께 명시합니다.
- 보고서 완료 후에는 이메일 주소를 받은 즉시 발송하며, 별도 재확인은 하지 않습니다.
- base64 이미지가 삽입된 큰 HTML 본문은 `email_send`의 `body` 파라미터로 직접 전달하지 않고, 파일로 저장 후 `email_draft`의 `bodyFilePath`로 발송합니다(MCP 파라미터 크기/인용 이슈 회피).
- 임시 파일은 반드시 `$TMPDIR` 아래에 생성합니다. 샌드박스 환경에서 `/tmp` 직접 쓰기는 실패할 수 있습니다.
