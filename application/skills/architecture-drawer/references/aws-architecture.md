# AWS Architecture Diagram Guidelines (draw.io)

standalone `drawio_cli.mjs`로 AWS 아키텍처를 그릴 때 따르는 시각·구조 규칙입니다.

## Visual hierarchy

항상 **바깥 → 안쪽** 순서로 **절대 좌표** 배치합니다 (모델 `set_parent` 사용 금지).

```
AWS Cloud
 └─ Region
     └─ VPC
         ├─ Public Subnet(s)
         │   └─ ALB, NAT, bastion, ...
         └─ Private Subnet(s)
             └─ EC2/ECS/Lambda ENI, RDS, ...
```

멀티 계정·하이브리드:
- `awsAccount`로 계정 경계
- `corporateDataCenter`로 온프레미스
- 계정/온프레미스 간은 점선 또는 라벨된 edge (VPN / Direct Connect)

## Layout patterns by architecture type

| Architecture | Pattern | Notes |
|---|---|---|
| 3-tier web | linear (L→R) or AZ columns | Public → Private → Data |
| Serverless API | hub (API GW) + satellites | Cognito/왼쪽, data stores/오른쪽 |
| Event-driven | linear pipeline | producers → EventBridge/SQS → consumers |
| Data lake | layered vertical | ingest → storage → analytics → consume |
| Multi-AZ HA | dual columns in VPC | 동일 티어를 AZ별로 대칭 |
| CI/CD | linear | Source → Build → Test → Deploy |

## Spacing & sizing

- Icon spacing: ≥ 100px (겹침 방지)
- Group padding: 자식 기준 최소 40–60px 여백
- Edge: `orthogonalEdgeStyle`, 교차 최소화
- Label: 서비스 역할 중심 (`API Handler`, `User DB`) — 긴 설명 금지

## Icon & label conventions

1. **공식 AWS4 아이콘만** 사용 (`insert_aws_icon`)
2. 라벨은 아이콘 아래/옆에 짧게
3. 동일 서비스 복제는 역할로 구분 (`Lambda — Auth`, `Lambda — Worker`)
4. 외부 사용자/시스템은 `insert_vertex` + 단순 style 또는 general 아이콘

## Connection semantics

| Edge meaning | Style hint |
|---|---|
| Sync request (HTTPS) | solid, `endArrow: classic`, label optional |
| Async event | solid or dashed, label `event` / topic name |
| Data store access | solid, label 포트/프로토콜 짧게 |
| Trust / IAM | 남용 금지; 꼭 필요하면 점선 + `IAM` |
| Network path (VPN/DX) | dashed + 명확한 label |

**Never** let an edge pass through another service icon. Rearrange with `move_cell` or adjust geometry in ops.

## Validation checklist

저장 전:

- [ ] `validate_diagram` / `drawio_cli.mjs validate` 통과
- [ ] overlap 없음 (또는 의도적 중첩만)
- [ ] Region/VPC/Subnet이 좌표상 포함 관계
- [ ] 모든 AWS 서비스가 아이콘 (일반 박스 아님)
- [ ] 파일명이 의미 있음: `ARTIFACTS_DIR/serverless-api.drawio`

## Mapping from IaC

CloudFormation / SAM / CDK / Terraform을 받으면:

1. 리소스 목록 추출 (compute, data, network, security, integration)
2. 네트워크 경계(VPC/subnet/security group) 식별 → groups
3. 의존·이벤트 관계 → edges
4. ops.json 작성 → `drawio_cli.mjs apply` → PNG export

불필요한 IAM Role/Policy 박스는 생략하고, 핵심 런타임·데이터·엣지 서비스에 집중하세요.

## Opening the result

채팅에서는 `export_png.py`로 만든 **PNG 미리보기**를 `![...](url)`로 보여주세요.
편집용 `.drawio`는 다음에서 열 수 있습니다.

- [diagrams.net](https://app.diagrams.net/)
- draw.io Desktop
- VS Code Draw.io Integration extension

```bash
python skills/architecture-drawer/scripts/export_png.py ARTIFACTS_DIR/name.drawio ARTIFACTS_DIR/name.png
```
