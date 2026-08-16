---
name: architecture-drawer
description: >
  skill name은 architecture-drawer 입니다. AWS 아키텍처 다이어그램을 draw.io(.drawio)로
  생성·수정합니다. 로컬 CLI(`drawio_cli.mjs`)로 공식 AWS 아이콘·VPC/Subnet 컨테이너를
  배치합니다. 사용자가 "아키텍처 그려줘", "AWS 다이어그램", "drawio", "draw.io",
  ".drawio", "아키텍처 다이어그램", "VPC 구성도", "서버리스 아키텍처", "인프라 다이어그램",
  "architecture diagram", "aws architecture" 등을 요청하거나 CloudFormation/SAM/CDK/Terraform
  에서 아키텍처를 시각화할 때 반드시 이 skill을 사용하세요.
compatibility: Requires Node.js 18+ (scripts 의존성은 최초 1회 npm install)
---

# architecture-drawer — AWS Architecture Diagrams

로컬 `drawio_cli.mjs`로 공식 AWS 아이콘·그룹 컨테이너를 사용해 `.drawio` 아키텍처 다이어그램을 만듭니다.

## Script Location

application working directory 기준 전체 경로를 사용하세요.

| 스크립트 | 용도 |
| --- | --- |
| `skills/architecture-drawer/scripts/drawio_cli.mjs` | 다이어그램 생성·수정·검증 |
| `skills/architecture-drawer/scripts/export_png.py` | `.drawio` → PNG 미리보기 |

**IMPORTANT**: `scripts/...`로 줄이지 말고 위 전체 경로를 사용하세요.

최초 1회(또는 `node_modules` 없을 때):

```bash
cd skills/architecture-drawer/scripts && npm install
```

## Output path

- 저장 경로: **`{ARTIFACTS_DIR}/<name>.drawio`** (절대 경로)
- 미리보기: **`{ARTIFACTS_DIR}/<name>.png`** (필수)
- ops JSON도 ARTIFACTS_DIR에 둡니다: `{ARTIFACTS_DIR}/<name>-ops.json`
- `/tmp`에 저장하지 마세요.
- 완료 후 `upload_file_to_s3`로 **drawio + png** 둘 다 업로드해 URL을 제공합니다.

## Workflow (필수 순서)

```
Task Progress:
- [ ] 1. Plan: layout-guidance / list-icons로 좌표·아이콘 확인
- [ ] 2. ops.json 작성 (create → groups → icons → edges → validate)
- [ ] 3. drawio_cli.mjs apply --ops ... --out ARTIFACTS_DIR/<name>.drawio
- [ ] 4. (필요 시) validate / info로 점검 후 ops 수정·재적용
- [ ] 5. export_png.py → ARTIFACTS_DIR/<name>.png
- [ ] 6. upload_file_to_s3 (drawio + png) → 최종 답변에 이미지 인라인 표시
```

### 1) Plan before placing

다이어그램을 만들기 **전에** 레이아웃 가이드를 확인하세요.

```bash
node skills/architecture-drawer/scripts/drawio_cli.mjs layout-guidance
node skills/architecture-drawer/scripts/drawio_cli.mjs list-groups
node skills/architecture-drawer/scripts/drawio_cli.mjs list-icons --category compute
node skills/architecture-drawer/scripts/drawio_cli.mjs search-icons lambda
```

| 규모 | 그리드 | spacing |
|------|--------|---------|
| 3–8 요소 | 8×8 | 100 |
| 8–15 요소 | 10×10 | 100 |
| 15+ 요소 | 12×12 | 100–150 |

좌표 공식: `x = col * spacing + margin`, `y = row * spacing + margin` (margin ≈ 50)

패턴 선택:
- **linear**: 파이프라인·요청 흐름 (좌→우)
- **single-center / hub**: API Gateway·ALB 중심
- **tree**: 계정/리전/VPC 계층
- **grid**: 서비스 카탈로그성 배치

### 2) Write ops.json and apply

`execute_code`로 ops JSON을 파일에 쓴 뒤, 한 번에 apply 합니다.

```bash
node skills/architecture-drawer/scripts/drawio_cli.mjs apply \
  --ops "{ARTIFACTS_DIR}/aws-architecture-ops.json" \
  --out "{ARTIFACTS_DIR}/aws-architecture.drawio"
```

Ops 형식:

```json
{
  "name": "VPC Web Tier",
  "ops": [
    { "op": "create_diagram", "name": "VPC Web Tier" },
    { "op": "insert_aws_group", "group_type": "region", "label": "ap-northeast-2",
      "geometry": { "x": 40, "y": 40, "width": 900, "height": 520 } },
    { "op": "insert_aws_group", "group_type": "vpc", "label": "VPC 10.0.0.0/16",
      "geometry": { "x": 80, "y": 100, "width": 820, "height": 420 } },
    { "op": "insert_aws_icon", "icon": "ec2", "category": "compute", "label": "Web",
      "geometry": { "x": 220, "y": 280 } },
    { "op": "insert_edge", "source_id": "...", "target_id": "...", "label": "HTTPS",
      "style": { "edgeStyle": "orthogonalEdgeStyle", "endArrow": "classic", "strokeWidth": 1 } },
    { "op": "validate_diagram" },
    { "op": "save_diagram", "file_path": "{ARTIFACTS_DIR}/aws-architecture.drawio" }
  ]
}
```

`--out`을 주면 마지막에 자동 저장되므로 `save_diagram`은 생략해도 됩니다.
셀 id가 필요하면 ops에 `"id": "web-ec2"`처럼 명시하세요. `insert_edge`의 `source_id`/`target_id`에 그 id를 씁니다.

### 3) Groups & icons

바깥→안쪽 순서로 그룹을 둡니다:

| group_type | 용도 |
|---|---|
| `awsCloud` / `awsCloudAlt` | AWS 클라우드 경계 |
| `region` | 리전 |
| `vpc` | VPC |
| `publicSubnet` / `privateSubnet` | 서브넷 |
| `availabilityZone` | AZ |
| `securityGroup` | 보안 그룹 |
| `autoScalingGroup` | ASG |
| `awsAccount` | 계정 |

```json
{ "op": "insert_aws_icon", "icon": "lambda", "category": "compute", "label": "API Handler", "geometry": { "x": 200, "y": 200 } }
{ "op": "insert_aws_icon", "icon": "s3", "category": "storage", "label": "Assets", "geometry": { "x": 400, "y": 200 } }
{ "op": "insert_aws_icon", "icon": "rds", "category": "database", "label": "Aurora", "geometry": { "x": 600, "y": 200 } }
```

아이콘 이름이 애매하면 `search-icons`로 확인하세요.

주요 카테고리: `compute`, `storage`, `database`, `networking`, `security`, `integration`, `management`, `analytics`, `machine_learning`, `general`

자주 쓰는 icon id: `ec2`, `lambda`, `ecs`, `eks`, `s3`, `ebs`, `efs`, `rds`, `dynamodb`, `aurora`, `api_gateway`, `alb`, `nlb`, `cloudfront`, `route_53`, `vpc`, `nat_gateway`, `cognito`, `iam`, `secrets_manager`, `sqs`, `sns`, `eventbridge`, `step_functions`, `bedrock`, `opensearch`, `elasticache`, `codepipeline`, `ecr`

### 4) Nesting (부모-자식)

권장 계층(시각적):
`awsCloud` → `region` → `vpc` → (`publicSubnet` | `privateSubnet`) → service icons

`set_parent`은 **시각적 의도만 기록**하고 모델 재부모화는 하지 않습니다.
자식 셀은 **절대 좌표(geometry)** 로 부모 박스 안에 배치하세요.

### 5) Connections

```json
{
  "op": "insert_edge",
  "source_id": "web-ec2",
  "target_id": "db-rds",
  "label": "3306",
  "style": { "edgeStyle": "orthogonalEdgeStyle", "endArrow": "classic", "strokeWidth": 1 }
}
```

규칙:
- 화살표가 **다른 서비스 박스를 관통하지 않게** 배치
- 방향은 데이터/요청 흐름을 따름
- 라벨은 짧게 (프로토콜, 포트, 이벤트명)

### 6) Validate & inspect

```bash
node skills/architecture-drawer/scripts/drawio_cli.mjs validate "{ARTIFACTS_DIR}/aws-architecture.drawio"
node skills/architecture-drawer/scripts/drawio_cli.mjs info "{ARTIFACTS_DIR}/aws-architecture.drawio"
```

수정이 필요하면 ops를 고친 뒤 `--load`로 기존 파일을 불러 편집하거나, ops 전체를 다시 apply 하세요.

```bash
node skills/architecture-drawer/scripts/drawio_cli.mjs apply \
  --load "{ARTIFACTS_DIR}/aws-architecture.drawio" \
  --ops "{ARTIFACTS_DIR}/aws-architecture-edit-ops.json" \
  --out "{ARTIFACTS_DIR}/aws-architecture.drawio"
```

### 7) PNG 미리보기 (필수)

`.drawio`만 링크하면 채팅에서 모습을 볼 수 없습니다. **반드시 PNG를 만들어 인라인 이미지로 보여주세요.**

```bash
python skills/architecture-drawer/scripts/export_png.py \
  "{ARTIFACTS_DIR}/aws-architecture.drawio" \
  "{ARTIFACTS_DIR}/aws-architecture.png"
```

그다음:

1. `upload_file_to_s3`로 `.drawio`와 `.png` 모두 업로드
2. 최종 답변에 **마크다운 이미지**로 PNG를 먼저 표시:

```markdown
![AWS Architecture](<png_upload_url>)

📥 **다운로드**: [aws-architecture.drawio](<drawio_upload_url>)
```

규칙:
- PNG URL은 `![...](url)` 형식 (링크 텍스트만 있는 `[...](url)` 금지 — 이미지가 안 보임)
- PNG export 실패 시 원인과 함께 `.drawio` 다운로드 링크만 제공하고, 사용자에게 draw.io에서 열라고 안내

## Quick example — VPC + EC2 + RDS

1. `layout-guidance` / `list-icons`로 계획
2. ops.json 작성:

```json
{
  "name": "VPC Web Tier",
  "ops": [
    { "op": "create_diagram", "name": "VPC Web Tier" },
    { "op": "insert_aws_group", "id": "region", "group_type": "region", "label": "ap-northeast-2",
      "geometry": { "x": 40, "y": 40, "width": 900, "height": 520 } },
    { "op": "insert_aws_group", "id": "vpc", "group_type": "vpc", "label": "VPC 10.0.0.0/16",
      "geometry": { "x": 80, "y": 100, "width": 820, "height": 420 } },
    { "op": "insert_aws_group", "id": "public", "group_type": "publicSubnet", "label": "Public Subnet",
      "geometry": { "x": 120, "y": 160, "width": 340, "height": 320 } },
    { "op": "insert_aws_group", "id": "private", "group_type": "privateSubnet", "label": "Private Subnet",
      "geometry": { "x": 500, "y": 160, "width": 360, "height": 320 } },
    { "op": "insert_aws_icon", "id": "web-ec2", "icon": "ec2", "category": "compute", "label": "Web",
      "geometry": { "x": 220, "y": 280 } },
    { "op": "insert_aws_icon", "id": "db-rds", "icon": "rds", "category": "database", "label": "RDS",
      "geometry": { "x": 620, "y": 280 } },
    { "op": "insert_edge", "source_id": "web-ec2", "target_id": "db-rds", "label": "3306" },
    { "op": "validate_diagram" }
  ]
}
```

3. `apply --ops ... --out ...`
4. `export_png.py` → upload → `![...](png_url)`로 표시

## Editing existing diagrams

1. `info` / `validate`로 현황 파악
2. 수정 ops 작성 (`update_cell` / `move_cell` / `insert_aws_icon` / `remove_cell` 등)
3. `apply --load <기존.drawio> --ops <edit-ops.json> --out <같은경로>`
4. **PNG 재export** → 인라인 이미지로 보여주기

## Do / Don't

**Do**
- AWS 서비스는 공식 아이콘 (`insert_aws_icon`)
- Region → VPC → Subnet 계층을 절대 좌표로 시각 표현
- 저장은 ARTIFACTS_DIR의 `.drawio` + `.png`
- apply 전/후 `validate`
- 최종 답변에 PNG를 `![...](url)`로 인라인 표시
- **로컬 CLI만 사용**

**Don't**
- 일반 사각형으로 AWS 서비스를 대체하지 마세요 (아이콘 검색 실패 시에만 fallback)
- 아이콘을 겹치거나 화살표가 박스를 관통하게 두지 마세요
- 한 다이어그램에 설명 텍스트를 과도하게 넣지 마세요 (라벨은 서비스명·역할 중심)
- `.drawio` 다운로드 링크만 주고 미리보기 이미지를 빼지 마세요

## Additional resources

- ops / CLI 명령 목록: [references/tools.md](references/tools.md)
- AWS 다이어그램 레이아웃 규칙: [references/aws-architecture.md](references/aws-architecture.md)
- 업스트림 엔진: https://aws-samples.github.io/sample-drawio-mcp/ (참고용)
